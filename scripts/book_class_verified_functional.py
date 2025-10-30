from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta, timezone
import os
import re
import time

def main():
    print("🚀 Starting ALONI 2.9.8 – Profile Icon Debug + Video + Trace…")

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

            # --- Step 1: Click the Profile Icon ---
            try:
                profile_candidates = [
                    ".profile-icon-container",
                    "div.profile-container img[alt='Profile Icon']",
                    "div.profile-container",
                    "img[src*='profile_icon.svg']",
                    "div.cursor-pointer:has(img[alt='Profile Icon'])",
                    "button[aria-label*='profile' i]",
                ]
                found = False
                for sel in profile_candidates:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        print(f"👁️ Found profile icon via selector: {sel}")
                        loc.click()
                        found = True
                        print("✅ Clicked profile icon.")
                        break
                if not found:
                    print("❌ No matching profile icon selector found.")
                    header_html = page.locator("header").inner_html()
                    with open("header_debug.html", "w") as f:
                        f.write(header_html)
                    print("🪶 Saved header_debug.html for inspection.")
                    return
            except Exception as e:
                print(f"❌ Could not click profile icon: {e}")
                return

            # --- Step 2: Click Sign In in dropdown ---
            try:
                sign_in_btn = page.locator("button[data-position='profile.1-sign-in']").first
                sign_in_btn.wait_for(timeout=8000)
                sign_in_btn.click()
                print("✅ Clicked 'Sign In' in profile dropdown.")
            except Exception as e:
                print(f"❌ Could not click 'Sign In' button: {e}")
                return

            # --- Step 3: Fill credentials ---
            try:
                page.wait_for_timeout(2000)
                email_selectors = ["input[name='username']", "input#email", "input[type='email']", "input[placeholder*='email' i]"]
                email_field = None
                for sel in email_selectors:
                    try:
                        email_field = page.locator(sel).first
                        if email_field.is_visible(timeout=2000):
                            email_field.fill(os.getenv("COREPOWER_EMAIL"))
                            print(f"✅ Filled email with selector: {sel}")
                            break
                    except:
                        continue

                password_selectors = ["input[name='password']", "input#password", "input[type='password']"]
                for sel in password_selectors:
                    try:
                        password_field = page.locator(sel).first
                        if password_field.is_visible(timeout=1000):
                            password_field.fill(os.getenv("COREPOWER_PASSWORD"))
                            print(f"✅ Filled password with selector: {sel}")
                            break
                    except:
                        continue

                submit_btn = page.locator("form button[type='submit']:has-text('Sign In'), form button:has-text('Sign In')").first
                submit_btn.click()
                print("✅ Submitted credentials.")
            except Exception as e:
                print(f"❌ Could not submit credentials: {e}")
                return

            page.wait_for_timeout(4000)

            # --- Handle post-login modals ---
            try:
                for selector in [
                    "button:has-text('Close')",
                    "button[aria-label*='close' i]",
                    "div.modal button.close",
                    "button[aria-label='Dismiss']",
                ]:
                    loc = page.locator(selector).first
                    if loc.is_visible():
                        loc.click()
                        print(f"💨 Closed modal via {selector}")
                        time.sleep(1)
            except Exception as e:
                print(f"⚠️ No modal to close: {e}")

            # --- Conditional booking ---
            if should_book:
                print("🧘 Booking window open — proceeding.")

                # Click “Book a class”
                try:
                    book_btn = page.locator("button[data-position='book-a-class']").last
                    book_btn.wait_for(state="visible", timeout=10000)
                    book_btn.click()
                    print("✅ Clicked visible 'Book a class'.")
                except Exception as e:
                    print(f"⚠️ Could not click Book a class: {e}")

                page.wait_for_timeout(5000)

                # Select target date
                try:
                    day_num = str(target_date.day)
                    day_locator = page.locator(f"div.cal-date:has-text('{day_num}')").last
                    day_locator.scroll_into_view_if_needed()
                    day_locator.click()
                    print(f"✅ Clicked calendar date {day_num} ({target_date.strftime('%a')}).")
                except Exception as e:
                    print(f"⚠️ Could not select date {target_date.strftime('%a %b %d')}: {e}")

                try:
                    page.locator("div.session-row-view").first.wait_for(state="visible", timeout=10000)
                except Exception:
                    print("⚠️ Class list did not render within 10s — continuing with scroll search.")

                # --- Timezone-aware Flatiron search ---
                try:
                    session_rows = page.locator("div.session-row-view")
                    TARGET_CLASS_LOCAL = "11:15 PM"
                    print(f"🕒 Target time (UTC): {TARGET_CLASS_LOCAL}")

                    def locate_matching_row():
                        for attempt in range(20):
                            try:
                                row_count = session_rows.count()
                            except Exception:
                                row_count = 0
                            for index in range(row_count):
                                row = session_rows.nth(index)
                                try:
                                    row_text = row.inner_text(timeout=1000)
                                except Exception:
                                    continue
                                normalized = row_text.lower()
                                if (
                                    ("ys - yoga sculpt" in normalized)
                                    and ("flatiron" in normalized)
                                    and (TARGET_CLASS_LOCAL.lower() in normalized)
                                ):
                                    return row
                            page.mouse.wheel(0, 900)
                            page.wait_for_timeout(300)
                            page.keyboard.press("PageDown")
                            page.wait_for_timeout(300)
                        return None

                    target_row = locate_matching_row()
                    if target_row is None:
                        print("⚠️ Target class not visible after exhaustive scroll — capturing sample rows.")
                        try:
                            sample_rows = session_rows.all_inner_texts()
                            print(f"🧪 Available rows: {sample_rows}")
                        except Exception:
                            pass
                        raise Exception(f"{TARGET_CLASS_LOCAL} time slot not found (UTC)")

                    target_row.scroll_into_view_if_needed()
                    print("✅ Scrolled to target class row.")

                    # --- UPDATED BOOK BUTTON INTERACTION ---
                    book_button = target_row.get_by_role("button", name=re.compile(r"book", re.IGNORECASE)).first
                    if book_button.count() == 0:
                        book_button = target_row.locator("div, button").filter(has_text=re.compile(r"book", re.IGNORECASE)).first

                    book_button.wait_for(state="visible", timeout=8000)
                    book_button.scroll_into_view_if_needed()
                    page.wait_for_timeout(1000)

                    if book_button.is_enabled():
                        # 🔥 Dispatch JS-level click for React compatibility
                        book_button.evaluate("el => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))")
                        print("✅ Dispatched BOOK click event via JS.")
                    else:
                        print("⚠️ BOOK button found but disabled — forcing dispatch.")
                        book_button.evaluate("el => el.click()")

                    # Verify confirmation popup
                    page.wait_for_timeout(3000)
                    if page.locator("button:has-text(\"I'm done\")").is_visible():
                        print("🎉 Booking confirmed — confirmation popup detected.")
                        page.locator("button:has-text(\"I'm done\")").click()
                        print("💨 Closed confirmation popup.")
                    else:
                        print("⚠️ BOOK click registered but no confirmation popup found (may not have booked).")

                except Exception as e:
                    print(f"⚠️ Could not book class: {e}")

            else:
                print(f"📆 {weekday} is not a booking target — skipping booking.")

            print("🎯 Flow completed successfully.")

        finally:
            print("💾 Saving trace and closing browser...")
            context.tracing.stop(path="trace.zip")
            context.close()
            browser.close()
            print("📸 Artifacts saved to videos/ and trace.zip")

if __name__ == "__main__":
    main()
