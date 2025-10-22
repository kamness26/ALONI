# scripts/book_class_verified_functional.py
#
# HARD ORDER GUARANTEE (no exceptions):
#   1) Open homepage
#   2) Click Profile icon
#   3) Click "Sign in" from the profile menu
#   4) Fill credentials INSIDE a real login form (requires password field)
#   5) Verify login
#   6) Navigate to Book a Class (route-first, then CTA fallback)
#   7) Select date (never before step 5)
#   8) Select class time and Reserve
#
# Notes:
# - Email-only promos (e.g., 30% off) are ignored/closed; we only fill
#   forms that include a PASSWORD input.
# - If any step fails, we export a Playwright trace + targeted screenshots
#   so CI always has artifacts.

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("COREPOWER_EMAIL", "").strip()
PASSWORD = os.getenv("COREPOWER_PASSWORD", "").strip()

BASE_URL = "https://www.corepoweryoga.com/"
TARGET_DAYS_AHEAD = 13       # adjust as needed
TARGET_TIME = "6:15 pm"      # adjust as needed

BOOK_PATHS = [
    "book-a-class",
    "classes/book",
    "schedule",
]

ARTIFACT_TRACE = "trace.zip"
ARTIFACT_SCREEN_DIR = Path("screenshots")
ARTIFACT_SCREEN_DIR.mkdir(exist_ok=True)

def log(msg: str):
    print(msg, flush=True)

def human_target_date(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%A, %b %d")

def on_fail_checkpoint(page, name: str):
    try:
        page.screenshot(path=str(ARTIFACT_SCREEN_DIR / f"{name}.png"), full_page=True)
    except:
        pass

def close_marketing_popups(page):
    """
    Close/ignore non-auth, marketing/survey/cookie dialogs — especially
    the 30% off promo that contains ONLY an email input (no password).
    We intentionally do NOT close the real login dialog/page.
    """
    candidates = [
        # Generic dialogs/banners
        "button:has-text('Close')",
        "button[aria-label*='close' i]",
        "[role='dialog'] button:has-text('Close')",
        "[data-testid*=close], [data-test*=close]",
        "[id*=close], [class*=close]",
        "button:has-text('No thanks')",
        "button:has-text('Maybe later')",

        # Cookie banners
        "button.cookie__accept",
        "button:has-text('Accept All')",
        "button:has-text('Accept all')",
    ]

    # If a dialog contains only email (no password), close it
    try:
        dialogs = page.locator("[role='dialog'], div[aria-modal='true']")
        for i in range(min(dialogs.count(), 6)):
            d = dialogs.nth(i)
            if not d.is_visible():
                continue
            has_email = d.locator("input[type='email'], input[name*='email' i]").count() > 0
            has_password = d.locator("input[type='password'], input[name='password'], input#password").count() > 0
            promo_keywords = d.locator("text=/30%|subscribe|newsletter|offer|promo/i").count() > 0
            if has_email and not has_password:
                # Close by common close controls inside the same dialog
                for sel in [
                    "button:has-text('Close')",
                    "button[aria-label*='close' i]",
                    "button:has-text('No thanks')",
                    "button:has-text('Maybe later')",
                ]:
                    if d.locator(sel).count() > 0:
                        try:
                            d.locator(sel).first.click(timeout=1500)
                            log("💨 Closed email-only promo dialog")
                            break
                else:
                    # brute: hide it to unblock clicks
                    try:
                        page.evaluate("el => el.style.display='none'", d.element_handle())
                        log("💨 Hid email-only promo dialog")
                    except:
                        pass
    except:
        pass

    # Generic best-effort closers
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=1000)
                page.wait_for_timeout(200)
                log(f"💨 Removed popup via {sel}")
        except:
            pass

def ensure_profile_icon_clicked(page):
    """
    STRICT: Click the Profile icon first, regardless of other routes.
    We fight through overlays by scrolling to top, closing PROMO popups,
    and force-clicking if necessary.
    """
    log("\n🔐 LOGIN PHASE (strict: profile icon → sign in)")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)

    # Repeated attempts with overlay clearing
    for attempt in range(1, 7):
        close_marketing_popups(page)
        try:
            icons = page.locator("img[alt='Profile Icon']")
            count = icons.count()
            if count == 0:
                # Sometimes the header inlines SVG; try a broader hit area:
                icons = page.locator("[data-position*='profile'], [aria-label*='profile' i]")
                count = icons.count()
                if count == 0:
                    raise RuntimeError("Profile icon not in DOM yet")

            # Prefer a visible one
            target = None
            for i in range(min(count, 5)):
                cand = icons.nth(i)
                if cand.is_visible():
                    target = cand
                    break
            if target is None:
                target = icons.first

            try:
                target.scroll_into_view_if_needed()
            except:
                pass

            # Try normal click, then force, then JS
            try:
                target.click(timeout=1500)
            except:
                try:
                    target.click(timeout=1500, force=True)
                except:
                    try:
                        handle = target.element_handle()
                        if handle:
                            page.evaluate("(el)=>el.click()", handle)
                        else:
                            raise
                    except:
                        raise

            log("✅ Clicked Profile icon")
            return True
        except Exception as e:
            log(f"⚠️ Profile icon click attempt {attempt} failed: {e}")
            page.wait_for_timeout(400)

    on_fail_checkpoint(page, "profile-icon-click-failed")
    return False

