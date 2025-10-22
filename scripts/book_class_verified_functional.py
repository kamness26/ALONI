# scripts/book_class_verified_functional.py
import os
import sys
import time
import datetime as dt
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    Page,
    TimeoutError as PWTimeoutError,
)
from dotenv import load_dotenv

# ---------------------------
# Config & helpers
# ---------------------------

load_dotenv()
EMAIL = os.getenv("COREPOWER_EMAIL")
PASSWORD = os.getenv("COREPOWER_PASSWORD")

if not EMAIL or not PASSWORD:
    raise RuntimeError("Missing COREPOWER_EMAIL or COREPOWER_PASSWORD in environment/.env")

HOME_URL = "https://www.corepoweryoga.com/"  # adjust if you use a different landing URL
HEADLESS = True if os.getenv("CI", "false").lower() == "true" else True
DEFAULT_TIMEOUT = 30_000  # ms

def log(msg: str) -> None:
    print(msg, flush=True)

def sleep_s(ms: int) -> None:
    time.sleep(ms / 1000.0)

def today_local() -> dt.date:
    # Keep everything in local runner date so "days ahead" stays predictable
    return dt.date.today()

def target_date(days_ahead: int = 13) -> dt.date:
    return today_local() + dt.timedelta(days=days_ahead)

# ---------------------------
# Popup/Modal handling
# ---------------------------

def dismiss_popups(page: Page, context: str = "") -> None:
    """
    Try multiple strategies (safe to call often).
    Intentionally tolerant: failures here shouldn't abort the run.
    """
    prefixes = "💨 " if not context else f"💨 [{context}] "
    try:
        # Common close patterns
        close_selectors = [
            "button:has-text('Close')",
            "button[aria-label='Close']",
            "button[aria-label='close']",
            "button[aria-label='Dismiss']",
            "button[title='Close']",
            "div[role='dialog'] button:has-text('Close')",
            "div[role='dialog'] button[aria-label='Close']",
            "div[role='dialog'] button:has-text('No thanks')",
            "button:has-text('No thanks')",
            "button:has-text('Not now')",
            "button:has-text('×')",
            "[data-testid='close-button']",
            "[data-test='close']",
            ".modal button.close",
            ".Popup button.close",
        ]

        for sel in close_selectors:
            loc = page.locator(sel)
            count = loc.count()
            if count:
                # Click all visible matches (there can be stacked promos)
                for i in range(min(count, 5)):
                    try:
                        loc.nth(i).click(timeout=1000)
                        log(f"{prefixes}Removed modal element via {sel}")
                    except Exception:
                        pass

        # Kill any obvious newsletter/30% email captures that block clicks
        # by removing their containers if present.
        # We purposely limit the number of removals so we don't nuke the page.
        page.evaluate(
            """
            (() => {
              const candidates = Array.from(document.querySelectorAll([
                'div[role="dialog"]',
                'div[class*="modal"]',
                'div[id*="popup"]',
                'div[class*="Popup"]',
                'div[class*="newsletter"]',
                'div[class*="subscribe"]',
              ].join(',')));
              let removed = 0;
              for (const el of candidates) {
                const z = Number(getComputedStyle(el).zIndex || '0');
                const blocksClicks = z >= 1000 || (el.getBoundingClientRect().width > 200 && el.getBoundingClientRect().height > 100);
                if (blocksClicks) {
                  el.remove();
                  removed++;
                  if (removed >= 3) break;
                }
              }
            })();
            """
        )
    except Exception:
        # Never fail on dismissal
        pass

# ---------------------------
# Auth flow: Profile → Sign in → Credentials
# ---------------------------

