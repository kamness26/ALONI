import os
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")

TARGET_LOCATION = "Flatiron"
TARGET_CLASS = "6:15 pm"


def close_all_modals(page):
    modals = [
        "button:has-text('Close')",
        "button[aria-label*='close' i]",
        "div.cpy-modal--sign-up",
        "div.cpy-modal--full-height",
        "div.modal.show"
    ]
    for selector in modals:
        try:
            elements = page.locator(selector)
            count = elements.count()
            if count > 0:
                for i in range(count):
                    elements.nth(i).evaluate("e => e.remove()")
                    print(f"💨 Removed modal element: {selector}")
        except Exception:
            pass


def verify_login(page):
    try:
        if page.locator("button[data-position='profile.1-sign-out']").count() > 0:
            print("🟢 Login verified — user is signed in.")
            return True
    except Exception:
        pass
    return False


def select_target_date(page, target_date_str):
    try:
        calendar_selector = f"div.cal-date:has-text('{target_date_str}')"
        print(f"🗓  Selecting date: {target_date_str}")
        page.wait_for_selector(calendar_selector, timeout=10000)
        page.locator(calendar_selector).last.scroll_into_view_if_needed()
        time.sleep(1)
        page.locator(calendar_selector).last.click()
        print(f"✅ Selected date {target_date_str}")
        return True
    except Exception as e:
        print(f"⚠️ Could not select date {target_date_str}: {e}")
        return False


def scroll_and_find_class(page):
    """Scrolls through the schedule to locate and book the target session."""
    for i in range(17):
        rows = page.locator("div.session-card_sessionTime__hNAfR")
        count = rows.count()
        print(f"🔍 Found {count} session rows (scroll {i+1}/17)")
        for j in range(count):
            try:
                time_text = rows.nth(j).inner_text().strip()
                if time_text == TARGET_CLASS:
                    location = rows.nth(j).locator(
                        "xpath=ancestor::div[contains(@class,'session-card')]//div[contains(text(), 'Flatiron')]"
                    )
                    if location.count() > 0:
                        print(f"✅ Found {TARGET_CLASS} at {TARGET_LOCATION} — attempting booking…")
                        book_button = rows.nth(j).locator(
                            "xpath=ancestor::div[contains(@class,'session-card')]//div[contains(@class,'btn-text') and contains(., 'BOOK')]"
                        )
                        book_button.scroll_into_view_if_needed()
                        time.sleep(1)
                        book_button.click()
                        time.sleep(3)
                        return True
            except Exception:
                continue
        page.mouse.wheel(0, 1200)
        time.sleep(1)
    print(f"⚠️ Could not find {TARGET_CLASS} {TARGET_LOCATION} class after scrolling.")
    return False


def main():
    print("🚀 Starting ALONI 2.9.12 – Hover-Click Functional Flow")

    target_date = datetime.now() + timedelta(days=13)
    target_date_str = target_date.strftime("%-d")
    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        print("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, timeout=60000)
        close_all_modals(page)

        # === LOGIN PHASE ===
        print("\n🔐 LOGIN PHASE")

        try:
            # Hover to make icon and menu visible
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

        time.sleep(5)
        close_all_modals(page)

        if not verify_login(page):
            print("❌ Login verification failed — stopping flow early.")
            browser.close()
            return

        # === BOOKING PHASE ===
        print("\n📘 BOOKING PHASE")

        try:
            page.wait_for_selector("button[data-position='book-a-class']", timeout=10000)
            page.click("button[data-position='book-a-class']")
            print("✅ Clicked 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Could not click 'Book a class': {e}")

        close_all_modals(page)

        if not select_target_date(page, target_date_str):
            print("⚠️ Date selection failed, attempting scroll fallback.")
            page.mouse.wheel(0, 2000)
            time.sleep(1)
            select_target_date(page, target_date_str)

        print("💫 Scrolling through class list to find target session…")
        found = scroll_and_find_class(page)

        if found:
            print("✅ Booking attempt complete — check confirmation popup or email.")
        else:
            print("⚠️ Booking click registered but no confirmation popup found.")

        print("🏁 Booking flow complete.")
        browser.close()


if __name__ == "__main__":
    main()