def click_sign_in_from_profile_menu(page):
    """
    STRICT: After clicking Profile icon, click the 'Sign in' control
    from that menu (even if hidden; we’ll force-click).
    """
    # Give the menu a moment to mount
    for _ in range(10):
        close_marketing_popups(page)
        # Primary known selector
        btn = page.locator("button[data-position='profile.1-sign-in']").first
        if btn.count() > 0:
            try:
                btn.scroll_into_view_if_needed()
            except:
                pass
            try:
                btn.click(timeout=1200)
            except:
                btn.click(timeout=1200, force=True)
            log("✅ Clicked 'Sign in' (profile menu)")
            return True

        # Fallbacks
        any_sign = page.locator("a:has-text('Sign in'), button:has-text('Sign in')").first
        if any_sign.count() > 0:
            try:
                any_sign.scroll_into_view_if_needed()
            except:
                pass
            try:
                any_sign.click(timeout=1200)
            except:
                any_sign.click(timeout=1200, force=True)
            log("✅ Clicked 'Sign in' (fallback in menu)")
            return True

        page.wait_for_timeout(250)

    log("❌ Could not find 'Sign in' in profile menu")
    on_fail_checkpoint(page, "sign-in-menu-missing")
    return False

def fill_real_login_form(page) -> bool:
    """
    Only fill within a REAL auth form: must include a PASSWORD input.
    Ignore/close any email-only capture. This prevents promo confusion.
    """
    # Wait briefly for navigation/dialog to render
    for _ in range(24):  # ~6s
        close_marketing_popups(page)

        # Find candidate containers that look like real login
        containers = page.locator(
            ",".join([
                "form[action*='login' i]",
                "form:has(input[type='password'])",
                "[data-testid='login-form']",
                "[aria-label*='Sign in' i] form",
                "form:has(input[name='password'])",
            ])
        )
        if containers.count() > 0:
            # Pick the first with both username and password
            for i in range(min(containers.count(), 5)):
                c = containers.nth(i)
                # Must have password
                pwd = c.locator("input[type='password'], input[name='password'], input#password")
                if pwd.count() == 0:
                    continue
                # Username/email
                user = c.locator("input[name='username'], input#username, input[type='email']")
                if user.count() == 0:
                    continue

                # Fill
                try:
                    if not user.first.is_visible():
                        user.first.scroll_into_view_if_needed()
                    user.first.fill(EMAIL)
                    if not pwd.first.is_visible():
                        pwd.first.scroll_into_view_if_needed()
                    pwd.first.fill(PASSWORD)
                    pwd.first.press("Enter")
                    log("✅ Submitted credentials in real login form")
                    return True
                except Exception as e:
                    log(f"⚠️ Could not fill login form: {e}")
            # If we’re here, we found containers but couldn’t fill; break to fail fast
            break

        page.wait_for_timeout(250)

    log("❌ No valid login form found (with password field)")
    on_fail_checkpoint(page, "login-form-missing")
    return False

def verify_logged_in(page) -> bool:
    # Heuristics: presence of Sign out / Account and absence of password
    for _ in range(20):  # ~10s
        close_marketing_popups(page)
        try:
            if page.locator("text=Sign out").first.is_visible():
                log("🔎 Login check: found 'Sign out'")
                return True
        except:
            pass
        try:
            if page.locator("input[type='password'], input[name='password'], input#password").count() == 0:
                if page.locator("text=/Account|Profile|My Account/i").count() > 0:
                    log("🔎 Login check: account UI present; no password fields")
                    return True
        except:
            pass
        page.wait_for_timeout(500)
    return False

def calendar_loaded(page) -> bool:
    probes = [
        "[data-testid*='calendar']",
        "[class*='calendar']",
        "section:has-text('Schedule')",
        "div[role='grid']",
    ]
    for sel in probes:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return True
        except:
            pass
    return False

