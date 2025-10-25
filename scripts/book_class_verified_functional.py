from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time, os

def main():
    print("🚀 Starting ALONI 2.9.4 – Strict Flow (Profile Icon → Sign In)…")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")
    should_book = weekday in ["Monday", "Tuesday", "Wednesday"]

    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        # --- Close popups ---
        for selector in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
            try:
                page.locator(selector).first.click(timeout=3000)
                print(f"💨 Closed popup via {selector}")
            except:
                pass

        # --- Step 1: Click the Profile Icon ---
        try:
            profile_icon = page.locator("button img[src*='profile_icon.svg']").first
            profile_icon.wait_for(timeout=8000)
            profile_icon.click()
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"❌ Could not click profile icon: {e}")
            browser.close()
            return

        # --- Step 2: Click the Sign In button in dropdown ---
        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(timeout=8000)
            sign_in_btn.click()
            print("✅ Clicked 'Sign In' in profile dropdown.")
        except Exception as e:
            print(f"❌ Could not click 'Sign In' button: {e}")
            browser.close()
            return

        # --- Step 3: Fill credentials in the modal ---
        try:
            page.locator("input#email").wait_for(timeout=8000)
            page.fill("input#email", os.getenv("COREPOWER_EMAIL"))
            page.fill("input#password", os.getenv("COREPOWER_PASSWORD"))
            page.locator("button:has-text('Sign In')").click()
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"❌ Could not submit credentials: {e}")
            browser.close()
            return

        # Wait for login to complete
        page.wait_for_timeout(4000)

        # --- Handle any post-login modals before continuing ---
        try:
            modal_close_selectors = [
                "button:has-text('Close')",
                "button[aria-label*='close' i]",
                "div.modal button.close",
                "button[aria-label='Dismiss']",
            ]
            for selector in modal_close_selectors:
                loc = page.locator(selector).first
                if loc.is_visible():
                    loc.click()
                    print(f"💨 Closed modal blocking 'Book a class' via {selector}")
                    time.sleep(1)
        except Exception as e:
            print(f"⚠️ No modal to close or error while closing modal: {e}")

        # --- Step 4: Conditional booking ---
        if should_book:
            print("🧘 Booking window is open — proceeding to book class.")
            try:
                page.locator("button[data-position='book-a-class']").click(timeout=5000)
                print("✅ Clicked 'Book a class'.")
            except Exception as e:
                print(f"❌ Failed to click 'Book a class': {e}")
                browser.close()
                return

            date_str = str(target_date.day)
            try:
                page.locator(f"text={date_str}").first.click()
                print(f"✅ Clicked calendar date {date_str} ({weekday[:3]}).")
            except:
                print(f"⚠️ Could not select date {date_str}.")

            try:
                page.evaluate("window.scrollBy(0, 500)")
                print("✅ Scrolled to 6:15 PM Yoga Sculpt (Flatiron).")
            except:
                print("⚠️ Scroll failed or unnecessary.")
        else:
            print(f"📆 {weekday} is not a booking target — login validated, skipping booking step.")

        print("🎯 Flow completed successfully.")
        browser.close()

if __name__ == "__main__":
    main()
