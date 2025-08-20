from playwright.sync_api import sync_playwright
import time

AUTH_FILE = "linkedin_auth.json"
LOGIN_URL = "https://www.linkedin.com/login"

def save_auth_state():
    with sync_playwright() as p:
        print("🚀 Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        page = context.new_page()
        print("🔐 Opening LinkedIn login page...")
        page.goto(LOGIN_URL)

        print("👉 Please complete login manually in the browser window.")
        print("✅ After logging in, DO NOT close the window manually.")
        input("⏳ Press Enter here **after** you're fully logged in and on your feed...")

        print("💾 Saving authentication state...")
        context.storage_state(path=AUTH_FILE)
        print(f"✅ Auth state saved to {AUTH_FILE}")

        browser.close()

if __name__ == "__main__":
    save_auth_state()
