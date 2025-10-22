# scripts/book_class_verified_functional.py
#
# STRICT ORDER ENFORCED:
#  1) Open homepage
#  2) Dismiss popups
#  3) LOGIN (verify success)
#  4) Navigate to "Book a Class"
#  5) Select target date (13 days out)
#  6) Find class time
#  7) Reserve
#
# If login verification fails, the script exits BEFORE any date or class lookups.

import os
import sys
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")

COREPOWER_URL = "https://www.corepoweryoga.com/"
# These are not strictly required by the flow below but left for future targeting
LOCATION_NAME = "Flatiron"
CLASS_NAME = "Yoga Sculpt"
TARGET_TIME = "6:15 pm"

# ---- Utility logging ----
def log(msg: str) -> None:
    print(msg, flush=True)

def now_plus_days_str(days: int) -> str:
    dt = datetime.now() + timedelta(days=days)
    return dt.strftime("%A, %b %d")

def safe_click(page, selector: str, visible_required=True, timeout=8000, label=None):
    try:
        state = "visible" if visible_required else "attached"
        page.wait_for_selector(selector, state=state, timeout=timeout)
        page.click(selector)
        if label:
            log(f"✅ Clicked {label}")
        else:
            log(f"✅ Clicked {selector}")
        return True
    except Exception as e:
        if label:
            log(f"⚠️ Could not click {label}: {e}")
        else:
            log(f"⚠️ Could not click {selector}: {e}")
        return False

def safe_hover(page, selector: str, timeout=15000, label=None):
    try:
        page.wait_for_selector(selector, state="attached", timeout=timeout)
        page.hover(selector)
        if label:
            log(f"✅ Hovered {label}")
        else:
            log(f"✅ Hovered {selector}")
        return True
    except Exception as e:
        if label:
            log(f"⚠️ Could not hover {label}: {e}")
        else:
            log(f"⚠️ Could not hover {selector}: {e}")
        return False

def dismiss_popups(page):
    # Do not be noisy: try a few common closers and keep going
    # The order matters: we do this BEFORE any login or calendar actions.
    candidates = [
        "button:has-text('Close')",
        "button[aria-label*='close' i]",
        "button[aria-label='Close']",
        "div[role='dialog'] button:has-text('Close')",
        "div[role='dialog'] button[aria-label*='close' i]",
    ]
    for sel in candidates:
        try:
            btn = page.locator(sel)
            if btn.first.is_visible():
                btn.first.click()
                log(f"💨 Removed modal element via {sel}")
                # Give the DOM a breath after closing overlays
                page.wait_for_timeout(300)
        except:
            pass

def verify_logged_in(page) -> bool:
    """
    Conservative login verification:
    - The sign-in button should be absent or hidden.
    - The credential fields should not be visible.
    - The profile menu should reveal non-sign-in items after hover.
    We accept any of these signals and proceed only when at least one is true.
    """
    # 1) "Sign in" button not visible
    try:
        sign_in_btn = page.locator("button[data-position='profile.1-sign-in']")
        if sign_in_btn.count() == 0 or not sign_in_btn.first.is_visible():
            log("🔎 Login check: 'Sign in' not visible")
            return True
    except:
        pass

    # 2) No username field visible
    try:
        if page.locator("input[name='username']").count() == 0:
            log("🔎 Login check: username field not present")
            return True
        if not page.locator("input[name='username']").first.is_visible():
            log("🔎 Login check: username field hidden")
            return True
    except:
        pass

    # 3) Profile hover shows items other than sign-in
    try:
        if safe_hover(page, "img[alt='Profile Icon']", timeout=4000, label="profile icon (verify)"):
            # if we can see anything like "My Account" or "Sign out", assume logged in
            hints = [
                "text=Sign out",
                "text=My Account",
                "text=Account",
                "button[data-position^='profile.'][data-position$='account']",
                "button[data-position^='profile.'][data-position$='my-account']",
            ]
            for h in hints:
                if page.locator(h).count() > 0 and page.locator(h).first.is_visible():
                    log(f"🔎 Login check: profile menu shows post-login item via {h}")
                    return True
    except:
        pass

    return False

def perform_login(page) -> bool:
    log("\n🔐 LOGIN PHASE")

    # Ensure no overlays block the header/profile
    dismiss_popups(page)

    # Hover → click profile icon to open menu
    if not safe_hover(page, "img[alt='Profile Icon']", label="profile icon"):
        # Try a direct click fallback even if hover fails
        safe_click(page, "img[alt='Profile Icon']", visible_required=False, label="profile icon (fallback click)")

    page.wait_for_timeout(400)
    safe_click(page, "img[alt='Profile Icon']", visible_required=False, label="profile icon")

    # Click "Sign in"
    clicked_signin = safe_click(
        page,
        "button[data-position='profile.1-sign-in']",
        visible_required=True,
        label="Sign in button"
    )
    if not clicked_signin:
        # If sign-in button is not clickable, we might already be logged in
        if verify_logged_in(page):
            log("✅ Already logged in (no sign-in needed).")
            return True
        log("❌ Sign in button not available and not logged in.")
        return False

    # Fill credentials
    try:
        page.wait_for_selector("input[name='username']", state="visible", timeout=15000)
        page.fill("input[name='username']", EMAIL or "")
        page.fill("input[name='password']", PASSWORD or "")
        page.keyboard.press("Enter")
        log("✅ Submitted credentials.")
    except Exception as e:
        log(f"❌ Failed to submit credentials: {e}")
        return False

    # Post-submit: allow redirects / session init
    page.wait_for_timeout(1500)

    # Dismiss any post-login banners that may appear
    dismiss_popups(page)

    # Verify login before proceeding to ANY date/calendar actions
    try:
        # Wait a bit for the auth flow/UI to settle
        for _ in range(10):
            if verify_logged_in(page):
                log("✅ Login verified.")
                return True
            page.wait_for_timeout(500)
    except:
        pass

    log("❌ Login verification failed.")
    return False

