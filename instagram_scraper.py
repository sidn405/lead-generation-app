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
    """Extract profiles from Instagram search results using Facebook's successful approach"""
    print("📋 Extracting Instagram profiles...")
    
    results = []
    excluded_count = 0  # ✅ ADD THIS
    
    # Wait for content to load
    time.sleep(DELAY_MIN)
    
    # Check page status first
    try:
        current_url = page.url
        print(f"🔍 Current URL: {current_url}")
        
        # Check if we're blocked or redirected
        if any(indicator in current_url.lower() for indicator in ['login', 'challenge', 'help', 'error', 'accounts/login']):
            print("🚨 Instagram is blocking access or redirected to login")
            print("💡 Please refresh your instagram_auth.json by logging in again")
            return []
            
        # Try to get page title
        try:
            page_title = page.title()
            print(f"📄 Page title: {page_title}")
            if any(indicator in page_title.lower() for indicator in ['login', 'error', 'help']):
                print("🚨 Page title suggests we're not on search results")
                return []
        except:
            print("⚠️ Could not get page title")
            
    except Exception as e:
        print(f"⚠️ Error checking page status: {e}")
        return []
    
    # Take screenshot with better error handling
    try:
        print("📸 Taking debug screenshot...")
        page.screenshot(path="instagram_extraction_debug.png", timeout=5000)
        print("📸 Debug screenshot saved: instagram_extraction_debug.png")
    except Exception as e:
        print(f"⚠️ Screenshot failed (continuing anyway): {str(e)[:100]}...")
    
    # Check if page has content
    try:
        page_text = page.inner_text('body')
        print(f"📄 Page content length: {len(page_text)} characters")
        
        if len(page_text) < 100:
            print("⚠️ Very little content on page")
            print(f"Content preview: {page_text[:200]}")
        
        # Look for Instagram-specific indicators
        try:
            page_title = page.title()
            print(f"📄 Page title: {page_title}")
            if "Instagram" not in page_title:
                print("⚠️ Title doesn't contain 'Instagram'")
        except:
            print("⚠️ Unable to get page title")

        # Only warn, don't block extraction
        if 'instagram' not in page_text.lower() and 'meta' not in page_text.lower():
            print("⚠️ Warning: Page content does not include common Instagram indicators")        
            
    except Exception as e:
        print(f"⚠️ Error reading page content: {e}")
        return []
    
    # Try multiple extraction approaches - COPIED FROM SUCCESSFUL FACEBOOK SCRAPER
    approaches = [
        {
            'name': 'Profile Links',
            'selector': 'a[href*="/"][href*="instagram.com"], a[href^="/"]',
            'description': 'Instagram profile links'
        },
        {
            'name': 'Profile Cards',
            'selector': 'div[role="button"], article, div[tabindex="0"]',
            'description': 'Instagram profile containers'
        },
        {
            'name': 'User Links',
            'selector': 'a[href*="/"]',
            'description': 'Any user links'
        },
        {
            'name': 'Content Containers',
            'selector': 'div[style*="flex"], div[class*="user"], div[class*="profile"]',
            'description': 'Content containers'
        },
        {
            'name': 'All Clickable Elements',
            'selector': 'div[role="button"], span[role="button"], a',
            'description': 'All clickable elements (fallback)'
        }
    ]
    
    for approach in approaches:
        print(f"\n🔍 Trying approach: {approach['name']}")
        
        try:
            elements = page.query_selector_all(approach['selector'])
            print(f"  Found {len(elements)} elements")
            
            if len(elements) == 0:
                continue
            
            approach_results = []
            processed = 0
            
            # 🚀 OPTIMIZED: Increased limits for high volume extraction
            max_elements = min(500, len(elements))
            max_results_per_approach = 200
            
            for i, element in enumerate(elements[:max_elements]):
                if processed >= max_results_per_approach:
                    break
                    
                try:
                    # Get text content with timeout protection
                    try:
                        text_content = element.inner_text()
                        if not text_content or len(text_content.strip()) < 3:
                            continue
                    except:
                        continue
                    
                    processed += 1
                    text_content = text_content.strip()
                    
                    # Skip if too short
                    if len(text_content) < 3:
                        continue
                    
                    # Extract username and handle
                    username = ""
                    handle = ""
                    profile_url = ""
                    
                    # Try to get href first
                    try:
                        href = element.get_attribute('href')
                        if href:
                            # Extract username from URL
                            if href.startswith('/'):
                                href = 'https://instagram.com' + href
                            
                            # Match Instagram username patterns
                            username_patterns = [
                                r'instagram\.com/([a-zA-Z0-9_.]{1,30})/?$',
                                r'/([a-zA-Z0-9_.]{1,30})/?$'
                            ]
                            
                            for pattern in username_patterns:
                                match = re.search(pattern, href)
                                if match:
                                    potential_username = match.group(1)
                                    # Validate username
                                    if (len(potential_username) >= 1 and 
                                        len(potential_username) <= 30 and
                                        not potential_username in ['explore', 'reels', 'tv', 'p', 'stories', 'accounts']):
                                        username = potential_username
                                        handle = f"@{username}"
                                        profile_url = href
                                        break
                    except:
                        pass
                    
                    # If no username from URL, try to extract from text
                    if not username:
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        if not lines:
                            continue
                        
                        # Look for potential usernames/names in text
                        for line in lines[:3]:
                            # Skip UI elements
                            if any(skip in line.lower() for skip in ['follow', 'following', 'followers', 'posts', 'see all', 'suggested']):
                                continue
                            
                            # Look for @ handles
                            handle_match = re.search(r'@([a-zA-Z0-9_.]{1,30})', line)
                            if handle_match:
                                username = handle_match.group(1)
                                handle = f"@{username}"
                                profile_url = f"https://instagram.com/{username}"
                                break
                            
                            # Or treat line as display name
                            if (len(line) >= 2 and len(line) <= 50 and  
                                not line.isdigit() and
                                not line.startswith('http')):
                                username = line.replace(' ', '_').lower()
                                handle = f"@{username}"
                                profile_url = f"https://instagram.com/{username}"
                                break
                    
                    if not username:
                        continue

                    # ✅ ADD EXCLUSION CHECK
                    if should_exclude_account(username, PLATFORM_NAME, config_loader):
                        excluded_count += 1
                        continue
                    
                    # Create display name
                    name = username.replace('_', ' ').replace('.', ' ').title()
                    if len(name) < 2:
                        name = username
                    
                    # Create bio based on available text and search term
                    bio_lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    bio = ""
                    for line in bio_lines[1:4]:  # Skip first line (usually name)
                        if (len(line) > 10 and 
                            not any(skip in line.lower() for skip in ['follow', 'posts', 'followers', 'following'])):
                            bio = line
                            break
                    
                    if not bio:
                        bio = f"Instagram creator interested in {SEARCH_TERM}"
                    
                    # Check relevance to search term
                    is_relevant, relevance_score = is_relevant_to_search_term(name, bio, "")
                    
                    # 🚀 OPTIMIZED: Accept lower relevance scores for volume
                    if relevance_score < 1:
                        continue
                    
                    # Create lead
                    lead = {
                        "name": name,
                        "handle": handle,
                        "bio": bio[:200],
                        "url": profile_url
                    }
                    
                    # Add platform and DM
                    lead["platform"] = "instagram"
                    lead["dm"] = generate_dm_with_fallback(
                        name=lead["name"],
                        bio=lead["bio"],
                        platform=lead["platform"]
                    )
                    
                    # Add Instagram-specific fields
                    lead.update({
                        'title': f'Instagram creator interested in {SEARCH_TERM}',
                        'location': 'Location not specified',
                        'followers': 'Followers not shown',
                        'profile_url': profile_url,
                        'contact_info': 'Contact not available',
                        'search_term': SEARCH_TERM,
                        'extraction_method': approach['name'],
                        'relevance_score': relevance_score
                    })
                    
                    approach_results.append(lead)
                    print(f"  ✅ {name[:30]}... | {handle} | Score: {relevance_score}")
                    
                except Exception as e:
                    continue
            
            if approach_results:
                print(f"✅ {approach['name']} found {len(approach_results)} leads")
                results.extend(approach_results)
                # Don't break early - let all approaches run for maximum extraction
            else:
                print(f"❌ No leads from {approach['name']}")
                
        except Exception as e:
            print(f"⚠️ Error with {approach['name']}: {str(e)[:100]}...")
            continue
    
    # 🚀 OPTIMIZED: More lenient duplicate filtering
    if results:
        unique_results = []
        seen_handles = set()
        for result in results:
            handle_key = result['handle'].lower().strip()
            # More lenient duplicate check
            if handle_key not in seen_handles and len(handle_key) > 2:
                unique_results.append(result)
                seen_handles.add(handle_key)
        
        print(f"\n📊 Total unique profiles extracted: {len(unique_results)}")
        print(f"🎯 Performance target: 50+ leads")
        return unique_results
    else:
        print(f"\n❌ No profiles extracted")
        print(f"💡 Try these solutions:")
        print(f"   1. Run Instagram auth script to refresh login")
        print(f"   2. Wait 30+ minutes before trying again")
        print(f"   3. Try a different search term")
        print(f"   4. Check if you're logged into Instagram in the browser")
        return []
    
