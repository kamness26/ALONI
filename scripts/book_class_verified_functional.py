#!/usr/bin/env python3
# scripts/book_class_verified_functional.py
# PYTHON ≥3.10

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, UTC

from playwright.sync_api import Playwright, sync_playwright, Page, BrowserContext

# ----------------------------
# Basic logging helpers
# ----------------------------
def log(msg: str) -> None:
    print(msg, flush=True)

def ts_safe() -> str:
    # Filesystem-safe UTC timestamp (no colons)
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

# ----------------------------
# Environment / config
# ----------------------------
HOMEPAGE_URL = "https://www.corepoweryoga.com/"

EMAIL_ENV = "COREPOWER_EMAIL"
PASS_ENV  = "COREPOWER_PASSWORD"

SCREENSHOTS_DIR = "screenshots"
VIDEOS_DIR      = "videos"
TRACE_ZIP       = "trace.zip"

DEFAULT_TIMEOUT = 15_000

# ----------------------------
# Popups & overlays
# ----------------------------
def dismiss_popups(page: Page, phase: str = "") -> None:
    """Best-effort removal of visible modals/overlays/blocks."""
    try:
        # Close known dialog with Close button (e.g., promos)
        for sel in [
            "div[role='dialog'] button:has-text('Close')",
            "div[role='dialog'] [aria-label='Close']",
            "[aria-label='Close']",
            "[data-testid='close']",
            ".modal [data-dismiss='modal']",
            "[data-position='close']",
        ]:
            btns = page.locator(sel)
            if btns.count() > 0:
                try:
                    btns.first.click(timeout=1000, trial=True)
                    btns.first.click(timeout=1000)
                    log(f"💨 [{phase}] Removed modal via {sel}")
                    break
                except Exception:
                    pass
    except Exception:
        pass

    # ESC to dismiss focus-trap overlays
    for _ in range(2):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    # Nuke common overlay/backdrop nodes
    try:
        page.evaluate(
            """
            (selectors) => {
              for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => el.remove());
              }
            }
            """,
            [
                ".modal-backdrop",
                "[aria-modal='true']",
                ".overlay, .Overlay",
                ".cookie-banner, .cookie-consent",
            ],
        )
    except Exception:
        pass

# ----------------------------
# Safe click utility
# ----------------------------
def safe_click(page: Page, selector: str, label: str, timeout=DEFAULT_TIMEOUT) -> bool:
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout)
        loc.scroll_into_view_if_needed(timeout=2000)
        dismiss_popups(page, f"pre-click-{label}")
        try:
            loc.click(timeout=5000)
            log(f"✅ Clicked: {label} ({selector})")
            return True
        except Exception:
            dismiss_popups(page, f"overlay-{label}")
            handle = loc.element_handle()
            if handle:
                page.evaluate("(el)=>el.click()", handle)
                log(f"✅ JS-clicked: {label} ({selector})")
                return True
            raise
    except Exception as e:
        log(f"… not clickable yet: {label} ({selector}) :: {e}")
        return False

# ----------------------------
# Header helpers (responsive)
# ----------------------------
HAMBURGER_CANDIDATES = [
    "button.navbar-toggler",
    "button[aria-label='Menu']",
    "button[aria-label='Open Menu']",
    "button[aria-haspopup='menu']",
    "button[data-position='hamburger']",
    "button:has(svg[aria-label='Menu'])",
]

PROFILE_CANDIDATES = [
    "[data-position='profile']",
    "button[data-position='profile']",
    "a[data-position='profile']",
    "img[alt='Profile Icon']",
    "button:has(svg[aria-label='Profile'])",
    "a[href*='profile']:not([href='#'])",
    "button[aria-label='Profile']",
    "button:has-text('Account')",
    "a:has-text('Account')",
]

SIGNIN_CANDIDATES = [
    "button:has-text('Sign in')",
    "a:has-text('Sign in')",
    "button:has-text('Sign In')",
    "a:has-text('Sign In')",
    "[data-position='sign-in']",
    "a[href*='sign-in']",
    "a[href*='signin']",
    "a[href*='login']",
]

