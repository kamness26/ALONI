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

                  # --- UPDATED BOOK BUTTON INTERACTION (robust for <div> BOOK button) ---
                    book_button = target_row.locator("div.session-card_sessionCardBtn__FQT3Z").first
                    if book_button.count() == 0:
                        # Fallbacks by text and class combo
                        book_button = target_row.locator("div.btn-outline-black.session-card_sessionCardBtn__FQT3Z").first
                    if book_button.count() == 0:
                        book_button = target_row.locator("div:has(.btn-text:has-text('BOOK'))").first
                    
                    book_button.wait_for(state="visible", timeout=8000)
                    book_button.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)  # small settle
                    
                    def confirm_popup_found() -> bool:
                        return (
                            page.locator("button:has-text(\"I'm done\")").first.is_visible(timeout=1000)
                            or page.locator("text=Added to your schedule").first.is_visible(timeout=1000)
                            or page.locator("text=Reservation successful").first.is_visible(timeout=1000)
                        )
                    
                    clicked = False
                    for attempt in range(1, 6):
                        try:
                            # 1) Normal click on the outer div
                            book_button.click(timeout=1500)
                            page.wait_for_timeout(500)
                            if confirm_popup_found():
                                print(f"✅ BOOK clicked (normal) on attempt #{attempt}.")
                                clicked = True
                                break
                        except Exception as e:
                            print(f"ℹ️ Normal click failed attempt #{attempt}: {e}")
                    
                        try:
                            # 2) Force click
                            book_button.click(timeout=1500, force=True)
                            page.wait_for_timeout(500)
                            if confirm_popup_found():
                                print(f"✅ BOOK clicked (force) on attempt #{attempt}.")
                                clicked = True
                                break
                        except Exception as e:
                            print(f"ℹ️ Force click failed attempt #{attempt}: {e}")
                    
                        try:
                            # 3) Click inner text node if present
                            inner = book_button.locator(".btn-text", has_text=re.compile(r"^\s*BOOK\s*$", re.I)).first
                            if inner.count() > 0 and inner.is_visible():
                                inner.click(timeout=1500, force=True)
                                page.wait_for_timeout(500)
                                if confirm_popup_found():
                                    print(f"✅ BOOK clicked via inner .btn-text on attempt #{attempt}.")
                                    clicked = True
                                    break
                        except Exception as e:
                            print(f"ℹ️ Inner .btn-text click failed attempt #{attempt}: {e}")
                    
                        try:
                            # 4) Simulated physical click at element center
                            box = book_button.bounding_box()
                            if box:
                                cx = box["x"] + box["width"] / 2
                                cy = box["y"] + box["height"] / 2
                                book_button.hover(timeout=1000)
                                page.mouse.move(cx, cy)
                                page.mouse.down()
                                page.mouse.up()
                                page.wait_for_timeout(500)
                                if confirm_popup_found():
                                    print(f"✅ BOOK clicked via mouse down/up at center on attempt #{attempt}.")
                                    clicked = True
                                    break
                            else:
                                print("⚠️ No bounding box available; skipping mouse click path.")
                        except Exception as e:
                            print(f"ℹ️ Mouse down/up click failed attempt #{attempt}: {e}")
                    
                        try:
                            # 5) Full React-friendly event dispatch sequence
                            book_button.evaluate("""
                                el => {
                                    const mk = (type) => new MouseEvent(type, {bubbles: true, cancelable: true, view: window, buttons: 1});
                                    const pk = (type) => new PointerEvent(type, {bubbles: true, cancelable: true, pointerType: 'mouse', isPrimary: true, buttons: 1});
                                    el.dispatchEvent(pk('pointerover'));
                                    el.dispatchEvent(mk('mouseover'));
                                    el.dispatchEvent(pk('pointerenter'));
                                    el.dispatchEvent(mk('mouseenter'));
                                    el.dispatchEvent(pk('pointerdown'));
                                    el.dispatchEvent(mk('mousedown'));
                                    el.dispatchEvent(pk('pointerup'));
                                    el.dispatchEvent(mk('mouseup'));
                                    el.dispatchEvent(mk('click'));
                                }
                            """)
                            page.wait_for_timeout(600)
                            if confirm_popup_found():
                                print(f"✅ BOOK clicked via event dispatch on attempt #{attempt}.")
                                clicked = True
                                break
                        except Exception as e:
                            print(f"ℹ️ Event dispatch failed attempt #{attempt}: {e}")
                    
                    if not clicked:
                        print("⚠️ BOOK click attempts exhausted — no confirmation detected.")
                    else:
                        # Close confirmation if present
                        try:
                            done_btn = page.locator("button:has-text(\"I'm done\")").first
                            if done_btn.is_visible():
                                done_btn.click()
                                print("💨 Closed confirmation popup.")
                        except Exception:
                            pass

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
