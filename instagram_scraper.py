from datetime import datetime
import time
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import csv
import re
import random
from dm_sequences import generate_dm_with_fallback
import os
from pathlib import Path
from persistence import save_leads_to_files

# Use your app volume mount. If you set CSV_DIR in Railway env, it will override.
CSV_DIR = Path(os.getenv("CSV_DIR", "/app/client_configs"))
CSV_DIR.mkdir(parents=True, exist_ok=True)

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

PLATFORM_NAME = "instagram"

# Load Instagram session state
try:
    with open("instagram_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("❌ instagram_auth.json not found!")
    exit(1)

# Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('instagram')

# Extract config values - SIMPLIFIED
SEARCH_TERM = config["search_term"]
MAX_SCROLLS = config["max_scrolls"]
MAX_PAGES = config.get("max_pages", 12)
DELAY_MIN = config.get("delay_min", 2)
DELAY_MAX = config.get("delay_max", 5)
LEAD_OUTPUT_FILE = config["lead_output_file"]
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45000)

# 🚀 Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")
SAVE_RAW_LEADS = config.get("save_raw_leads", True)

# 🚀 NEW: Dynamic excluded accounts (NO HARDCODING!)
excluded_accounts = config_loader.get_excluded_accounts('instagram')
print(f"📋 Instagram Config Loaded:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  📄 Max Pages: {MAX_PAGES}")
print(f"  ⏱️ Delay Range: {DELAY_MIN}-{DELAY_MAX}s")
print(f"  📁 Output File: {LEAD_OUTPUT_FILE}")

if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")
    
def is_relevant_to_search_term(name, bio, location=""):
    """Check if the profile is relevant to the search term - OPTIMIZED FOR HIGH VOLUME"""
    # Combine all text for analysis
    analysis_text = f"{name} {bio} {location}".lower()
    
    # Get search keywords
    search_keywords = SEARCH_TERM.lower().split()
    
    # Score based on keyword presence
    relevance_score = 0
    
    # Primary keywords (search term) - weight 3
    for keyword in search_keywords:
        if keyword in analysis_text:
            relevance_score += 3
    
    # Investment/finance related keywords if searching for investors
    if any(word in SEARCH_TERM.lower() for word in ['investor', 'trading', 'stock', 'crypto', 'finance']):
        finance_keywords = ['investor', 'trading', 'stocks', 'crypto', 'finance', 'money', 'wealth', 'portfolio', 'investment', 'analyst', 'advisor', 'capital']
        for keyword in finance_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Fitness related keywords if searching for coaches
    if any(word in SEARCH_TERM.lower() for word in ['coach', 'trainer', 'fitness']):
        fitness_keywords = ['coach', 'trainer', 'fitness', 'workout', 'exercise', 'health', 'nutrition', 'wellness', 'personal trainer', 'fit', 'gym', 'muscle', 'weight', 'cardio', 'yoga', 'pilates']
        for keyword in fitness_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Business related keywords
    if any(word in SEARCH_TERM.lower() for word in ['business', 'entrepreneur', 'ceo']):
        business_keywords = ['ceo', 'founder', 'entrepreneur', 'business', 'startup', 'executive', 'director', 'manager']
        for keyword in business_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # 🚀 OPTIMIZED: Lowered threshold from 3 to 2 for higher volume
    return relevance_score >= 2, relevance_score

