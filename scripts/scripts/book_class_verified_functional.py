from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time, os

def main():
    print("🚀 Starting ALONI – Verified Functional Flow")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")

    # Skip if not Mon/Tue/Wed
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸ Skipping — target date ({target_date.strftime('%a %b %d')}) is not Mon/Tue/Wed.")
        return

    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        # Use slow_mo for stability in headless runs
        browser = p.chromium.launch(headless=True, slow_mo=150)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        # Close any popups that block view
        popup_selectors = [
            "button:has-text('Close')",
            "button[aria-label*='close' i]",
            "div[role='dialog'] button:has-text('×')",
        ]
        for sel in popup_selectors:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed popup via {sel}")
                    time.sleep(1)
            except:
                pass

        # Click profile icon
        try:
            page.locator("img[alt='Profile Icon']").first.click()
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to click profile icon: {e}")

        # Click Sign In
        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(state="visible", timeout=8000)
            sign_in_btn.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible; continuing… ({e})")

        # Login
        try:
            email = os.getenv("COREPOWER_EMAIL", "YOUR_EMAIL")
            password = os.getenv("COREPOWER_PASSWORD", "YOUR_PASSWORD")
            page.fill("input[name='username']", email)
            page.fill("input[name='password']", password)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        # Wait for login redirect
        time.sleep(5)

        # Close any post-login popups
        for sel in popup_selectors:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed popup via {sel}")
                    time.sleep(1)
            except:
                pass

        # Click “Book a class”
        try:
            book_btn = page.locator("button[data-position='book-a-class']").last
            book_btn.wait_for(state="visible", timeout=10000)
            book_btn.click()
            print("✅ Clicked visible 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Could not click Book a class: {e}")

        # Wait for schedule to load
        page.wait_for_timeout(5000)

        # Select target date
        try:
            day_num = str(target_date.day)
            day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
            day_locator.scroll_into_view_if_needed()
            day_locator.click()
            print(f"✅ Clicked calendar date {day_num} ({target_date.strftime('%a')}).")
        except Exception as e:
            print(f"⚠️ Could not select date {target_date.strftime('%a %b %d')}: {e}")

        # Wait for schedule to render
        time.sleep(5)

        # === FUNCTIONAL SCROLL LOGIC (the one that worked) ===
        print("💫 Scrolling through class list to find 6:15 pm Flatiron...")
        found = False
        for _ in range(20):  # Scroll up to ~16,000px total
            if page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").count() > 0:
                found = True
                break
            page.mouse.wheel(0, 800)
            time.sleep(0.3)

        if not found:
            print("⚠️ Could not find 6:15 pm Flatiron class after scrolling.")
        else:
            try:
                class_row = page.locator(
                    "div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')"
                ).last
                class_row.scroll_into_view_if_needed()
                print("✅ Scrolled to 6:15 pm Flatiron class.")

                book_button = class_row.locator("div.btn-text:has-text('BOOK')").last
                page.wait_for_timeout(1000)
                if book_button.is_enabled():
                    book_button.click()
                    print("✅ Clicked BOOK button.")
                else:
                    print("⚠️ BOOK button found but disabled — forcing click.")
                    page.wait_for_timeout(2000)
                    book_button.click(force=True)

                # Check for success
                page.wait_for_timeout(3000)
                if page.locator("button:has-text(\"I'm done\")").is_visible():
                    print("🎉 Booking confirmed — popup detected.")
                    page.locator("button:has-text(\"I'm done\")").click()
                    print("💨 Closed confirmation popup.")
                else:
                    print("⚠️ BOOK clicked but no confirmation popup found.")
            except Exception as e:
                print(f"⚠️ Error clicking class/book button: {e}")

        print("🏁 Booking flow complete.")
        browser.close()

if __name__ == "__main__":
    main()
