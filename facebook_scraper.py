from datetime import datetime
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

# 🚀 NEW: Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

# 🚀 NEW: Import the enhanced config system
from enhanced_config_loader import ConfigLoader, should_exclude_account

PLATFORM_NAME = "facebook"

# Load Facebook session state
try:
    with open("facebook_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("❌ facebook_auth.json not found!")
    exit(1)

# ✅ CORRECT: Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
enhanced_config_loader = ConfigLoader()
config = config_loader.get_platform_config('facebook')

# ✅ FIXED: Extract all config values properly
SEARCH_TERM = config["search_term"]
MAX_SCROLLS = config["max_scrolls"]
MAX_PAGES = config.get("max_pages", 100)
DELAY_MIN = config.get("delay_min", 2)
DELAY_MAX = config.get("delay_max", 5)
LEAD_OUTPUT_FILE = config["lead_output_file"]
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45000)

# 🚀 NEW: Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")  # Can be: keep_all, session_only, smart_user_aware, aggressive
SAVE_RAW_LEADS = config.get("save_raw_leads", True)  # Always save raw leads to separate file

# 🚀 NEW: Dynamic excluded accounts (NO HARDCODING!)
excluded_accounts = config_loader.get_excluded_accounts('facebook')
print(f"📋 Facebook Scraper Configuration:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  📄 Max Pages: {MAX_PAGES}")
print(f"  ⏱️ Delay Range: {DELAY_MIN}-{DELAY_MAX}s")
print(f"  📁 Output File: {LEAD_OUTPUT_FILE}")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

def safe_get_text(element):
    """Get text with multiple fallback methods"""
    methods = [
        lambda: element.inner_text(timeout=2000),
        lambda: element.text_content(),
        lambda: re.sub(r'<[^>]+>', ' ', element.inner_html()),
    ]
    
    for method in methods:
        try:
            text = method()
            if text and len(text.strip()) > 5:
                return text.strip()
        except:
            continue
    return ""

def is_relevant_to_search_term(name, title, location):
    """Check if the profile is relevant to the search term"""
    analysis_text = f"{name} {title} {location}".lower()
    search_keywords = SEARCH_TERM.lower().split()
    relevance_score = 0
    
    # Primary keywords (search term) - weight 3
    for keyword in search_keywords:
        if keyword in analysis_text:
            relevance_score += 3
    
    # Investment/finance related keywords
    if any(word in SEARCH_TERM.lower() for word in ['investor', 'trading', 'stock', 'crypto', 'finance']):
        finance_keywords = ['investor', 'trading', 'stocks', 'crypto', 'finance', 'money', 'wealth', 'portfolio', 'investment', 'analyst', 'advisor', 'capital']
        for keyword in finance_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Fitness related keywords
    if any(word in SEARCH_TERM.lower() for word in ['coach', 'trainer', 'fitness']):
        fitness_keywords = ['coach', 'trainer', 'fitness', 'workout', 'exercise', 'health', 'nutrition', 'wellness', 'personal trainer']
        for keyword in fitness_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Business related keywords
    if any(word in SEARCH_TERM.lower() for word in ['business', 'entrepreneur', 'ceo']):
        business_keywords = ['ceo', 'founder', 'entrepreneur', 'business', 'startup', 'executive', 'director', 'manager']
        for keyword in business_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # 🍰 Culinary related keywords
    if any(word in SEARCH_TERM.lower() for word in ['chef', 'baker', 'culinary', 'cook', 'pastry']):
        culinary_keywords = ['chef', 'baker', 'culinary', 'cook', 'cooking', 'baking', 'pastry', 'restaurant', 'kitchen', 'food', 'cuisine', 'recipe', 'culinary arts', 'dessert', 'cake', 'bread', 'confectionery']
        for keyword in culinary_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Lower threshold for higher volume
    return relevance_score >= 1, relevance_score