def extract_instagram_profiles(page):
    """Extract ONLY verified Instagram profile links"""
    print("Extracting Instagram profiles with strict validation...")
    
    results = []
    
    try:
        # Only target actual profile links with this very specific selector
        profile_links = page.query_selector_all('a[href^="/"][href$="/"], a[href^="/"][href*="/"][href*="instagram.com/"]')
        
        valid_usernames = set()
        
        for link in profile_links:
            try:
                href = link.get_attribute('href')
                if not href:
                    continue
                
                # Extract username with VERY strict validation
                username = extract_validated_username(href)
                if not username or username in valid_usernames:
                    continue
                
                # Double-check this is a real profile link
                if not is_real_profile_link(link, username):
                    continue
                
                # Skip excluded accounts
                if should_exclude_account(username, PLATFORM_NAME, config_loader):
                    continue
                
                valid_usernames.add(username)
                
                lead = {
                    "name": username.replace('_', ' ').replace('.', ' ').title(),
                    "handle": f"@{username}",
                    "bio": f"Instagram user interested in {SEARCH_TERM}",
                    "url": f"https://instagram.com/{username}",
                    "platform": "instagram",
                    "dm": generate_dm_with_fallback(username, f"Instagram user interested in {SEARCH_TERM}", "instagram"),
                    "title": f"Instagram user interested in {SEARCH_TERM}",
                    "location": "Location not specified",
                    "followers": "Followers not shown", 
                    "profile_url": f"https://instagram.com/{username}",
                    "contact_info": "Contact not available",
                    "search_term": SEARCH_TERM,
                    "extraction_method": "Validated Profile Link",
                    "relevance_score": 2
                }
                
                results.append(lead)
                print(f"Valid profile: @{username}")
                
            except Exception as e:
                continue
        
        print(f"Extracted {len(results)} validated profiles")
        return results
        
    except Exception as e:
        print(f"Error extracting profiles: {e}")
        return []

def extract_validated_username(href):
    """Extract username only if it matches exact Instagram patterns"""
    if not href or not isinstance(href, str):
        return None
    
    # Remove any domain if present
    if 'instagram.com' in href:
        href = href.split('instagram.com')[-1]
    
    # Must start with / and contain only valid characters
    if not href.startswith('/'):
        return None
    
    # Extract the username part (first segment after /)
    parts = href.strip('/').split('/')
    if not parts or len(parts) == 0:
        return None
    
    potential_username = parts[0]
    
    # Validate username format
    if not re.match(r'^[a-zA-Z0-9_.]{1,30}$', potential_username):
        return None
    
    # Block known UI elements and system pages
    blocked_names = {
        'explore', 'reels', 'tv', 'stories', 'accounts', 'direct', 'p',
        'help', 'about', 'privacy', 'terms', 'support', 'press', 'api',
        'jobs', 'blog', 'developer', 'legal', 'more', 'also_from_meta',
        'meta', 'facebook', 'whatsapp', 'download', 'app', 'store'
    }
    
    if potential_username.lower() in blocked_names:
        return None
    
    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', potential_username):
        return None
    
    return potential_username

def is_real_profile_link(link_element, username):
    """Verify this is actually a profile link, not UI navigation"""
    try:
        # Get the text content of the link
        link_text = link_element.inner_text().strip().lower()
        
        # If link text contains the username, it's probably real
        if username.lower() in link_text:
            return True
        
        # If link text is a common UI element, skip it
        ui_phrases = [
            'also from meta', 'more', 'see all', 'suggested', 
            'people you may know', 'follow', 'download'
        ]
        
        for phrase in ui_phrases:
            if phrase in link_text:
                return False
        
        # If link text is very short or just symbols, skip
        if len(link_text) < 2 or link_text.isdigit():
            return False
        
        return True
        
    except:
        return True  # If we can't check, assume it's valid


# IMMEDIATE FIX 5: Better CSV validation
def save_and_validate_csv(leads, output_file):
    """Save CSV with proper validation"""
    if not leads:
        print("❌ No leads to save")
        return False
    
    print(f"💾 Saving {len(leads)} leads with validation...")
    
    # Validate each lead
    valid_leads = []
    for i, lead in enumerate(leads):
        # Check required fields
        required = ['name', 'handle', 'bio', 'url', 'platform']
        if all(lead.get(field) and str(lead.get(field)).strip() for field in required):
            valid_leads.append(lead)
            print(f"  ✅ Lead {i+1}: {lead['name']} - VALID")
        else:
            missing = [field for field in required if not lead.get(field)]
            print(f"  ❌ Lead {i+1}: Missing {missing}")
    
    if not valid_leads:
        print("❌ No valid leads found!")
        return False
    
    # Save to CSV
    fieldnames = ['name', 'handle', 'bio', 'url', 'platform', 'dm', 'search_term', 'extraction_method', 'relevance_score']
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(valid_leads)
        
        # Verify file
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.count('\n')
            print(f"  ✅ File saved: {len(content)} chars, {lines} lines")
            
            # Show first few lines
            print(f"  📋 First few lines:")
            for i, line in enumerate(content.split('\n')[:3]):
                print(f"    {i+1}: {line[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Save error: {e}")
        return False

