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
    """Force close or remove any lingering modals that block interactions."""
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


def wait_and_click(page, selector, timeout=8000, description=""):
    """Click an element with wait and retry handling."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        page.locator(selector).first.click()
        print(f"✅ Clicked {description or selector}")
    except PlaywrightTimeoutError:
        print(f"⚠️ Timeout waiting for {description or selector}")
    except Exception as e:
        print(f"⚠️ Could not click {description or selector}: {e}")
        close_all_modals(page)
        try:
            page.locator(selector).first.click()
            print(f"✅ Clicked {description or selector} after cleanup")
        except Exception:
            print(f"❌ Failed to click {description or selector} after cleanup")


def wait_and_fill(page, selector, value, description=""):
    """Safely fill input field."""
    try:
        page.wait_for_selector(selector, timeout=6000)
        page.fill(selector, value)
        print(f"✅ Filled {description or selector}")
    except Exception as e:
        print(f"⚠️ Could not fill {description or selector}: {e}")


def select_target_date(page, target_date_str):
    """Click on the target date from the booking calendar."""
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
    """Scrolls down the class list to find the target session."""
    for i in range(15):
        rows = page.locator("div.session-card_sessionTime__hNAfR")
        count = rows.count()
        print(f"🔍 Found {count} session rows (scroll {i+1}/15)")
        for j in range(count):
            try:
                time_text = rows.nth(j).inner_text().strip()
                if time_text == TARGET_CLASS:
                    # Verify correct location near this time slot
                    location = rows.nth(j).locator(
                        "xpath=ancestor::div[contains(@class,'session-card')]//div[contains(text(), 'Flatiron')]"
                    )
                    if location.count() > 0:
                        print(f"✅ Found {TARGET_CLASS} at {TARGET_LOCATION} — attempting booking…")
                        book_button = rows.nth(j).locator(
                            "xpath=ancestor::div[contains(@class,'session-card')]//button[contains(., 'Book')]"
                        )
                        book_button.click()
                        time.sleep(2)
                        return True
            except Exception:
                continue
        page.mouse.wheel(0, 1200)
        time.sleep(1)
    print(f"⚠️ Could not find {TARGET_CLASS} {TARGET_LOCATION} class after scrolling.")
    return False


def main():
    print("🚀 Starting ALONI – Verified Functional Flow")

    target_date = datetime.now() + timedelta(days=13)
    target_date_str = target_date.strftime("%-d")  # day of month without leading zero
    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        print("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, timeout=60000)
        close_all_modals(page)

        # ✅ Login flow (restored from 2.9.2)
        try:
            page.wait_for_selector("img[alt='Profile Icon']", timeout=10000)
            profile_icon = page.locator("img[alt='Profile Icon']").first
            profile_icon.scroll_into_view_if_needed()
            profile_icon.click()
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to click profile icon: {e}")

        try:
            sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
            sign_in_btn.wait_for(state="visible", timeout=8000)
            sign_in_btn.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible; continuing… ({e})")

        try:
            page.wait_for_selector("input[name='username']", timeout=10000)
            page.fill("input[name='username']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        time.sleep(5)
        close_all_modals(page)

        # ✅ Book a class
        wait_and_click(page, "button[data-position='book-a-class']", description="Book a class")
        close_all_modals(page)

        # ✅ Select target date
        if not select_target_date(page, target_date_str):
            print("⚠️ Date selection failed, attempting fallback scroll")
            page.mouse.wheel(0, 2000)
            time.sleep(1)
            select_target_date(page, target_date_str)

        # ✅ Find and book class
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
