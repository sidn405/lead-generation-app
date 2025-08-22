
# save_tiktok_auth_state.py - Improved Version

import json
import os
from playwright.sync_api import sync_playwright

COOKIES_FILE = "tiktok_auth.json"

def save_authentication():
    """Save TikTok authentication state for the scraper"""
    
    if os.path.exists(COOKIES_FILE):
        print(f"🗑️ Removing old {COOKIES_FILE}...")
        os.remove(COOKIES_FILE)

    with sync_playwright() as p:
        print("🚀 Launching browser for TikTok authentication...")
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        page = context.new_page()
        
        print("🔐 Navigating to TikTok login...")
        page.goto("https://www.tiktok.com/login/phone-or-email/email")

        print("\n" + "="*60)
        print("📋 AUTHENTICATION INSTRUCTIONS:")
        print("="*60)
        print("1. ✅ Log in to TikTok using your credentials")
        print("2. ✅ Complete any 2FA/verification if prompted")
        print("3. ✅ Wait until you can see your TikTok feed/homepage")
        print("4. ✅ Try searching for something to verify you're logged in")
        print("5. ⚠️  DO NOT close the browser window")
        print("="*60)
        
        input("\n⏳ Press ENTER ONLY after you are FULLY logged in and can browse TikTok normally...")

        # Verify login by checking current URL
        current_url = page.url
        print(f"📍 Current URL: {current_url}")
        
        if 'login' in current_url.lower() or 'sign' in current_url.lower():
            print("⚠️ Warning: Still on login page. Make sure you're fully logged in.")
            proceed = input("Continue anyway? (y/N): ").lower().strip()
            if proceed != 'y':
                print("❌ Authentication cancelled")
                browser.close()
                return False

        try:
            # Try to navigate to a user search to test authentication
            print("🧪 Testing authentication by performing a search...")
            page.goto("https://www.tiktok.com/search/user?q=test")
            page.wait_for_timeout(3000)
            
            if 'login' in page.url.lower():
                print("❌ Authentication test failed - redirected to login")
                browser.close()
                return False
            
            print("✅ Authentication test passed!")
            
        except Exception as e:
            print(f"⚠️ Authentication test error: {e}")
            print("Proceeding anyway...")

        # Save both cookies and full storage state
        try:
            # Method 1: Save cookies (for compatibility)
            cookies = context.cookies()
            
            # Method 2: Save full storage state (preferred)
            storage_state = context.storage_state()
            
            # Save the storage state (which includes cookies, local storage, etc.)
            with open(COOKIES_FILE, "w") as f:
                json.dump(storage_state, f, indent=2)

            print(f"✅ Authentication state saved to {COOKIES_FILE}")
            print(f"📊 Saved {len(cookies)} cookies and full storage state")
            
            # Verify the saved file
            with open(COOKIES_FILE, "r") as f:
                saved_data = json.load(f)
                if 'cookies' in saved_data and len(saved_data['cookies']) > 0:
                    print(f"✅ Verification: {len(saved_data['cookies'])} cookies saved successfully")
                else:
                    print("⚠️ Warning: No cookies found in saved file")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving authentication: {e}")
            return False
        finally:
            print("🔍 Keeping browser open for 3 seconds...")
            page.wait_for_timeout(3000)
            browser.close()

def test_authentication():
    """Test if the saved authentication works"""
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ {COOKIES_FILE} not found. Please run save_authentication() first.")
        return False
    
    try:
        with open(COOKIES_FILE, "r") as f:
            storage_state = json.load(f)
        
        print("🧪 Testing saved authentication...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                storage_state=storage_state,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            page.goto("https://www.tiktok.com/search/user?q=fitness")
            page.wait_for_timeout(5000)
            
            if 'login' in page.url.lower():
                print("❌ Authentication test failed - still redirected to login")
                browser.close()
                return False
            else:
                print("✅ Authentication test passed!")
                browser.close()
                return True
                
    except Exception as e:
        print(f"❌ Authentication test error: {e}")
        return False

if __name__ == "__main__":
    print("🎯 TikTok Authentication Setup")
    print("=" * 40)
    
    success = save_authentication()
    
    if success:
        print("\n🧪 Testing the saved authentication...")
        if test_authentication():
            print("\n🎉 SUCCESS! TikTok authentication is ready!")
            print("✅ You can now run tiktok_scraper.py")
        else:
            print("\n❌ Authentication test failed. You may need to try again.")
    else:
        print("\n❌ Failed to save authentication. Please try again.")
    
    print("\n💡 Tips for success:")
    print("   - Make sure you're fully logged in to TikTok")
    print("   - Complete any 2FA verification")
    print("   - Don't use incognito/private browsing")
    print("   - Try refreshing TikTok in the browser before saving")