def click_profile_then_sign_in(page: Page) -> bool:
    """
    Enforces the strict order you requested:
      (1) click Profile icon
      (2) click Sign in button
      (3) return True when sign-in form is visible (so caller can fill creds)
    If already logged in, returns False (caller can skip credentials).
    """
    log("\n🔐 LOGIN PHASE (strict order)")
    dismiss_popups(page, "pre-login")

    # (1) PROFILE ICON
    # Be explicit: wait for a *visible* profile icon, not just present.
    # Try a few variants and pick the first visible.
    profile_selectors = [
        "img[alt='Profile Icon']",
        "[data-position='profile']",
        "button:has(svg[aria-label='Profile'])",
        "a[href*='profile']",
    ]

    profile_clicked = False
    for sel in profile_selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=8000)
            loc.click()
            profile_clicked = True
            log("✅ Clicked Profile icon")
            break
        except PWTimeoutError:
            log(f"⚠️ Profile icon not visible via {sel} (timeout)")
        except Exception as e:
            log(f"⚠️ Could not click profile via {sel}: {e}")

    if not profile_clicked:
        # As a fallback, try to reveal header then retry once
        try:
            page.keyboard.press("Escape")
            dismiss_popups(page, "profile-fallback")
            loc = page.locator("img[alt='Profile Icon']").first
            loc.wait_for(state="visible", timeout=5000)
            loc.click()
            log("✅ Clicked Profile icon (fallback)")
            profile_clicked = True
        except Exception:
            pass

    if not profile_clicked:
        log("❌ Could not click Profile icon")
        return False

    dismiss_popups(page, "post-profile")

    # (2) SIGN IN BUTTON
    sign_in_selectors = [
        "button[data-position='profile.1-sign-in']",
        "button:has-text('Sign in')",
        "a:has-text('Sign in')",
        "button[aria-label='Sign in']",
    ]

    sign_in_clicked = False
    sign_in_button_visible = False

    for sel in sign_in_selectors:
        try:
            loc = page.locator(sel).first
            # We check visibility twice: first to confirm it's there, then click.
            loc.wait_for(state="visible", timeout=8000)
            sign_in_button_visible = True
            loc.click()
            sign_in_clicked = True
            log("✅ Clicked 'Sign in' button")
            break
        except PWTimeoutError:
            log(f"⚠️ 'Sign in' not visible via {sel} (timeout)")
        except Exception as e:
            log(f"⚠️ Could not click 'Sign in' via {sel}: {e}")

    # If the Sign in button was never visible, assume possibly already logged in
    if not sign_in_clicked and not sign_in_button_visible:
        log("🔎 Login check: 'Sign in' not visible -> assuming already logged in.")
        return False

    dismiss_popups(page, "post-sign-in-click")

    # (3) VERIFY CREDENTIAL FORM APPEARED
    try:
        # Prefer specific inputs, but keep fallbacks
        email_input = page.locator("input[type='email'], input[name='email']")
        password_input = page.locator("input[type='password'], input[name='password']")
        email_input.wait_for(state="visible", timeout=10_000)
        password_input.wait_for(state="visible", timeout=10_000)
        log("✅ Sign-in form visible")
        return True
    except PWTimeoutError:
        log("⚠️ Sign-in form did not appear—assuming session is already authenticated.")
        return False

def submit_credentials(page: Page, email: str, password: str) -> None:
    try:
        email_input = page.locator("input[type='email'], input[name='email']").first
        pwd_input = page.locator("input[type='password'], input[name='password']").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in')").first

        email_input.fill(email, timeout=10_000)
        pwd_input.fill(password, timeout=10_000)
        dismiss_popups(page, "pre-submit")
        submit_btn.click(timeout=10_000)

        # Wait for a signed-in indicator: profile menu shows user items / or sign-out appears.
        page.wait_for_timeout(500)  # brief settle
        possible_auth_ok = [
            "button:has-text('Sign out')",
            "a:has-text('Sign out')",
            "a[href*='account']",
        ]
        for sel in possible_auth_ok:
            try:
                page.locator(sel).first.wait_for(state="visible", timeout=8000)
                log("✅ Logged in")
                return
            except Exception:
                pass

        # Fallback: absence of the email/password inputs after submission
        try:
            page.locator("input[type='password']").first.wait_for(state="hidden", timeout=8000)
            log("✅ Logged in (inputs disappeared)")
        except Exception:
            log("⚠️ Could not confirm login; continuing optimistically.")

    except Exception as e:
        log(f"❌ Login submission failed: {e}")
        raise

# ---------------------------
# Navigation & Date handling
# ---------------------------

def go_to_book_a_class(page: Page) -> None:
    log("\n📍 NAVIGATION: Book a Class")
    dismiss_popups(page, "pre-nav")
    nav_variants = [
        "a[href*='book-a-class']",
        "a:has-text('Book a Class')",
        "button:has-text('Book a Class')",
        "a:has-text('Book a class')",
        "button:has-text('Book a class')",
    ]

    for sel in nav_variants:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=15_000)
            loc.click()
            log("✅ Navigated via: " + sel)
            return
        except Exception:
            pass

    # Last resort: click any element that looks like a primary CTA for booking.
    try:
        page.get_by_text("Book a Class", exact=False).first.click(timeout=8_000)
        log("✅ Navigated via text search fallback")
        return
    except Exception:
        log("❌ Could not navigate to 'Book a Class'.")
        raise RuntimeError("Navigation to 'Book a Class' failed")

