#!/usr/bin/env python3
# scripts/book_class_verified_functional.py
#
# Purpose: End-to-end class booking flow that strictly opens the PROFILE ICON menu,
#          signs in, navigates to the schedules page, picks the date 13 days out,
#          and clicks the 6:15 pm Yoga Sculpt @ Flatiron BOOK button.
#
# Key fixes vs. earlier regressions:
#   • Never uses the "Book a class" CTA for auth; only the PROFILE ICON menu.
#   • Ensures the Sign In modal is OPEN and INTERACTIVE before filling.
#   • Repeatedly closes any modal/backdrop intercepting pointer events (e.g., signup modal).
#   • Uses the top-nav "Book" link to reach schedules (avoids CTA pop/auth modals).
#   • Waits for overlays to detach before any critical click.
#
# Env:
#   COREPOWER_EMAIL, COREPOWER_PASSWORD  -> required
#   HEADLESS=0 (optional)                -> run headed locally
#   DEBUG=1   (optional)                 -> dump HTML alongside screenshots
#
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
import json
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

COREPOWER_URL = "https://www.corepoweryoga.com/"
EMAIL = os.getenv("COREPOWER_EMAIL", "").strip()
PASSWORD = os.getenv("COREPOWER_PASSWORD", "").strip()
HEADLESS = os.getenv("HEADLESS", "1") != "0"
DEBUG = os.getenv("DEBUG", "0") == "1"

# CI artifact paths (match your workflow uploader)
TRACE_PATH = Path("trace.zip")
SCREENSHOTS_DIR = Path("screenshots")
VIDEOS_DIR = Path("videos")
for d in (SCREENSHOTS_DIR, VIDEOS_DIR):
    d.mkdir(parents=True, exist_ok=True)

if not EMAIL or not PASSWORD:
    print("❌ Set COREPOWER_EMAIL and COREPOWER_PASSWORD environment variables.")
    sys.exit(1)

# ------------------------------ Utilities ------------------------------

def shot(page, name: str):
    try:
        f = SCREENSHOTS_DIR / f"{name}.png"
        page.screenshot(path=str(f), full_page=True)
        print(f"📸 {f}")
    except Exception as e:
        print(f"⚠️ screenshot failed: {e}")

def dump_dom(page, name: str):
    if not DEBUG:
        return
    try:
        f = SCREENSHOTS_DIR / f"{name}.html"
        f.write_text(page.content(), encoding="utf-8")
        print(f"📝 {f}")
    except Exception as e:
        print(f"⚠️ dom dump failed: {e}")

def wait_visible(page, selector, timeout=20000):
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    return page.locator(selector)

def maybe_click(page, selector, timeout=2000):
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        page.click(selector, timeout=timeout)
        return True
    except PWTimeout:
        return False

def overlays_present(page):
    # Common CPY modals/backdrops that intercept clicks
    # - Role/dialog modals
    # - .cpy-modal.modal.show
    # - generic .modal.show
    # - Backdrops
    selectors = [
        "div[role='dialog'].modal.show",
        ".cpy-modal.modal.show",
        ".modal.show",
        ".modal-backdrop.show",
        "[aria-modal='true']",
    ]
    for sel in selectors:
        if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
            return True
    return False

def close_overlays(page, attempts=6):
    # Aggressively close any modal/backdrop that steals clicks
    closer_selectors = [
        "button:has-text('Close')",
        "button[aria-label*='close' i]",
        "button:has(img[alt='Close icon'])",
        "button:has-text('Got it')",
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
    ]
    for i in range(attempts):
        closed_any = False
        for sel in closer_selectors:
            if maybe_click(page, sel, timeout=500):
                closed_any = True
        # ESC often dismisses
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(150)
        if not overlays_present(page):
            return True
        # Try clicking backdrop to close
        try:
            page.locator(".modal-backdrop.show, .cpy-modal.modal.show, .modal.show").first.click(force=True)
            page.wait_for_timeout(150)
            if not overlays_present(page):
                return True
        except Exception:
            pass
        if closed_any:
            continue
    return not overlays_present(page)

def header_profile_candidates():
    # Strictly exclude 'book-a-class'
    return [
        "button[data-position='profile']",
        "button[data-position='profile.menu']",
        "button[data-position='profile-icon']",
        "header button[data-position^='profile.']:not([data-position='profile.1-sign-in'])",
        "button[aria-label*='profile' i]",
        "button[aria-label*='account' i]",
        "header button:has(svg[aria-label*='profile' i])",
        "header .cursor-pointer img[alt*='profile' i]",
        "header .cursor-pointer img[title*='profile' i]",
        "header [role='button'][data-position^='profile.']",
        # Some builds render the profile icon as a plain button with no attributes—fallback to last header button
        "header button:last-of-type",
    ]