# APPLY THESE FIXES TO YOUR EXISTING CODE:
# 1. Replace extract_instagram_profiles() with extract_instagram_profiles_fixed()
# 2. Replace your CSV saving with save_and_validate_csv()
# 3. Add quick_debug_page_content() after page loads

def improved_browser_setup(p):
    """Enhanced browser setup to avoid detection"""
    return p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor'
        ]
    )

def stealth_page_setup(page):
    """Add stealth properties to avoid detection"""
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

def check_for_blocks_and_handle(page):
    """Check if we're being blocked and handle appropriately"""
    current_url = page.url.lower()
    page_content = ""
    
    try:
        page_content = page.inner_text('body').lower()
    except:
        pass
    
    # Detection patterns
    block_indicators = [
        'download the instagram app',
        'meta verified',
        'app store',
        'login',
        'challenge',
        'error',
        'blocked',
        'suspended'
    ]
    
    for indicator in block_indicators:
        if indicator in current_url or indicator in page_content:
            print(f"🚨 Block detected: {indicator}")
            print(f"📍 Current URL: {page.url}")
            
            # Take screenshot for debugging
            try:
                page.screenshot(path=f"instagram_block_{indicator.replace(' ', '_')}.png")
                print(f"📸 Block screenshot saved")
            except:
                pass
            
            return True, indicator
    
    return False, None

def human_like_scrolling(page, max_scrolls):
    """More human-like scrolling pattern"""
    print(f"📜 Starting human-like scrolling ({max_scrolls} scrolls)...")
    
    for i in range(max_scrolls):
        print(f"  🔄 Scroll {i + 1}/{max_scrolls}")
        
        # Random scroll amounts (humans don't scroll consistently)
        scroll_amount = random.randint(300, 700)
        
        # Sometimes scroll up a bit (humans do this)
        if random.random() < 0.1:
            page.mouse.wheel(0, -100)
            time.sleep(random.uniform(0.5, 1.0))
        
        # Main scroll
        page.mouse.wheel(0, scroll_amount)
        
        # Variable pause times (humans pause irregularly)
        if random.random() < 0.3:  # 30% chance of longer pause
            pause_time = random.uniform(3, 8)
            print(f"    ⏳ Extended pause: {pause_time:.1f}s")
            time.sleep(pause_time)
        else:
            time.sleep(random.uniform(1, 3))
        
        # Occasionally move mouse (humans do this)
        if random.random() < 0.2:
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            page.mouse.move(x, y)

