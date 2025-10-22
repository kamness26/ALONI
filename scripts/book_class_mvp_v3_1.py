# scripts/book_class_mvp_v3_2.py
import os, datetime, time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def book_class():
    target_date = (datetime.date.today() + datetime.timedelta(days=13))
    target_day = target_date.day
    target_str = target_date.strftime("%A, %b %d")
    print(f"🚀 Starting ALONI 2.9.15 – Scroll & Sync Fix")
    print(f"📅 Target date: {target_str}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Open homepage
        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com", wait_until="load")

        # Click profile icon
        page.locator("button[aria-label*='profile' i]").click()
        print("✅ Clicked profile icon.")

        # Wait for dropdown to expand (explicitly)
        try:
            page.wait_for_selector("button[data-position='profile.1-sign-in']", state="visible", timeout=5000)
        except PlaywrightTimeout:
            print("⚠️ Sign In still hidden — forcing second click and recheck")
            page.locator("button[aria-label*='profile' i]").click()
            page.wait_for_timeout(1000)

        # Click Sign In
        page.locator("button[data-position='profile.1-sign-in']").click()
        print("✅ Clicked 'Sign In'.")

        # Fill credentials
        page.wait_for_selector("input[name='username']", timeout=10000)
        page.fill("input[name='username']", os.getenv("COREPOWER_EMAIL"))
        page.fill("input[name='password']", os.getenv("COREPOWER_PASSWORD"))
        page.click("button:has-text('Sign In')")
        print("✅ Submitted credentials.")

        # Post-login popup
        try:
            page.locator("button:has-text('Close')").first.click(timeout=3000)
            print("💨 Closed post-login popup.")
        except:
            pass

        # Book a class
        page.get_by_role("button", name="Book a class").click()
        print("✅ Clicked 'Book a class'.")

        # Click the date
        date_button = page.locator(f"//button[normalize-space(text())='{target_day}']")
        date_button.scroll_into_view_if_needed()
        date_button.click()
        print(f"✅ Clicked calendar date {target_day}.")

        # NEW: actively scroll class list to bottom
        print("💫 Scrolling class list to find Flatiron 6:15 PM...")
        for _ in range(12):
            page.mouse.wheel(0, 500)
            time.sleep(0.4)
            if page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").count() > 0:
                break

        try:
            session = page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").last
            session.scroll_into_view_if_needed()
            session.click()
            print("✅ Clicked Flatiron 6:15 PM session.")
        except PlaywrightTimeout:
            print("⚠️ Could not find or click the class.")

        print("🏁 Booking flow complete.")
        context.close()
        browser.close()

if __name__ == "__main__":
    book_class()
