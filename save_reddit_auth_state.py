
from pathlib import Path
from playwright.sync_api import sync_playwright

AUTH_FILE = "reddit_auth.json"

def save_auth_state():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-dev-shm-usage',
                '--disable-gpu-sandbox',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        # Add extra headers to appear more legitimate
        context.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        page = context.new_page()
        
        # Remove automation indicators
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            window.chrome = {
                runtime: {},
            };
        """)

        print("🔐 Opening Reddit...")
        page.goto("https://www.reddit.com")

        print("👉 Please log into your Reddit account manually in the browser window.")
        print("✅ After logging in, you should see the Reddit homepage.")
        print("💡 Note: Reddit scraping works without login, but login may help with rate limits.")
        input("⏳ Press Enter here **after** you're logged in (or skip login and press Enter)...")

        print("💾 Saving authentication state...")
        context.storage_state(path=AUTH_FILE)
        print(f"✅ Auth state saved to {AUTH_FILE}")

        browser.close()

if __name__ == "__main__":
    save_auth_state()