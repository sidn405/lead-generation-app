import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import csv
import re
from datetime import datetime
import sys
import json
import random
from dm_sequences import generate_dm_with_fallback

# Import the centralized usage tracker
from usage_tracker import setup_scraper_with_limits, finalize_scraper_results

# 🚀 NEW: Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

PLATFORM_NAME = "twitter"

# Use centralized config
from config_loader import ConfigLoader, should_exclude_account, get_platform_config

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = get_platform_config('twitter')

# Extract values from config with fallbacks for missing keys
SEARCH_TERM = config["search_term"]
MAX_SCROLLS = config["max_scrolls"]
OUTPUT_CSV = config["lead_output_file"]

# 🔧 FIX: Make backup_output_file optional
BACKUP_CSV = config.get("backup_output_file", f"backup_twitter_leads_{datetime.now().strftime('%Y%m%d')}.csv")

LOCATION_CSV = config.get("location_csv", "locations.csv")  # Also make this optional
DEFAULT_DM = config["default_dm"]
FALLBACK_DM = config["fallback_dm"]

# Get DM template rules
DM_TEMPLATE_RULES = config_loader.get_dm_templates()

# Human-like timing configurations
HUMAN_DELAYS = {
    'scroll_min': 10,     # Even slower for stealth
    'scroll_max': 20,     # Much longer delays
    'error_pause': 45,    # Longer error pause
    'stability_wait': 8,  # Longer stability wait
    'retry_delay': 30,    # Longer retry delay
    'micro_scroll_delay': 3,  # Slower micro scrolls
    'initial_wait': 15,   # Wait before starting
}

# 🔒 STEALTH CONFIGURATIONS
STEALTH_CONFIG = {
    'user_agents': [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
    ],
    'viewports': [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
        {'width': 1536, 'height': 864}
    ]
}

# 🚀 NEW: Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")  # Can be: keep_all, session_only, smart_user_aware, aggressive
SAVE_RAW_LEADS = config.get("save_raw_leads", True)  # Always save raw leads to separate file

# 🚀 NEW: Dynamic excluded accounts (NO HARDCODING!)
excluded_accounts = config_loader.get_excluded_accounts('twitter')
print("🔒 STEALTH Twitter Scraper Config:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  🛡️ Anti-Detection: MAXIMUM")
print(f"  ⏱️ Delays: {HUMAN_DELAYS['scroll_min']}-{HUMAN_DELAYS['scroll_max']}s")
print(f"  💾 Output CSV: {OUTPUT_CSV}")
print(f"  🔄 Backup CSV: {BACKUP_CSV}")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

# Load locations
try:
    with open(LOCATION_CSV, "r", encoding="utf-8") as loc_file:
        location_list = [line.strip() for line in loc_file if line.strip()]
        print(f"📍 Loaded {len(location_list)} locations")
except FileNotFoundError:
    location_list = []
    print(f"⚠️ Location file not found: {LOCATION_CSV}")

def create_stealth_browser(p):
    """Create browser with maximum stealth settings"""
    print("🔒 Creating stealth browser with anti-detection measures...")
    
    # Random user agent and viewport
    user_agent = random.choice(STEALTH_CONFIG['user_agents'])
    viewport = random.choice(STEALTH_CONFIG['viewports'])
    
    print(f"  👤 User Agent: {user_agent[:50]}...")
    print(f"  📺 Viewport: {viewport['width']}x{viewport['height']}")
    
    # Maximum stealth browser args
    browser_args = [
        #'--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-web-security',
        #'--disable-features=VizDisplayCompositor',
        #'--disable-background-networking',
        #'--disable-background-timer-throttling',
        #'--disable-backgrounding-occluded-windows',
        #'--disable-breakpad',
        #'--disable-client-side-phishing-detection',
        #'--disable-component-extensions-with-background-pages',
        #'--disable-default-apps',
        #'--disable-extensions',
        #'--disable-features=TranslateUI',
        #'--disable-hang-monitor',
        #'--disable-ipc-flooding-protection',
        #'--disable-popup-blocking',
        #'--disable-prompt-on-repost',
        #'--disable-renderer-backgrounding',
        #'--disable-sync',
        #'--force-color-profile=srgb',
        #'--metrics-recording-only',
        #'--no-first-run',
        #'--password-store=basic',
        #'--use-mock-keychain',
        #'--disable-component-update'
    ]
    
    try:
        # Your existing browser creation code...
        browser = p.chromium.launch(headless=True, args=browser_args)
        context = browser.new_context(...)
        
        # Test that everything works
        page = context.new_page()
        print("Page created successfully")
        page.goto("https://twitter.com")
        print("Navigation successful")
        page.close()  # Close test page
        
        print("Returning browser and context")
        return browser, context
        
    except Exception as e:
        print(f"Error in create_stealth_browser: {e}")
        import traceback
        traceback.print_exc()
        return None  # This is likely what's happening

