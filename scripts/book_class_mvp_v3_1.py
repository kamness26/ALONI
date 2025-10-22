import os, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")
TARGET_CLASS = "6:15 pm"
TARGET_LOCATION = "Flatiron"

def get_target_date():
    target = datetime.now() + timedelta(days=13)
    while target.strftime("%A") not in ["Monday", "Tuesday", "Wednesday"]:
        target += timedelta(days=1)
    return target

def run_aloni():
    target_date = get_target_date()
    day = target_date.day
    weekday = target_date.strftime("%A")
    print(f"🚀 Starting ALONI 2.9.12 – Reliable Login + Scroll Booking Flow")
    print(f"📅 Target date: {weekday}, {target_date:%b %d} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, timeout=60000)

        # Close popups
        for sel in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
            try:
                page.locator(sel).first.click(timeout=3000)
                print(f"💨 Closed popup via {sel}")
            except Exception:
                pass

        # --- LOGIN HANDSHAKE ---
        print("🔑 Checking for Sign In button...")
        try:
            login_btn = page.locator("text=Sign In, button[data-position='profile.1-sign-in']").first
            login_btn.wait_for(state="visible", timeout=20000)
            login_btn.click()
            print("✅ Clicked Sign In button.")
        except PlaywrightTimeout:
            print("⚠️ Sign In button not found, refreshing once…")
            page.reload()
            page.wait_for_timeout(4000)
            try:
                page.get_by_text("Sign In", exact=False).first.click(timeout=5000)
                print("✅ Clicked Sign In after refresh.")
            except Exception:
                print("⚠️ Still no Sign In button, proceeding cautiously.")

        # Fill credentials
        try:
            page.fill("input[name='email']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.click("button[type='submit']")
            print("✅ Submitted credentials.")
            page.wait_for_timeout(5000)
        except Exception:
            print("⚠️ Login fields not found; may already be logged in.")

        # --- BOOKING FLOW ---
        try:
            page.get_by_text("Book a class", exact=False).first.click(timeout=10000)
            print("✅ Clicked 'Book a class'.")
        except PlaywrightTimeout:
            print("⚠️ Could not find 'Book a class' button; may already be on schedule page.")

        # Select calendar date
        try:
            date_sel = page.locator(f"div.cal-date:has-text('{day}')")
            date_sel.first.click()
            print(f"✅ Clicked calendar date {day} ({weekday}).")
        except Exception:
            print(f"⚠️ Could not click calendar date {day}.")

        # Scroll and search
        print("🔍 Scanning for class…")
        found = None
        for attempt in range(18):
            items = page.locator("div.session-row-view")
            for i in range(items.count()):
                try:
                    text = items.nth(i).inner_text()
                    if TARGET_CLASS in text and TARGET_LOCATION in text:
                        found = items.nth(i)
                        break
                except Exception:
                    continue
            if found:
                break
            page.mouse.wheel(0, 1000)
            time.sleep(0.5)

        if found:
            found.scroll_into_view_if_needed()
            found.click()
            print(f"✅ Found and clicked {TARGET_CLASS} at {TARGET_LOCATION}.")
        else:
            print(f"⚠️ Could not find {TARGET_CLASS} at {TARGET_LOCATION} after scrolling.")

        print("🏁 Booking flow complete.")
        context.close()
        browser.close()

if __name__ == "__main__":
    run_aloni()
