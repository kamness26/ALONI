from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time
import re

def main():
    print("🚀 Starting ALONI – Verified Functional Flow")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")

    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸ Skipping — target date ({target_date.strftime('%a %b %d')}) is not Mon/Tue/Wed.")
        return

    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1️⃣ Open homepage
        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

        # 2️⃣ Handle popups
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

        # 3️⃣ Click profile icon
        try:
            page.evaluate(
                "(el) => el.click()", 
                page.locator("img[alt='Profile Icon']").first.element_handle()
            )
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to click profile icon: {e}")

        # 4️⃣ Click “Sign In”
        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(state="visible", timeout=8000)
            sign_in_btn.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible; continuing… ({e})")

        # 5️⃣ Login
        try:
            page.fill("input[name='username']", "YOUR_EMAIL")
            page.fill("input[name='password']", "YOUR_PASSWORD")
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        time.sleep(6)

        # 6️⃣ Close post-login popups
        for sel in popup_selectors:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed popup via {sel}")
                    time.sleep(1)
            except:
                pass

        # 7️⃣ Click “Book a class”
        try:
            book_btn = page.locator("button[data-position='book-a-class']").last
            book_btn.wait_for(state="visible", timeout=10000)
            book_btn.click()
            print("✅ Clicked visible 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Could not click Book a class: {e}")

        # Wait for calendar
        page.wait_for_timeout(5000)

        # 8️⃣ Click target date
        try:
            day_num = str(target_date.day)
            day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
            day_locator.scroll_into_view_if_needed()
            day_locator.click()
            print(f"✅ Clicked calendar date {day_num} ({target_date.strftime('%a')}).")
        except Exception as e:
            print(f"⚠️ Could not select date {target_date.strftime('%a %b %d')}: {e}")

        time.sleep(4)

        # 9️⃣ Scroll within schedule to find 6:15 pm Flatiron
        print("💫 Scrolling through class list to find 6:15 pm Flatiron...")

        try:
            found = False
            scroll_attempts = 0
            max_scrolls = 15

            schedule_container = page.locator("div.schedule-container, div.schedule-page, div.class-list").first

            while not found and scroll_attempts < max_scrolls:
                rows = schedule_container.locator("div.session-row-view")
                row_count = rows.count()
                print(f"🔍 Found {row_count} session rows (scroll {scroll_attempts + 1}/{max_scrolls})")

                match = schedule_container.locator(
                    "div.session-row-view:has(div.session-card_sessionTime__hNAfR:has-text('6:15 pm')):has(div.session-card_sessionStudio__yRE6h:has-text('Flatiron'))"
                )

                if match.count() > 0:
                    print("✅ Found target row for 6:15 pm Flatiron.")
                    target = match.first
                    target.scroll_into_view_if_needed()
                    page.wait_for_timeout(1000)

                    book_button = target.locator("div.btn-text:has-text('BOOK')")
                    if book_button.count() > 0 and book_button.first.is_visible():
                        book_button.first.click()
                        print("🧘 Clicked BOOK button successfully.")
                    else:
                        print("⚠️ BOOK button not visible or already booked.")

                    found = True
                else:
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(1000)
                    scroll_attempts += 1

            if not found:
                print("⚠️ Could not find 6:15 pm Flatiron class after scrolling.")

        except Exception as e:
            print(f"⚠️ Booking section error: {e}")

        # 🔟 Confirm booking
        page.wait_for_timeout(3000)
        try:
            if page.locator("button:has-text(\"I'm done\")").is_visible():
                print("🎉 Booking confirmed — popup detected.")
                page.locator("button:has-text(\"I'm done\")").click()
                print("💨 Closed confirmation popup.")
            else:
                print("⚠️ Booking click registered but no confirmation popup found.")
        except Exception as e:
            print(f"⚠️ Confirmation check error: {e}")

        print("🏁 Booking flow complete.")
        browser.close()


if __name__ == "__main__":
    main()
