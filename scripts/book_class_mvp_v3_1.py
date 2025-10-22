import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")

TARGET_LOCATION = "Flatiron"
TARGET_CLASS = "6:15 pm"

def get_target_date():
    """Return the weekday 13 days from today (Mon/Tue/Wed only)."""
    target = datetime.now() + timedelta(days=13)
    while target.strftime("%A") not in ["Monday", "Tuesday", "Wednesday"]:
        target += timedelta(days=1)
    return target

def run_aloni():
    target_date = get_target_date()
    day = target_date.day
    weekday = target_date.strftime("%A")
    print(f"🚀 Starting ALONI 2.9.11 – Verified Booking Flow…")
    print(f"📅 Target date: {weekday}, {target_date.strftime('%b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, timeout=60000)

        # Close modal popups if visible
        for sel in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
            try:
                page.locator(sel).first.click(timeout=3000)
                print(f"💨 Closed popup via {sel}")
                break
            except PlaywrightTimeout:
                pass

        # Click profile icon to open login
        try:
            page.locator("button[data-position='profile.1-sign-in'], button[data-position='profile.1-account']").first.click(timeout=5000)
            print("✅ Clicked profile icon.")
        except PlaywrightTimeout:
            print("⚠️ Could not find profile icon; continuing anyway.")

        # Login flow
        try:
            page.fill("input[name='email']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            print("✅ Submitted credentials.")
        except PlaywrightTimeout:
            print("⚠️ Login form not visible; may already be signed in.")

        # Navigate to booking page
        try:
            page.get_by_text("Book a class", exact=False).first.click(timeout=8000)
            print("✅ Clicked visible 'Book a class'.")
        except PlaywrightTimeout:
            print("⚠️ Could not find 'Book a class' button.")

        # Select target date
        try:
            page.locator(f"div.cal-date:has-text('{day}')").click()
            page.wait_for_selector(f"div.cal-date.is-selected:has-text('{day}')", timeout=3000)
            print(f"✅ Clicked calendar date {day} ({weekday}).")
        except PlaywrightTimeout:
            print(f"⚠️ Could not confirm calendar selection for {day} ({weekday}).")

        # Scroll and find target class
        print("🔍 Scanning for class...")
        target_class = None
        for scroll_attempt in range(15):
            sessions = page.locator("div.session-row-view")
            count = sessions.count()
            for i in range(count):
                try:
                    text = sessions.nth(i).inner_text(timeout=2000)
                    if TARGET_CLASS in text and TARGET_LOCATION in text:
                        target_class = sessions.nth(i)
                        break
                except PlaywrightTimeout:
                    continue
            if target_class:
                break
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(600)

        if target_class:
            target_class.scroll_into_view_if_needed()
            target_class.click()
            print(f"✅ Found and clicked {TARGET_CLASS} at {TARGET_LOCATION}.")
        else:
            print(f"⚠️ Could not find {TARGET_CLASS} at {TARGET_LOCATION} after scrolling.")

        print("🏁 Booking flow complete.")
        context.close()
        browser.close()

if __name__ == "__main__":
    run_aloni()
