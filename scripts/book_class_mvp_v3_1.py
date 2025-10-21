# scripts/book_class_mvp_v3_1.py
# ALONI 2.9.7 — closes stray signup modal before login submit

import os, sys, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

def _ci(): return os.getenv("CI") == "true"
def _env(k):
    v=os.getenv(k,"").strip()
    if not v: raise RuntimeError(f"Missing env var: {k}")
    return v
def _log(m): print(m, flush=True)
def _target_date(n=13): return datetime.now().date()+timedelta(days=n)
def _shot(p,n):
    try:
        os.makedirs("screenshots",exist_ok=True)
        p.screenshot(path=f"screenshots/{n}.png",full_page=True)
    except Exception: pass

def main():
    email=_env("COREPOWER_EMAIL"); pwd=_env("COREPOWER_PASSWORD")
    target=_target_date(13); day=target.strftime("%A")
    _log(f"🚀 ALONI 2.9.7 — Target {day}, {target:%b %d}")
    if day not in ["Monday","Tuesday","Wednesday"]:
        _log(f"ℹ️ {day} is not a booking day."); return

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=_ci(), slow_mo=0)
        ctx=browser.new_context(record_video_dir="videos" if _ci() else None,
                                viewport={"width":1440,"height":900})
        page=ctx.new_page()
        ctx.tracing.start(screenshots=True,snapshots=True,sources=True)
        try:
            _log("🏠 Opening homepage…")
            page.goto("https://www.corepoweryoga.com/",timeout=90000)
            page.wait_for_load_state("networkidle")
            page.evaluate("window.scrollTo(0,0)")
            _shot(page,"01_home")

            for sel in ["button:has-text('Close')","button[aria-label*='close' i]",
                        "button:has-text('Accept')","button:has-text('Got it')"]:
                try: page.locator(sel).first.click(timeout=1500)
                except Exception: pass

            _log("🔐 Logging in…")
            # ensure hydration
            page.evaluate("window.dispatchEvent(new Event('scroll'));window.dispatchEvent(new Event('mousemove'));")

            # click sign-in or open profile
            page.evaluate("""
              const b=[...document.querySelectorAll('button,a')].find(e=>/sign\\s*in/i.test(e.textContent||'')); 
              if(b){b.style.display='block';b.style.visibility='visible';b.click();}
            """)
            time.sleep(2)
            _shot(page,"02_after_signin_click")

            # close accidental signup overlay if it appeared
            for _ in range(3):
                modals=page.locator("div.cpy-modal--sign-up")
                if modals.count()>0:
                    _log("⚠️ Signup modal detected — closing it before login attempt…")
                    page.keyboard.press("Escape")
                    try:
                        page.locator("button:has-text('Close')").first.click(timeout=1000)
                    except Exception: pass
                    time.sleep(1)
                else: break

            # fill credentials
            page.wait_for_selector("input[name='email']",timeout=20000)
            page.fill("input[name='email']",email)
            page.fill("input[name='password']",pwd)
            _shot(page,"03_credentials_filled")

            # if overlay re-appears, close again
            for _ in range(2):
                try:
                    page.locator("div.cpy-modal--sign-up").first.is_visible()
                    _log("⚠️ Signup overlay still present — closing again.")
                    page.keyboard.press("Escape")
                    page.locator("button:has-text('Close')").first.click(timeout=1000)
                except Exception: break
                time.sleep(0.5)

            # click submit (retry if blocked)
            _log("➡️ Submitting login form…")
            for _ in range(3):
                try:
                    page.click("form button[type='submit']",timeout=8000)
                    break
                except Exception:
                    _log("⏳ Retrying submit after overlay close attempt…")
                    page.keyboard.press("Escape"); time.sleep(1)

            page.wait_for_selector("button[data-position='profile.1-logged-in']",timeout=30000)
            _log("✅ Login successful.")

            # booking steps (unchanged)
            _log("📅 Navigating to booking page…")
            page.get_by_text("Book a Class").click(timeout=15000)
            page.wait_for_load_state("networkidle")

            _log("📍 Selecting Flatiron studio…")
            page.fill("input[placeholder*='Search']","Flatiron")
            page.keyboard.press("Enter"); time.sleep(2)
            page.get_by_text("Flatiron").first.click(timeout=10000)

            _log(f"🗓 Selecting {target:%A %b %d}…")
            page.locator(f"button:has-text('{target.day}')").first.click(timeout=5000)
            time.sleep(1)

            _log("💪 Searching for 6:15 PM Yoga Sculpt class…")
            cards=page.locator("div.class-card"); found=False
            for i in range(cards.count()):
                c=cards.nth(i); t=c.inner_text().lower()
                if "yoga sculpt" in t and "6:15" in t:
                    c.scroll_into_view_if_needed()
                    try:c.get_by_text("Book").first.click(timeout=5000)
                    except Exception:
                        try:c.get_by_text("Join Waitlist").first.click(timeout=5000)
                        except Exception:pass
                    found=True; _log("✅ Target class clicked."); break
            if not found: _log("⚠️ No matching class found."); return

            try:
                page.get_by_text("Reserve My Spot").first.click(timeout=10000)
                _log("✅ Booking complete.")
            except Exception:
                _log("⚠️ Could not click 'Reserve My Spot' (maybe already booked).")
            _log("🎉 Flow finished.")
        except Exception as e:
            _log(f"❌ {e}"); raise
        finally:
            try:ctx.tracing.stop(path="trace.zip")
            except Exception:pass
            ctx.close(); browser.close()

if __name__=="__main__":
    print("🧘 Starting ALONI automation…")
    try:main()
    except Exception as e:print(f"##[error]{e}");sys.exit(1)