# IMMEDIATE FIX 1: Add this debugging right after page loading
def quick_debug_page_content(page):
    """Quick debug to see what's actually on the page"""
    print("\n🔍 QUICK DEBUG:")
    try:
        page_title = page.title()
        current_url = page.url
        print(f"  📄 Page title: {page_title}")
        print(f"  🌐 Current URL: {current_url}")
        
        # Check for actual Instagram content
        body_text = page.inner_text('body')
        print(f"  📝 Page content length: {len(body_text)} characters")
        
        # Look for profile indicators
        profile_links = page.query_selector_all('a[href^="/"]')
        print(f"  👤 Profile-like links found: {len(profile_links)}")
        
        # Sample some usernames
        for i, link in enumerate(profile_links[:5]):
            href = link.get_attribute('href')
            if href and re.match(r'^/[a-zA-Z0-9_.]+/?$', href):
                username = href.strip('/').split('/')[0]
                print(f"    {i+1}. @{username}")
        
        return len(profile_links) > 0
    except Exception as e:
        print(f"  ❌ Debug error: {e}")
        return False

# IMMEDIATE FIX 2: Better username extraction
def extract_username_from_element(element):
    """Extract username with better validation"""
    try:
        href = element.get_attribute('href')
        if not href:
            return None
        
        # Clean href
        href = href.strip()
        if not href.startswith('/'):
            return None
        
        # Extract username
        match = re.match(r'^/([a-zA-Z0-9_.]{1,30})/?$', href)
        if not match:
            return None
        
        username = match.group(1)
        
        # Validate username
        excluded = ['explore', 'reels', 'p', 'tv', 'stories', 'accounts', 'direct']
        if username in excluded:
            return None
        
        # Check if it looks like a real username
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            return None
        
        return username
    except:
        return None

# IMMEDIATE FIX 3: Better bio/caption extraction
def extract_bio_from_context(page, username):
    """Extract bio/caption with better selectors"""
    bio_candidates = []
    
    # Try multiple selectors for bio/caption content
    bio_selectors = [
        'article span[style*="line-height"]',
        'div[role="button"] span',
        'article div span',
        'span[dir="auto"]',
        'div h1 + div span'
    ]
    
    for selector in bio_selectors:
        try:
            elements = page.query_selector_all(selector)
            for element in elements:
                text = element.inner_text()
                if (text and len(text) > 15 and len(text) < 500 and
                    username.lower() not in text.lower() and
                    not any(skip in text.lower() for skip in ['like', 'comment', 'follow', 'view'])):
                    bio_candidates.append(text)
        except:
            continue
    
    # Return the best bio candidate
    if bio_candidates:
        # Prefer longer, more descriptive text
        best_bio = max(bio_candidates, key=len)
        return best_bio[:300]
    
    return f"Instagram user @{username}"


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