def stealth_delay(min_sec=None, max_sec=None, reason=""):
    """Stealth delays with variation"""
    if min_sec is None:
        min_sec = HUMAN_DELAYS['scroll_min']
    if max_sec is None:
        max_sec = HUMAN_DELAYS['scroll_max']
    
    # Add random variation
    base_delay = random.uniform(min_sec, max_sec)
    variation = random.uniform(-2, 3)  # -2 to +3 seconds random
    delay = max(1, base_delay + variation)
    
    if reason:
        print(f"  🕐 Stealth pause: {delay:.1f}s ({reason})")
    time.sleep(delay)

def detect_blocking(page):
    """Detect if Twitter is blocking us"""
    try:
        current_url = page.url.lower()
        
        # Check URL for blocking indicators
        blocking_urls = [
            'login' in current_url and 'twitter.com' in current_url,
            'challenge' in current_url,
            'suspended' in current_url,
            'help' in current_url,
        ]
        
        if any(blocking_urls):
            print(f"🚨 URL indicates blocking: {current_url}")
            return True
        
        # Check page content
        try:
            page_text = page.inner_text('body', timeout=5000).lower()
            
            blocking_content = [
                'browser not supported' in page_text,
                'something went wrong' in page_text,
                'try again' in page_text,
                'unusual activity' in page_text,
                'rate limit' in page_text,
                'temporarily restricted' in page_text,
                'automated behavior' in page_text,
                'suspicious activity' in page_text,
            ]
            
            if any(blocking_content):
                print(f"🚨 Page content indicates blocking")
                return True
                
        except:
            print(f"⚠️ Could not read page content")
            return True
        
        return False
        
    except Exception as e:
        print(f"⚠️ Error checking blocking: {e}")
        return True

def handle_blocking(page, context, attempt):
    """Handle blocking with recovery strategies"""
    print(f"🚨 Blocking detected (attempt {attempt})")
    
    # Take screenshot
    try:
        page.screenshot(path=f"twitter_blocking_attempt_{attempt}.png")
        print(f"📸 Blocking screenshot saved")
    except:
        pass
    
    if attempt >= 3:
        print("❌ Too many blocking attempts, giving up")
        return False
    
    # Strategy 1: Clear cookies and reload
    print("🔄 Strategy 1: Clearing cookies and reloading...")
    try:
        context.clear_cookies()
        stealth_delay(30, 60, "after clearing cookies")
        
        page.goto("https://twitter.com/home", timeout=30000)
        stealth_delay(10, 20, "after navigation")
        
        if not detect_blocking(page):
            print("✅ Successfully cleared blocking")
            return True
            
    except Exception as e:
        print(f"❌ Cookie clearing failed: {e}")
    
    # Strategy 2: Navigate to different pages first
    print("🔄 Strategy 2: Warming up with different pages...")
    try:
        warmup_pages = ["https://twitter.com/explore", "https://twitter.com/notifications"]
        
        for warmup_url in warmup_pages:
            page.goto(warmup_url, timeout=30000)
            stealth_delay(15, 25, f"warming up on {warmup_url}")
            
            if detect_blocking(page):
                continue
            else:
                print("✅ Warmup successful")
                return True
                
    except Exception as e:
        print(f"❌ Warmup failed: {e}")
    
    # Strategy 3: Extended wait
    print("🔄 Strategy 3: Extended wait...")
    stealth_delay(120, 180, "extended blocking recovery")
    
    return False

def stealth_scroll(page, scroll_number, total_scrolls):
    """Stealth scrolling with maximum human simulation"""
    print(f"📜 Stealth scroll {scroll_number}/{total_scrolls}")
    
    try:
        # Random mouse movements before scrolling
        page.mouse.move(random.randint(100, 500), random.randint(100, 400))
        time.sleep(random.uniform(0.5, 1.5))
        
        # Variable scroll amounts
        scroll_pixels = random.randint(400, 1200)
        
        # Scroll in multiple small increments
        increments = random.randint(3, 7)
        pixels_per_increment = scroll_pixels // increments
        
        for i in range(increments):
            page.evaluate(f"window.scrollBy(0, {pixels_per_increment})")
            time.sleep(random.uniform(0.3, 1.2))
        
        # Random pause after scrolling
        stealth_delay(HUMAN_DELAYS['scroll_min'], HUMAN_DELAYS['scroll_max'], "after scroll")
        
        # Check for blocking after each scroll
        if detect_blocking(page):
            print(f"🚨 Blocking detected after scroll {scroll_number}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Scroll {scroll_number} failed: {e}")
        return False

