from contextlib import suppress
from datetime import datetime, timedelta
import os, re, time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def _target_iso(target_date: datetime) -> str:
    return target_date.strftime("%Y-%m-%d")


def _save_debug_screenshot(page, label: str) -> None:
    """Capture a checkpoint screenshot to diagnose date drift in CI."""
    with suppress(Exception):
        os.makedirs("screenshots", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        page.screenshot(path=f"screenshots/{stamp}_{label}.png", full_page=False)


def _read_selected_schedule_date(page) -> datetime | None:
    """Read the selected schedule date from heading text like 'Sat, Feb 28'."""
    heading_selectors = [
        "div.schedule-page h2",
        "main h2",
        "h2",
    ]
    text_value = None
    for selector in heading_selectors:
        locator = page.locator(selector)
        with suppress(Exception):
            for i in range(min(locator.count(), 6)):
                text = (locator.nth(i).inner_text(timeout=500) or "").strip()
                if re.match(r"^[A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}$", text):
                    text_value = text
                    break
        if text_value:
            break

    if not text_value:
        return None

    try:
        parsed = datetime.strptime(text_value, "%a, %b %d")
    except ValueError:
        return None

    now = datetime.now()
    candidate = parsed.replace(year=now.year)
    # Handle year rollover around Jan/Dec boundaries.
    if candidate.date() < (now - timedelta(days=200)).date():
        candidate = candidate.replace(year=now.year + 1)
    elif candidate.date() > (now + timedelta(days=200)).date():
        candidate = candidate.replace(year=now.year - 1)
    return candidate


def _is_target_day_selected(page, target_date: datetime) -> bool:
    """Prefer schedule heading/day bar text to confirm the selected day."""
    selected = _read_selected_schedule_date(page)
    if selected and selected.date() == target_date.date():
        return True

    target_label_long = target_date.strftime("%a, %b %d").lower()
    target_label_short = target_label_long.replace(" 0", " ")
    target_compact = target_label_long.replace(" 0", " ")

    daybar_selectors = [
        "div.days-bar",
        "div[class*='days-bar']",
    ]
    for selector in daybar_selectors:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_visible():
                continue
            text = (locator.inner_text(timeout=600) or "").strip().lower()
            text = re.sub(r"\s+", " ", text)
            if text in {target_label_long, target_compact, target_label_short}:
                return True
    return False


def _read_days_bar_label(page) -> str | None:
    """Read the selected day label from the sticky day bar (e.g., 'Mon, Mar 02')."""
    selectors = [
        "div.days-bar",
        "div[class*='days-bar']",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_visible():
                continue
            text = (locator.inner_text(timeout=700) or "").strip()
            text = re.sub(r"\s+", " ", text)
            match = re.search(r"[A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}", text)
            if match:
                return match.group(0)
    return None


def _assert_exact_target_day(page, target_date: datetime) -> None:
    """Require exact selected day match before any booking actions."""
    label = _read_days_bar_label(page)
    target_labels = {
        target_date.strftime("%a, %b %d"),
        target_date.strftime("%a, %b %d").replace(" 0", " "),
    }
    if not label or label not in target_labels:
        _save_debug_screenshot(page, "target_day_exact_mismatch")
        raise RuntimeError(
            f"Active day mismatch. Expected one of {sorted(target_labels)}, got '{label or 'none'}'."
        )


def _wait_for_day_lock(page, target_date: datetime, timeout: float = 4000) -> None:
    """Ensure the calendar acknowledges the selected day before proceeding."""
    if _is_target_day_selected(page, target_date):
        return

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
                const parent = el.closest('[data-date], [data-fulldate], .cal-item');
                const parentDataset = parent && parent.dataset ? parent.dataset : {};
                const dataDate = normalize(
                    dataset.date ||
                    dataset.fulldate ||
                    parentDataset.date ||
                    parentDataset.fulldate ||
                    el.getAttribute('data-date') ||
                    el.getAttribute('data-fulldate') ||
                    (parent ? parent.getAttribute('data-date') : '') ||
                    (parent ? parent.getAttribute('data-fulldate') : '')
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
    """Return strict selectors for a specific day and avoid ambiguous text matches."""
    iso = _target_iso(target_date)
    suffix = target_date.strftime("-%m-%d")
    month_short = target_date.strftime("%b").lower()
    month_long = target_date.strftime("%B").lower()
    day = str(target_date.day)
    day_padded = target_date.strftime("%d")
    weekday_short = target_date.strftime("%a").lower()
    weekday_long = target_date.strftime("%A").lower()

    return [
        f"[data-date='{iso}']",
        f"[data-fulldate='{iso}']",
        f"[data-date$='{suffix}']",
        f"[data-fulldate$='{suffix}']",
        f"[aria-label*='{weekday_short}, {month_short} {day}' i]",
        f"[aria-label*='{weekday_long}, {month_long} {day}' i]",
        f"[aria-label*='{month_short} {day_padded}' i]",
        f"[aria-label*='{month_long} {day}' i]",
    ]


def _calendar_day_visible(page, target_date: datetime) -> bool:
    """Check if the target day appears in the current calendar view."""
    for selector in _calendar_day_selectors(target_date):
        with suppress(Exception):
            if page.locator(selector).count() > 0:
                return True

    # Fallback for UI variants where day cells are text-only without data-date attributes.
    target_day = target_date.day
    target_weekday = target_date.strftime("%a")[0].lower()
    target_month_tokens = {
        target_date.strftime("%b").lower(),
        target_date.strftime("%B").lower(),
    }
    with suppress(Exception):
        return bool(
            page.evaluate(
                """
                ({ targetDay, weekdayInitial, monthTokens }) => {
                    const norm = (v) => (v || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    const cells = Array.from(
                        document.querySelectorAll(
                            ".cal-item, .cal-item-container, [class*='cal-item'], [class*='calendar-day'], [class*='day-item']"
                        )
                    );
                    return cells.some((cell) => {
                        const txt = norm(cell.textContent);
                        if (!txt) return false;
                        if (!txt.includes(String(targetDay))) return false;
                        if (!txt.includes(weekdayInitial)) return false;

                        const attrs = [
                            cell.getAttribute('aria-label') || '',
                            cell.getAttribute('data-date') || '',
                            cell.getAttribute('data-fulldate') || '',
                        ]
                            .map(norm)
                            .join(' ');
                        if (!attrs) return true;
                        return monthTokens.some((m) => attrs.includes(m));
                    });
                }
                """,
                {
                    "targetDay": target_day,
                    "weekdayInitial": target_weekday,
                    "monthTokens": list(target_month_tokens),
                },
            )
        )
    return False


def _calendar_reset_detected(page, target_date: datetime) -> bool:
    """Return True when the calendar snaps back to today's date."""
    if target_date.date() == datetime.now().date():
        return False

    today_locator = page.locator("[aria-current='date']").first
    try:
        if today_locator.count() == 0 or not today_locator.is_visible():
            return False
    except Exception:
        return False

    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip().lower()

    today = datetime.now()
    month_tokens = {
        today.strftime("%b").lower(),
        today.strftime("%B").lower(),
    }
    day_tokens = {
        str(today.day),
        today.strftime("%d"),
    }

    text_parts = []
    for accessor in ("data-date", "data-fulldate", "aria-label"):
        with suppress(Exception):
            value = today_locator.get_attribute(accessor)
            if value:
                text_parts.append(value)
    with suppress(Exception):
        text_parts.append(today_locator.inner_text())

    combined = _normalize(" ".join(text_parts))
    if combined:
        has_day = any(token in combined for token in day_tokens)
        has_month = any(token in combined for token in month_tokens)
        if not (has_day and has_month):
            return False

    try:
        target_visible = _calendar_day_visible(page, target_date)
    except Exception:
        target_visible = True

    return not target_visible


def _find_calendar_day(page, target_date: datetime):
    """Find the locator for the target calendar day, if present."""
    for selector in _calendar_day_selectors(target_date):
        locator = page.locator(selector)
        with suppress(Exception):
            if locator.count() > 0:
                for i in range(locator.count()):
                    candidate = locator.nth(i)
                    if candidate.is_visible():
                        return candidate

    # Text-based fallback when data attributes are absent.
    target_day = target_date.day
    weekday_initial = target_date.strftime("%a")[0]
    fallback_selectors = [
        f".cal-item:has-text('{target_day}')",
        f".cal-item-container:has-text('{target_day}')",
        f"[class*='cal-item']:has-text('{target_day}')",
        f"[class*='calendar-day']:has-text('{target_day}')",
        f"[class*='day-item']:has-text('{target_day}')",
        f"text=/\\b{weekday_initial}\\s*{target_day}\\b/i",
    ]
    for selector in fallback_selectors:
        locator = page.locator(selector)
        with suppress(Exception):
            if locator.count() > 0:
                for i in range(locator.count()):
                    candidate = locator.nth(i)
                    if candidate.is_visible():
                        return candidate
    return None


def _wait_for_calendar_strip(page, timeout_ms: int = 12000) -> None:
    """Ensure the horizontal day strip is rendered before selecting dates."""
    strip_selectors = [
        "div.days-bar",
        "div[class*='days-bar']",
        "div.schedule-calendar",
        "div[class*='calendarScroll']",
    ]
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        for selector in strip_selectors:
            locator = page.locator(selector).first
            with suppress(Exception):
                if locator.count() > 0 and locator.is_visible():
                    txt = (locator.inner_text(timeout=400) or "").strip()
                    if txt:
                        return
        page.wait_for_timeout(200)
    raise RuntimeError("Calendar strip did not render in time.")


def _nudge_calendar(page, target_date: datetime, aggressive: bool = False) -> bool:
    """Nudge the calendar forward/backward to reveal the target date."""
    forward_controls = [
        "button[aria-label*='next' i]",
        "button[aria-label*='forward' i]",
        "button[data-testid='calendar-next']",
        "button[data-testid='calendar-forward']",
        "button:has-text('Next week')",
        "button:has-text('Next Week')",
        "button:has-text('Next')",
    ]
    backward_controls = [
        "button[aria-label*='previous' i]",
        "button[aria-label*='prev' i]",
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

    # Some UI variants use horizontal calendar scrolling instead of nav buttons.
    dx = 360 if is_future else -360
    scroll_containers = [
        "div.days-bar",
        "div[class*='days-bar']",
        "div.calendar-container",
        "div.schedule-calendar",
        "div[class*='calendarScroll']",
        "div[class*='calendar-container']",
    ]
    for selector in scroll_containers:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_visible():
                continue
            for _ in range(3 if aggressive else 1):
                locator.evaluate(
                    """(el, delta) => {
                        if (!(el instanceof HTMLElement)) return;
                        el.scrollBy({ left: delta, behavior: 'auto' });
                    }""",
                    dx,
                )
                page.wait_for_timeout(250)
                if _calendar_day_visible(page, target_date):
                    return True

    # Last-resort generic horizontal scroll across likely strip elements.
    with suppress(Exception):
        moved = page.evaluate(
            """(delta) => {
                const nodes = Array.from(document.querySelectorAll('div, section')).filter((el) => {
                    if (!(el instanceof HTMLElement)) return false;
                    const style = getComputedStyle(el);
                    const scrollableX = el.scrollWidth > el.clientWidth + 8;
                    const overflowX = style.overflowX;
                    const canScroll =
                        overflowX === 'auto' || overflowX === 'scroll' || overflowX === 'overlay' || scrollableX;
                    if (!canScroll) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 200 && r.height > 24 && r.top >= 0 && r.top < window.innerHeight * 0.7;
                });
                let any = false;
                for (const el of nodes) {
                    const before = el.scrollLeft;
                    el.scrollBy({ left: delta, behavior: 'auto' });
                    if (el.scrollLeft !== before) any = true;
                }
                return any;
            }""",
            dx,
        )
        if moved:
            page.wait_for_timeout(300)
            if _calendar_day_visible(page, target_date):
                return True
    return False


def _wait_for_session_reload(page, timeout_ms: int = 9000) -> bool:
    """Wait for the session list/calendar container to blank and repopulate."""
    selectors = [
        ".SessionPickerCalendar_calendarScroll__",
        "div.session-row-view",
    ]
    start = time.time()
    saw_blank = False

    def _any_visible() -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            with suppress(Exception):
                if locator.count() > 0 and locator.is_visible():
                    return True
        return False

    while True:
        elapsed = time.time() - start
        if elapsed * 1000 >= timeout_ms:
            break
        visible = _any_visible()
        if visible and (saw_blank or elapsed > 0.6):
            return True
        if not visible:
            saw_blank = True
        page.wait_for_timeout(150)

    return _any_visible()


def _scroll_calendar_strip(page, forward: bool = True, pixels: int = 420) -> bool:
    """Scroll the calendar strip horizontally when next/prev buttons are missing."""
    dx = pixels if forward else -pixels
    selectors = [
        "div.calendar-container",
        "div.schedule-calendar",
        "div[class*='calendarScroll']",
        "div[class*='calendar-container']",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_visible():
                continue
            moved = locator.evaluate(
                """(el, delta) => {
                    if (!(el instanceof HTMLElement)) return false;
                    const before = el.scrollLeft;
                    el.scrollBy({ left: delta, behavior: 'auto' });
                    return el.scrollLeft !== before;
                }""",
                dx,
            )
            if moved:
                page.wait_for_timeout(250)
                return True
    return False


def _step_selected_calendar_day(page, forward: bool = True) -> bool:
    """Advance selection by one day from the currently selected calendar cell."""
    selected_selectors = [
        "div.cal-item-container.today",
        "div.cal-item-container.active",
        "div.cal-item-container.selected",
        "[aria-selected='true']",
    ]

    for selector in selected_selectors:
        selected = page.locator(selector).first
        with suppress(Exception):
            if selected.count() == 0 or not selected.is_visible():
                continue
            clicked = selected.evaluate(
                """(el, dir) => {
                    const findCell = (node) => {
                        if (!node) return null;
                        if (node.classList && node.classList.contains('cal-item-container')) return node;
                        return node.closest ? node.closest('.cal-item-container') : null;
                    };
                    const startCell = findCell(el);
                    if (!startCell) return false;
                    const item = startCell.closest('.cal-item') || startCell.parentElement;
                    if (!item) return false;

                    const sibling = dir > 0 ? item.nextElementSibling : item.previousElementSibling;
                    if (!sibling) return false;
                    const target = sibling.querySelector('.cal-item-container') || sibling;
                    if (!(target instanceof HTMLElement)) return false;
                    target.click();
                    return true;
                }""",
                1 if forward else -1,
            )
            if clicked:
                page.wait_for_timeout(250)
                return True
    return False


def _navigate_calendar_to_target(page, target_date: datetime, max_steps: int = 28) -> bool:
    """Deterministically walk day-by-day until the selected date reaches target_date."""
    target = target_date.date()
    for step in range(max_steps):
        current = _read_selected_schedule_date(page)
        if current and current.date() == target:
            _save_debug_screenshot(page, "target_date_header_matched")
            return True

        forward = True
        if current:
            forward = current.date() < target

        _save_debug_screenshot(page, f"calendar_nav_attempt_{step + 1}")

        progressed = _step_selected_calendar_day(page, forward=forward)
        if not progressed:
            progressed = _scroll_calendar_strip(page, forward=forward)
        if not progressed:
            # Last resort: try existing nudge controls.
            progressed = _nudge_calendar(page, target_date, aggressive=False)

        if not progressed:
            page.wait_for_timeout(300)
            continue

        with suppress(Exception):
            _wait_for_session_reload(page, timeout_ms=5000)
        page.wait_for_timeout(250)

    return False


def _scroll_session_list(page, pixels: int = 900) -> None:
    """Scroll the sessions container first; fall back to page wheel if needed."""
    scrollers = [
        ".SessionPickerCalendar_calendarScroll__",
        "div[class*='calendarScroll']",
        "div[class*='sessionList']",
    ]

    for selector in scrollers:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() == 0 or not locator.is_visible():
                continue
            moved = locator.evaluate(
                """(el, amount) => {
                    if (!(el instanceof HTMLElement)) return false;
                    const before = el.scrollTop;
                    el.scrollBy(0, amount);
                    return el.scrollTop !== before;
                }""",
                pixels,
            )
            if moved:
                return

    page.mouse.wheel(0, pixels)


def _ensure_target_day_locked(page, target_date: datetime, retries: int = 3) -> None:
    """Guard against calendar snap-back by continuously re-locking target day."""
    for _ in range(retries):
        if _is_target_day_selected(page, target_date):
            return
        if _calendar_reset_detected(page, target_date):
            print("↩️ Calendar jumped to today — restoring target date.")
            _select_target_day(page, target_date)
        try:
            _wait_for_day_lock(page, target_date, timeout=2500)
            return
        except PlaywrightTimeout:
            print("🔁 Target day lock lost — reselecting target date.")
            _select_target_day(page, target_date)
    raise RuntimeError("Target date lock could not be maintained.")


def _assert_target_day_before_book(page, target_date: datetime) -> None:
    """Hard gate: never click BOOK unless the target day is still selected."""
    _assert_exact_target_day(page, target_date)
    _ensure_target_day_locked(page, target_date, retries=2)
    try:
        _wait_for_day_lock(page, target_date, timeout=2000)
        _assert_exact_target_day(page, target_date)
    except PlaywrightTimeout as exc:
        _save_debug_screenshot(page, "target_day_assert_failed")
        raise RuntimeError("Target day assertion failed immediately before BOOK click.") from exc


def _row_cta_text(row) -> str:
    """Return normalized CTA text for the session row."""
    cta_selectors = [
        "div.session-card_sessionCardBtn__FQT3Z",
        "button",
        "a",
    ]
    for selector in cta_selectors:
        locator = row.locator(selector)
        with suppress(Exception):
            count = locator.count()
            for i in range(count):
                text = (locator.nth(i).inner_text(timeout=400) or "").strip()
                text = re.sub(r"\s+", " ", text).lower()
                if text:
                    return text
    return ""


def _row_has_forbidden_status(text_norm: str) -> bool:
    forbidden = [
        "booked",
        "waitlisted",
        "join waitlist",
        "session started",
        "class full",
        "cancel class",
    ]
    return any(token in text_norm for token in forbidden)


def _cancel_modal_present(page) -> bool:
    """Detect cancel confirmation dialog and avoid destructive action."""
    modal = page.locator("div.cpy-modal:has-text('Are you sure you want to cancel')").first
    with suppress(Exception):
        return modal.count() > 0 and modal.is_visible()
    return False


def _dismiss_cancel_modal_safe(page) -> bool:
    """Always prefer keeping reservation when cancel modal appears."""
    if not _cancel_modal_present(page):
        return False
    keep_selectors = [
        "div.cpy-modal button:has-text('KEEP RESERVATION')",
        "div.cpy-modal div:has-text('KEEP RESERVATION')",
    ]
    for selector in keep_selectors:
        locator = page.locator(selector).first
        with suppress(Exception):
            if locator.count() > 0 and locator.is_visible():
                locator.click()
                page.wait_for_timeout(250)
                return True
    return False


def _select_target_day(page, target_date: datetime) -> None:
    """Click the desired calendar day and re-assert selection if the UI jumps."""
    day_label = target_date.strftime('%a')
    reload_reselect_done = False

    if _navigate_calendar_to_target(page, target_date, max_steps=28):
        with suppress(PlaywrightTimeout):
            _wait_for_day_lock(page, target_date, timeout=2500)
        print(f"✅ Reached target calendar day via deterministic navigation: {target_date.strftime('%a, %b %d')}")
        return

    for attempt in range(5):
        locator = _find_calendar_day(page, target_date)
        if locator is None:
            print("🔎 Target day not visible — nudging calendar…")
            if not _nudge_calendar(page, target_date, aggressive=True):
                print("⚠️ Could not navigate calendar to target day yet.")
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
        reload_observed = _wait_for_session_reload(page, timeout_ms=9000)

        if _calendar_reset_detected(page, target_date):
            if not reload_reselect_done:
                reload_reselect_done = True
                print("↩️ Calendar reloaded, reselecting target date")
            else:
                print("↩️ Calendar reset to today — re-selecting target date…")
            _nudge_calendar(page, target_date, aggressive=True)
            page.wait_for_timeout(300)
            continue
        try:
            _wait_for_day_lock(page, target_date)
            if reload_observed:
                print("✅ Calendar stable after reload")
            _save_debug_screenshot(page, "date_locked")
            print(f"✅ Clicked calendar date {target_date.day} ({day_label}).")
            return
        except PlaywrightTimeout:
            if _calendar_reset_detected(page, target_date):
                print(f"↩️ Calendar reset detected (attempt {attempt + 1}/5) — recovering target date…")
            else:
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
    _scroll_session_list(page, 800)
    page.wait_for_timeout(200)
    _scroll_session_list(page, 800)
    print("🖱️ Primed session list scroll for selected day.")


def _ensure_studio_filter(page, studio_name: str) -> None:
    """Best-effort studio filter setup to reduce cross-studio noise."""
    chip = page.locator(f"text={studio_name}").first
    with suppress(Exception):
        if chip.count() > 0 and chip.is_visible():
            print(f"✅ Studio filter already set: {studio_name}")
            return

    with suppress(Exception):
        page.locator("button:has-text('Filter')").first.click(timeout=2000)
        page.wait_for_timeout(500)
        option = page.locator(f"text={studio_name}").first
        if option.count() > 0 and option.is_visible():
            option.click()
            with suppress(Exception):
                page.locator("button:has-text('Apply')").first.click(timeout=1000)
            with suppress(Exception):
                page.locator("button:has-text('Done')").first.click(timeout=1000)
            page.wait_for_timeout(800)
            print(f"✅ Applied studio filter: {studio_name}")
            return

    print(f"⚠️ Could not confirm studio filter '{studio_name}' in UI.")


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
    execute_booking = (os.getenv("EXECUTE_BOOKING", "false").strip().lower() in {"1", "true", "yes", "y"})
    print(f"📅 Target date: {target_date.strftime('%A, %b %d')} (13 days from today)")
    print(f"🧪 Mode: {'EXECUTE' if execute_booking else 'DRY RUN'}")

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

                # Go directly to schedule view for stability.
                try:
                    page.goto(
                        "https://www.corepoweryoga.com/yoga-schedules/studio",
                        timeout=60000,
                        wait_until="domcontentloaded",
                    )
                    # Avoid networkidle on this page because long polling can keep the network busy.
                    with suppress(Exception):
                        page.locator("div.schedule-page").first.wait_for(state="visible", timeout=20000)
                    with suppress(Exception):
                        page.locator("div.schedule-calendar").first.wait_for(state="visible", timeout=20000)
                    _wait_for_calendar_strip(page, timeout_ms=15000)
                    page.wait_for_timeout(1500)
                    print("✅ Opened studio schedule page directly.")
                    _ensure_studio_filter(page, "Flatiron")
                except Exception as e:
                    _save_debug_screenshot(page, "book_class_button_error")
                    raise RuntimeError(f"Schedule navigation error: {e}") from e

                page.wait_for_timeout(1000)

                # Pick date + scroll-lock
                try:
                    _select_target_day(page, target_date)
                    _ensure_target_day_locked(page, target_date)
                    _assert_exact_target_day(page, target_date)
                    _prime_session_scroll(page)
                except Exception as e:
                    _save_debug_screenshot(page, "date_select_error")
                    raise RuntimeError(f"Date select error: {e}") from e

                # Locate target class and book
                try:
                    rows = page.locator("div.session-row-view")
                    TARGET_CLASS_LOCAL = (os.getenv("TARGET_CLASS_TIME_UTC") or "11:15 PM").strip()
                    print(f"🕒 Target time (UTC): {TARGET_CLASS_LOCAL}")
                    target_time_token = re.sub(r"\s+", "", TARGET_CLASS_LOCAL.lower())

                    def find_row():
                        for attempt in range(26):
                            if attempt % 4 == 0:
                                _ensure_target_day_locked(page, target_date, retries=1)
                            elif not _is_target_day_selected(page, target_date):
                                _ensure_target_day_locked(page, target_date, retries=1)
                            _assert_exact_target_day(page, target_date)

                            row_count = rows.count()
                            if row_count == 0:
                                _scroll_session_list(page, 900)
                                page.wait_for_timeout(300)
                                continue

                            for i in range(rows.count()):
                                try:
                                    text = rows.nth(i).inner_text(timeout=1000).lower()
                                    text_norm = re.sub(r"\s+", " ", text).strip()
                                    time_norm = re.sub(r"\s+", "", text_norm)
                                    if (
                                        "ys - yoga sculpt" in text_norm
                                        and "flatiron" in text_norm
                                        and target_time_token in time_norm
                                    ):
                                        if _row_has_forbidden_status(text_norm):
                                            print("⛔ Matched row has forbidden status; skipping.")
                                            continue
                                        cta_text = _row_cta_text(rows.nth(i))
                                        if cta_text != "book":
                                            print(f"⛔ Matched row CTA is '{cta_text}', not 'book'; skipping.")
                                            continue
                                        return rows.nth(i)
                                except:
                                    continue
                            _scroll_session_list(page, 900)
                            page.wait_for_timeout(300)
                        return None

                    row = find_row()
                    if row is None:
                        _save_debug_screenshot(page, "target_class_not_found")
                        raise RuntimeError("Target class not found on target date.")
                    row.scroll_into_view_if_needed()
                    print("✅ Scrolled to target class row.")

                    book = row.locator("div.session-card_sessionCardBtn__FQT3Z").filter(
                        has_text=re.compile(r"^\s*BOOK\s*$", re.IGNORECASE)
                    ).first
                    if book.count() == 0:
                        book = row.locator("button, div").filter(
                            has_text=re.compile(r"^\s*BOOK\s*$", re.IGNORECASE)
                        ).first
                    try:
                        _assert_target_day_before_book(page, target_date)
                        if _cancel_modal_present(page):
                            _dismiss_cancel_modal_safe(page)
                            raise RuntimeError("Cancel modal was already open before booking click.")

                        if not execute_booking:
                            print("🧪 Dry run complete — BOOK click skipped (set EXECUTE_BOOKING=true to execute).")
                        else:
                            if book.count() == 0:
                                raise RuntimeError("Exact 'BOOK' CTA not found on matched row.")
                            book.evaluate("el => el.click()")
                            page.wait_for_timeout(800)
                            if _cancel_modal_present(page):
                                _dismiss_cancel_modal_safe(page)
                                _save_debug_screenshot(page, "cancel_modal_intercepted")
                                raise RuntimeError("Cancel modal appeared after click; reservation preserved.")
                            print("✅ Clicked BOOK button.")
                    except Exception as e:
                        _save_debug_screenshot(page, "book_click_failed")
                        raise RuntimeError(f"BOOK click failed: {e}") from e
                except Exception as e:
                    raise RuntimeError(f"Booking error: {e}") from e

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
