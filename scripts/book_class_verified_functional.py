from contextlib import suppress
from datetime import datetime, timedelta
import os, re, time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def _wait_for_day_lock(page, target_date: datetime, timeout: float = 4000) -> None:
    """Ensure the calendar acknowledges the selected day before proceeding."""
    suffix = target_date.strftime("-%m-%d").lower()
    day_plain = str(target_date.day)
    day_padded = target_date.strftime("%d")
    months = [
        target_date.strftime("%b").lower(),
        target_date.strftime("%B").lower(),
    ]
    page.wait_for_function(
        """
        ({ dayPlain, dayPadded, months, suffix }) => {
            const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            const selectedNodes = Array.from(
                document.querySelectorAll(
                    '[aria-selected="true"], [aria-current="date"], [aria-current="true"], .selected, .active, .is-selected'
                )
            );

            return selectedNodes.some((el) => {
                const dataset = el.dataset || {};
                const dataDate = normalize(
                    dataset.date || dataset.fulldate || el.getAttribute('data-date') || el.getAttribute('data-fulldate')
                );
                if (dataDate && dataDate.includes(suffix)) {
                    return true;
                }

                const text = normalize(el.textContent);
                const aria = normalize(el.getAttribute('aria-label'));
                const combined = `${text} ${aria}`.trim();
                const hasDay = combined.includes(dayPlain) || combined.includes(dayPadded);
                const hasMonth = months.some((month) => combined.includes(month));
                return hasDay && hasMonth;
            });
        }
        """,
        arg={
            "dayPlain": day_plain,
            "dayPadded": day_padded,
            "months": months,
            "suffix": suffix,
        },
        timeout=timeout,
    )


def _dismiss_klaviyo_popup(page) -> bool:
    """Dismiss the Klaviyo marketing modal if it is intercepting clicks."""
    klaviyo_selectors = [
        "div[aria-label='POPUP Form'] button:has-text('×')",
        "div[aria-label='POPUP Form'] button:has-text('Close')",
        "div[aria-label='POPUP Form'] button:has-text('No thanks')",
        "div[aria-label='POPUP Form'] button[aria-label='Close']",
        "div.kl-private-reset-css-Xuajs1 button[aria-label='Close']",
        "div.kl-private-reset-css-Xuajs1 button:has-text('Maybe Later')",
    ]

    for sel in klaviyo_selectors:
        locator = page.locator(sel).first
        with suppress(Exception):
            if locator.count() > 0 and locator.is_visible():
                locator.click()
                print(f"🧹 Closed Klaviyo via {sel}")
                return True

    # Fallback: try escape and remove overlay if still present
    with suppress(Exception):
        page.keyboard.press("Escape")
        print("🧹 Sent Escape to close Klaviyo modal.")
        page.wait_for_timeout(200)
        if page.locator("div[aria-label='POPUP Form']").first.count() == 0:
            return True

    with suppress(Exception):
        removed = page.evaluate(
            """
            () => {
                const el = document.querySelector('div.kl-private-reset-css-Xuajs1');
                if (el) {
                    el.remove();
                    return true;
                }
                return false;
            }
            """
        )
        if removed:
            print("🧹 Removed lingering Klaviyo overlay via DOM patch.")
            return True

    return False


def _calendar_day_selectors(target_date: datetime) -> list[str]:
    """Return selectors that identify the target calendar day without relying on the year."""
    suffix = target_date.strftime("-%m-%d")
    day = str(target_date.day)
    month_variants = list(dict.fromkeys([
        target_date.strftime("%b"),
        target_date.strftime("%b").upper(),
        target_date.strftime("%B"),
    ]))

    selectors = [
        f"[data-date$='{suffix}']",
        f"[data-date*='{suffix}']",
        f"[data-fulldate$='{suffix}']",
        f"[data-fulldate*='{suffix}']",
        f"[data-date='{target_date.strftime('%Y-%m-%d')}']",
    ]

    for month in month_variants:
        selectors.extend([
            f"button:has-text('{month} {day}')",
            f"button:has-text('{day} {month}')",
            f"div.cal-date:has-text('{month} {day}')",
            f"div.cal-date:has-text('{day} {month}')",
        ])

    # Fallback: bare day inside calendar cells.
    selectors.append(f"div.cal-date:has-text('{day}')")
    selectors.append(f"button:has-text('{day}')")
    return selectors


