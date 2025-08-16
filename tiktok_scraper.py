from datetime import datetime, timedelta
import time
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import csv
import re
import random
from dm_sequences import generate_dm_with_fallback

# Import the centralized usage tracker
from usage_tracker import setup_scraper_with_limits, finalize_scraper_results

# 🚀 NEW: Import the enhanced config system
from config_loader import ConfigLoader, should_exclude_account, get_platform_config

# 🚀 Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

PLATFORM_NAME = "tiktok"

# Load TikTok session state
try:
    with open("tiktok_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("❌ tiktok_auth.json not found!")
    exit(1)

# Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('tiktok')

# Extract config values
SEARCH_TERM = config["search_term"]
MAX_SCROLLS = config["max_scrolls"]
DELAY_MIN = config.get("delay_min", 3)  # Longer delays for TikTok
DELAY_MAX = config.get("delay_max", 8)
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45)
LEAD_OUTPUT_FILE = config["lead_output_file"]

# 🚀 NEW: Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")  # Can be: keep_all, session_only, smart_user_aware, aggressive
SAVE_RAW_LEADS = config.get("save_raw_leads", True)  # Always save raw leads to separate file

# 🚀 NEW: Show excluded accounts info
excluded_accounts = config_loader.get_excluded_accounts('tiktok')
print(f"📋 TikTok Config Loaded:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  ⏱️ Delay Range: {DELAY_MIN}-{DELAY_MAX}s")
print(f"  📁 Output File: {LEAD_OUTPUT_FILE}")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")


def check_last_run_time():
    """Check if enough time has passed since last TikTok scraper run"""
    try:
        with open("tiktok_last_run.json", "r") as f:
            data = json.load(f)
            last_run = datetime.fromisoformat(data["last_run"])
            
        time_since_last = datetime.now() - last_run
        min_wait_time = timedelta(hours=2)  # Wait 2 hours between TikTok runs
        
        if time_since_last < min_wait_time:
            remaining = min_wait_time - time_since_last
            print(f"⚠️ TikTok cooldown active. Wait {remaining} before running again.")
            print(f"💡 Try alternating with Instagram or Facebook scraper instead!")
            return False, remaining
        
        return True, None
        
    except FileNotFoundError:
        # First run, create the file
        return True, None

def update_last_run_time():
    """Update the last run time for TikTok scraper"""
    data = {"last_run": datetime.now().isoformat()}
    with open("tiktok_last_run.json", "w") as f:
        json.dump(data, f)

def handle_tiktok_simple(page):
    """SIMPLE: Wait for page to load, then click 'try again' if it exists"""
    print("⏳ Waiting 3 seconds for page to fully load...")
    time.sleep(3)  # Give page time to render the "try again" button
    
    print("🔍 Looking for 'try again' button...")
    
    try:
        # Look for try again button
        retry_selectors = [
            'button:has-text("Try again")',
            'button:has-text("Retry")', 
            'button:has-text("try again")',
            '[data-e2e="retry"]'
        ]
        
        for selector in retry_selectors:
            try:
                button = page.query_selector(selector)
                if button and button.is_visible():
                    print(f"🖱️ Found 'try again' button - clicking it")
                    button.click()
                    time.sleep(3)  # Wait for results page to load
                    print("✅ Button clicked - results page should be loading")
                    return True
            except:
                continue
                
        print("✅ No 'try again' button found - already on results page")
        return True
        
    except Exception as e:
        print(f"⚠️ Error checking for button: {e}")
        return True  # Continue anyway



