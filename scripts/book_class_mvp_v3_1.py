# scripts/book_class_mvp_v3_1.py

import os
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


def _ci() -> bool:
    return os.getenv("CI") == "true"


def _get_env_or_die(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            "In GitHub, set it under Settings → Secrets and variables → Actions, "
            "then expose it via env: in your workflow."
        )
    return val


def _log(msg: str) -> None:
    print(msg, flush=True)


def _target_date(days_ahead: int = 13) -> datetime:
    return (datetime.now()).date() + timedelta(days=days_ahead)


def main() -> None:
    email = _get_env_or_die("COREPOWER_EMAIL")
    password = _get_env_or_die("COREPOWER_PASSWORD")

    target = _target_date(13)
    _log("🚀 Starting ALONI 2.9.2 – Verified Booking Flow…")
    _log(f"📅 Target date: {target.strftime('%A, %b %d')} (13 days from today)")

    # Headless & speed settings for CI vs local
    headless = True if _ci() else False   # headed locally if you want to watch; headless in CI
    slow_mo = 0 if _ci() else 150

    with sync_playwright() as p:
        # *** CRITICAL FIX: run headless in CI ***
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)

        # Optional: capture artifacts to debug CI runs
        context = browser.new_context(record_video_dir="videos" if _ci() else None)
        page = context.new_page()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        try:
            # ----------------------------
            # YOUR EXISTING FLOW STARTS
            # ----------------------------
            #
            # Keep your existing navigation, cookie banner handling, login,
            # calendar selection, 6:15 PM class selection, booking, etc.
            #
            # Example log markers you likely already use:
            # _log("✅ Login successful")
            # _log(f"ℹ️ Weekday/Time window condition not met for {target}")
            # _log("✅ Booking completed")
            #
            # ----------------------------
            # YOUR EXISTING FLOW ENDS
            # ----------------------------

            _log("✅ Reached end of script without errors")

        except PWTimeoutError as e:
            _log(f"❌ Playwright timeout waiting for an element: {e}")
            raise
        except Exception as e:
            _log(f"❌ Unhandled exception: {e}")
            raise
        finally:
            # Always produce a trace for CI artifact upload
            try:
                context.tracing.stop(path="trace.zip")
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    print("🧘 Starting ALONI automation...")
    try:
        main()
    except Exception as exc:
        # Non-zero exit so GitHub marks job as failed
        print(f"##[error]{exc}")
        sys.exit(1)