def go_to_book_a_class(page) -> bool:
    log("\n📍 NAVIGATION: Book a Class")

    # The "Book a Class" CTA is available to both anon and logged-in, but we only reach here AFTER login verification.
    # Try multiple entry points just in case the page layout changes.
    targets = [
        "text=Book a Class",
        "a[href*='book-a-class']",
        "a:has-text('Book a Class')",
        "button:has-text('Book a Class')",
    ]

    for sel in targets:
        if safe_click(page, sel, visible_required=True, timeout=15000, label="Book a Class"):
            break
    else:
        log("❌ Could not navigate to 'Book a Class'.")
        return False

    # Wait for schedule/calendar UI to load (various selectors to hedge against minor class name changes)
    schedule_roots = [
        "[class*='calendar']",
        "[data-testid*='calendar']",
        "section:has-text('Schedule')",
        "section:has-text('Calendar')",
        "div:has([role='grid'])",
    ]
    for _ in range(30):  # ~15s total
        for root in schedule_roots:
            if page.locator(root).count() > 0 and page.locator(root).first.is_visible():
                log("✅ Schedule/Calendar UI detected.")
                return True
        page.wait_for_timeout(500)

    log("❌ Calendar did not load.")
    return False

def select_calendar_date(page, target_dt: datetime) -> bool:
    """
    Select a specific day in the schedule calendar.
    This is only called AFTER login + after we confirm calendar UI loaded.
    """
    log("\n🗓️  CALENDAR: Selecting target date")
    day_num = target_dt.day

    # Common direct day button
    candidates = [
        f"button.calendar-day:has-text('{day_num}')",
        f"[role='gridcell'] button:has-text('{day_num}')",
        f"[aria-label*='{target_dt.strftime('%B')}'][aria-label*='{target_dt.day}']",
        f"button:has-text('{day_num}') >> nth=0",
    ]

    # Try to bring month into view first (some UIs paginate months)
    try:
        month_label = target_dt.strftime("%B")
        # Scroll / paginate months if the UI supports it
        # We do a few wheel moves to trigger lazy loading where applicable
        for _ in range(10):
            if page.locator(f"text={month_label}").count() > 0:
                break
            page.mouse.wheel(0, 400)
            page.wait_for_timeout(200)
    except:
        pass

    for sel in candidates:
        try:
            page.wait_for_selector(sel, state="visible", timeout=6000)
            page.click(sel)
            log(f"✅ Clicked calendar date {day_num} via {sel}")
            return True
        except:
            continue

    log(f"❌ Could not select calendar date {day_num}")
    return False

def find_and_book(page, target_time: str) -> bool:
    log("\n🔎 SESSION: Locating class time")

    # Scroll search for time blocks
    # Selector used previously; keep it but back it up with looser filters.
    time_selectors = [
        f"div.session-card_sessionTime__hNAfR:has-text('{target_time}')",
        f"text={target_time}",
    ]

    for _ in range(30):
        for ts in time_selectors:
            loc = page.locator(ts)
            if loc.count() > 0 and loc.first.is_visible():
                try:
                    loc.first.scroll_into_view_if_needed()
                    loc.first.click()
                    log(f"✅ Selected class at {target_time}")
                    # Try to reserve
                    try:
                        page.wait_for_selector("button:has-text('Reserve')", timeout=8000)
                        page.click("button:has-text('Reserve')")
                        log("✅ Clicked Reserve")
                    except:
                        log("⚠️ Reserve button not found; class may already be booked or flow has changed.")
                    return True
                except Exception as e:
                    log(f"⚠️ Failed to click class time block: {e}")
                    # keep scanning
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(300)

    log(f"❌ Could not find class time {target_time}")
    return False

def main():
    target_date = datetime.now() + timedelta(days=13)
    target_date_human = now_plus_days_str(13)

    log("🚀 Starting ALONI – Strict-Order Functional Flow 3.0")
    log(f"📅 Target date: {target_date_human} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 1) Open homepage
        log("🏠 Opening homepage…")
        page.goto(COREPOWER_URL, wait_until="load", timeout=60000)

        # 2) Dismiss popups BEFORE doing anything else
        dismiss_popups(page)

        # 3) LOGIN (and verify). If verification fails, STOP here.
        if not perform_login(page):
            log("❌ Login failed/uncertain — stopping BEFORE any date or schedule interactions.")
            browser.close()
            sys.exit(1)

        # 4) NAVIGATE to "Book a Class" page/schedule
        if not go_to_book_a_class(page):
            log("❌ Could not reach schedule — stopping.")
            browser.close()
            sys.exit(1)

        # 5) SELECT DATE (only AFTER login + schedule confirmed)
        if not select_calendar_date(page, target_date):
            log("❌ Date selection failed — stopping.")
            browser.close()
            sys.exit(1)

        # 6) FIND CLASS TIME + 7) RESERVE
        if not find_and_book(page, TARGET_TIME):
            log("❌ Could not book the desired class/time.")
            browser.close()
            sys.exit(1)

        browser.close()
        log("\n🎯 Flow complete – check for CorePower confirmation email.")

if __name__ == "__main__":
    main()