def _calendar_day_visible(page, target_date: datetime) -> bool:
    """Check if the target day appears in the current calendar view."""
    for selector in _calendar_day_selectors(target_date):
        with suppress(Exception):
            if page.locator(selector).count() > 0:
                return True
    return False


def _find_calendar_day(page, target_date: datetime):
    """Find the locator for the target calendar day, if present."""
    for selector in _calendar_day_selectors(target_date):
        locator = page.locator(selector)
        with suppress(Exception):
            if locator.count() > 0:
                return locator.last
    return None


def _nudge_calendar(page, target_date: datetime, aggressive: bool = False) -> bool:
    """Nudge the calendar forward/backward to reveal the target date."""
    forward_controls = [
        "button[aria-label*='next']",
        "button[aria-label*='forward']",
        "button[data-testid='calendar-next']",
        "button[data-testid='calendar-forward']",
        "button:has-text('Next week')",
        "button:has-text('Next Week')",
        "button:has-text('Next')",
    ]
    backward_controls = [
        "button[aria-label*='previous']",
        "button[aria-label*='prev']",
        "button[data-testid='calendar-prev']",
        "button[data-testid='calendar-back']",
        "button:has-text('Previous week')",
        "button:has-text('Previous Week')",
        "button:has-text('Prev')",
    ]

    is_future = target_date.date() >= datetime.now().date()
    controls = forward_controls if is_future else backward_controls
    steps = 2 if aggressive else 1

    for control in controls:
        locator = page.locator(control).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_enabled():
                continue
        for _ in range(steps):
            with suppress(Exception):
                locator.click()
            page.wait_for_timeout(250)
            if _calendar_day_visible(page, target_date):
                return True
    return False


def _select_target_day(page, target_date: datetime) -> None:
    """Click the desired calendar day and re-assert selection if the UI jumps."""
    day_label = target_date.strftime('%a')

    for attempt in range(5):
        locator = _find_calendar_day(page, target_date)
        if locator is None:
            print("🔎 Target day not visible — nudging calendar…")
            _nudge_calendar(page, target_date, aggressive=True)
            page.wait_for_timeout(300)
            continue

        with suppress(Exception):
            locator.scroll_into_view_if_needed()
        page.wait_for_timeout(120)

        clicked = False
        with suppress(Exception):
            locator.click()
            clicked = True
        if not clicked:
            with suppress(Exception):
                locator.click(force=True)
                clicked = True

        if not clicked:
            print("⚠️ Calendar click failed — nudging calendar…")
            _nudge_calendar(page, target_date, aggressive=True)
            page.wait_for_timeout(250)
            continue

        page.wait_for_timeout(200)
        try:
            _wait_for_day_lock(page, target_date)
            print(f"✅ Clicked calendar date {target_date.day} ({day_label}).")
            return
        except PlaywrightTimeout:
            print(f"🔁 Calendar selection drift detected (attempt {attempt + 1}/5) — refocusing…")
            _nudge_calendar(page, target_date, aggressive=True)
            page.wait_for_timeout(300)

    raise RuntimeError(f"Unable to stabilize calendar on {target_date.day} ({day_label}).")


def _prime_session_scroll(page) -> None:
    """Scroll the session list slightly to lock the selected day's classes in place."""
    try:
        page.locator("div.session-row-view").first.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeout:
        print("⚠️ Class list did not render in time.")
        return

    page.wait_for_timeout(200)
    page.mouse.wheel(0, 800)
    page.wait_for_timeout(200)
    page.mouse.wheel(0, 800)
    print("🖱️ Primed session list scroll for selected day.")


