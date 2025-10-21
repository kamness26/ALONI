# scripts/book_class_mvp_v3_1.py
# ALONI 2.9.10 — Restored verified local booking flow with CI-safe scroll/load logic

import os, sys, time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright


def _env(key: str) -> str:
    v = os.getenv(key, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {key}")
    return v


def main():
    print("🚀 Starting ALONI 2.9.10 – Verified Booking Flow…")

    email = _env("COREPOWER_EMAIL")
    password = _env("COREPOWER_PASSWORD")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")

    # Skip if not Mon/Tue/Wed
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

        # Open homepage
        print("🏠 Opening homepage…")
        page.goto("https://www.corepoweryoga.com/", timeout=60000)

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

        # Click profile icon (via JS for reliability)
        try:
            page.evaluate(
                "(el)=>el.click()",
                page.locator("img[alt='Profile Icon']").first.element_handle(),
            )
            print("✅ Clicked profile icon.")
        except Exception as e:
            print(f"⚠️ Failed to click profile icon: {e}")

        # Click Sign In
        try:
            btn = page.locator("button[data-position='profile.1-sign-in']").first
            btn.wait_for(state="visible", timeout=5000)
            btn.click()
            print("✅ Clicked Sign In button.")
        except Exception as e:
            print(f"⚠️ Sign In button not visible; continuing… ({e})")

        # Login form
        try:
            page.fill("input[name='username']", email)
            page.fill("input[name='password']", password)
            page.keyboard.press("Enter")
            print("✅ Submitted credentials.")
        except Exception as e:
            print(f"⚠️ Could not fill credentials: {e}")

        # Wait for redirect after login
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

        # Wait for schedule page
        page.wait_for_timeout(5000)

        # Select target date (calendar on top left)
        try:
            day_num = str(target_date.day)
            day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
            day_locator.scroll_into_view_if_needed()
            day_locator.click()
            print(f"✅ Clicked calendar date {day_num} ({target_date:%a}).")
        except Exception as e:
            print(f"⚠️ Could not select date {target_date:%a %b %d}: {e}")

        # 🪄 Force schedule grid to load after date click
        try:
            page.wait_for_selector("div.cal-date.is-selected", timeout=10000)
            # Scroll down into schedule grid
            page.evaluate("window.scrollBy(0, 800)")
            # Wait for any class rows to appear
            page.wait_for_selector("div.session-row-view", timeout=45000)
            # Scroll further to trigger lazy-load if needed
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ Schedule grid may not have fully loaded: {e}")

        # Locate and book 6:15 pm Flatiron class
        try:
            row = page.locator(
                "div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')"
            ).last
            row.scroll_into_view_if_needed()
            print("✅ Scrolled to 6:15 pm Flatiron class.")
            book = row.locator("div.btn-text:has-text('BOOK')").last
            book.wait_for(state="visible", timeout=10000)
            book.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            if book.is_enabled():
                book.click()
                print("✅ Clicked BOOK button.")
            else:
                print("⚠️ BOOK button disabled — retrying after short wait.")
                page.wait_for_timeout(2000)
                book.click(force=True)

            # Confirm success
            page.wait_for_timeout(3000)
            if page.locator("button:has-text(\"I'm done\")").is_visible():
                print("🎉 Booking confirmed — popup detected.")
                page.locator("button:has-text(\"I'm done\")").click()
                print("💨 Closed confirmation popup.")
            else:
                print("⚠️ Booking click registered but no confirmation popup found.")
        except Exception as e:
            print(f"⚠️ Could not book class: {e}")

        print("🏁 Booking flow complete.")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"##[error]{e}")
        sys.exit(1)