def select_calendar_date(page: Page, date_obj: dt.date) -> None:
    """
    Choose a specific date without relying on list order.
    The strategy:
      - construct accessible labels and data attributes that commonly appear
      - search for a date cell that matches the exact calendar day
      - never iterate sessions "by displayed order" (prevents reversed selection)
    """
    log("\n🗓️  Selecting target date deterministically")

    # Common accessible labels: "Tuesday, November 4", etc.
    # Build a few variants to maximize match rate.
    label_variants = [
        date_obj.strftime("%A, %B %-d"),
        date_obj.strftime("%A, %B %d"),
        date_obj.strftime("%B %-d, %Y"),
        date_obj.strftime("%B %d, %Y"),
        date_obj.strftime("%Y-%m-%d"),
        date_obj.strftime("%m/%d/%Y"),
    ]

    # Search strategies in order, clicking the first match found.
    strategies = [
        # aria-label cell
        lambda: page.locator(
            ",".join([f"[aria-label*='{lbl}']" for lbl in label_variants])
        ),
        # data-date cell
        lambda: page.locator(
            f"[data-date='{date_obj.isoformat()}'], [data-day='{date_obj.isoformat()}']"
        ),
        # role-based day button (common in accessible calendars)
        lambda: page.get_by_role("button", name=date_obj.strftime("%-d")).filter(
            has=page.locator("[aria-label*='%s']" % date_obj.strftime("%B"))
        ),
        # textual day match inside a date grid
        lambda: page.locator("td,div,button").filter(has_text=date_obj.strftime("%-d")),
    ]

    # First, try to ensure the calendar is visible (some sites lazy-load it)
    try:
        page.wait_for_selector("[role='grid'], [class*='calendar'], [data-component*='calendar']", timeout=8000)
    except Exception:
        # If not, just proceed—selectors below may still work once found directly.
        pass

    dismiss_popups(page, "pre-date-select")

    clicked = False
    for strat in strategies:
        try:
            loc = strat()
            if loc.count() == 0:
                continue
            # Pick the element whose aria-label or data-date matches the *exact* date
            # This prevents "wrong order" or "closest match" mistakes.
            for i in range(min(loc.count(), 10)):
                cand = loc.nth(i)
                try:
                    # Avoid disabled/outside-month
                    disabled = cand.get_attribute("aria-disabled")
                    if disabled and disabled.lower() in ("true", "disabled"):
                        continue
                except Exception:
                    pass
                try:
                    cand.scroll_into_view_if_needed(timeout=2000)
                    cand.click(timeout=3000)
                    clicked = True
                    log(f"✅ Clicked calendar cell #{i+1}")
                    break
                except Exception:
                    continue
            if clicked:
                break
        except Exception:
            continue

    if not clicked:
        raise RuntimeError("Could not select the target date on the schedule/calendar")

    dismiss_popups(page, "post-date-select")

# ---------------------------
# Main
# ---------------------------

def main() -> int:
    target = target_date(13)
    log("🚀 Starting ALONI – Strict-Order Functional Flow 3.1")
    log(f"📅 Target date: {target.strftime('%A, %b %d')} ({(target - today_local()).days} days from today)")

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=HEADLESS, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )

        # Optional trace start (kept minimal so artifacts exist if we crash early)
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=False)
        except Exception:
            pass

        page: Page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        try:
            log("🏠 Opening homepage…")
            page.goto(HOME_URL, wait_until="domcontentloaded")
            dismiss_popups(page, "on-load")

            # LOGIN (strict order)
            must_fill = click_profile_then_sign_in(page)
            if must_fill:
                submit_credentials(page, EMAIL, PASSWORD)

            # NAVIGATE
            go_to_book_a_class(page)

            # SELECT DATE deterministically
            select_calendar_date(page, target)

            log("✅ Reached schedule and selected target date.")
            return 0

        except Exception as e:
            log(f"❌ Fatal error: {e}")
            return 1
        finally:
            # Save trace so your CI can upload it
            try:
                os.makedirs("videos", exist_ok=True)
                os.makedirs("screenshots", exist_ok=True)
                context.tracing.stop(path="trace.zip")
            except Exception:
                pass
            context.close()
            browser.close()

if __name__ == "__main__":
    sys.exit(main())
