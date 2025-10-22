# scripts/book_class_verified_functional.py

import os
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")
COREPOWER_URL = "https://www.corepoweryoga.com/"
LOCATION_NAME = "Flatiron"
CLASS_NAME = "Yoga Sculpt"
TARGET_TIME = "6:15 pm"

def main():
    target_date = datetime.now() + timedelta(days=13)
    formatted_date = target_date.strftime("%A, %b %d")
    print(f"🚀 Starting ALONI 2.9.13 – Hover-Click Functional Flow")
    print(f"📅 Target date: {formatted_date} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        print("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, wait_until="load", timeout=60000)

        # 🔧 Close any modal or cookie banner BEFORE login
        try:
            page.wait_for_selector("button:has-text('Close')", timeout=5000)
            page.click("button:has-text('Close')")
            print("💨 Closed popup via button:has-text('Close')")
        except:
            pass

        try:
            page.click("button[aria-label*='close' i]", timeout=3000)
            print("💨 Closed popup via button[aria-label*='close' i]")
        except:
            pass

        # -------------------------
        # LOGIN PHASE
        # -------------------------
        print("\n🔐 LOGIN PHASE")
        try:
            page.wait_for_selector("img[alt='Profile Icon']", state="attached", timeout=15000)
            page.hover("img[alt='Profile Icon']")
            page.wait_for_timeout(800)
            page.click("img[alt='Profile Icon']")
            print("✅ Hovered and clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to interact with profile icon: {e}")

        try:
            page.wait_for_selector("button[data-position='profile.1-sign-in']", state="visible", timeout=8000)
            page.click("button[data-position='profile.1-sign-in']")
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Could not click Sign In button: {e}")

        try:
            page.wait_for_selector("input[name='username']", timeout=15000)
            page.fill("input[name='username']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        # -------------------------
        # VERIFY LOGIN SUCCESS
        # -------------------------
        try:
            page.wait_for_selector("text=Book a Class", timeout=15000)
            print("✅ Login successful!")
        except:
            print("❌ Login verification failed — stopping flow early.")
            browser.close()
            return

        # -------------------------
        # BOOKING FLOW
        # -------------------------
        print("\n🧘 BOOKING PHASE")

        try:
            page.click("text=Book a Class", timeout=15000)
            print("✅ Clicked 'Book a class'")
        except Exception as e:
            print(f"⚠️ Could not click 'Book a class': {e}")

        try:
            # Select the correct calendar date
            day_num = target_date.day
            selector = f"button.calendar-day:has-text('{day_num}')"
            page.wait_for_selector(selector, timeout=10000)
            page.click(selector)
            print(f"✅ Clicked calendar date {day_num}")
        except Exception as e:
            print(f"⚠️ Could not select calendar date: {e}")

        try:
            # Scroll to find the desired class time
            print("💨 Scrolling to find class time…")
            for _ in range(25):
                if page.locator(f"div.session-card_sessionTime__hNAfR:has-text('{TARGET_TIME}')").count() > 0:
                    print(f"✅ Found class time: {TARGET_TIME}")
                    break
                page.mouse.wheel(0, 400)
                time.sleep(0.3)
            else:
                print(f"❌ Could not find class time {TARGET_TIME}")
                browser.close()
                return

            # Click the class
            class_card = page.locator(
                f"div.session-card_sessionTime__hNAfR:has-text('{TARGET_TIME}')"
            ).first
            class_card.scroll_into_view_if_needed()
            class_card.click()
            print(f"✅ Selected class at {TARGET_TIME}")

            # Confirm booking
            try:
                page.wait_for_selector("button:has-text('Reserve')", timeout=10000)
                page.click("button:has-text('Reserve')")
                print("✅ Clicked Reserve")
            except:
                print("⚠️ Reserve button not found; may already be booked.")
        except Exception as e:
            print(f"❌ Booking phase error: {e}")

        browser.close()
        print("\n🎯 Flow complete – check email for CorePower confirmation.")

if __name__ == "__main__":
    main()
