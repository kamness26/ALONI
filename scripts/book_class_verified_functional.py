from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta, timezone
import os, re, time


def main():
    print("🚀 Starting ALONI 2.9.11 – Scroll-Lock Patch…")

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
                try:
                    page.locator(selector).first.click(timeout=3000)
                    print(f"💨 Closed popup via {selector}")
                except:
                    pass

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
                page.locator("input[name='username']").fill(os.getenv("COREPOWER_EMAIL"))
                page.locator("input[name='password']").fill(os.getenv("COREPOWER_PASSWORD"))
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
                    day_num = str(target_date.day)
                    day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
                    day_locator.scroll_into_view_if_needed()
                    day_locator.click()
                    print(f"✅ Clicked calendar date {day_num} ({target_date.strftime('%a')}).")

                    # Scroll to anchor selection
                    page.wait_for_timeout(1000)
                    page.mouse.wheel(0, 2000)
                    page.wait_for_timeout(1000)
                    print("🖱️ Scrolled down to stabilize selected date.")
                except Exception as e:
                    print(f"⚠️ Date select error: {e}")

                # Wait for classes
                try:
                    page.locator("div.session-row-view").first.wait_for(state="visible", timeout=10000)
                except:
                    print("⚠️ Class list timeout.")

                # Locate target class and book
                try:
                    rows = page.locator("div.session-row-view")
                    TARGET_CLASS_LOCAL = "11:15 PM"
                    print(f"🕒 Target time (UTC): {TARGET_CLASS_LOCAL}")

                    def find_row():
                        for _ in range(20):
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
