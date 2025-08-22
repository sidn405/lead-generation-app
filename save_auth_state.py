
from playwright.sync_api import sync_playwright

def save_login_persistent_context():
    with sync_playwright() as p:
        # Launch persistent browser context
        user_data_dir = "twitter_profile"
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            slow_mo=100,
        )
        page = browser.new_page()
        page.goto("https://twitter.com/login")
        print("👉 Log in manually in the opened browser...")

        # Wait up to 2 minutes for login
        page.wait_for_timeout(120000)
        print("✅ Persistent login profile saved.")

        browser.close()

save_login_persistent_context()