EMAIL_INPUT_CANDIDATES = [
    "input[type='email']",
    "input[name='email']",
    "input[id*='email']",
    "input[autocomplete='email']",
]

PASSWORD_INPUT_CANDIDATES = [
    "input[type='password']",
    "input[name='password']",
    "input[id*='password']",
    "input[autocomplete='current-password']",
]

SUBMIT_CANDIDATES = [
    "button[type='submit']",
    "button:has-text('Sign in')",
    "button:has-text('Log in')",
    "button:has-text('Log In')",
]

def ensure_header_ready(page: Page) -> None:
    # Let hydration/layout finish to avoid “hidden” header controls
    try:
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(500)
    try:
        page.evaluate("() => window.scrollTo({top: 0, behavior: 'instant'})")
    except Exception:
        pass
    dismiss_popups(page, "header-ready")

def try_open_hamburger(page: Page) -> bool:
    for sel in HAMBURGER_CANDIDATES:
        if safe_click(page, sel, "Hamburger / Menu"):
            # tiny settle
            page.wait_for_timeout(300)
            return True
    return False

# ----------------------------
# STRICT LOGIN ORDER (with responsive fallbacks)
#   1) Try visible Profile
#   2) If not visible, open hamburger then retry
#   3) Click Sign in within that menu
#   4) Enter credentials
# ----------------------------
def strict_open_account_menu(page: Page) -> None:
    log("\n🔐 LOGIN PHASE (strict order)")
    ensure_header_ready(page)

    # 1) Try profile straight away
    for sel in PROFILE_CANDIDATES:
        if safe_click(page, sel, "Profile icon/menu", timeout=8000):
            return

    # 2) If hidden, open hamburger/off-canvas and retry
    if try_open_hamburger(page):
        for sel in PROFILE_CANDIDATES + SIGNIN_CANDIDATES:
            if safe_click(page, sel, "Profile or Sign in (mobile menu)", timeout=6000):
                return

    # 3) As an extra fallback, try Sign in directly without profile
    for sel in SIGNIN_CANDIDATES:
        if safe_click(page, sel, "Sign in (direct)"):
            return

    raise RuntimeError("Profile/Sign in entrypoint not found (header likely hidden or variant changed).")

def click_sign_in(page: Page) -> None:
    # If we didn’t already hit Sign in via strict_open_account_menu, try here.
    dismiss_popups(page, "pre-sign-in")
    for sel in SIGNIN_CANDIDATES:
        if safe_click(page, sel, "Sign in"):
            return
    # retry after tiny settle
    page.wait_for_timeout(400)
    for sel in SIGNIN_CANDIDATES:
        if safe_click(page, sel, "Sign in (retry)"):
            return
    # If we are already on the form, that’s fine; otherwise fail
    if page.locator("form").count() == 0 and page.locator("input[type='email'], input[type='password']").count() == 0:
        raise RuntimeError("Could not click 'Sign in' after opening the profile/menu.")

def perform_login(page: Page, email: str, password: str) -> None:
    dismiss_popups(page, "pre-credentials")

    email_field = None
    pwd_field = None

    for sel in EMAIL_INPUT_CANDIDATES:
        loc = page.locator(sel)
        if loc.count() > 0:
            email_field = loc.first
            break
    for sel in PASSWORD_INPUT_CANDIDATES:
        loc = page.locator(sel)
        if loc.count() > 0:
            pwd_field = loc.first
            break

    if not email_field:
        raise RuntimeError("Email input not found on sign-in form.")
    if not pwd_field:
        raise RuntimeError("Password input not found on sign-in form.")

    email_field.fill(email, timeout=DEFAULT_TIMEOUT)
    pwd_field.fill(password, timeout=DEFAULT_TIMEOUT)

    # Submit
    for sel in SUBMIT_CANDIDATES:
        if safe_click(page, sel, "Submit credentials"):
            break
    else:
        pwd_field.press("Enter")

    page.wait_for_timeout(1000)
    log("🔒 Credentials submitted.")