def extract_tiktok_profiles(page):
    """Extract TikTok profiles - FIXED: No unnecessary bot detection checks"""
    print("📋 Extracting TikTok profiles...")
    
    results = []
    excluded_count = 0  # ✅ ADD THIS
    
    # REMOVED: Unnecessary bot detection check - if we're here, we're ready to extract
    # Wait for content to load
    time.sleep(DELAY_MIN)
    
    # Take screenshot for debugging
    try:
        page.screenshot(path="tiktok_extraction_debug.png", timeout=5000)
        print("📸 Debug screenshot: tiktok_extraction_debug.png")
    except:
        pass
    
    # TikTok-specific extraction approaches
    approaches = [
        {
            'name': 'User Profile Cards',
            'selector': '[data-e2e="search-user-item"], [data-e2e="user-item"]',
            'description': 'TikTok user profile cards'
        },
        {
            'name': 'Profile Links',
            'selector': 'a[href*="/@"]',
            'description': 'TikTok profile links'
        },
        {
            'name': 'User Containers',
            'selector': 'div[class*="user" i], div[class*="profile" i]',
            'description': 'User profile containers'
        },
        {
            'name': 'Avatar Links',
            'selector': 'a[href*="tiktok.com/@"]',
            'description': 'Avatar profile links'
        }
    ]
    
    for approach in approaches:
        print(f"\n🔍 Trying: {approach['name']}")
        
        try:
            elements = page.query_selector_all(approach['selector'])
            print(f"  Found {len(elements)} elements")
            
            if len(elements) == 0:
                continue
            
            approach_results = []
            max_elements = min(200, len(elements))  # Conservative limit for TikTok
            
            for i, element in enumerate(elements[:max_elements]):
                try:
                    # Get text content
                    text_content = element.inner_text()
                    if not text_content or len(text_content.strip()) < 3:
                        continue
                    
                    text_content = text_content.strip()
                    
                    # Extract username and profile info
                    username = ""
                    profile_url = ""
                    
                    # Try to get href first
                    try:
                        href = element.get_attribute('href')
                        if href and '/@' in href:
                            # Extract username from TikTok URL
                            match = re.search(r'/@([a-zA-Z0-9_.]{1,24})', href)
                            if match:
                                username = match.group(1)
                                profile_url = href
                    except:
                        pass
                    
                    # If no username from URL, try from text
                    if not username:
                        lines = text_content.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.startswith('@'):
                                username = line[1:]  # Remove @
                                profile_url = f"https://www.tiktok.com/@{username}"
                                break
                            elif len(line) > 2 and len(line) < 25 and line.replace('_', '').replace('.', '').isalnum():
                                username = line
                                profile_url = f"https://www.tiktok.com/@{username}"
                                break
                    
                    if not username:
                        continue

                    handle = f"@{username}"
                    
                    # ✅ ADD EXCLUSION CHECK
                    if should_exclude_account(username, PLATFORM_NAME, config_loader):
                        excluded_count += 1
                        continue

                    # Create display name
                    name = username.replace('_', ' ').replace('.', ' ').title()
                    
                    # Create bio
                    bio_lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    bio = f"TikTok creator interested in {SEARCH_TERM}"
                    for line in bio_lines:
                        if (len(line) > 10 and 
                            not line.startswith('@') and
                            'followers' not in line.lower() and
                            'following' not in line.lower()):
                            bio = line[:200]
                            break
                    
                    # Create lead
                    lead = {
                        "name": name,
                        "handle": handle,
                        "bio": bio,
                        "url": profile_url,
                        "platform": "tiktok",
                        "title": f"TikTok creator interested in {SEARCH_TERM}",
                        "location": "Location not specified",
                        "followers": "Followers not shown",
                        "profile_url": profile_url,
                        "search_term": SEARCH_TERM,
                        "extraction_method": approach['name']
                    }
                    
                    lead["dm"] = generate_dm_with_fallback(
                        name=lead["name"],
                        bio=lead["bio"],
                        platform=lead["platform"]
                    )
                    
                    approach_results.append(lead)
                    print(f"  ✅ {name} | {handle}")
                    
                except Exception as e:
                    continue
            
            if approach_results:
                print(f"✅ {approach['name']}: {len(approach_results)} leads")
                results.extend(approach_results)
            else:
                print(f"❌ No leads from {approach['name']}")
                
        except Exception as e:
            print(f"⚠️ Error with {approach['name']}: {str(e)[:100]}...")
            continue
    
    # Remove duplicates
    if results:
        unique_results = []
        seen_handles = set()
        for result in results:
            handle_key = result['handle'].lower().strip()
            if handle_key not in seen_handles:
                unique_results.append(result)
                seen_handles.add(handle_key)
        
        print(f"\n📊 Total unique profiles: {len(unique_results)}")
        return unique_results
    else:
        print(f"\n❌ No profiles extracted")
        return []