def go_to_book_a_class(page, base_url: str) -> bool:
    log("\n📍 NAVIGATION: Book a Class (post-login)")
    # Prefer direct routes (more robust than header)
    for seg in BOOK_PATHS:
        url = base_url + seg if not base_url.endswith("/") else base_url + seg
        log(f"➡️  Trying booking URL: {url}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            close_marketing_popups(page)
            if calendar_loaded(page):
                log("✅ Schedule/Calendar UI detected (direct route).")
                return True
        except PWTimeout:
            log("⏱️  Booking route timed out, trying next…")
        except Exception as e:
            log(f"⚠️ Booking route failed: {e}")

    # Fallback: CTAs on homepage
    page.goto(base_url, wait_until="load", timeout=60000)
    close_marketing_popups(page)
    cta_candidates = [
        "text=Book a Class",
        "a[href*='book-a-class']",
        "a:has-text('Book a Class')",
        "button:has-text('Book a Class')",
        "[data-position='book-a-class']",
        "[data-position*=book][data-position*=class]",
    ]
    for sel in cta_candidates:
        try:
            btn = page.locator(sel).first
            if btn.count() == 0:
                continue
            btn.scroll_into_view_if_needed()
            try:
                btn.click(timeout=2500)
            except:
                btn.click(timeout=2500, force=True)
            for _ in range(30):
                if calendar_loaded(page):
                    log("✅ Schedule/Calendar UI detected (CTA route).")
                    return True
                page.wait_for_timeout(300)
        except:
            continue

    log("❌ Could not navigate to 'Book a Class'.")
    on_fail_checkpoint(page, "book-a-class-navigation")
    return False

def select_calendar_date(page, target_dt: datetime) -> bool:
    log("\n🗓️  CALENDAR: Selecting target date")
    day = target_dt.day
    month_label = target_dt.strftime("%B")

    try:
        # Nudge scroll so month header appears if virtualized
        for _ in range(8):
            if page.locator(f"text={month_label}").count() > 0:
                break
            page.mouse.wheel(0, 500)
            page.wait_for_timeout(120)
    except:
        pass

    candidates = [
        f"[role='gridcell'] button:has-text('{day}')",
        f"button.calendar-day:has-text('{day}')",
        f"button:has([aria-label*='{month_label}']):has-text('{day}')",
        f"button:has-text('{day}')",
    ]
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() == 0:
                continue
            el.scroll_into_view_if_needed()
            try:
                el.click(timeout=3500)
            except:
                el.click(timeout=3500, force=True)
            log(f"✅ Clicked date {day} via {sel}")
            return True
        except:
            continue

    log(f"❌ Could not select calendar date {day}.")
    on_fail_checkpoint(page, "calendar-date-select")
    return False

def find_and_book(page, target_time: str) -> bool:
    log("\n🔎 SESSION: Locating class time")

    time_selectors = [
        f"text={target_time}",
        f"div[class*='session'] :text('{target_time}')",
        f"[data-testid*='time']:has-text('{target_time}')",
    ]
    for _ in range(50):
        for ts in time_selectors:
            try:
                loc = page.locator(ts).first
                if loc.count() > 0 and loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    try:
                        loc.click(timeout=2500)
                    except:
                        loc.click(timeout=2500, force=True)
                    log(f"✅ Selected class at {target_time}")
                    # Reserve
                    reserve = page.locator("button:has-text('Reserve')").first
                    try:
                        reserve.scroll_into_view_if_needed()
                    except:
                        pass
                    try:
                        reserve.click(timeout=3500)
                    except:
                        reserve.click(timeout=3500, force=True)
                    log("✅ Clicked Reserve")
                    return True
            except:
                pass
        page.mouse.wheel(0, 650)
        page.wait_for_timeout(220)

    log(f"❌ Could not find class time {target_time}")
    on_fail_checkpoint(page, "class-time-not-found")
    return False

def main():
    if not EMAIL or not PASSWORD:
        log("❌ Missing COREPOWER_EMAIL or COREPOWER_PASSWORD.")
        sys.exit(1)

    target_dt = datetime.now() + timedelta(days=TARGET_DAYS_AHEAD)
    log("🚀 Starting ALONI – Strict-Order Functional Flow 3.2")
    log(f"📅 Target date: {human_target_date(TARGET_DAYS_AHEAD)} ({TARGET_DAYS_AHEAD} days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        # Always capture trace for CI
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        try:
            # 1) Open homepage
            log("🏠 Opening homepage…")
            page.goto(BASE_URL, wait_until="load", timeout=60000)

            # 2) Profile icon FIRST
            if not ensure_profile_icon_clicked(page):
                log("❌ Could not click profile icon — stopping before any login/date actions.")
                raise SystemExit(1)

            # 3) Click “Sign in” from menu
            if not click_sign_in_from_profile_menu(page):
                log("❌ Could not click 'Sign in' in profile menu — stopping.")
                raise SystemExit(1)

            # 4) Fill credentials only in a REAL login form (has password)
            if not fill_real_login_form(page):
                log("❌ Login form not found or could not submit — stopping.")
                raise SystemExit(1)

            # 5) Verify login
            if not verify_logged_in(page):
                log("❌ Login verification failed — stopping BEFORE any schedule/date interaction.")
                on_fail_checkpoint(page, "login-verification-failed")
                raise SystemExit(1)

            # 6) Navigate to booking/schedule (post-login)
            if not go_to_book_a_class(page, BASE_URL):
                log("❌ Could not reach schedule — stopping.")
                raise SystemExit(1)

            # 7) Select date
            if not select_calendar_date(page, target_dt):
                log("❌ Date selection failed — stopping.")
                raise SystemExit(1)

            # 8) Find class time and reserve
            if not find_and_book(page, TARGET_TIME):
                log("❌ Could not book desired class/time.")
                raise SystemExit(1)

            log("\n🎯 Flow complete – check for CorePower confirmation email.")
        finally:
            try:
                context.tracing.stop(path=ARTIFACT_TRACE)
            except:
                pass
            browser.close()

if __name__ == "__main__":
    main()