def extract_facebook_profiles(page):
    """Extract profiles from Facebook search results - PRESERVES ALL RAW LEADS"""
    print("📋 Extracting Facebook profiles (preserving all raw leads)...")
    
    results = []
    excluded_count = 0
    
    # Wait for content to load
    time.sleep(DELAY_MIN)
    
    # Check page status
    try:
        current_url = page.url
        print(f"🔍 Current URL: {current_url}")
        
        if any(indicator in current_url.lower() for indicator in ['login', 'checkpoint', 'help', 'error', 'facebook.com/login']):
            print("🚨 Facebook is blocking access or redirected to login")
            print("💡 Please refresh your facebook_auth.json by logging in again")
            return []
            
        page_title = page.title()
        print(f"📄 Page title: {page_title}")
    except Exception as e:
        print(f"⚠️ Error checking page status: {e}")
        return []
    
    # Take screenshot for debugging
    try:
        print("📸 Taking debug screenshot...")
        page.screenshot(path="facebook_extraction_debug.png", timeout=5000)
        print("📸 Debug screenshot saved: facebook_extraction_debug.png")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {str(e)[:50]}...")
    
    # Use the optimized extraction approach that worked
    print("🔍 Using optimized profile extraction...")
    
    try:
        # Primary selector - divs containing Facebook profile links
        elements = page.query_selector_all('div:has(a[href*="facebook.com"])')
        print(f"  Found {len(elements)} potential profile containers")
        
        if len(elements) == 0:
            print("⚠️ No profile containers found - trying fallback approaches")
            fallback_selectors = [
                'div[tabindex="0"]',
                'div[role="button"]', 
                'div[role="article"]',
                'a[href*="facebook.com"]'
            ]
            
            for selector in fallback_selectors:
                elements = page.query_selector_all(selector)
                if len(elements) > 0:
                    print(f"  Fallback selector '{selector}' found {len(elements)} elements")
                    break
        
        if len(elements) == 0:
            print("❌ No elements found with any approach")
            return []
        
        processed = 0
        errors = 0
        max_elements = min(500, len(elements))
        max_results = 300  # Increased target for raw leads
        
        print(f"📊 Processing up to {max_elements} elements...")
        
        for i, element in enumerate(elements[:max_elements]):
            if len(results) >= max_results:
                print(f"🎯 Reached processing limit of {max_results} - stopping")
                break
                
            try:
                # Get text content
                text_content = safe_get_text(element)
                if not text_content or len(text_content) < 10:
                    continue
                
                processed += 1
                
                # Extract name using multiple patterns
                lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                if not lines:
                    continue
                
                name = ""
                name_patterns = [
                    # Clean line that looks like a name
                    lambda lines: next((line for line in lines[:3] 
                                      if 2 <= len(line) <= 80 
                                      and not line.isdigit() 
                                      and not line.startswith('http')
                                      and not any(skip in line.lower() for skip in ['add friend', 'follow', 'message', 'see all', 'mutual'])), None),
                    # Capitalized words
                    lambda lines: next((line for line in lines[:5] 
                                      if len(line.split()) <= 4 
                                      and all(word[0].isupper() for word in line.split() if word)), None),
                    # First substantial line
                    lambda lines: lines[0] if lines and len(lines[0]) >= 2 else None
                ]
                
                for pattern_func in name_patterns:
                    try:
                        potential_name = pattern_func(lines)
                        if potential_name:
                            name = potential_name
                            break
                    except:
                        continue
                
                if not name:
                    continue
                
                # Very lenient relevance check for raw leads
                is_relevant, relevance_score = is_relevant_to_search_term(name, text_content, "")
                
                # Accept almost everything for raw leads
                if relevance_score < 1 and len(name) < 3:  # Only filter obviously bad data
                    continue

                # Check for exclusion (with error handling)
                try:
                    if should_exclude_account(name, PLATFORM_NAME, enhanced_config_loader):
                        excluded_count += 1
                        continue
                except Exception as e:
                    # Don't let exclusion errors stop extraction
                    pass
                
                # Extract profile URL
                profile_url = ""
                try:
                    link_selectors = [
                        'a[href*="facebook.com"]',
                        'a[href*="/profile"]',
                        'a[href*="profile.php"]'
                    ]
                    
                    for selector in link_selectors:
                        links = element.query_selector_all(selector)
                        for link in links:
                            href = link.get_attribute('href') or ""
                            if href and ('facebook.com' in href or 'profile' in href):
                                if href.startswith('/'):
                                    profile_url = 'https://facebook.com' + href
                                else:
                                    profile_url = href
                                break
                        if profile_url:
                            break
                except:
                    pass
                
                # Create raw lead (preserve everything)
                lead = {
                    "name": name,
                    "handle": name,
                    "bio": text_content[:200] if len(text_content) > 200 else text_content,
                    "url": profile_url or 'URL not found'
                }
                
                # Add platform and DM
                lead["platform"] = "facebook"
                try:
                    lead["dm"] = generate_dm_with_fallback(
                        name=lead["name"],
                        bio=lead["bio"],
                        platform=lead["platform"]
                    )
                except Exception as e:
                    lead["dm"] = f"Hi {name}! I noticed you're interested in {SEARCH_TERM}."
                
                # Add Facebook-specific fields
                lead.update({
                    'title': f'Professional interested in {SEARCH_TERM}',
                    'location': 'Location not specified',
                    'followers': 'Followers not shown',
                    'profile_url': profile_url or 'URL not found',
                    'search_term': SEARCH_TERM,
                    'extraction_method': 'Facebook Raw Extraction',
                    'relevance_score': relevance_score,
                    'is_verified': False,
                    'has_email': False,
                    'has_phone': False,
                    'extracted_at': datetime.now().isoformat(),
                    'raw_text_sample': text_content[:100]  # Keep sample of raw text for debugging
                })
                
                results.append(lead)
                
                # Progress updates
                if len(results) % 50 == 0:
                    print(f"  📊 Progress: {len(results)} raw leads extracted...")
                
            except Exception as e:
                errors += 1
                continue
        
        print(f"📊 Raw extraction complete:")
        print(f"  🎯 Elements processed: {processed}")
        print(f"  📥 Raw leads extracted: {len(results)}")
        print(f"  🚫 Excluded accounts: {excluded_count}")
        print(f"  ⚠️ Processing errors: {errors}")
        
        # Return ALL raw leads - deduplication happens later with user context
        return results
        
    except Exception as e:
        print(f"🚨 Major extraction error: {str(e)}")
        return []

