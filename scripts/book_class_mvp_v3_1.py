# scripts/book_class_mvp_v3_1.py
# ALONI 2.9.4 — Full production version with robust login

import os
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ----------------------------------------------------------------------
# Utility helpers
# ----------------------------------------------------------------------

def _ci() -> bool:
    return os.getenv("CI") == "true"

def _get_env_or_die(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            "Set it under Settings → Secrets → Actions and expose via env in workflow."
        )
    return val

def _log(msg: str) -> None:
    print(msg, flush=True)

def _target_date(days_ahead: int = 13):
    return datetime.now().date() + timedelta(days=days_ahead)

# ----------------------------------------------------------------------
# Core automation
# ----------------------------------------------------------------------

def main() -> None:
    email = _get_env_or_die("COREPOWER_EMAIL")
    password = _get_env_or_die("COREPOWER_PASSWORD")

    target = _target_date(13)
    weekday = target.strftime("%A")
    _log("🚀 Starting ALONI 2.9.4 – Verified Booking Flow…")
    _log(f"📅 Target date: {weekday}, {target.strftime('%b %d')} (13 days from today)")

    # Only book on Mon/Tue/Wed
    valid_days = ["Monday", "Tuesday", "Wednesday"]
    if weekday not in valid_days:
        _log(f"ℹ️ Skipping — {weekday} is not a booking day.")
        return

    headless = True if _ci() else False
    slow_mo = 0 if _ci() else 150

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(record_video_dir="videos" if _ci() else None)
        page = context.new_page()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        try:
            # ------------------------------------------------------------------
            # 1. Open CorePower homepage
            # ------------------------------------------------------------------
            _log("🏠 Opening CorePower homepage…")
            page.goto("https://www.corepoweryoga.com/", timeout=60000)

            # Close any popups or cookie banners
            for close_sel in [
                "button:has-text('Close')",
                "button[aria-label*='close' i]",
                "button:has-text('Accept')",
                "button:has-text('Got it')",
            ]:
                try:
                    page.locator(close_sel).first.click(timeout=3000)
                except Exception:
                    pass

            # ------------------------------------------------------------------
            # 2. Login flow (robust headless-safe version)
            # ------------------------------------------------------------------
            _log("🔐 Logging in…")

            page.wait_for_selector("button[data-position*='profile']", timeout=15000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            login_selectors = [
                "button[data-position='profile.1-sign-in']",
                "button:has-text('Sign in')",
                "text=Sign in",
            ]

            clicked = False
            for sel in login_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible():
                        btn.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                _log("⚠️ Could not find visible Sign In button, retrying after closing popups…")
                for close_sel in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
                    try:
                        page.locator(close_sel).first.click(timeout=2000)
                    except Exception:
                        pass
                page.wait_for_timeout(2000)
                for sel in login_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible():
                            btn.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue

            if not clicked:
                raise PWTimeoutError("Could not find or click the Sign In button.")

            # Fill credentials
            page.wait_for_selector("input[name='email']", timeout=10000)
            page.fill("input[name='email']", email)
            page.fill("input[name='password']", password)
            page.click("button[type='submit']")

            # Wait for profile icon confirmation
            page.wait_for_selector("button[data-position='profile.1-logged-in']", timeout=20000)
            _log("✅ Login successful.")

            # ------------------------------------------------------------------
            # 3. Navigate to “Book a Class”
            # ------------------------------------------------------------------
            _log("📅 Navigating to booking page…")
            page.get_by_text("Book a Class").click(timeout=15000)
            page.wait_for_load_state("networkidle")

            # Select the Flatiron studio
            _log("📍 Selecting Flatiron studio…")
            page.fill("input[placeholder*='Search']", "Flatiron")
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            page.get_by_text("Flatiron").first.click(timeout=10000)

            # ------------------------------------------------------------------
            # 4. Pick the target date
            # ------------------------------------------------------------------
            _log(f"🗓 Selecting date {target.strftime('%A %b %d')}…")
            day_str = str(target.day)
            date_locator = f"button:has-text('{day_str}')"
            page.locator(date_locator).first.click(timeout=5000)
            page.wait_for_timeout(2000)

            # ------------------------------------------------------------------
            # 5. Find 6:15 PM Yoga Sculpt class
            # ------------------------------------------------------------------
            _log("💪 Searching for 6:15 PM Yoga Sculpt class…")
            classes = page.locator("div.class-card")
            found = False
            count = classes.count()
            for i in range(count):
                card = classes.nth(i)
                text = card.inner_text().lower()
                if "yoga sculpt" in text and "6:15" in text:
                    card.scroll_into_view_if_needed()
                    card.get_by_text("Book").first.click(timeout=5000)
                    found = True
                    _log("✅ Found target class, attempting to book…")
                    break

            if not found:
                _log("⚠️ No matching class found (Yoga Sculpt 6:15 PM). Exiting gracefully.")
                return

            # ------------------------------------------------------------------
            # 6. Confirm booking
            # ------------------------------------------------------------------
            try:
                page.get_by_text("Reserve My Spot").first.click(timeout=10000)
                page.wait_for_timeout(3000)
                _log("✅ Booking completed successfully.")
            except Exception:
                _log("⚠️ Could not click 'Reserve My Spot' — possibly already booked or on waitlist.")

            _log("🎉 ALONI booking flow finished without fatal errors.")

        except PWTimeoutError as e:
            _log(f"❌ Playwright timeout: {e}")
            raise
        except Exception as e:
            _log(f"❌ Unhandled exception: {e}")
            raise
        finally:
            try:
                context.tracing.stop(path="trace.zip")
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("🧘 Starting ALONI automation…")
    try:
        main()
    except Exception as exc:
        print(f"##[error]{exc}")
        sys.exit(1)
