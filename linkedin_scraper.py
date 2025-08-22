import json
import time
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import csv
from datetime import datetime
import os
import re
import sys
import random
from dm_sequences import generate_dm_with_fallback

# Directory where your CSV files are saved
CSV_DIR = os.path.join(os.getcwd(), "csv_exports")
os.makedirs(CSV_DIR, exist_ok=True)
# Import the centralized usage tracker
from usage_tracker import setup_scraper_with_limits, finalize_scraper_results

 #🚀 NEW: Import the enhanced config system
from config_loader import ConfigLoader, should_exclude_account, get_platform_config

# 🚀 Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

PLATFORM_NAME = "linkedin"

# ✅ CORRECT: Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('linkedin')

AUTH_FILE = "linkedin_auth.json"

# ✅ FIXED: Extract values directly from config with safe fallbacks where needed
SEARCH_TERM = config["search_term"]  # Uses "stock investor" from global config
MAX_SCROLLS = config["max_scrolls"]  # Uses actual config value (8)
MAX_PAGES = config.get("max_pages", 3)  # Safe fallback since not all platforms have this
DELAY_BETWEEN_SCROLLS = config.get("delay_between_scrolls", 4)  # Uses config value (4)
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 60000)  # Uses config value (60)
LEAD_OUTPUT_FILE = config.get("lead_output_file")  # Uses config value

# For search filters (nested dictionary):
SEARCH_FILTERS = config.get("search_filters", {})
PEOPLE_ONLY = SEARCH_FILTERS.get("people_only", True)
CURRENT_COMPANY = SEARCH_FILTERS.get("current_company", True)
CONNECTION_LEVEL = SEARCH_FILTERS.get("connection_level", "2nd")

# 🚀 Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")
SAVE_RAW_LEADS = config.get("save_raw_leads", True)

# 🚀 NEW: Dynamic excluded accounts (NO HARDCODING!)
excluded_accounts = config_loader.get_excluded_accounts('linkedin')
print(f"📋 LinkedIn Config Loaded:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  📄 Max Pages: {MAX_PAGES}")
print(f"  ⏱️ Delay: {DELAY_BETWEEN_SCROLLS}s")
print(f"  📁 Output File: {LEAD_OUTPUT_FILE}")
print(f"  🎯 Connection Level: {CONNECTION_LEVEL}")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

def human_delay(min_sec=1, max_sec=3):
    """Add human-like delays"""
    time.sleep(random.uniform(min_sec, max_sec))

def is_linkedin_blocking(page):
    """Detect if LinkedIn is blocking or challenging us"""
    try:
        current_url = page.url.lower()
        page_text = page.inner_text('body').lower()
        
        blocking_indicators = [
            'challenge' in current_url,
            'login' in current_url and 'linkedin.com/login' in current_url,
            'verification' in page_text,
            'unusual activity' in page_text,
            'security check' in page_text,
            'captcha' in page_text,
            'blocked' in page_text,
            'rate limit' in page_text,
            'try again later' in page_text
        ]
        
        return any(blocking_indicators)
    except:
        return True  # If we can't check, assume we're blocked

def manual_intervention_mode(page, action_description):
    """Switch to manual mode when LinkedIn blocks automation"""
    print(f"\n🚨 MANUAL INTERVENTION REQUIRED")
    print(f"LinkedIn has detected automation. Switching to manual mode...")
    print(f"\n📋 What you need to do:")
    print(f"1. {action_description}")
    print(f"2. Complete any security challenges (CAPTCHA, verification, etc.)")
    print(f"3. Navigate to where you want to be")
    print(f"4. DO NOT close the browser window")
    print(f"5. Press Enter here when you're ready to continue...")
    
    # Take screenshot to show current state
    try:
        page.screenshot(path="manual_intervention_needed.png")
        print(f"📸 Screenshot saved: manual_intervention_needed.png")
    except:
        pass
    
    input("\n⏳ Press Enter after you've completed the manual steps...")
    
    # Verify we're in a good state
    try:
        current_url = page.url
        print(f"✅ Resuming automation from: {current_url}")
        return True
    except:
        print("❌ Something went wrong, please try again")
        return False

