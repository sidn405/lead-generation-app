from pathlib import Path
from playwright.sync_api import sync_playwright
import json
import os

AUTH_FILE = "youtube_auth.json"

def get_chrome_profile_path():
    """Get the default Chrome profile path for different operating systems"""
    import platform
    
    system = platform.system()
    if system == "Windows":
        return os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
    elif system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:  # Linux
        return os.path.expanduser("~/.config/google-chrome")

def save_auth_state_with_existing_profile():
    """Use existing Chrome profile if available"""
    chrome_path = get_chrome_profile_path()
    
    if os.path.exists(chrome_path):
        print(f"🔍 Found Chrome profile at: {chrome_path}")
        print("📝 This method will use your existing Chrome profile")
        
        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(
                    chrome_path,
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--no-first-run'
                    ]
                )
                
                page = context.new_page()
                
                print("🔐 Opening YouTube...")
                page.goto("https://www.youtube.com")
                
                print("👉 Please make sure you're logged into YouTube in this browser.")
                print("✅ If not logged in, please log in now.")
                input("⏳ Press Enter here **after** you're logged into YouTube...")
                
                print("💾 Saving authentication state...")
                context.storage_state(path=AUTH_FILE)
                print(f"✅ Auth state saved to {AUTH_FILE}")
                
                context.close()
                return True
                
            except Exception as e:
                print(f"❌ Error with existing profile: {e}")
                return False
    else:
        print("❌ Chrome profile not found at expected location")
        return False

def save_auth_state_manual():
    """Manual cookie extraction method"""
    print("\n🍪 Manual Cookie Extraction Method")
    print("=" * 50)
    print("Since automated login is blocked, let's extract cookies manually:")
    print()
    print("1. Open Chrome and go to https://www.youtube.com")
    print("2. Log into your YouTube account")
    print("3. Press F12 to open Developer Tools")
    print("4. Go to the 'Application' tab")
    print("5. Click 'Cookies' in the left sidebar")
    print("6. Click on 'https://www.youtube.com'")
    print("7. Look for these important cookies:")
    print("   - VISITOR_INFO1_LIVE")
    print("   - YSC") 
    print("   - SAPISID")
    print("   - HSID")
    print("   - SSID")
    print("   - APISID")
    print("   - SID")
    print()
    
    cookies = []
    
    print("📝 Please enter the cookie values (press Enter to skip any):")
    
    cookie_names = [
        "VISITOR_INFO1_LIVE",
        "YSC", 
        "SAPISID",
        "HSID", 
        "SSID",
        "APISID",
        "SID"
    ]
    
    for cookie_name in cookie_names:
        value = input(f"  {cookie_name}: ").strip()
        if value:
            cookies.append({
                "name": cookie_name,
                "value": value,
                "domain": ".youtube.com",
                "path": "/",
                "httpOnly": "SID" in cookie_name or "HSID" in cookie_name,
                "secure": True,
                "sameSite": "None"
            })
    
    if cookies:
        auth_data = {
            "cookies": cookies,
            "origins": [
                {
                    "origin": "https://www.youtube.com",
                    "localStorage": []
                }
            ]
        }
        
        with open(AUTH_FILE, 'w') as f:
            json.dump(auth_data, f, indent=2)
        
        print(f"✅ Manually created {AUTH_FILE} with {len(cookies)} cookies")
        return True
    else:
        print("❌ No cookies provided")
        return False

def main():
    print("🔐 YouTube Authentication Setup")
    print("=" * 40)
    print()
    print("Choose authentication method:")
    print("1. Use existing Chrome profile (recommended)")
    print("2. Manual cookie extraction")
    print("3. Try improved automated login")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        success = save_auth_state_with_existing_profile()
        if not success:
            print("\n⚠️ Existing profile method failed. Try option 2 (manual) or 3 (automated).")
    
    elif choice == "2":
        success = save_auth_state_manual()
    
    elif choice == "3":
        # Use the improved automated method
        from save_youtube_auth_state import save_auth_state
        try:
            save_auth_state()
            success = True
        except Exception as e:
            print(f"❌ Automated login failed: {e}")
            success = False
    
    else:
        print("❌ Invalid choice")
        return
    
    if success:
        print(f"\n🎉 Authentication setup complete!")
        print(f"📁 You can now run: python youtube_scraper.py")
    else:
        print(f"\n⚠️ Authentication setup failed. Try a different method.")

if __name__ == "__main__":
    main()