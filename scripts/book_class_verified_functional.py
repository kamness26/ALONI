#!/usr/bin/env python3
# book_yoga.py
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL", "").strip()
PASSWORD = os.getenv("COREPOWER_PASSWORD", "").strip()
HEADLESS = os.getenv("HEADLESS", "1") != "0"
DEBUG = os.getenv("DEBUG", "0") == "1"
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

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

def _screenshot(page, name: str):
    try:
        file = ARTIFACTS_DIR / f"{name}.png"
        page.screenshot(path=str(file), full_page=True)
        print(f"📸 Saved screenshot: {file}")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")

def _dump_dom(page, name: str):
    if not DEBUG:
        return
    try:
        html = page.content()
        file = ARTIFACTS_DIR / f"{name}.html"
        file.write_text(html, encoding="utf-8")
        print(f"📝 Saved DOM: {file}")
    except Exception as e:
        print(f"⚠️ DOM dump failed: {e}")

# --------------------- Stable Steps ---------------------

def open_profile_menu(page):
    """
    Open the profile menu ONLY via the profile icon (NOT the 'Book a class' CTA).
    Success condition: 'button[data-position="profile.1-sign-in"]' becomes visible.
    Uses multiple resilient candidates and a guarded header sweep that EXCLUDES 'book-a-class'.
    """
    sign_in_btn = "button[data-position='profile.1-sign-in']"

    # Sometimes the sign-in button is already visible (SSR/rehydration timing).
    try:
        if page.locator(sign_in_btn).first.is_visible():
            return
    except PWError:
        pass

    # Known/likely profile icon candidates (do not include book-a-class).
    candidates = [
        "button[data-position='profile']",
        "button[data-position='profile.menu']",
        "button[data-position='profile-icon']",
        "header button[data-position^='profile.']:not([data-position='profile.1-sign-in'])",
        "button[aria-label*='profile' i]",
        "button[aria-label*='account' i]",
        "header button:has(svg[aria-label*='profile' i])",
        "header .cursor-pointer img[alt*='profile' i]",
        "header .cursor-pointer img[title*='profile' i]",
        # Role-based fallbacks
        "header [role='button'][data-position^='profile.']",
    ]

    # Give the header time to hydrate
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_load_state("networkidle")

    for sel in candidates:
        if _maybe_click(page, sel, timeout=2500):
            try:
                page.wait_for_selector(sign_in_btn, state="visible", timeout=4000)
                return
            except PWTimeout:
                # Try next candidate
                pass

    # Guarded sweep: try header buttons except the known CTA.
    header_buttons = page.locator("header button")
    count = header_buttons.count()
    tried = 0
    for i in range(count):
        btn = header_buttons.nth(i)
        try:
            dp = btn.get_attribute("data-position") or ""
            if dp.strip() == "book-a-class":  # explicitly skip Book a class
                continue
            # Skip obvious menu toggles if they fail once (we'll try a few)
            btn.focus()
            btn.click()
            tried += 1
            try:
                page.wait_for_selector(sign_in_btn, state="visible", timeout=1500)
                return
            except PWTimeout:
                pass
            if tried >= 6:
                break
        except PWError:
            continue

    _screenshot(page, "failed_open_profile_menu")
    _dump_dom(page, "failed_open_profile_menu")
    raise PWTimeout("Could not open profile menu via profile icon; 'Sign in' button never appeared.")

def login(page):
    print("🔐 Open profile menu via profile icon…")
    open_profile_menu(page)

    print("🔑 Click Sign in…")
    _wait_and_click(page, "button[data-position='profile.1-sign-in']")

    print("🪟 Wait for Sign In modal…")
    page.wait_for_selector("form#sign-in-form", timeout=20000)

    print("✉️  Fill email…")
    _wait_and_fill(page, "input#username42[name='username'][type='text']", EMAIL)

    print("🔒 Fill password…")
    _wait_and_fill(page, "input#password[name='password'][type='password']", PASSWORD)

    print("➡️  Submit Sign In…")
    _wait_and_click(page, "form#sign-in-form button.btn.btn-primary:has(.btn-text:has-text('Sign In'))")

    print("⏳ Wait for nav to hydrate…")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("span.nav-link a[data-position='1-book'][href='/yoga-schedules']", timeout=35000)

def go_to_book_page(page):
    print("📖 Open Book page…")
    _wait_and_click(page, "span.nav-link a[data-position='1-book'][href='/yoga-schedules']")
    page.wait_for_load_state("networkidle")

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
    candidate.first.scroll_into_view_if_needed()
    candidate.first.click()
    page.wait_for_load_state("networkidle")

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
    page.wait_for_load_state("networkidle")

# --------------------- Main ---------------------

def main():
    target_dt = datetime.now() + timedelta(days=13)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},  # desktop layout to keep header consistent
            device_scale_factor=1.0,                  # deterministic rendering
            java_script_enabled=True
        )

        # Enable tracing to debug flakiness in CI
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        try:
            print("🏁 Opening homepage…")
            page.goto(COREPOWER_URL, wait_until="domcontentloaded", timeout=60000)

            # Dismiss common banners/popups if present (best-effort)
            _maybe_click(page, "button:has-text('Accept')", timeout=2000)
            _maybe_click(page, "button:has-text('I Accept')", timeout=2000)
            _maybe_click(page, "[aria-label*='close' i]", timeout=1000)
            _maybe_click(page, "button:has-text('Close')", timeout=1000)

            login(page)
            go_to_book_page(page)

            print(f"🗓️  Pick date {target_dt.strftime('%a %b %d')} (13 days out)…")
            click_calendar_date(page, target_dt)

            print("🔎 Locate 6:15 pm Yoga Sculpt @ Flatiron…")
            click_sculpt_615_flatiron(page)

            # Optional “I’m done”
            if _maybe_click(page, "button.cpy-button.cpy-button-md.cpy-button-outline:has(span.button-text:has-text(\"I'm done\"))", timeout=2000):
                print("✅ Clicked “I’m done.”")

            print(f"🌐 Current URL: {page.url}")
            print("🎉 Completed flow through BOOK click.")

        except Exception as e:
            print(f"💥 Failure: {e}")
            _screenshot(page, "failure_final_state")
            _dump_dom(page, "failure_final_state")
            raise
        finally:
            trace_path = ARTIFACTS_DIR / "trace.zip"
            try:
                context.tracing.stop(path=str(trace_path))
                print(f"🧪 Saved Playwright trace: {trace_path}")
            except Exception as te:
                print(f"⚠️ Trace save failed: {te}")
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