# ----------------------------
# Navigation: Book a Class (exact + fallbacks)
# ----------------------------
def go_to_book_a_class(page: Page) -> None:
    log("\n📍 NAVIGATION: Book a Class")
    dismiss_popups(page, "pre-nav")

    sel_exact = "button[data-position='book-a-class']"
    fallbacks = [
        "button.btn.btn-primary:has-text('Book a class')",
        "button:has-text('Book a class')",
        "button:has-text('Book a Class')",
        "a[href*='book-a-class']",
        "a:has-text('Book a class')",
        "a:has-text('Book a Class')",
    ]

    if safe_click(page, sel_exact, "Book a class (exact)"):
        return

    # If header is collapsed, open it then retry exact
    if try_open_hamburger(page) and safe_click(page, sel_exact, "Book a class (exact, after menu)"):
        return

    for i, fb in enumerate(fallbacks):
        if safe_click(page, fb, f"Book a class fallback #{i+1}"):
            return

    try:
        positions = page.eval_on_selector_all(
            "button[data-position]",
            "els => els.map(e => e.getAttribute('data-position'))"
        )
        log(f"🔎 Buttons with data-position on page: {positions}")
    except Exception:
        pass

    raise RuntimeError("Could not navigate to 'Book a Class'.")

# ----------------------------
# Example: pick a date (T+13 days)
# ----------------------------
def pick_target_date(page: Page, days_ahead: int = 13) -> None:
    target = datetime.now(UTC).date() + timedelta(days=days_ahead)
    label = target.strftime("%A, %b %d")
    log(f"🗓️  Selecting target date: {label}")

    dismiss_popups(page, "pre-date-pick")

    candidates = [
        f"button[aria-label*='{label}']",
        f"button:has-text('{label}')",
        f"[role='button']:has-text('{label}')",
    ]
    for sel in candidates:
        if safe_click(page, sel, f"date {label}"):
            return

    for _ in range(3):
        if safe_click(page, "button[aria-label='Next']", "calendar next"):
            page.wait_for_timeout(300)
            if safe_click(page, candidates[0], f"date {label} (post-next)"):
                return

    log(f"⚠️ Could not positively select date {label}; continuing (non-fatal).")

# ----------------------------
# Main run
# ----------------------------
def run(playwright: Playwright) -> int:
    email = os.getenv(EMAIL_ENV, "").strip()
    password = os.getenv(PASS_ENV, "").strip()
    if not email or not password:
        log(f"❌ Missing credentials. Ensure {EMAIL_ENV} and {PASS_ENV} are set.")
        return 1

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)

    log("🚀 Starting ALONI – Strict-Order Functional Flow 3.2")
    target = datetime.now(UTC).date() + timedelta(days=13)
    log(f"📅 Target date: {target.strftime('%A, %b %d')} (13 days from today)")

    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    context: BrowserContext = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=VIDEOS_DIR,
    )

    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page: Page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)

    try:
        log("🏠 Opening homepage…")
        page.goto(HOMEPAGE_URL, wait_until="domcontentloaded", timeout=45_000)
        dismiss_popups(page, "on-load")

        # STRICT LOGIN ORDER (with hamburger/mobile fallbacks)
        strict_open_account_menu(page)
        click_sign_in(page)  # no-op if we already clicked it above
        perform_login(page, email, password)

        # Navigate explicitly to Book a Class
        go_to_book_a_class(page)

        # (Optional) date selection to prove nav works
        pick_target_date(page, days_ahead=13)

        log("🎉 Flow completed through date selection.")
        rc = 0

    except Exception as e:
        log(f"❌ Fatal error: {e}")
        try:
            fname = f"{SCREENSHOTS_DIR}/failure-{ts_safe()}.png"
            page.screenshot(path=fname, full_page=True)
            log(f"📸 Saved failure screenshot: {fname}")
        except Exception:
            pass

        traceback.print_exc()
        rc = 1

    finally:
        try:
            context.tracing.stop(path=TRACE_ZIP)
            log(f"🧵 Trace exported: {TRACE_ZIP}")
        except Exception:
            pass
        try:
            context.close()
            browser.close()
        except Exception:
            pass

    return rc

def main() -> None:
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)

    with sync_playwright() as playwright:
        code = run(playwright)
        sys.exit(code)

if __name__ == "__main__":
    main()
