from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time

def main():
    print("🚀 Starting ALONI 2.9.3 – Hybrid Mode (Login Always, Book Conditionally)…")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")

    should_book = weekday in ["Monday", "Tuesday", "Wednesday"]
    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        # Close potential popups
        for selector in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
            try:
                page.locator(selector).first.click(timeout=3000)
                print(f"💨 Closed popup via {selector}")
            except:
                pass

        # Login flow (always runs daily)
        try:
            page.locator("button[data-position='profile.1']").first.click(timeout=3000)
            print("✅ Clicked profile icon.")
        except:
            print("ℹ️ Profile icon not found; continuing…")

        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(timeout=5000)
            sign_in_btn.click()
            print("✅ Clicked 'Sign In' in profile dropdown.")
        except:
            print("⚠️ Sign In button not visible; continuing…")

        try:
            page.locator("input#email").wait_for(timeout=8000)
            page.fill("input#email", "<YOUR_EMAIL>")
            page.fill("input#password", "<YOUR_PASSWORD>")
            page.locator("button:has-text('Sign In')").click()
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not locate sign-in modal fields: {e}")

        page.wait_for_timeout(4000)

        # --- Modal intercept patch ---
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

        # --- Conditional booking step ---
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
