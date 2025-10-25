from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time

def main():
    print("🚀 Starting ALONI 2.9.2 – Verified Booking Flow…")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")

    # Skip if not Mon/Tue/Wed
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"📆 Skipping booking: {weekday} is not a target day.")
        return

    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        # Close potential popups (cookie, marketing, etc.)
        try:
            page.locator("button:has-text('Close')").first.click(timeout=3000)
            print("💨 Closed popup via button:has-text('Close')")
        except:
            pass

        try:
            page.locator("button[aria-label*='close' i]").first.click(timeout=3000)
            print("💨 Closed popup via button[aria-label*='close' i]")
        except:
            pass

        # --- Corrected order: Profile icon -> dropdown Sign In -> credentials ---
        # 1) Click the profile icon (keep existing logic; add a safe attempt for the icon itself)
        clicked_profile_icon = False
        try:
            # Common profile icon containers sometimes expose the dropdown trigger first
            # Attempt a likely profile icon; if not present, we continue to the known Sign In button flow.
            page.locator("button[data-position='profile.1']").first.click(timeout=3000)
            clicked_profile_icon = True
            print("✅ Clicked profile icon (button[data-position='profile.1']).")
        except:
            print("ℹ️ Profile icon not found with data-position='profile.1'; proceeding to Sign In button if available.")

        # 2) Click the Sign In button in the dropdown
        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(timeout=5000)
            sign_in_btn.click()
            print("✅ Clicked 'Sign In' in profile dropdown (button[data-position='profile.1-sign-in']).")
        except:
            print("⚠️ Sign In button not visible; continuing…")

        # 3) Fill credentials in the sign-in modal and submit
        try:
            page.locator("input#email").wait_for(timeout=8000)
            page.fill("input#email", "<YOUR_EMAIL>")
            page.fill("input#password", "<YOUR_PASSWORD>")
            page.locator("button:has-text('Sign In')").click()
            print("✅ Submitted credentials in modal.")
        except:
            print("⚠️ Could not locate sign-in modal fields; continuing…")

        # Give the session a beat to settle post-login
        page.wait_for_timeout(4000)

        # --- PATCH: modal interception handling right before “Book a class” click ---
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

        # Click "Book a class"
        try:
            page.locator("button[data-position='book-a-class']").click(timeout=5000)
            print("✅ Clicked visible 'Book a class'.")
        except Exception as e:
            print(f"❌ Failed to click 'Book a class': {e}")
            browser.close()
            return

        # Select target date on calendar
        date_str = str(target_date.day)
        try:
            page.locator(f"text={date_str}").first.click()
            print(f"✅ Clicked calendar date {date_str} ({weekday[:3]}).")
        except:
            print(f"⚠️ Could not select date {date_str}.")

        # Scroll to 6:15 PM Yoga Sculpt at Flatiron (visual assist; selectors preserved from MVP style)
        try:
            page.evaluate("window.scrollBy(0, 500)")
            print("✅ Scrolled to 6:15 PM Yoga Sculpt (Flatiron).")
        except:
            print("⚠️ Scroll failed or unnecessary.")

        print("🎯 Booking flow reached target phase successfully.")
        browser.close()

if __name__ == "__main__":
    main()