def main():
    print("🚀 Starting ALONI 2.9.11 – Scroll-Lock Patch…")

    load_dotenv()
    email = os.getenv("COREPOWER_EMAIL")
    password = os.getenv("COREPOWER_PASSWORD")
    if not email or not password:
        missing = [
            name for name, value in [("COREPOWER_EMAIL", email), ("COREPOWER_PASSWORD", password)] if not value
        ]
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    target_date = datetime.now() + timedelta(days=13)
    weekday = target_date.strftime("%A")
    should_book = weekday in ["Monday", "Tuesday", "Wednesday"]
    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="videos/",
            viewport={"width": 1280, "height": 800}
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        try:
            print("🏠 Opening homepage…")
            page.goto("https://www.corepoweryoga.com/", timeout=60000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)

            # Close popups
            for selector in ["button:has-text('Close')", "button[aria-label*='close' i]"]:
                with suppress(Exception):
                    page.locator(selector).first.click(timeout=3000)
                    print(f"💨 Closed popup via {selector}")

            _dismiss_klaviyo_popup(page)

            # Profile icon
            try:
                for sel in [
                    ".profile-icon-container",
                    "div.profile-container img[alt='Profile Icon']",
                    "div.profile-container",
                    "img[src*='profile_icon.svg']",
                    "div.cursor-pointer:has(img[alt='Profile Icon'])",
                    "button[aria-label*='profile' i]",
                ]:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        if _dismiss_klaviyo_popup(page):
                            page.wait_for_timeout(200)
                        print(f"👁️ Found profile icon via {sel}")
                        loc.click()
                        print("✅ Clicked profile icon.")
                        break
            except Exception as e:
                print(f"❌ Profile icon error: {e}")
                return

            # Sign in
            try:
                btn = page.locator("button[data-position='profile.1-sign-in']").first
                btn.wait_for(timeout=8000)
                btn.click()
                print("✅ Clicked 'Sign In'.")
            except Exception as e:
                print(f"❌ Sign In button error: {e}")
                return

            # Credentials
            try:
                page.wait_for_timeout(2000)
                page.locator("input[name='username']").fill(email)
                page.locator("input[name='password']").fill(password)
                page.locator("form button[type='submit']:has-text('Sign In')").click()
                print("✅ Submitted credentials.")
            except Exception as e:
                print(f"❌ Credential error: {e}")
                return

            page.wait_for_timeout(4000)

            # Handle modals
            for selector in [
                "button:has-text('Close')",
                "button[aria-label*='close' i]",
                "div.modal button.close",
                "button[aria-label='Dismiss']",
            ]:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible():
                        loc.click()
                        print(f"💨 Closed modal via {selector}")
                        time.sleep(1)
                except:
                    pass

            if should_book:
                print("🧘 Booking window open — proceeding.")

                # Book a class
                try:
                    book_btn = page.locator("button[data-position='book-a-class']").last
                    book_btn.wait_for(state="visible", timeout=10000)
                    book_btn.click()
                    print("✅ Clicked 'Book a class'.")
                except Exception as e:
                    print(f"⚠️ Book button error: {e}")

                page.wait_for_timeout(5000)

                # Pick date + scroll-lock
                try:
                    _select_target_day(page, target_date)
                    _prime_session_scroll(page)
                except Exception as e:
                    print(f"⚠️ Date select error: {e}")

                # Locate target class and book
                try:
                    rows = page.locator("div.session-row-view")
                    TARGET_CLASS_LOCAL = "11:15 PM"
                    print(f"🕒 Target time (UTC): {TARGET_CLASS_LOCAL}")

                    def find_row():
                        for _ in range(20):
                            with suppress(PlaywrightTimeout):
                                _wait_for_day_lock(page, target_date, timeout=1500)
                            for i in range(rows.count()):
                                try:
                                    text = rows.nth(i).inner_text(timeout=1000).lower()
                                    if "ys - yoga sculpt" in text and "flatiron" in text and TARGET_CLASS_LOCAL.lower() in text:
                                        return rows.nth(i)
                                except:
                                    continue
                            page.mouse.wheel(0, 900)
                            page.wait_for_timeout(300)
                        return None

                    row = find_row()
                    if row is None:
                        print("⚠️ Target class not found.")
                        return
                    row.scroll_into_view_if_needed()
                    print("✅ Scrolled to target class row.")

                    book = row.locator("div.session-card_sessionCardBtn__FQT3Z").first
                    if book.count() == 0:
                        book = row.locator("div:has-text('BOOK')").first
                    try:
                        book.evaluate("el => el.click()")
                        page.wait_for_timeout(800)
                        print("✅ Clicked BOOK button.")
                    except Exception as e:
                        print(f"⚠️ BOOK click failed: {e}")
                except Exception as e:
                    print(f"⚠️ Booking error: {e}")

            else:
                print(f"📆 {weekday} is not a booking day — skipping.")

            print("🎯 Flow completed.")

        finally:
            print("💾 Saving trace and closing browser…")
            context.tracing.stop(path="trace.zip")
            context.close()
            browser.close()
            print("📸 Artifacts saved to videos/ and trace.zip")


if __name__ == "__main__":
    main()
