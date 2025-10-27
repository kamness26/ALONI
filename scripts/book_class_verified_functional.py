from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import time, os

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
                    ".profile-icon-container",  # Desktop version - the clickable div
                    "div.profile-container img[alt='Profile Icon']",  # The image itself
                    "div.profile-container",  # Parent container
                    "img[src*='profile_icon.svg']",  # By image source
                    "div.cursor-pointer:has(img[alt='Profile Icon'])",  # Mobile version
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
                # Try to find the login form - wait for the form to appear
                page.wait_for_timeout(2000)  # Give dropdown time to expand and show sign-in form
                
                # Find username field with multiple fallbacks
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
                
                # Find password field
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
                
                # Click the form's submit button (not the dropdown button)
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
                page.locator("button[data-position='book-a-class']").click(timeout=5000)
                print("✅ Clicked 'Book a class'.")
                
                # Wait for calendar to load
                page.wait_for_timeout(2000)
                
                # Click the date
                date_str = str(target_date.day)
                page.locator(f"text={date_str}").first.click()
                print(f"✅ Clicked calendar date {date_str} ({weekday[:3]}).")
                
                # Wait for class list to load
                page.wait_for_timeout(3000)
                
                # Scroll to find the specific class (Flatiron 6:15 PM)
                print("💫 Scrolling class list to find Flatiron 6:15 PM...")
                for _ in range(15):
                    page.mouse.wheel(0, 500)
                    time.sleep(0.4)
                    if page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").count() > 0:
                        print("✅ Found Flatiron 6:15 PM class")
                        break
                
                # Click the class session
                try:
                    session = page.locator("div.session-row-view:has-text('6:15 pm'):has-text('Flatiron')").last
                    session.scroll_into_view_if_needed()
                    session.click()
                    print("✅ Clicked Flatiron 6:15 PM session.")
                    
                    # Wait for booking confirmation
                    page.wait_for_timeout(3000)
                    print("🎉 Booking completed!")
                except Exception as e:
                    print(f"⚠️ Could not find or click the class: {e}")
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
