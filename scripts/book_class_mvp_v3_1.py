# scripts/book_class_mvp_v3_1.py
# ALONI 2.9.6 — Hydration-safe login with JS-forced open + screenshots

import os, sys, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

def _ci(): return os.getenv("CI") == "true"
def _env(k):
    v = os.getenv(k, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {k}")
    return v
def _log(m): print(m, flush=True)
def _target_date(n=13): return datetime.now().date() + timedelta(days=n)

def _shot(page, name):
    try:
        os.makedirs("screenshots", exist_ok=True)
        page.screenshot(path=f"screenshots/{name}.png", full_page=True)
    except Exception:
        pass

def main():
    email = _env("COREPOWER_EMAIL")
    pwd   = _env("COREPOWER_PASSWORD")

    target = _target_date(13)
    day = target.strftime("%A")
    _log(f"🚀 ALONI 2.9.6 — Target {day}, {target:%b %d}")

    # Only attempt on Mon/Tue/Wed
    if day not in ["Monday", "Tuesday", "Wednesday"]:
        _log(f"ℹ️ {day} is not a booking day — exiting.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=_ci(), slow_mo=0)
        context = browser.new_context(
            record_video_dir="videos" if _ci() else None,
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.0,
        )
        page = context.new_page()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        try:
            # 1) Home
            _log("🏠 Opening homepage…")
            page.goto("https://www.corepoweryoga.com/", timeout=90000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_load_state("networkidle")
            page.evaluate("window.scrollTo(0,0)")
            page.evaluate("document.body.style.minHeight='2000px';")
            page.evaluate("window.dispatchEvent(new Event('scroll'));")
            page.evaluate("window.dispatchEvent(new Event('mousemove'));")
            _shot(page, "01_home_loaded")

            # Close overlays if any
            for sel in [
                "button:has-text('Close')",
                "button[aria-label*='close' i]",
                "button:has-text('Accept')",
                "button:has-text('Got it')",
            ]:
                try:
                    page.locator(sel).first.click(timeout=1500)
                except Exception:
                    pass
            _shot(page, "02_after_overlay_close")

            # 2) Login: be aggressive — try visible click, then JS click, then menu fallbacks
            _log("🔐 Logging in…")

            # Ensure profile region exists in DOM (even if not visible)
            try:
                page.wait_for_selector("button[data-position*='profile']", timeout=15000)
            except Exception:
                _log("⚠️ Profile selector not found via wait — proceeding with JS search anyway.")

            # Strategy A: normal click if visible
            tried_click = False
            for sel in [
                "button[data-position='profile.1-sign-in']",
                "button:has-text('Sign in')",
                "text=Sign in",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible():
                        btn.click(timeout=4000)
                        tried_click = True
                        _log(f"✅ Clicked visible selector: {sel}")
                        break
                except Exception:
                    continue

            # Strategy B: force visibility + JS click (bypasses Playwright visibility rules)
            if not tried_click:
                _log("⚠️ Forcing Sign in via JS (visibility bypass)…")
                page.evaluate("""
                    const cand = Array.from(document.querySelectorAll('button, a'))
                      .find(el => /sign\\s*in/i.test(el.textContent || ''));
                    if (cand) {
                        cand.style.display = 'block';
                        cand.style.visibility = 'visible';
                        cand.style.opacity = '1';
                        cand.click();
                    }
                """)
                tried_click = True
                time.sleep(1.0)

            # Strategy C: open profile menu first, then click sign-in inside it
            if tried_click:
                # if a drawer/menu is used, give it a moment to render
                time.sleep(1.0)

            # As a final nudge, try opening any profile/menu button via JS
            page.evaluate("""
                const profile = document.querySelector("button[data-position*='profile']");
                if (profile) { profile.click(); }
            """)
            time.sleep(0.8)
            # Try sign-in text again after menu
            try:
                page.locator("text=Sign in").first.click(timeout=2500)
            except Exception:
                pass

            _shot(page, "03_after_signin_click_attempts")

            # 3) Credentials
            page.wait_for_selector("input[name='email']", timeout=20000)
            page.fill("input[name='email']", email)
            page.fill("input[name='password']", pwd)
            _shot(page, "04_credentials_filled")
            page.click("button[type='submit']")
            _shot(page, "05_after_submit")

            # 4) Verify login
            page.wait_for_selector("button[data-position='profile.1-logged-in']", timeout=30000)
            _log("✅ Login successful.")

            # 5) Book a Class
            _log("📅 Navigating to booking page…")
            page.get_by_text("Book a Class").click(timeout=15000)
            page.wait_for_load_state("networkidle")

            # 6) Studio
            _log("📍 Selecting Flatiron studio…")
            page.fill("input[placeholder*='Search']", "Flatiron")
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            page.get_by_text("Flatiron").first.click(timeout=10000)

            # 7) Date
            _log(f"🗓 Selecting {target:%A %b %d}…")
            page.locator(f"button:has-text('{target.day}')").first.click(timeout=6000)
            page.wait_for_timeout(1500)

            # 8) Class
            _log("💪 Searching for 6:15 PM Yoga Sculpt class…")
            cards = page.locator("div.class-card")
            found = False
            count = cards.count()
            for i in range(count):
                card = cards.nth(i)
                text = card.inner_text().lower()
                if "yoga sculpt" in text and "6:15" in text:
                    card.scroll_into_view_if_needed()
                    try:
                        card.get_by_text("Book").first.click(timeout=5000)
                    except Exception:
                        # sometimes it's "Join Waitlist" if full
                        try:
                            card.get_by_text("Join Waitlist").first.click(timeout=5000)
                        except Exception:
                            pass
                    found = True
                    _log("✅ Found target class, proceeded to booking/waitlist screen.")
                    break

            if not found:
                _log("⚠️ Target class not found — exiting gracefully.")
                return

            # 9) Confirm
            try:
                page.get_by_text("Reserve My Spot").first.click(timeout=10000)
                page.wait_for_timeout(2000)
                _log("✅ Booking completed successfully.")
            except Exception:
                _log("⚠️ Could not click 'Reserve My Spot' — possibly already booked / waitlist.")

            _log("🎉 ALONI flow finished cleanly.")

        except Exception as e:
            _log(f"❌ {e}")
            raise
        finally:
            try: context.tracing.stop(path="trace.zip")
            except Exception: pass
            try: context.close()
            except Exception: pass
            try: browser.close()
            except Exception: pass

if __name__ == "__main__":
    print("🧘 Starting ALONI automation…")
    try:
        main()
    except Exception as e:
        print(f"##[error]{e}")
        sys.exit(1)