def main():
    """Main function to run Instagram scraper with smart user-aware deduplication"""
    
    # 🚀 OPTIMIZED: Increased estimated leads calculation
    estimated_leads = MAX_SCROLLS * 8  # More realistic estimate
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print("🎯 Launching Instagram scraper with ULTRA-PERMISSIVE detection...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
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
            # Navigate to hashtag
            # Convert search term to hashtag format
            hashtag_clean = SEARCH_TERM.replace(' ', '').lower()
            search_url = f"https://www.instagram.com/explore/tags/{hashtag_clean}/"
            print(f"🏋️ Searching: '{SEARCH_TERM}'")
            print(f"📍 URL: {search_url}")
            
            page.goto(search_url, timeout=60000)
            time.sleep(random.uniform(5, 8))
            
            # Check login
            if any(indicator in page.url.lower() for indicator in ['login', 'challenge', 'accounts']):
                print("🚨 Authentication issue detected!")
                browser.close()
                return []
            
            print("✅ Successfully loaded hashtag page")
            
            # Enhanced scrolling with error handling
            print(f"📜 Scrolling to load more posts...")
            for i in range(5):
                try:
                    print(f"   Scroll {i+1}/5")
                    page.mouse.wheel(0, 800)
                    time.sleep(random.uniform(2, 4))
                    
                except Exception as e:
                    print(f"   ⚠️ Scroll error: {str(e)[:30]}")
            
            print("⏳ Final content stabilization...")
            time.sleep(random.uniform(3, 5))
            
            # Extract profiles (raw leads)
            raw_leads = extract_instagram_profiles(page)
            
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
            print(f"  📊 Scrolls completed: 5")
            
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
            
            # Save results to multiple files (into persistent volume)
            if leads or (raw_leads and SAVE_RAW_LEADS):
                output_file = f"instagram_leads_{username}_{timestamp}.csv"
                fieldnames = [
                    'name','handle','bio','url','platform','dm','title','location',
                    'followers','profile_url','contact_info','search_term',
                    'extraction_method','relevance_score'
                ]

                files_saved = save_leads_to_files(
                    leads=leads,
                    raw_leads=raw_leads,
                    username=username,
                    timestamp=timestamp,
                    platform_name=PLATFORM_NAME,
                    csv_dir=CSV_DIR,           # ← use YOUR existing per-scraper CSV_DIR
                    save_raw=SAVE_RAW_LEADS,   # ← if you have this flag
                )

                if leads:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(leads)
                    files_saved.append(str(output_file))
                    

                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    raw_filename = f"instagram_leads_raw_{username}_{timestamp}.csv"
                    raw_path = CSV_DIR / raw_filename
                    with open(raw_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(raw_leads)
                    files_saved.append(str(raw_path))
                    print(f"📋 Raw leads saved to {raw_path}")

                
                print(f"\n✅ Successfully saved {len(leads)} leads")
                print(f"🔍 Files saved: {', '.join(files_saved)}")
                print(f"🎯 Performance target: 50+ leads - {'✅ ACHIEVED' if len(leads) >= 50 else '❌ MISSED'}")
                
                # After saving files for <username>:
                try:
                    # Recompute fresh totals from CSV_DIR and persist
                    from pathlib import Path
                    from frontend_app import calculate_empire_from_csvs
                    stats = calculate_empire_from_csvs(username)
                    snapshot = {"platforms": stats, "total_empire": sum(stats.values())}
                    (CSV_DIR / f"empire_totals_{username}.json").write_text(json.dumps(snapshot))
                except Exception as e:
                    print(f"ℹ️ Could not write empire snapshot: {e}")

                
                # Upload to Google Sheets and send email
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    print("📝 Writing to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print("✅ Successfully uploaded to Google Sheets")
                    
                    print("📤 Sending Instagram leads via email...")
                    send_daily_leads_email()
                    print("✅ Instagram leads email sent!")
                    
                except ImportError:
                    print("📦 sheets_writer.py or daily_emailer.py not found - export features skipped")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show sample results
                if leads:
                    print(f"\n🎉 Sample processed results:")
                    for i, lead in enumerate(leads[:5]):
                        print(f"  {i+1}. {lead['name']}")
                        print(f"     Handle: {lead['handle']}")
                        print(f"     Bio: {lead['bio'][:50]}...")
                        print(f"     Relevance Score: {lead.get('relevance_score', 'N/A')}")
                        print(f"     DM: {lead['dm'][:50]}...")
                        print(f"     URL: {lead.get('url', 'N/A')}")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    
            else:
                print("⚠️ No profiles extracted")
                print("🔍 Check instagram_extraction_debug.png to see what was on the page")
                print("💡 You may need to:")
                print("   - Refresh your Instagram authentication")
                print("   - Try a different search term")
                print("   - Check if Instagram has changed their layout")
                
        except Exception as e:
            print(f"🚨 Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Keep browser open briefly to see final state
            print("🔍 Keeping browser open for 5 seconds...")
            time.sleep(5)
            try:
                browser.close()
            except:
                pass
            
        return leads

if __name__ == "__main__":
    print(f"🚀 Instagram Scraper - Smart Deduplication Version")
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"📜 Max scrolls: {MAX_SCROLLS}")
    print(f"⏱️ Delay range: {DELAY_MIN}-{DELAY_MAX}s")
    print(f"🎯 Target: 50+ leads (improved from 3)")
    print(f"🛡️ Features:")
    print(f"  • Ultra-permissive detection")
    print(f"  • Automatic account exclusion")
    print(f"  • Client-configurable settings")
    print(f"  🚀 Smart user-aware deduplication")
    print(f"  📊 Enhanced result tracking")
    print()
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print()
    
    results = main()
    
    if results and len(results) >= 50:
        print(f"🎉 INSTAGRAM SUCCESS: Instagram scraper completed with {len(results)} leads!")
    elif results:
        print(f"✅ Instagram scraper completed with {len(results)} leads")
    else:
        print(f"❌ Instagram scraper completed with 0 leads")