def main():
    """Main TikTok scraper with smart user-aware deduplication"""
    
    estimated_leads = MAX_SCROLLS * 3  # Conservative for TikTok
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    # Update last run time
    update_last_run_time()
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print("🔐 Launching TikTok scraper with smart bot detection...")
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Handle storage state
        if isinstance(storage_state, list):
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            context.add_cookies(storage_state)
        else:
            context = browser.new_context(
                storage_state=storage_state,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        
        page = context.new_page()
        
        try:
            # Navigate to TikTok search
            search_url = f"https://www.tiktok.com/search/user?q={SEARCH_TERM.replace(' ', '%20')}"
            print(f"🔍 Searching: '{SEARCH_TERM}'")
            print(f"📍 URL: {search_url}")
            
            page.goto(search_url, timeout=EXTRACTION_TIMEOUT * 1000)
            time.sleep(5)
            
            # SIMPLE: Just check for 'try again' button and click it
            handle_tiktok_simple(page)
            
            # FIXED: Simplified scrolling - no bot detection checks during scrolling
            print(f"📜 Scrolling {MAX_SCROLLS} times...")
            for i in range(MAX_SCROLLS):
                print(f"  🔄 Scroll {i + 1}/{MAX_SCROLLS}")
                
                # Slow, human-like scrolling
                page.mouse.wheel(0, 300)
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                
                # Extended pause every 5 scrolls for content loading
                if (i + 1) % 5 == 0:
                    print(f"    ⏳ Content loading pause...")
                    time.sleep(random.uniform(3, 6))
            
            print("⏳ Final content stabilization...")
            time.sleep(8)
            
            # Extract profiles (raw leads)
            raw_leads = extract_tiktok_profiles(page)
            
            if not raw_leads:
                print("❌ No raw leads extracted")
                browser.close()
                return []
            
            # 🚀 APPLY SMART USER-AWARE DEDUPLICATION
            print(f"\n🧠 Applying deduplication strategy: {DEDUP_MODE}")
            print(f"👤 User-specific deduplication for: {username}")
            
            if SMART_DEDUP_AVAILABLE and DEDUP_MODE == "smart_user_aware":
                unique_leads, dedup_stats = process_leads_with_smart_deduplication(
                    raw_leads=raw_leads,
                    username=username,
                    platform=PLATFORM_NAME
                )
            elif SMART_DEDUP_AVAILABLE:
                # Use configuration-based deduplication
                mode_mapping = {
                    "keep_all": DeduplicationMode.KEEP_ALL,
                    "session_only": DeduplicationMode.SESSION_ONLY,
                    "smart_user_aware": DeduplicationMode.SMART_USER_AWARE,
                    "aggressive": DeduplicationMode.AGGRESSIVE
                }
                mode = mode_mapping.get(DEDUP_MODE, DeduplicationMode.SMART_USER_AWARE)
                unique_leads, raw_leads_copy, dedup_stats = apply_deduplication_strategy(
                    raw_leads, username, PLATFORM_NAME, mode
                )
            else:
                # Fallback to simple deduplication
                print("📋 Using basic deduplication (smart dedup not available)")
                unique_leads = []
                seen_handles = set()
                for lead in raw_leads:
                    handle_key = lead.get('handle', '').lower().strip()
                    if handle_key not in seen_handles and len(handle_key) > 1:
                        unique_leads.append(lead)
                        seen_handles.add(handle_key)
                dedup_stats = {"basic": True, "kept": len(unique_leads)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw leads extracted: {len(raw_leads)}")
            print(f"  ✅ Unique leads after dedup: {len(unique_leads)}")
            print(f"  📈 Efficiency: {(len(unique_leads) / len(raw_leads) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            print(f"  📊 Scrolls completed: {MAX_SCROLLS}")
            
            if len(unique_leads) > 100:
                print(f"🎉 EXCELLENT: {len(unique_leads)} leads (target exceeded!)")
            elif len(unique_leads) > 50:
                print(f"✅ GOOD: {len(unique_leads)} leads")
            elif len(unique_leads) > 25:
                print(f"⚠️ MODERATE: {len(unique_leads)} leads")
            else:
                print(f"⚠️ LOW: {len(unique_leads)} leads")
            
            leads = unique_leads

            # Finalize results with usage tracking
            if leads:
                try:
                    finalized_leads = finalize_scraper_results(PLATFORM_NAME, leads, SEARCH_TERM, username)
                    leads = finalized_leads
                    print("✅ Results finalized and usage tracked")
                except Exception as e:
                    print(f"⚠️ Error finalizing results: {e}")
            
            # Save results to multiple files
            if leads or (raw_leads and SAVE_RAW_LEADS):
                output_file = f"tiktok_leads_{username}_{timestamp}.csv"
                fieldnames = ['name', 'handle', 'bio', 'url', 'platform', 'dm', 'title', 'location', 'followers', 'profile_url', 'search_term', 'extraction_method']
                
                files_saved = []
                
                # Save processed results to main CSV
                if leads:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(leads)
                    files_saved.append(output_file)
                
                # Save raw results if enabled and different from processed
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    raw_filename = f"tiktok_leads_raw_{username}_{timestamp}.csv"
                    with open(raw_filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(raw_leads)
                    files_saved.append(raw_filename)
                    print(f"📋 Raw leads saved to {raw_filename}")
                
                print(f"\n✅ Successfully saved {len(leads)} TikTok leads")
                print(f"🔍 Files saved: {', '.join(files_saved)}")
                
                # Upload to Google Sheets and send email
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    print("📝 Writing to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print("✅ Successfully uploaded to Google Sheets")
                    
                    print("📤 Sending TikTok leads via email...")
                    send_daily_leads_email()
                    print("✅ TikTok leads email sent!")
                    
                except ImportError:
                    print("📦 Export features not available")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show sample results
                if leads:
                    print(f"\n🎉 Sample processed results:")
                    for i, lead in enumerate(leads[:3]):
                        print(f"  {i+1}. {lead['name']} ({lead['handle']})")
                        print(f"     Bio: {lead['bio'][:50]}...")
                        print(f"     URL: {lead.get('url', 'N/A')}")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    
            else:
                print("⚠️ No TikTok profiles extracted")
                leads = []
                
        except Exception as e:
            print(f"🚨 TikTok scraper error: {e}")
            leads = []
        finally:
            print("🔍 Keeping browser open for 3 seconds...")
            time.sleep(3)
            browser.close()
            
        return leads

if __name__ == "__main__":
    print(f"🚀 TikTok Scraper - Smart Deduplication Version")
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"⏱️ Delay range: {DELAY_MIN}-{DELAY_MAX}s")
    print(f"🛠️ SIMPLIFIED APPROACH:")
    print(f"  • Check for 'try again' button") 
    print(f"  • Click it if found")
    print(f"  • Start scrolling immediately")
    print(f"  • No other bot detection complexity")
    print(f"  • Automatic account exclusion from config.json")
    print(f"  • Client-configurable through frontend")
    print(f"  • No hardcoded usernames")
    print(f"  🚀 Smart user-aware deduplication")
    print(f"  📊 Enhanced result tracking")
    print()
    print(f"📜 Max scrolls: {MAX_SCROLLS}")
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print()
    
    results = main()
    
    if results and len(results) >= 50:
        print(f"🎉 TIKTOK SUCCESS: TikTok scraper completed with {len(results)} leads!")
    elif results:
        print(f"✅ TikTok scraper completed with {len(results)} leads")
    else:
        print(f"❌ TikTok scraper completed with 0 leads")