def open_profile_menu(page):
    """
    Open the profile dropdown ONLY via the profile icon (never the CTA).
    Success when: button[data-position='profile.1-sign-in'] is visible.
    """
    sign_in_btn = "button[data-position='profile.1-sign-in']"

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_load_state("networkidle")
    close_overlays(page)

    # Quick exit if Sign in already visible
    try:
        if page.locator(sign_in_btn).first.is_visible():
            return
    except PWError:
        pass

    for attempt in range(1, 5):
        print(f"👤 Open profile menu (attempt {attempt}/4)…")
        for sel in header_profile_candidates():
            # Skip any obvious CTA
            if "book-a-class" in sel:
                continue
            try:
                # Scroll into view & js click to bypass hit-test quirks
                btn = page.locator(sel).first
                if btn.count() == 0 or not btn.is_visible():
                    continue
                page.evaluate("(el)=>el.scrollIntoView({block:'center'})", btn)
                page.wait_for_timeout(50)
                # Prefer a normal click; if blocked, fallback to JS click
                try:
                    btn.click(timeout=1200)
                except Exception:
                    page.evaluate("(el)=>el.click()", btn)
                page.wait_for_timeout(250)
                close_overlays(page)
                page.wait_for_timeout(150)
                if page.locator(sign_in_btn).first.is_visible():
                    return
            except Exception:
                continue

        # One guarded sweep across header buttons excluding the CTA
        try:
            hb = page.locator("header button, header [role='button']")
            for i in range(min(8, hb.count())):
                el = hb.nth(i)
                dp = (el.get_attribute("data-position") or "").strip()
                if dp == "book-a-class":
                    continue
                try:
                    el.click(timeout=800)
                except Exception:
                    page.evaluate("(el)=>el.click()", el)
                page.wait_for_timeout(200)
                close_overlays(page)
                if page.locator(sign_in_btn).first.is_visible():
                    return
        except PWError:
            pass

    # Diagnostics
    try:
        hdr = page.evaluate("""
        () => Array.from(document.querySelectorAll('header button, header [role="button"]')).map(el => ({
          text:(el.innerText||'').trim(),
          aria:el.getAttribute('aria-label'),
          pos:el.getAttribute('data-position'),
          cls:el.className
        }))
        """)
        (SCREENSHOTS_DIR / "header_buttons.json").write_text(json.dumps(hdr, indent=2), encoding="utf-8")
        print("🧭 wrote screenshots/header_buttons.json")
    except Exception:
        pass

    shot(page, "failed_open_profile_menu")
    dump_dom(page, "failed_open_profile_menu")
    raise PWTimeout("Profile menu never revealed the Sign In button.")

def ensure_signin_modal(page):
    """
    Ensure Sign In modal is open and interactive.
    """
    sign_in_btn = "button[data-position='profile.1-sign-in']"
    modal_form = "form#sign-in-form"
    # If modal not visible yet, click Sign in
    try:
        if page.locator(modal_form).count() == 0 or not page.locator(modal_form).first.is_visible():
            wait_visible(page, sign_in_btn, timeout=8000).click()
    except PWTimeout:
        # Some builds render Sign in as hidden until menu toggled again
        open_profile_menu(page)
        wait_visible(page, sign_in_btn, timeout=8000).click()
    # Wait for the modal to be fully active
    wait_visible(page, modal_form, timeout=12000)

def login(page):
    print("🔐 Opening profile menu…")
    open_profile_menu(page)

    print("🔑 Ensuring Sign In modal…")
    ensure_signin_modal(page)

    print("✉️ Filling credentials…")
    page.fill("input[name='username']", EMAIL)
    page.fill("input[name='password']", PASSWORD)

    # Submit
    try:
        page.click("form#sign-in-form button.btn.btn-primary:has(.btn-text:has-text('Sign In'))", timeout=5000)
    except Exception:
        # Fallback: press Enter
        page.keyboard.press("Enter")

    # Wait for successful auth & nav to hydrate
    page.wait_for_load_state("networkidle")
    # The presence of the top nav "Book" is our success signal
    wait_visible(page, "span.nav-link a[data-position='1-book'][href='/yoga-schedules']", timeout=35000)

    # Make sure NO modal remains
    close_overlays(page)
    # Wait until any modal/backdrop is detached
    page.wait_for_selector(".modal.show, .cpy-modal.modal.show, .modal-backdrop.show", state="detached", timeout=15000)