def stealth_extraction(page):
    """Extract with stealth timing"""
    print("📋 Stealth extraction starting...")
    
    stealth_delay(5, 10, "before extraction")
    
    results = []
    excluded_count = 0  # ✅ Initialize the counter
    
    try:
        # Get page content slowly
        print("🔍 Getting page elements...")
        
        selectors = [
            'div[data-testid="cellInnerDiv"]',
            'article[data-testid="tweet"]',
            'div[data-testid="UserCell"]',
            'div[role="article"]'
        ]
        
        elements = []
        for selector in selectors:
            try:
                found = page.query_selector_all(selector)
                if len(found) > 5:
                    elements = found
                    print(f"✅ Using {selector}: {len(found)} elements")
                    break
            except:
                continue
        
        if not elements:
            print("❌ No elements found")
            return []
        
        print(f"🎯 Processing {len(elements)} elements with stealth...")
        
        for i, element in enumerate(elements):
            try:
                # Progress with stealth pauses
                if i > 0 and i % 20 == 0:
                    print(f"  📊 Progress: {i}/{len(elements)} (pausing for stealth)")
                    stealth_delay(2, 5, "stealth processing pause")
                
                text = element.inner_text().strip()
                
                if '@' not in text or len(text) < 10:
                    continue
                
                # Extract username with regex
                username_match = re.search(r'@(\w+)', text)
                if not username_match:
                    continue
                
                username = f"@{username_match.group(1)}"

                # 🚀 NEW: CHECK FOR EXCLUSION (ONE LINE!)
                if should_exclude_account(username, PLATFORM_NAME, config_loader):
                    excluded_count += 1
                    continue
                
                # Extract name (multiple strategies)
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                name = extract_name_from_lines(lines, username)
                
                if not name:
                    name = username.lstrip('@').replace('_', ' ').title()
                
                # Extract bio
                bio = extract_bio_from_lines(lines, username, name)
                if not bio:
                    bio = f"Twitter user interested in {SEARCH_TERM}"
                
                # Create lead
                location = infer_location(bio) if location_list else "Unknown"
                
                lead = {
                    "name": name,
                    "handle": username,
                    "bio": bio[:250],
                    "platform": "twitter",
                    "dm": "",
                    "username": username,
                    "location": location,
                    "url": f"https://twitter.com/{username.lstrip('@')}",
                    "is_verified": "verified" in text.lower(),
                    "has_email": bool(re.search(r'\S+@\S+\.\S+', bio)),
                    "has_phone": bool(re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', bio)),
                    "extraction_method": "Twitter Stealth"
                }
                
                lead["dm"] = generate_dm_with_fallback(
                    name=lead["name"],
                    bio=lead["bio"],
                    platform=lead["platform"]
                )
                
                results.append(lead)
                
                if len(results) % 10 == 0:
                    print(f"  ✅ Extracted {len(results)} leads...")
                
            except Exception as e:
                continue
        
        print(f"📊 Stealth extraction complete: {len(results)} leads, {excluded_count} excluded")
        return results
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return []

def extract_name_from_lines(lines, username):
    """Extract name from text lines"""
    username_idx = -1
    for i, line in enumerate(lines):
        if username in line:
            username_idx = i
            break
    
    # Look before username
    for i in range(max(0, username_idx - 3), username_idx):
        line = lines[i] if i < len(lines) else ""
        if is_valid_name(line):
            return clean_name(line)
    
    # Look after username
    for i in range(username_idx + 1, min(len(lines), username_idx + 3)):
        line = lines[i] if i < len(lines) else ""
        if is_valid_name(line):
            return clean_name(line)
    
    return ""

def extract_bio_from_lines(lines, username, name):
    """Extract bio from text lines"""
    bio_parts = []
    for line in lines:
        if (line and 
            line != name and 
            username not in line and
            not any(ui in line.lower() for ui in ['follow', 'following', 'verified', 'subscribe']) and
            len(line) > 5):
            bio_parts.append(line)
        
        if len(' '.join(bio_parts)) > 150:
            break
    
    return ' '.join(bio_parts[:3])

def is_valid_name(text):
    """Check if text looks like a name"""
    if not text or len(text) < 2 or len(text) > 50:
        return False
    
    bad_indicators = ['follow', 'verified', 'subscribe', 'http', '@', '#']
    if any(bad in text.lower() for bad in bad_indicators):
        return False
    
    return bool(re.search(r'[a-zA-Z]', text))

def clean_name(name):
    """Clean extracted name"""
    name = re.sub(r'\s*•.*', '', name)
    name = re.sub(r'^(verified|follow)\s*', '', name, flags=re.IGNORECASE)
    return name.strip()

def infer_location(bio):
    """Extract location from bio"""
    if not location_list:
        return "Unknown"
    
    bio_lower = bio.lower()
    for location in location_list:
        if location.lower() in bio_lower:
            return location
    return "Unknown"

def login_and_scrape():
    """Main stealth scraper with smart user-aware deduplication"""
    estimated_leads = MAX_SCROLLS * 5
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    csv_filename = f"twitter_leads_stealth_{username}_{date_str}.csv"
    
    with sync_playwright() as p:
        browser, context = create_stealth_browser(p)
        page = context.new_page()
        
        try:
            print("🔒 Starting stealth Twitter scraping...")
            
            # Initial warmup
            print("🔥 Warming up browser...")
            page.goto("https://twitter.com/home", timeout=30000)
            stealth_delay(HUMAN_DELAYS['initial_wait'], HUMAN_DELAYS['initial_wait'] + 10, "initial warmup")
            
            blocking_attempts = 0
            
            while blocking_attempts < 3:
                if detect_blocking(page):
                    blocking_attempts += 1
                    if not handle_blocking(page, context, blocking_attempts):
                        browser.close()
                        return []
                else:
                    break
            
            # Navigate to search
            print(f"🔍 Navigating to search: '{SEARCH_TERM}'")
            search_url = f"https://twitter.com/search?q={SEARCH_TERM.replace(' ', '%20')}&src=typed_query&f=user"
            page.goto(search_url, timeout=30000)
            stealth_delay(15, 25, "after search navigation")
            
            if detect_blocking(page):
                print("🚨 Blocked on search page")
                browser.close()
                return []
            
            print("✅ Search page loaded successfully")
            
            # Stealth scrolling
            print(f"📜 Starting stealth scrolling ({MAX_SCROLLS} scrolls)...")
            successful_scrolls = 0
            
            for i in range(MAX_SCROLLS):
                if stealth_scroll(page, i + 1, MAX_SCROLLS):
                    successful_scrolls += 1
                else:
                    print(f"❌ Scroll {i + 1} failed")
                    if detect_blocking(page):
                        print("🚨 Blocking detected during scroll")
                        break
            
            print(f"📊 Scrolling complete: {successful_scrolls}/{MAX_SCROLLS}")
            
            # Final extraction
            raw_results = stealth_extraction(page)
            
            if not raw_results:
                print("❌ No raw results extracted")
                browser.close()
                return []
            
            # 🚀 APPLY SMART USER-AWARE DEDUPLICATION
            print(f"\n🧠 Applying deduplication strategy: {DEDUP_MODE}")
            print(f"👤 User-specific deduplication for: {username}")
            
            if SMART_DEDUP_AVAILABLE and DEDUP_MODE == "smart_user_aware":
                unique_results, dedup_stats = process_leads_with_smart_deduplication(
                    raw_leads=raw_results,
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
                unique_results, raw_results_copy, dedup_stats = apply_deduplication_strategy(
                    raw_results, username, PLATFORM_NAME, mode
                )
            else:
                # Fallback to simple deduplication
                print("📋 Using basic deduplication (smart dedup not available)")
                unique_results = []
                seen_usernames = set()
                for result in raw_results:
                    username_key = result.get('username', '').lower().strip()
                    if username_key not in seen_usernames and len(username_key) > 1:
                        unique_results.append(result)
                        seen_usernames.add(username_key)
                dedup_stats = {"basic": True, "kept": len(unique_results)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw results extracted: {len(raw_results)}")
            print(f"  ✅ Unique results after dedup: {len(unique_results)}")
            print(f"  📈 Efficiency: {(len(unique_results) / len(raw_results) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            print(f"  📊 Scrolls: {successful_scrolls}/{MAX_SCROLLS}")
            
            if len(unique_results) > 100:
                print(f"🎉 EXCELLENT: {len(unique_results)} results (target exceeded!)")
            elif len(unique_results) > 50:
                print(f"✅ GOOD: {len(unique_results)} results")
            elif len(unique_results) > 25:
                print(f"⚠️ MODERATE: {len(unique_results)} results")
            else:
                print(f"⚠️ LOW: {len(unique_results)} results")
            
            results = unique_results

            # Finalize results with usage tracking
            if results:
                try:
                    finalized_results = finalize_scraper_results(PLATFORM_NAME, results, SEARCH_TERM, username)
                    results = finalized_results
                    print("✅ Results finalized and usage tracked")
                except Exception as e:
                    print(f"⚠️ Error finalizing results: {e}")
            
            # Save results to multiple files
            if results or (raw_results and SAVE_RAW_LEADS):
                fieldnames = ["name", "handle", "bio", "url", "platform", "dm", "username", "location", "is_verified", "has_email", "has_phone", "extraction_method"]
                
                files_saved = []
                
                # Save processed results to main CSV
                if results:
                    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(results)
                    files_saved.append(csv_filename)
                    
                    # Save to backup CSV if different
                    if BACKUP_CSV != csv_filename:
                        with open(BACKUP_CSV, "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(results)
                        files_saved.append(BACKUP_CSV)
                        print(f"💾 Backup saved to {BACKUP_CSV}")
                
                # Save raw results if enabled and different from processed
                if raw_results and SAVE_RAW_LEADS and len(raw_results) != len(results):
                    raw_filename = f"twitter_leads_raw_{username}_{date_str}.csv"
                    with open(raw_filename, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(raw_results)
                    files_saved.append(raw_filename)
                    print(f"📋 Raw results saved to {raw_filename}")
                
                # Upload to Google Sheets and send email
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    print("📝 Writing to Google Sheets...")
                    write_leads_to_google_sheet(results)
                    print("✅ Successfully uploaded to Google Sheets")
                    
                    print("📤 Sending leads via email...")
                    send_daily_leads_email()
                    print("✅ Daily leads email sent!")
                    
                except ImportError:
                    print("📦 Export features not available")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                print(f"\n✅ STEALTH SCRAPER SUCCESS!")
                print(f"💾 Saved {len(results)} leads to {csv_filename}")
                print(f"📊 Results: {len(results)/max(successful_scrolls,1):.1f} leads per scroll")
                print(f"🔍 Files saved: {', '.join(files_saved)}")
                
                # Show sample results
                if results:
                    print(f"\n🎉 Sample processed results:")
                    for i, result in enumerate(results[:3]):
                        print(f"  {i+1}. {result['name']} ({result.get('username', 'N/A')}) - {result.get('location', 'N/A')}")
                        print(f"     Bio: {result['bio'][:60]}...")
                        print(f"     URL: {result.get('url', 'N/A')}")
                        print()
                
                if raw_results and SAVE_RAW_LEADS and len(raw_results) != len(results):
                    print(f"\n📋 Raw results preserved: {len(raw_results)} total")
                
                browser.close()
                return results
            else:
                print("⚠️ No results to save")
                browser.close()
                return []
                
        except Exception as e:
            print(f"🚨 Critical stealth error: {e}")
            try:
                page.screenshot(path="stealth_error.png")
            except:
                pass
            browser.close()
            return []

if __name__ == "__main__":
    print(f"🔒 STEALTH Twitter Scraper - Smart Deduplication Version")
    print(f"🛡️ Features:")
    print(f"  • Maximum anti-detection measures")
    print(f"  • Random user agents and viewports")
    print(f"  • Comprehensive browser stealth")
    print(f"  • Blocking detection and recovery")
    print(f"  • Extended human-like delays")
    print(f"  • Cookie clearing on block")
    print(f"  🚀 Smart user-aware deduplication")
    print(f"  📊 Enhanced result tracking")
    print()
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"📜 Max scrolls: {MAX_SCROLLS}")
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print()
    
    results = login_and_scrape()
    
    if results and len(results) >= 50:
        print(f"🎉 STEALTH SUCCESS: Twitter scraper completed with {len(results)} leads!")
    elif results:
        print(f"✅ Twitter scraper completed with {len(results)} leads")
    else:
        print("❌ Stealth scraper blocked or failed")
        print("💡 Twitter's detection is very aggressive")
        print("🔧 Try running during different hours or with different search terms")