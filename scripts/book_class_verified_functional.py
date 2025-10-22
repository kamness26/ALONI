# scripts/book_class_verified_functional.py
# ALONI 3.0 — Functional, GitHub-ready build (restores JS click + scroll logic)

from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import os, sys, time


def _env(key: str) -> str:
    v = os.getenv(key, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {key}")
    return v


def main():
    print("🚀 Starting ALONI – Verified Functional Flow")

    email = _env("COREPOWER_EMAIL")
    password = _env("COREPOWER_PASSWORD")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸ Skipping — target date ({target_date:%a %b %d}) is not Mon/Tue/Wed.")
        return
    print(f"📅 Target date: {target_date:%A, %b %d} (13 days from today)")

    with sync_playwright() as p:
        headless = os.getenv("CI", "").lower() == "true"
        slow = 0 if headless else 150
        browser = p.chromium.launch(headless=headless, slow_mo=slow)
        context = browser.new_context()
        page = context.new_page()

        # ---------------- HOME ----------------
        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)
        page.wait_for_load_state("domcontentloaded")

        # Close popups
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

        # ---------------- LOGIN ----------------
        try:
            page.wait_for_load_state("networkidle")
            icon = page.locator("img[alt='Profile Icon']").first
            page.evaluate("(el)=>el.click()", icon.element_handle())
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to click profile icon: {e}")

        try:
            btn = page.locator("button[data-position='profile.1-sign-in']").first
            btn.wait_for(state="visible", timeout=8000)
            btn.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible; continuing… ({e})")

        try:
            page.wait_for_selector("input[name='username']", timeout=15000)
            page.fill("input[name='username']", email)
            page.fill("input[name='password']", password)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        time.sleep(6)

        # Close post-login popups
        for sel in popup_selectors:
            try:
                if page.is_visible(sel):
                    page.click(sel)
                    print(f"💨 Closed popup via {sel}")
                    time.sleep(1)
            except:
                pass

        # ---------------- BOOKING ----------------
        try:
            book_btn = page.locator("button[data-position='book-a-class']").last
            book_btn.wait_for(state="visible", timeout=10000)
            book_btn.click()
            print("✅ Clicked visible 'Book a class'.")
        except Exception as e:
            print(f"⚠️ Could not click Book a class: {e}")

        page.wait_for_timeout(4000)

        # Select target date
        try:
            day_num = str(target_date.day)
            day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
            day_locator.scroll_into_view_if_needed()
            day_locator.click()
            print(f"✅ Clicked calendar date {day_num} ({target_date:%a}).")
        except Exception as e:
            print(f"⚠️ Could not select date {target_date:%a %b %d}: {e}")

        # Scroll to load all classes
        try:
            print("💫 Scrolling through class list to find 6:15 pm Flatiron...")
            for _ in range(15):
                if page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").count() > 0:
                    break
                page.mouse.wheel(0, 600)
                time.sleep(0.6)
            else:
                print("⚠️ Could not find 6:15 pm Flatiron class after scrolling.")
        except Exception as e:
            print(f"⚠️ Scroll logic failed: {e}")

        # Try booking
        try:
            class_row = page.locator(
                "div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')"
            ).last
            class_row.scroll_into_view_if_needed()
            print("✅ Scrolled to 6:15 pm Flatiron class.")

            book_button = class_row.locator("div.btn-text:has-text('BOOK')").last
            if book_button.is_visible():
                book_button.click()
                print("✅ Clicked BOOK button.")
            else:
                print("⚠️ BOOK button not visible.")
        except Exception as e:
            print(f"⚠️ Could not book class: {e}")

        # Confirmation check
        page.wait_for_timeout(3000)
        if page.locator("button:has-text(\"I'm done\")").is_visible():
            print("🎉 Booking confirmed — confirmation popup detected.")
            page.locator("button:has-text(\"I'm done\")").click()
            print("💨 Closed confirmation popup.")
        else:
            print("⚠️ Booking click registered but no confirmation popup found.")

        print("🏁 Booking flow complete.")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"##[error]{e}")
        sys.exit(1)
