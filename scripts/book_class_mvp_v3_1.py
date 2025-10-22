import os, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def main():
    print("🚀 Starting ALONI 2.9.14 – Restored Reliable Flow")

    email = os.getenv("COREPOWER_EMAIL")
    password = os.getenv("COREPOWER_PASSWORD")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸ Skipping — {weekday}")
        return

    print(f"📅 Target: {weekday}, {target_date:%b %d}")

    with sync_playwright() as p:
        headless = os.getenv("CI", "").lower() == "true"
        browser = p.chromium.launch(headless=headless, slow_mo=75)
        context = browser.new_context()
        page = context.new_page()

        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        for sel in [
            "button:has-text('Close')",
            "button[aria-label*='close' i]",
            "div[role='dialog'] button:has-text('×')",
        ]:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed popup {sel}")
                    time.sleep(1)
            except:
                pass

        # Click profile icon first
        try:
            icon = page.locator("img[alt='Profile Icon']").first
            page.evaluate("(el)=>el.click()", icon.element_handle())
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Profile icon issue: {e}")

        # Then click Sign In
        try:
            sign_in = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in.wait_for(state="visible", timeout=8000)
            sign_in.click()
            print("✅ Clicked Sign In.")
        except Exception as e:
            print(f"⚠️ Sign In not visible: {e}")

        # Fill login form
        try:
            page.fill("input[name='username']", email)
            page.fill("input[name='password']", password)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill creds: {e}")

        time.sleep(5)

        # Close post-login popups
        for sel in [
            "button:has-text('Close')",
            "button[aria-label*='close' i]",
            "div[role='dialog'] button:has-text('×')",
        ]:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed post-login popup {sel}")
                    time.sleep(1)
            except:
                pass

        # Book a class
        try:
            btn = page.locator("button[data-position='book-a-class']").last
            btn.wait_for(state="visible", timeout=10000)
            btn.click()
            print("✅ Clicked 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Booking button issue: {e}")

        page.wait_for_timeout(5000)

        # Select calendar date
        try:
            d = str(target_date.day)
            cal = page.locator(f"div.cal-date:has-text('{d}')").last
            cal.scroll_into_view_if_needed()
            cal.click()
            print(f"✅ Clicked calendar date {d}.")
        except Exception as e:
            print(f"⚠️ Date select fail: {e}")

        time.sleep(5)

        # Find & book class
        try:
            row = page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").last
            row.scroll_into_view_if_needed()
            print("✅ Found target class.")
            book = row.locator("div.btn-text:has-text('BOOK')").last
            book.wait_for(state="visible", timeout=10000)
            if book.is_enabled():
                book.click()
                print("✅ Clicked BOOK.")
            else:
                time.sleep(2)
                book.click(force=True)
                print("⚠️ Forced BOOK click.")

            time.sleep(3)
            if page.locator("button:has-text(\"I'm done\")").is_visible():
                print("🎉 Booking confirmed.")
                page.locator("button:has-text(\"I'm done\")").click()
        except Exception as e:
            print(f"⚠️ Booking flow failed: {e}")

        print("🏁 Done.")
        browser.close()

if __name__ == "__main__":
    main()
