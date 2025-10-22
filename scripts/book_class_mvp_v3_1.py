import os, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")
TARGET_CLASS = "6:15 pm"
TARGET_LOCATION = "Flatiron"

def main():
    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸  {target_date:%A %b %d} not a booking day.")
        return

    print(f"🚀  Starting ALONI 2.9.13 – Full Login → Scroll → Book Flow")
    print(f"📅  Target date: {weekday}, {target_date:%b %d}")

    with sync_playwright() as p:
        headless = os.getenv("CI", "").lower() == "true"
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # — HOME —
        print("🏠  Opening homepage…")
        page.goto(COREPOWER_URL, timeout=60000)

        # Close pop-ups
        for sel in [
            "button:has-text('Close')",
            "button[aria-label*='close' i]",
            "div[role='dialog'] button:has-text('×')",
        ]:
            try:
                page.locator(sel).first.click(timeout=3000)
                print(f"💨  Closed popup via {sel}")
            except Exception:
                pass

        # — PROFILE ICON → SIGN IN —
        try:
            profile_icon = page.locator("img[alt='Profile Icon']").first
            profile_icon.wait_for(state="visible", timeout=10000)
            page.evaluate("(el)=>el.click()", profile_icon.element_handle())
            print("✅  Clicked Profile Icon.")
        except Exception as e:
            print(f"⚠️ Profile icon click failed: {e}")

        try:
            sign_in = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in.wait_for(state="visible", timeout=8000)
            sign_in.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible: {e}")

        # — LOGIN FORM —
        try:
            page.fill("input[name='username'], input[name='email']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Credential entry failed: {e}")

        page.wait_for_timeout(5000)

        # — POST-LOGIN POPUPS —
        for sel in [
            "button:has-text('Close')",
            "button[aria-label*='close' i]",
            "div[role='dialog'] button:has-text('×')",
        ]:
            try:
                page.locator(sel).first.click(timeout=3000)
                print(f"💨 Closed post-login popup via {sel}")
            except Exception:
                pass

        # — BOOK A CLASS —
        try:
            book_btn = page.locator("button[data-position='book-a-class']").last
            book_btn.wait_for(state="visible", timeout=10000)
            book_btn.click()
            print("✅ Clicked 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Could not click Book a class: {e}")

        page.wait_for_timeout(4000)

        # — SELECT DATE (top-left calendar) —
        day_num = str(target_date.day)
        try:
            cal = page.locator(f"div.cal-date:has-text('{day_num}')").last
            cal.scroll_into_view_if_needed()
            cal.click()
            print(f"✅ Clicked calendar date {day_num} ({weekday}).")
        except Exception as e:
            print(f"⚠️ Calendar click failed: {e}")

        # — SCROLL AND BOOK CLASS —
        print("🔍 Searching for target class…")
        target = None
        for _ in range(20):
            rows = page.locator("div.session-row-view")
            for i in range(rows.count()):
                try:
                    txt = rows.nth(i).inner_text(timeout=2000)
                    if TARGET_CLASS in txt and TARGET_LOCATION in txt:
                        target = rows.nth(i)
                        break
                except Exception:
                    continue
            if target:
                break
            page.mouse.wheel(0, 1000)
            time.sleep(0.4)

        if target:
            target.scroll_into_view_if_needed()
            btn = target.locator("div.btn-text:has-text('BOOK')").last
            try:
                btn.click(timeout=5000)
                print(f"✅ Booked {TARGET_CLASS} at {TARGET_LOCATION}.")
            except Exception as e:
                print(f"⚠️ BOOK button click failed: {e}")
        else:
            print(f"⚠️ No {TARGET_CLASS} at {TARGET_LOCATION} found.")

        print("🏁 Flow complete.")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
