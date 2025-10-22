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