def go_to_schedules(page):
    print("📖 Opening schedules via top nav Book…")
    page.click("span.nav-link a[data-position='1-book'][href='/yoga-schedules']", timeout=10000)
    page.wait_for_load_state("networkidle")
    close_overlays(page)

def weekday_letter(dt: datetime) -> str:
    return ["M","T","W","T","F","S","S"][dt.weekday()]

def month_abbrev(dt: datetime) -> str:
    return dt.strftime("%b")

def pick_date(page, target_dt: datetime):
    print(f"🗓 Picking {target_dt.strftime('%a %b %d')} (13 days out)…")
    wait_visible(page, ".calendar-container", timeout=25000)

    day_letter = weekday_letter(target_dt)
    day_of_month = str(target_dt.day)
    crossing = (target_dt.month != datetime.now().month)

    base = page.locator(
        ".cal-item-container:has(.cal-day:has-text('%s')):has(.cal-date:has-text('^%s$'))"
        % (day_letter, day_of_month)
    )
    if crossing:
        base = base.filter(has=page.locator(".next-month", has_text=month_abbrev(target_dt)))

    base.first.scroll_into_view_if_needed()
    base.first.click()
    page.wait_for_load_state("networkidle")
    close_overlays(page)

def click_sculpt_615_flatiron(page):
    print("🔎 Locating 6:15 pm • Yoga Sculpt • Flatiron…")
    wait_visible(page, ".session-row-view", timeout=30000)

    rows = page.locator(".session-row-view:has(.session-card_sessionTime__hNAfR:has-text('6:15 pm'))")
    rows = rows.filter(has=page.locator(":scope .session-card_sessionStudio__yRE6h", has_text="Flatiron"))
    rows = rows.filter(has=page.locator("a.session-title-link", has_text="Yoga Sculpt"))

    book = rows.locator(":scope .session-card_sessionCardBtn__FQT3Z:has-text('BOOK')")
    if book.count() == 0:
        book = rows.locator(":scope :text('BOOK')")

    book.first.scroll_into_view_if_needed()
    # Ensure no overlay intercepts
    close_overlays(page)
    page.wait_for_timeout(150)

    # Click with fallback to force
    try:
        book.first.click(timeout=8000)
    except Exception:
        book.first.click(force=True, timeout=8000)

    page.wait_for_load_state("networkidle")
    # Optional: handle confirmation
    done_btn = page.locator("button.cpy-button:has(span.button-text:has-text(\"I'm done\"))")
    try:
        if done_btn.first.is_visible():
            done_btn.first.click()
            print("✅ Closed confirmation popup.")
    except Exception:
        pass

# ------------------------------ Main ------------------------------

def main():
    print("🚀 Starting ALONI 2.9.3 – Stable Profile→Login→Book Flow")
    target_dt = datetime.now() + timedelta(days=13)
    weekday = target_dt.strftime("%A")
    if weekday not in ["Monday", "Tuesday", "Wednesday"]:
        print(f"⏸ Skipping — target date ({target_dt.strftime('%a %b %d')}) is not Mon/Tue/Wed.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 900},
            record_video_dir=str(VIDEOS_DIR)
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        try:
            print("🏠 Opening homepage…")
            page.goto(COREPOWER_URL, timeout=70000, wait_until="domcontentloaded")
            close_overlays(page)

            login(page)
            go_to_schedules(page)
            pick_date(page, target_dt)
            click_sculpt_615_flatiron(page)

            print(f"🌐 URL: {page.url}")
            print("🏁 Flow complete.")
        except Exception as e:
            print(f"💥 Failure: {e}")
            shot(page, "failure_state")
            dump_dom(page, "failure_state")
            raise
        finally:
            try:
                context.tracing.stop(path=str(TRACE_PATH))
                print(f"🧪 Trace saved: {TRACE_PATH}")
            except Exception as te:
                print(f"⚠️ Trace save failed: {te}")
            context.close()
            browser.close()

if __name__ == "__main__":
    try:
        main()
    except PWTimeout as e:
        print(f"⏱️ Timeout: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"💥 Error: {e}")
        sys.exit(3)