def save_leads_to_files(leads, raw_leads, username, timestamp):
    """Save leads to multiple files for different purposes"""
    files_saved = []
    
    try:
        fieldnames = ['name', 'handle', 'bio', 'url', 'platform', 'dm', 'title', 'location', 'followers', 'profile_url', 'search_term', 'extraction_method', 'relevance_score', 'is_verified', 'has_email', 'has_phone', 'extracted_at']
        
        # Save processed leads
        processed_file = f"facebook_leads_processed_{timestamp}.csv"
        with open(processed_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(leads)
        files_saved.append(processed_file)
        print(f"✅ Processed leads saved: {processed_file}")
        
        # Save raw leads if requested
        if SAVE_RAW_LEADS and raw_leads and len(raw_leads) != len(leads):
            raw_fieldnames = fieldnames + ['raw_text_sample']
            raw_file = f"facebook_leads_raw_{timestamp}.csv"
            with open(raw_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=raw_fieldnames)
                writer.writeheader()
                writer.writerows(raw_leads)
            files_saved.append(raw_file)
            print(f"✅ Raw leads saved: {raw_file}")
        
        # Save user-specific backup
        user_file = f"facebook_leads_{username}_{timestamp}.csv"
        with open(user_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(leads)
        files_saved.append(user_file)
        print(f"✅ User backup saved: {user_file}")
        
        return files_saved
        
    except Exception as e:
        print(f"⚠️ Error saving files: {e}")
        return []

def main():
    """Main function with smart user-aware deduplication"""
    
    estimated_leads = MAX_SCROLLS * 8
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    with sync_playwright() as p:
        print("🔐 Launching Facebook scraper...")
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            storage_state=storage_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        try:
            # Navigate to search
            search_url = f"https://www.facebook.com/search/people/?q={SEARCH_TERM.replace(' ', '%20')}"
            print(f"🔍 Searching for: '{SEARCH_TERM}'")
            print(f"📍 URL: {search_url}")
            
            page.goto(search_url, timeout=EXTRACTION_TIMEOUT * 1000)
            time.sleep(3)
            
            # Check login status
            if 'login' in page.url.lower():
                print("🚨 Not logged in properly!")
                print("💡 Please run Facebook auth script to save login session")
                browser.close()
                return []
            
            print("✅ Successfully loaded search results")
            
            # Enhanced scrolling
            print(f"📜 Scrolling {MAX_SCROLLS} times to load profiles...")
            for i in range(MAX_SCROLLS):
                for micro_scroll in range(3):
                    page.mouse.wheel(0, 800)
                    time.sleep(0.5)
                
                if (i + 1) % 5 == 0:
                    print(f"  🔄 Scroll checkpoint {i + 1}/{MAX_SCROLLS}")
                    time.sleep(random.uniform(3, 6))
                else:
                    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            
            print("⏳ Stabilizing content...")
            time.sleep(5)
            
            # Extract ALL raw leads
            raw_leads = extract_facebook_profiles(page)
            
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
                seen_names = set()
                for lead in raw_leads:
                    name_key = lead.get('name', '').lower().strip()
                    if name_key not in seen_names and len(name_key) > 1:
                        unique_leads.append(lead)
                        seen_names.add(name_key)
                dedup_stats = {"basic": True, "kept": len(unique_leads)}
            
            # Final results summary
            print(f"\n📊 FINAL RESULTS SUMMARY:")
            print(f"  📥 Raw leads extracted: {len(raw_leads)}")
            print(f"  ✅ Unique leads after dedup: {len(unique_leads)}")
            print(f"  📈 Efficiency: {(len(unique_leads) / len(raw_leads) * 100):.1f}% kept")
            print(f"  👤 User: {username}")
            print(f"  🔄 Dedup mode: {DEDUP_MODE}")
            
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
            
            # Save to multiple files
            if leads or (raw_leads and SAVE_RAW_LEADS):
                files_saved = save_leads_to_files(leads, raw_leads, username, timestamp)
                
                # Upload to Google Sheets and send email
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    print("📝 Writing to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print("✅ Successfully uploaded to Google Sheets")
                    
                    print("📤 Sending leads via email...")
                    send_daily_leads_email()
                    print("✅ Daily leads email sent!")
                    
                except ImportError:
                    print("📦 Export features not available")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show sample results
                if leads:
                    print(f"\n🎉 Sample processed leads:")
                    for i, lead in enumerate(leads[:3]):
                        print(f"  {i+1}. {lead['name']}")
                        print(f"     Bio: {lead['bio'][:50]}...")
                        print(f"     URL: {lead.get('profile_url', 'N/A')}")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    print(f"🔍 Files saved: {', '.join(files_saved)}")
                    
            else:
                print("⚠️ No leads to save")
                
        except Exception as e:
            print(f"🚨 Error: {e}")
            leads = []
        finally:
            print("🔍 Keeping browser open for 3 seconds...")
            time.sleep(3)
            browser.close()
            
        return leads

if __name__ == "__main__":
    print(f"🚀 Facebook Scraper - FINAL VERSION")
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"📜 Max scrolls: {MAX_SCROLLS}")
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    
    results = main()
    
    if results and len(results) >= 50:
        print(f"🎉 SUCCESS: Facebook scraper completed with {len(results)} leads!")
    elif results:
        print(f"✅ Facebook scraper completed with {len(results)} leads")
    else:
        print(f"❌ Facebook scraper completed with 0 leads")