def is_relevant_to_search_term(name, headline, location):
    """Check if the profile is relevant to the search term"""
    # Combine all text for analysis
    analysis_text = f"{name} {headline} {location}".lower()
    
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
    
    # Business related keywords
    if any(word in SEARCH_TERM.lower() for word in ['business', 'entrepreneur', 'ceo', 'founder']):
        business_keywords = ['ceo', 'founder', 'entrepreneur', 'business', 'startup', 'executive', 'director', 'manager']
        for keyword in business_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Consider relevant if score >= 3
    return relevance_score >= 3, relevance_score

def extract_profiles_from_page(page):
    """Extract profile data from current page"""
    results = []
    excluded_count = 0  # ✅ ADD THIS
    
    # Multiple strategies to find profiles
    selectors = [
        'div.entity-result__content',
        'div.reusable-search__result-container',
        'li.reusable-search__result-container', 
        'div[data-chameleon-result-urn]',
        'div.search-result__info',
        'article[data-chameleon-result-urn]',
        'div[class*="result"][class*="container"]'
    ]
    
    profile_elements = []
    working_selector = None
    
    for selector in selectors:
        try:
            elements = page.query_selector_all(selector)
            if len(elements) >= 3:  # Need at least 3 to be confident
                profile_elements = elements
                working_selector = selector
                print(f"✅ Using selector '{selector}' - found {len(elements)} profiles")
                break
        except:
            continue
    
    if not profile_elements:
        print("❌ No profile elements found with standard selectors")
        # Try manual extraction guidance
        print("\n🔍 Let me help you manually extract data...")
        page.screenshot(path="manual_extraction_needed.png")
        print("📸 Screenshot saved: manual_extraction_needed.png")
        
        print("\n📋 MANUAL EXTRACTION MODE:")
        print("1. Look at the browser window")
        print("2. I'll help you extract visible profiles")
        print("3. Press Enter to continue...")
        input()
        
        # Try to get all visible text and parse it
        try:
            page_text = page.inner_text('body')
            # Look for lines that might be names (simple heuristic)
            lines = page_text.split('\n')
            potential_profiles = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                # Heuristics for potential names/profiles
                if (len(line) > 5 and len(line) < 50 and 
                    ' ' in line and 
                    not any(skip in line.lower() for skip in ['search', 'filter', 'sort', 'message', 'connect', 'follow'])):
                    
                    # Look for job title in next few lines
                    headline = ""
                    for j in range(i+1, min(i+4, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and len(next_line) > 10 and len(next_line) < 100:
                            headline = next_line
                            break
                    
                    # Check relevance
                    is_relevant, relevance_score = is_relevant_to_search_term(line, headline, "")
                    
                    if not is_relevant:
                        continue
                    
                    # Create lead with required structure
                    lead = {
                        "name": line,
                        "handle": line.replace(" ", "").lower(),  # Create a handle from name
                        "bio": headline[:200] if headline else f"LinkedIn professional interested in {SEARCH_TERM}",
                        "url": "https://linkedin.com/in/profile-not-found"
                    }
                    # Add platform and DM
                    lead["platform"] = "linkedin"
                    lead["dm"] = generate_dm_with_fallback(
                        name=lead["name"],
                        bio=lead["bio"],
                        platform=lead["platform"]
                    )
                    
                    # Add additional LinkedIn-specific fields
                    lead.update({
                        'headline': headline or f'Professional in {SEARCH_TERM} field',
                        'location': 'Manual extraction',
                        'extraction_method': 'text_parsing',
                        'search_term': SEARCH_TERM,
                        'relevance_score': relevance_score
                    })
                    
                    potential_profiles.append(lead)
            
            # Take first 10 reasonable looking profiles
            if potential_profiles:
                print(f"🎯 Found {len(potential_profiles)} potential profiles via text parsing")
                return potential_profiles[:10]
        except:
            pass
        
        return []
    
    # Extract data from found elements
    for i, element in enumerate(profile_elements):
        try:
            element_text = element.inner_text().strip()
            
            if len(element_text) < 10:
                continue
                
            print(f"🔍 Processing profile {i+1}: {element_text[:50]}...")
            
            lines = [line.strip() for line in element_text.split('\n') if line.strip()]
            
            name = ""
            headline = ""
            location = ""
            
            # Extract name (usually first substantial line)
            if lines:
                name = lines[0]
                
                # Extract headline and location from remaining lines
                for line in lines[1:]:
                    if line and not headline and len(line) > 5:
                        # Skip UI elements
                        if line not in ['Connect', 'Message', 'Follow', 'View profile', 'Save']:
                            headline = line
                            break
                
                # Location often contains area/region keywords or is near the end
                for line in lines:
                    if any(indicator in line.lower() for indicator in ['area', 'region', 'greater', 'metro']):
                        location = line
                        break
            
            if name and len(name) > 2:
                # Check relevance to search term
                is_relevant, relevance_score = is_relevant_to_search_term(name, headline, location)
                
                if not is_relevant:
                    print(f"  ⏭️ Skipping {name} (not relevant to '{SEARCH_TERM}', score: {relevance_score})")
                    continue

                # ✅ ADD EXCLUSION CHECK
                if should_exclude_account(name, PLATFORM_NAME, config_loader):
                    excluded_count += 1
                    continue
                
                # Create lead with required structure
                lead = {
                    "name": name,
                    "handle": name.replace(" ", "").lower(),  # Create a handle from name
                    "bio": (headline or f'LinkedIn professional interested in {SEARCH_TERM}')[:200],
                    "url": "https://linkedin.com/in/profile-not-found"  # LinkedIn profile URLs are hard to extract
                }
                # Add platform and DM
                lead["platform"] = "linkedin"
                lead["dm"] = generate_dm_with_fallback(
                    name=lead["name"],
                    bio=lead["bio"],
                    platform=lead["platform"]
                )
                
                # Add additional LinkedIn-specific fields
                lead.update({
                    'headline': headline or f'Professional in {SEARCH_TERM} field',
                    'location': location or 'Location not specified',
                    'extraction_method': 'automated',
                    'search_term': SEARCH_TERM,
                    'relevance_score': relevance_score
                })
                
                results.append(lead)
                print(f"✅ {name} | Score: {relevance_score} | {headline[:30]}...")
            
        except Exception as e:
            print(f"⚠️ Error processing profile {i+1}: {e}")
            continue
    
    return results

def create_lead(name, handle, bio, platform, tweet_text=None):
    """
    Create a standardized lead dictionary with additional filters.
    """
    # Determine verification from tweet text
    is_verified = "verified" in tweet_text.lower() if tweet_text else False

    # Email detection
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    has_email = bool(re.search(email_pattern, bio))

    # Phone detection
    phone_pattern = r"(\+\d{1,2}\s)?\(?\d{3}[\)\s.-]?\d{3}[\s.-]?\d{4}"
    has_phone = bool(re.search(phone_pattern, bio))

    return {
        "name": name,
        "handle": handle,
        "bio": bio,
        "platform": platform,
        "dm": "",  # DM will be generated later
        "is_verified": is_verified,
        "has_email": has_email,
        "has_phone": has_phone,
        "extraction_method": "Linkedin Search"  # or however you label your method
    }

def handle_linkedin_simple():
    """Main LinkedIn scraper with simple welcome page handling and smart user-aware deduplication"""
    
    if not os.path.exists(AUTH_FILE):
        print(f"❌ {AUTH_FILE} not found!")
        print("💡 Please run the auth script first to save your login session")
        return []
    
    # Setup scraper with usage limits
    estimated_leads = MAX_PAGES * 5  # LinkedIn typically gives ~5 leads per page
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print("🔐 Launching LinkedIn scraper with simple welcome handling...")
        
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--disable-default-apps'
            ]
        )
        
        context = browser.new_context(
            storage_state=AUTH_FILE,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale='en-US'
        )
        
        # Add stealth scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        
        page = context.new_page()
        all_raw_results = []
        
        try:
            # Step 1: Navigate to LinkedIn and handle welcome page simply
            print("🔍 Testing LinkedIn access...")
            
            try:
                page.goto("https://www.linkedin.com/", timeout=EXTRACTION_TIMEOUT * 1000)
                human_delay(2, 4)
                
                # SIMPLE: Handle LinkedIn two-step login flow with proper timing
                print("⏳ Waiting 3 seconds for LinkedIn page to fully load...")
                time.sleep(3)
                
                current_url = page.url
                print(f"🔍 Current URL: {current_url}")
                
                # Step 1: Handle /hp page (first login page)
                if '/hp' in current_url:
                    print("🖱️ Found LinkedIn /hp page - looking for 'Sign in as Sidney'...")
                    
                    try:
                        # Wait a bit more for page content to load
                        time.sleep(2)
                        page_text = page.inner_text('body')
                        
                        if 'sign in as sidney' in page_text.lower():
                            print("✅ Found 'Sign in as Sidney' option")
                            
                            # Look for Sidney profile box on /hp page
                            hp_selectors = [
                                'div:has-text("Sign in as Sidney")',
                                'button:has-text("Sign in as Sidney")', 
                                'div:has-text("Sidney")',
                                'div:has-text("4*****@gmail.com")',
                                'button:has-text("4*****@gmail.com")',
                                # Generic selectors for profile area
                                'div:has(text("Sidney"))',
                                'div:has(text("@gmail.com"))'
                            ]
                            
                            profile_clicked = False
                            for selector in hp_selectors:
                                try:
                                    element = page.query_selector(selector)
                                    if element and element.is_visible():
                                        print(f"🖱️ Clicking Sidney profile on /hp page: {selector}")
                                        element.click()
                                        profile_clicked = True
                                        print("✅ Clicked Sidney profile on /hp page")
                                        break
                                except:
                                    continue
                            
                            if not profile_clicked:
                                print("⚠️ Could not find Sidney profile box on /hp page - trying fallback")
                                # Fallback: click in area where "Sign in as Sidney" typically appears
                                try:
                                    page.click('body', position={'x': 400, 'y': 400})
                                    print("✅ Fallback click attempted on /hp page")
                                except:
                                    print("⚠️ Fallback click failed on /hp page")
                            
                            # Wait longer for redirect and page load
                            print("⏳ Waiting 5 seconds for redirect to /login page...")
                            time.sleep(5)
                            
                        else:
                            print("⚠️ 'Sign in as Sidney' not found on /hp page")
                            
                    except Exception as e:
                        print(f"⚠️ Error handling /hp page: {e}")
                
                # Step 2: Handle /login page (second login page) - with fresh URL check
                current_url = page.url
                print(f"🔍 Updated URL after potential redirect: {current_url}")
                
                if '/login' in current_url:
                    print("🖱️ Now on LinkedIn /login page - waiting for page to fully load...")
                    
                    # Wait for login page to fully load
                    time.sleep(3)
                    
                    try:
                        # Wait for specific elements to be present before proceeding
                        print("⏳ Waiting for login page elements to load...")
                        
                        # Try to wait for page content to be ready
                        for attempt in range(3):
                            try:
                                page_text = page.inner_text('body')
                                if len(page_text) > 100:  # Page has substantial content
                                    break
                                print(f"   Attempt {attempt + 1}: Page content still loading...")
                                time.sleep(2)
                            except:
                                time.sleep(2)
                        
                        page_text = page.inner_text('body')
                        print(f"📄 Login page content loaded (length: {len(page_text)} chars)")
                        
                        if ('sidney' in page_text.lower() and '@gmail.com' in page_text) or '4*****@gmail.com' in page_text:
                            print("✅ Found Sidney profile on /login page")
                            
                            # Look for Sidney profile box on /login page
                            login_selectors = [
                                'div:has-text("Sidney Muhammad")',
                                'div:has-text("Sidney")',
                                'button:has-text("Sidney")',
                                'div:has-text("4*****@gmail.com")',
                                'div:has-text("@gmail.com")',
                                'button:has-text("4*****@gmail.com")',
                                # Look for clickable profile containers
                                'div[role="button"]:has-text("Sidney")',
                                'button[data-test-id="profile-card"]',
                                'div[data-test-id="guest-user-card"]',
                                # Broader selectors
                                'div:has(div:has-text("Sidney"))',
                                'div:has(div:has-text("@gmail.com"))'
                            ]
                            
                            login_clicked = False
                            for selector in login_selectors:
                                try:
                                    element = page.query_selector(selector)
                                    if element and element.is_visible():
                                        print(f"🖱️ Clicking Sidney profile on /login page: {selector}")
                                        element.click()
                                        login_clicked = True
                                        print("✅ Clicked Sidney profile on /login page")
                                        break
                                except:
                                    continue
                            
                            if not login_clicked:
                                print("⚠️ Could not find Sidney profile box on /login page - trying fallback")
                                # Fallback: click in center area where profile typically appears
                                try:
                                    page.click('body', position={'x': 400, 'y': 350})
                                    print("✅ Fallback click attempted on /login page")
                                except:
                                    print("⚠️ Fallback click failed on /login page")
                            
                            # Wait longer for final login completion
                            print("⏳ Waiting 6 seconds for login completion...")
                            time.sleep(6)
                            
                        else:
                            print("⚠️ Sidney profile not found on /login page")
                            print(f"📄 Page text preview: {page_text[:200]}...")
                            
                    except Exception as e:
                        print(f"⚠️ Error handling /login page: {e}")
                
                else:
                    print(f"⚠️ Expected /login URL but got: {current_url}")
                
                # Check final login status with more time
                time.sleep(2)
                final_url = page.url
                print(f"🔍 Final URL after login: {final_url}")
                
                if '/feed' in final_url or '/in/' in final_url or (final_url == 'https://www.linkedin.com/' and '/login' not in final_url and '/hp' not in final_url):
                    print("✅ Login successful - now on LinkedIn main page")
                else:
                    print("⚠️ Login may not be complete - continuing anyway")
                    print(f"   Current URL: {final_url}")
                
            except PlaywrightTimeout:
                print("⚠️ LinkedIn main page timeout")
                # Try manual intervention
                if not manual_intervention_mode(page, "Navigate to linkedin.com manually and log in if needed"):
                    browser.close()
                    return []
            
            # Check if we're blocked
            if is_linkedin_blocking(page):
                print("🚨 LinkedIn is blocking access")
                if not manual_intervention_mode(page, "Complete any security challenges and navigate to LinkedIn"):
                    browser.close()
                    return []
            
            print("✅ LinkedIn access confirmed")
            
            # Step 2: Navigate to search
            print(f"\n🔍 Searching for '{SEARCH_TERM}'...")
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={SEARCH_TERM.replace(' ', '%20')}"
            
            try:
                page.goto(search_url, timeout=EXTRACTION_TIMEOUT * 1000)
                human_delay(3, 5)
                
                # Handle any additional welcome pages on search
                print("🔍 Checking for additional welcome prompts on search page...")
                time.sleep(2)
                
                # Quick check for welcome elements on search page
                for selector in ['button:has-text("Skip")', 'button:has-text("Not now")', 'button:has-text("Continue")']:
                    try:
                        button = page.query_selector(selector)
                        if button and button.is_visible():
                            print(f"🖱️ Found additional welcome prompt - clicking skip")
                            button.click()
                            time.sleep(2)
                            break
                    except:
                        continue
                
            except PlaywrightTimeout:
                print("⚠️ Search page timeout")
                # Manual fallback
                if not manual_intervention_mode(page, f"Navigate to LinkedIn search and search for '{SEARCH_TERM}' manually"):
                    browser.close()
                    return []
            
            # Check if search is blocked
            if is_linkedin_blocking(page):
                print("🚨 Search is being blocked")
                if not manual_intervention_mode(page, f"Complete challenges and search for '{SEARCH_TERM}' manually"):
                    browser.close()
                    return []
            
            # Step 3: Extract profiles from current page (raw results)
            print("📋 Extracting profiles from search results...")
            page.screenshot(path="linkedin_search_page.png")
            print("📸 Search page screenshot: linkedin_search_page.png")
            
            results = extract_profiles_from_page(page)
            all_raw_results.extend(results)
            
            if not results:
                print("❌ No profiles extracted automatically")
                print("🔄 Switching to manual guidance mode...")
                
                if manual_intervention_mode(page, "Navigate to search results and scroll to see all profiles"):
                    # Try extraction again after manual intervention
                    results = extract_profiles_from_page(page)
                    all_raw_results.extend(results)
            
            print(f"📊 Page 1 profiles found: {len(results)}")
            
            # Step 4: Try to get more results (next pages) if successful
            if all_raw_results and len(all_raw_results) < 50:  # If we got some but want more
                for page_num in range(2, MAX_PAGES + 1):
                    try:
                        print(f"\n📄 Trying to get page {page_num} results...")
                        
                        # Look for next page button or pagination
                        next_selectors = [
                            'button[aria-label="Next"]',
                            'button:has-text("Next")',
                            f'button[aria-label="Page {page_num}"]',
                            'li.artdeco-pagination__indicator--number button'
                        ]
                        
                        page_found = False
                        for selector in next_selectors:
                            try:
                                next_button = page.query_selector(selector)
                                if next_button and next_button.is_visible():
                                    print(f"🖱️ Found next page button - clicking...")
                                    next_button.click()
                                    human_delay(3, 5)
                                    page_found = True
                                    break
                            except:
                                continue
                        
                        if not page_found:
                            print(f"❌ Could not find page {page_num} automatically")
                            try_manual = input(f"🤔 Try manual navigation to page {page_num}? (y/n): ")
                            if try_manual.lower() == 'y':
                                if manual_intervention_mode(page, f"Navigate to page {page_num} of search results manually"):
                                    page_results = extract_profiles_from_page(page)
                                    if page_results:
                                        all_raw_results.extend(page_results)
                                        print(f"✅ Added {len(page_results)} results from manual page {page_num}")
                                    continue
                            break
                        
                        # Extract from new page
                        page_results = extract_profiles_from_page(page)
                        if page_results:
                            all_raw_results.extend(page_results)
                            print(f"✅ Added {len(page_results)} results from page {page_num}")
                        else:
                            print(f"❌ No results from page {page_num}")
                            break
                            
                    except Exception as e:
                        print(f"⚠️ Error getting page {page_num}: {e}")
                        break
            
            print(f"📊 Total raw profiles collected: {len(all_raw_results)}")
            
            if not all_raw_results:
                print("❌ No raw results extracted")
                browser.close()
                return []
            
            # 🚀 APPLY SMART USER-AWARE DEDUPLICATION
            print(f"\n🧠 Applying deduplication strategy: {DEDUP_MODE}")
            print(f"👤 User-specific deduplication for: {username}")
            
            if SMART_DEDUP_AVAILABLE and DEDUP_MODE == "smart_user_aware":
                unique_results, dedup_stats = process_leads_with_smart_deduplication(
                    raw_leads=all_raw_results,
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
                    all_raw_results, username, PLATFORM_NAME, mode
                )
            else:
                # Fallback to simple deduplication
                print("📋 Using basic deduplication (smart dedup not available)")
                unique_results = []
                seen_names = set()
                for result in all_raw_results:
                    name_key = result.get('name', '').lower().strip()
                    if name_key not in seen_names and len(name_key) > 1:
                        unique_results.append(result)
                        seen_names.add(name_key)
                dedup_stats = {"basic": True, "kept": len(unique_results)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw profiles extracted: {len(all_raw_results)}")
            print(f"  ✅ Unique profiles after dedup: {len(unique_results)}")
            print(f"  📈 Efficiency: {(len(unique_results) / len(all_raw_results) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            print(f"  📄 Pages processed: {min(MAX_PAGES, len(all_raw_results) // 5 + 1)}")
            
            if len(unique_results) > 50:
                print(f"🎉 EXCELLENT: {len(unique_results)} profiles (target exceeded!)")
            elif len(unique_results) > 20:
                print(f"✅ GOOD: {len(unique_results)} profiles")
            elif len(unique_results) > 10:
                print(f"⚠️ MODERATE: {len(unique_results)} profiles")
            else:
                print(f"⚠️ LOW: {len(unique_results)} profiles")
            
            all_results = unique_results

        except Exception as e:
            print(f"🚨 Unexpected error: {e}")
            print("🔄 Switching to full manual mode...")
            if manual_intervention_mode(page, "Handle the error and navigate to where you want to extract profiles"):
                results = extract_profiles_from_page(page)
                all_raw_results.extend(results)
                
                # Apply deduplication even on manual results
                if all_raw_results:
                    if SMART_DEDUP_AVAILABLE and DEDUP_MODE == "smart_user_aware":
                        unique_results, dedup_stats = process_leads_with_smart_deduplication(
                            raw_leads=all_raw_results,
                            username=username,
                            platform=PLATFORM_NAME
                        )
                    else:
                        # Simple dedup fallback
                        unique_results = []
                        seen_names = set()
                        for result in all_raw_results:
                            name_key = result.get('name', '').lower().strip()
                            if name_key not in seen_names and len(name_key) > 1:
                                unique_results.append(result)
                                seen_names.add(name_key)
                    all_results = unique_results
                else:
                    all_results = []

        # Finalize results with usage tracking
        if all_results:
            try:
                finalized_results = finalize_scraper_results(PLATFORM_NAME, all_results, SEARCH_TERM, username)
                all_results = finalized_results
                print("✅ Results finalized and usage tracked")
            except Exception as e:
                print(f"⚠️ Error finalizing results: {e}")
                # Continue with original results if finalization fails
        
        # Save results to multiple files
        if all_results or (all_raw_results and SAVE_RAW_LEADS):
            output_file = f"linkedin_leads_{username}_{date_str}.csv"
            fieldnames = ['name', 'handle', 'bio', 'url', 'platform', 'dm', 'headline', 'location', 'extraction_method', 'search_term', 'relevance_score', 'is_verified', 'has_email', 'has_phone']
            
            files_saved = []
            
            # Save processed results to main CSV
            if all_results:
                out_path = CSV_DIR / output_file
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_results)
                files_saved.append(output_file)
            
            # Save raw results if enabled and different from processed
            if all_raw_results and SAVE_RAW_LEADS and len(all_raw_results) != len(all_results):
                raw_filename = f"linkedin_leads_raw_{username}_{date_str}.csv"
                raw_path = CSV_DIR / raw_filename
                with open(raw_filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_raw_results)
                files_saved.append(raw_filename)
                print(f"📋 Raw leads saved to {raw_filename}")
            
            print(f"\n💾 Saving {len(all_results)} unique profiles...")
            print(f"🔍 Files saved: {', '.join(files_saved)}")
            
            # Upload to Google Sheets and send email
            try:
                from sheets_writer import write_leads_to_google_sheet
                from daily_emailer import send_daily_leads_email
                
                print("📝 Writing to Google Sheets...")
                write_leads_to_google_sheet(all_results)
                print("✅ Successfully uploaded to Google Sheets")
                
                print("📤 Sending LinkedIn leads via email...")
                send_daily_leads_email()
                print("✅ LinkedIn leads email sent!")
                
            except ImportError:
                print("📦 sheets_writer.py or daily_emailer.py not found - export features skipped")
            except Exception as e:
                print(f"⚠️ Export/email error: {e}")
            
            # Show sample results
            if all_results:
                print(f"\n🎉 Sample processed results:")
                for i, result in enumerate(all_results[:3]):
                    print(f"  {i+1}. {result['name']}")
                    print(f"     {result['headline']}")
                    print(f"     📍 {result['location']}")
                    print(f"     Score: {result.get('relevance_score', 'N/A')}")
                    print(f"     DM: {result['dm'][:50]}...")
                    print()
            
            if all_raw_results and SAVE_RAW_LEADS and len(all_raw_results) != len(all_results):
                print(f"\n📋 Raw profiles preserved: {len(all_raw_results)} total")
        else:
            print("⚠️ No profiles extracted")
            all_results = []
        
        # Keep browser open for additional manual work if desired
        if all_results:
            continue_manual = input(f"\n🤔 Keep browser open for more manual extraction? (y/n): ")
            if continue_manual.lower() == 'y':
                print("🔄 Browser staying open for manual work...")
                print("Close the browser window when you're done")
                try:
                    while not page.is_closed():
                        time.sleep(1)
                except:
                    pass
        
        browser.close()
        return all_results

if __name__ == "__main__":
    print(f"🚀 LinkedIn Scraper - Simple Welcome Handler with Smart Deduplication")
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"💡 Features:")
    print(f"  • Simple automatic welcome page handling")
    print(f"  • Multi-page extraction with manual fallback")
    print(f"  • Smart user-aware deduplication")
    print(f"  • Enhanced result tracking")
    print(f"  • Automatic account exclusion")
    print()
    print(f"📄 Max pages: {MAX_PAGES}")
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print()
    
    results = handle_linkedin_simple()
    
    if results and len(results) >= 20:
        print(f"\n🎉 LINKEDIN SUCCESS: {len(results)} qualified leads extracted!")
    elif results:
        print(f"\n✅ LinkedIn scraper completed with {len(results)} leads")
    else:
        print(f"\n💡 No results this time. LinkedIn's bot detection is very aggressive.")
        print(f"💭 Tips for next time:")
        print(f"  - Wait longer between attempts (hours, not minutes)")
        print(f"  - Try different search terms")
        print(f"  - Consider using LinkedIn's official tools")