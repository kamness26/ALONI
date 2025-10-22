#!/usr/bin/env python3
# book_yoga.py
import os
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL", "").strip()
PASSWORD = os.getenv("COREPOWER_PASSWORD", "").strip()

if not EMAIL or not PASSWORD:
    print("❌ Set COREPOWER_EMAIL and COREPOWER_PASSWORD environment variables.")
    sys.exit(1)

# --------------------- Helpers ---------------------

def _wait_and_click(page, selector, *, timeout=15000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.click(selector, timeout=timeout)

def _wait_and_fill(page, selector, text, *, timeout=15000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.fill(selector, text, timeout=timeout)

def _maybe_click(page, selector, *, timeout=3000):
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        page.click(selector, timeout=timeout)
        return True
    except PWTimeout:
        return False

def _weekday_letter(dt: datetime) -> str:
    # Mon=0..Sun=6 -> letters on site: M T W T F S S
    return ["M","T","W","T","F","S","S"][dt.weekday()]

def _month_abbrev(dt: datetime) -> str:
    return dt.strftime("%b")

def open_profile_menu(page):
    """
    Open the profile menu ONLY via the profile icon (NOT the 'Book a class' CTA).
    We try a set of robust candidates and confirm success by the appearance of the
    Sign In button with data-position='profile.1-sign-in'.
    """
    page.wait_for_selector("header, body", timeout=30000)

    sign_in_btn = "button[data-position='profile.1-sign-in']"

    # If it's already visible (some pages render it immediately), we're done.
    if page.locator(sign_in_btn).first.is_visible():
        return

    # Candidate selectors for the profile icon (explicitly excluding book-a-class).
    candidates = [
        # Common explicit data-positions seen across builds
        "button[data-position='profile']",
        "button[data-position='profile.menu']",
        "button[data-position='profile-icon']",
        # Any header button whose data-position starts with 'profile.' but is NOT the sign-in button
        "header button[data-position^='profile.']:not([data-position='profile.1-sign-in'])",
        # Generic aria-labels
        "button[aria-label*='profile' i]",
        "button[aria-label*='account' i]",
        # SVG/icon button inside header with a likely profile label
        "header button:has(svg[aria-label*='profile' i])",
        # Fallback: clickable element with user avatar image alt/title hints
        "header .cursor-pointer img[alt*='profile' i]",
        "header .cursor-pointer img[title*='profile' i]",
    ]

    for sel in candidates:
        if _maybe_click(page, sel, timeout=2000):
            try:
                page.wait_for_selector(sign_in_btn, state="visible", timeout=4000)
                return
            except PWTimeout:
                # Not opened yet; try the next candidate
                pass

    # As a last resort, try focusing header and pressing Enter/Space on likely icons
    # (No-op if nothing matches; keeps behavior deterministic in CI)
    header_icons = page.locator("header button")
    count = min(6, header_icons.count())
    for i in range(count):
        btn = header_icons.nth(i)
        # Skip if it's obviously the Book-a-class CTA
        if btn.get_attribute("data-position") == "book-a-class":
            continue
        btn.focus()
        page.keyboard.press("Enter")
        try:
            page.wait_for_selector(sign_in_btn, state="visible", timeout=2000)
            return
        except PWTimeout:
            pass

    raise PWTimeout("Could not open profile menu via profile icon; 'Sign in' button never appeared.")

def click_calendar_date(page, target_dt: datetime):
    """
    Click a calendar tile that matches weekday letter + day-of-month.
    If crossing into next month, prefer tiles showing .next-month == target abbrev.
    """
    page.wait_for_selector(".calendar-container", state="visible", timeout=25000)

    day_letter = _weekday_letter(target_dt)
    day_of_month = str(target_dt.day)
    target_mon = _month_abbrev(target_dt)
    crossing_month = (target_dt.month != datetime.now().month)

    base = page.locator(
        ".cal-item-container:has(.cal-day:has-text('%s')):has(.cal-date:has-text('^%s$'))"
        % (day_letter, day_of_month)
    )

    candidate = base
    if crossing_month:
        marked = base.filter(has=page.locator(".next-month", has_text=target_mon))
        if marked.count() > 0:
            candidate = marked

    candidate.first.wait_for(state="visible", timeout=15000)
    candidate.first.click()

def click_sculpt_615_flatiron(page):
    """
    Locate the session row for 6:15 pm, Yoga Sculpt, Flatiron, and click BOOK.
    Matches both mobile and desktop layouts from provided markup.
    """
    page.wait_for_selector(".session-row-view", timeout=30000)

    rows = page.locator(".session-row-view:has(.session-card_sessionTime__hNAfR:has-text('6:15 pm'))")
    rows = rows.filter(has=page.locator(":scope .session-card_sessionStudio__yRE6h", has_text="Flatiron"))
    rows = rows.filter(has=page.locator("a.session-title-link", has_text="Yoga Sculpt"))

    # Desktop-first button target
    book_btn = rows.locator(":scope .session-card_sessionCardBtn__FQT3Z:has-text('BOOK')")
    if book_btn.count() == 0:
        # Fallback to any BOOK text within the row (mobile)
        book_btn = rows.locator(":scope :text('BOOK')")

    book_btn.first.wait_for(state="visible", timeout=15000)
    book_btn.first.scroll_into_view_if_needed()
    book_btn.first.click()

# --------------------- Main ---------------------

def main():
    target_dt = datetime.now() + timedelta(days=13)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        print("🏁 Opening homepage…")
        page.goto(COREPOWER_URL, wait_until="domcontentloaded", timeout=60000)

        # Dismiss common banners/popups if present (best-effort)
        _maybe_click(page, "button:has-text('Accept')", timeout=2000)
        _maybe_click(page, "button:has-text('I Accept')", timeout=2000)
        _maybe_click(page, "[aria-label*='close' i]", timeout=1000)
        _maybe_click(page, "button:has-text('Close')", timeout=1000)

        # STRICT: Use ONLY the profile icon to progress
        print("👤 Open profile menu via profile icon…")
        open_profile_menu(page)

        print("🔐 Click Sign in…")
        _wait_and_click(page, "button[data-position='profile.1-sign-in']")

        print("🪟 Wait for Sign In modal…")
        page.wait_for_selector("form#sign-in-form", timeout=20000)

        print("✉️  Fill email…")
        _wait_and_fill(page, "input#username42[name='username'][type='text']", EMAIL)

        print("🔑 Fill password…")
        _wait_and_fill(page, "input#password[name='password'][type='password']", PASSWORD)

        print("➡️  Submit Sign In…")
        _wait_and_click(page, "form#sign-in-form button.btn.btn-primary:has(.btn-text:has-text('Sign In'))")

        print("✅ Verify login by locating Book nav…")
        page.wait_for_selector("span.nav-link a[data-position='1-book'][href='/yoga-schedules']", timeout=35000)

        print("📖 Open Book page…")
        _wait_and_click(page, "span.nav-link a[data-position='1-book'][href='/yoga-schedules']")

        print(f"🗓️  Pick date {(datetime.now()+timedelta(days=13)).strftime('%a %b %d')} (13 days out)…")
        click_calendar_date(page, target_dt)

        print("🔎 Locate 6:15 pm Yoga Sculpt @ Flatiron…")
        click_sculpt_615_flatiron(page)

        # Optional “I’m done”
        if _maybe_click(page, "button.cpy-button.cpy-button-md.cpy-button-outline:has(span.button-text:has-text(\"I'm done\"))", timeout=2000):
            print("✅ Clicked “I’m done.”")

        print(f"🌐 Current URL: {page.url}")
        print("🎉 Completed flow through BOOK click.")

        context.close()
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except PWTimeout as e:
        print(f"⏱️ Timeout waiting for element: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        sys.exit(3)
