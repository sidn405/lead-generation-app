
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
from persistence import save_leads_to_files

# Directory where your CSV files are saved
CSV_DIR = os.path.join(os.getcwd(), "csv_exports")
os.makedirs(CSV_DIR, exist_ok=True)

# Import the centralized usage tracker
from usage_tracker import setup_scraper_with_limits, finalize_scraper_results
from config_loader import ConfigLoader, should_exclude_account, get_platform_config

# 🚀 Import smart duplicate detection
try:
    from smart_duplicate_handler import process_leads_with_smart_deduplication
    from deduplication_config import DeduplicationMode, apply_deduplication_strategy
    SMART_DEDUP_AVAILABLE = True
except ImportError:
    print("⚠️ Smart deduplication not available - using basic dedup")
    SMART_DEDUP_AVAILABLE = False

PLATFORM_NAME = "youtube"

# Load YouTube session state
try:
    with open("youtube_auth.json", "r") as f:
        storage_state = json.load(f)
except FileNotFoundError:
    print("❌ youtube_auth.json not found!")
    print("🔑 Run save_youtube_auth_state.py first to authenticate")
    exit(1)

# ✅ CORRECT: Use centralized config system
from config_loader import get_platform_config, config_loader

# 🚀 NEW: Initialize config loader
config_loader = ConfigLoader()
config = config_loader.get_platform_config('youtube')

# ✅ FIXED: Extract all config values properly
SEARCH_TERM = config["search_term"]  # Uses "stock investor" from global config
MAX_SCROLLS = config["max_scrolls"]  # Uses actual config value (10)
DELAY_BETWEEN_SCROLLS = config.get("delay_between_scrolls", 3) # Uses config value (3)
EXTRACTION_TIMEOUT = config.get("extraction_timeout", 45000)  # Uses config value (45)
LEAD_OUTPUT_FILE = config["lead_output_file"]  # Uses config value

# Extract search filter values
SEARCH_FILTERS = config.get("search_filters", {})
CHANNELS_ONLY = SEARCH_FILTERS.get("channels_only", True)
MIN_SUBSCRIBERS = SEARCH_FILTERS.get("min_subscribers", 100)
UPLOAD_FREQUENCY = SEARCH_FILTERS.get("upload_frequency", "active")

# 🚀 Deduplication configuration
DEDUP_MODE = config.get("deduplication_mode", "smart_user_aware")
SAVE_RAW_LEADS = config.get("save_raw_leads", True)

# 🚀 NEW: Dynamic excluded accounts (NO HARDCODING!)
excluded_accounts = config_loader.get_excluded_accounts('youtube')
print(f"📋 YouTube Config Loaded:")
print(f"  🔍 Search Term: '{SEARCH_TERM}'")
print(f"  📜 Max Scrolls: {MAX_SCROLLS}")
print(f"  ⏱️ Delay: {DELAY_BETWEEN_SCROLLS}s")
print(f"  👥 Min Subscribers: {MIN_SUBSCRIBERS}")
print(f"  📺 Channels Only: {CHANNELS_ONLY}")
print(f"  🔄 Deduplication Mode: {DEDUP_MODE}")
print(f"  💾 Save Raw Leads: {SAVE_RAW_LEADS}")
if excluded_accounts:
    print(f"  🚫 Excluding {len(excluded_accounts)} accounts: {', '.join(excluded_accounts[:3])}{'...' if len(excluded_accounts) > 3 else ''}")
else:
    print(f"  🚫 No accounts excluded (configured via frontend)")

def is_relevant_to_search_term(channel_name, description):
    """Check if the channel is relevant to the search term"""
    # Combine all text for analysis
    analysis_text = f"{channel_name} {description}".lower()
    
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
        finance_keywords = ['invest', 'trading', 'stock', 'crypto', 'finance', 'money', 'wealth', 'portfolio', 'market', 'trading', 'analysis', 'advisor']
        for keyword in finance_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Fitness related keywords if searching for coaches
    if any(word in SEARCH_TERM.lower() for word in ['coach', 'trainer', 'fitness']):
        fitness_keywords = ['fitness', 'coach', 'trainer', 'workout', 'exercise', 'health', 'nutrition', 'wellness', 'gym', 'bodybuilding']
        for keyword in fitness_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Business related keywords
    if any(word in SEARCH_TERM.lower() for word in ['business', 'entrepreneur', 'ceo']):
        business_keywords = ['business', 'entrepreneur', 'startup', 'ceo', 'founder', 'company', 'executive', 'leadership']
        for keyword in business_keywords:
            if keyword in analysis_text:
                relevance_score += 2
    
    # Consider relevant if score >= 3
    return relevance_score >= 3, relevance_score

def extract_subscriber_count(sub_text):
    """Extract numerical subscriber count from text like '1.2K subscribers'"""
    if not sub_text:
        return 0
    
    # Remove 'subscribers' and clean text
    clean_text = sub_text.lower().replace('subscribers', '').replace('subscriber', '').strip()
    
    try:
        # Handle K, M, B suffixes
        if 'k' in clean_text:
            num = float(clean_text.replace('k', '')) * 1000
        elif 'm' in clean_text:
            num = float(clean_text.replace('m', '')) * 1000000
        elif 'b' in clean_text:
            num = float(clean_text.replace('b', '')) * 1000000000
        else:
            # Handle comma-separated numbers
            num = float(clean_text.replace(',', ''))
        
        return int(num)
    except:
        return 0

def get_search_url_for_term(search_term):
    """Get appropriate YouTube search URL based on search term"""
    base_url = "https://www.youtube.com/results"
    
    # Channel filter parameter
    channel_filter = "&sp=EgIQAg%253D%253D"  # Filter for channels only
    
    # Encode search term
    encoded_term = search_term.replace(' ', '+')
    
    search_url = f"{base_url}?search_query={encoded_term}{channel_filter}"
    
    return search_url

def extract_youtube_channels(page):
    """Extract channel information from YouTube search results with relevance filtering"""
    print("📋 Extracting YouTube channels...")
    
    results = []
    excluded_count = 0  # ✅ ADD THIS LINE
    
    # Wait for content to load
    time.sleep(DELAY_BETWEEN_SCROLLS)
    
    # Take screenshot for debugging
    try:
        page.screenshot(path="youtube_extraction_debug.png", timeout=10000)
        print("📸 Debug screenshot: youtube_extraction_debug.png")
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")
    
    # Check page status
    try:
        current_url = page.url
        page_title = page.title()
        print(f"🔍 Current URL: {current_url}")
        print(f"📄 Page title: {page_title}")
        
        if 'youtube.com' not in current_url.lower():
            print("🚨 Not on YouTube - check authentication")
            return []
            
    except Exception as e:
        print(f"⚠️ Error checking page status: {e}")
    
    # Multiple approaches to find channel elements
    approaches = [
        # Approach 1: Channel renderer elements
        {
            'name': 'Channel Renderers',
            'selector': 'ytd-channel-renderer',
            'description': 'Main channel result cards'
        },
        # Approach 2: Video owner elements (in case we get video results)
        {
            'name': 'Video Owner Info',
            'selector': 'ytd-video-owner-renderer',
            'description': 'Channel info from video results'
        },
        # Approach 3: Shelf renderer with channels
        {
            'name': 'Shelf Channels',
            'selector': 'ytd-shelf-renderer ytd-channel-renderer',
            'description': 'Channels in shelf sections'
        },
        # Approach 4: Generic approach for any channel links
        {
            'name': 'Channel Links',
            'selector': 'a[href*="/channel/"], a[href*="/@"]',
            'description': 'Any links to channel pages'
        },
        # Approach 5: Compact channel renderer
        {
            'name': 'Compact Channels',
            'selector': 'ytd-compact-channel-renderer',
            'description': 'Compact channel display'
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
            
            for i, element in enumerate(elements):
                try:
                    # Extract channel information
                    channel_name = ""
                    description = ""
                    subscriber_text = ""
                    subscriber_count = 0
                    channel_url = ""
                    channel_handle = ""
                    
                    # Get all text content for analysis
                    try:
                        element_text = element.inner_text().strip()
                        if len(element_text) < 10:
                            continue
                    except:
                        continue
                    
                    # Extract channel name
                    name_selectors = [
                        '#text.ytd-channel-name',
                        '.ytd-channel-name #text',
                        'yt-formatted-string#text',
                        '.yt-simple-endpoint.style-scope.yt-formatted-string',
                        '#channel-title',
                        'a#main-link'
                    ]
                    
                    for selector in name_selectors:
                        try:
                            name_elem = element.query_selector(selector)
                            if name_elem:
                                channel_name = name_elem.inner_text().strip()
                                if channel_name:
                                    break
                        except:
                            continue
                    
                    # If no name found in sub-elements, parse from text
                    if not channel_name:
                        lines = [line.strip() for line in element_text.split('\n') if line.strip()]
                        for line in lines:
                            if (len(line) > 2 and len(line) < 100 and 
                                not any(skip in line.lower() for skip in ['subscribers', 'videos', 'views', 'ago', 'subscribe'])):
                                channel_name = line
                                break
                    
                    if not channel_name or len(channel_name) < 2:
                        continue
                    
                    # Extract channel URL and handle
                    link_selectors = [
                        'a[href*="/channel/"]',
                        'a[href*="/@"]',
                        'yt-simple-endpoint[href*="/channel/"]',
                        'yt-simple-endpoint[href*="/@"]'
                    ]
                    
                    for selector in link_selectors:
                        try:
                            link_elem = element.query_selector(selector)
                            if link_elem:
                                href = link_elem.get_attribute('href')
                                if href:
                                    if href.startswith('/'):
                                        channel_url = 'https://www.youtube.com' + href
                                    else:
                                        channel_url = href
                                    
                                    # Extract handle from URL
                                    if '/@' in channel_url:
                                        channel_handle = channel_url.split('/@')[-1].split('?')[0]
                                    break
                        except:
                            continue
                    
                    # Extract subscriber count
                    sub_patterns = [
                        r'([\d.,]+[KMB]?\s*subscribers?)',
                        r'(\d+[\d.,]*[KMB]?\s*subscribers?)',
                        r'(\d+\s*subscribers?)'
                    ]
                    
                    for pattern in sub_patterns:
                        sub_match = re.search(pattern, element_text, re.IGNORECASE)
                        if sub_match:
                            subscriber_text = sub_match.group(1)
                            subscriber_count = extract_subscriber_count(subscriber_text)
                            break
                    
                    # Extract description
                    desc_selectors = [
                        '#description-text',
                        '.ytd-channel-about-metadata-renderer',
                        'yt-formatted-string#description-text',
                        '.metadata-snippet-text',
                        '#snippet'
                    ]
                    
                    for selector in desc_selectors:
                        try:
                            desc_elem = element.query_selector(selector)
                            if desc_elem:
                                desc_text = desc_elem.inner_text().strip()
                                if len(desc_text) > 10:
                                    description = desc_text
                                    break
                        except:
                            continue
                    
                    # If no description found, create adaptive one
                    if not description:
                        description = f"YouTube channel covering {SEARCH_TERM} topics"
                    
                    # Check relevance to search term
                    is_relevant, relevance_score = is_relevant_to_search_term(channel_name, description)
                    
                    if not is_relevant:
                        print(f"  ⏭️ Skipping {channel_name} (not relevant to '{SEARCH_TERM}', score: {relevance_score})")
                        continue
                    
                    # Check minimum subscriber requirement
                    if subscriber_count > 0 and subscriber_count < MIN_SUBSCRIBERS:
                        print(f"  ⏭️ Skipping {channel_name} ({subscriber_count} subscribers < {MIN_SUBSCRIBERS} minimum)")
                        continue

                    # 🚀 NEW: CHECK FOR EXCLUSION (ONE LINE!)
                    username_to_check = channel_handle if channel_handle else channel_name
                    if should_exclude_account(username_to_check, PLATFORM_NAME, config_loader):
                        excluded_count += 1
                        print(f"  🚫 Excluded: {channel_name}")
                        continue
                    
                    # Create lead with required structure
                    lead = {
                        "name": channel_name,
                        "handle": f"@{channel_handle}" if channel_handle else channel_name,
                        "bio": description[:200],
                        "url": channel_url or 'URL not found'
                    }
                    
                    # Add platform and DM
                    lead["platform"] = "youtube"
                    lead["dm"] = generate_dm_with_fallback(
                        name=lead["name"],
                        bio=lead["bio"],
                        platform=lead["platform"]
                    )
                    
                    # Add YouTube-specific fields
                    lead.update({
                        'subscribers': subscriber_text or 'Subscribers not shown',
                        'subscriber_count': subscriber_count,
                        'video_count': 'Video count not shown',  # Hard to extract reliably
                        'description': description,
                        'channel_url': channel_url or 'URL not found',
                        'search_term': SEARCH_TERM,
                        'extraction_method': approach['name'],
                        'relevance_score': relevance_score
                    })
                    
                    approach_results.append(lead)
                    sub_display = subscriber_text if subscriber_text else "No sub count"
                    print(f"  ✅ {channel_name} | {sub_display} | Score: {relevance_score} | {description[:30]}...")
                    
                except Exception as e:
                    continue
            
            if approach_results:
                print(f"✅ Successfully extracted {len(approach_results)} channels using {approach['name']}")
                results.extend(approach_results)
                break  # Use the first successful approach
            else:
                print(f"❌ No valid channels found with {approach['name']}")
                
        except Exception as e:
            print(f"⚠️ Error with {approach['name']}: {e}")
            continue
    
    # Remove duplicates from all results
    unique_results = []
    seen_names = set()
    for result in results:
        name_key = result['name'].lower().strip()
        if name_key not in seen_names:
            unique_results.append(result)
            seen_names.add(name_key)
    
    print(f"\n📊 Total unique channels extracted: {len(unique_results)}")
    return unique_results

def main():
    """Main function to run YouTube scraper with smart user-aware deduplication"""
    
    # 🚀 FIXED: Setup scraper with usage limits - correct platform name
    estimated_leads = MAX_SCROLLS * 2  # YouTube typically gives ~2 leads per scroll
    can_proceed, message, username = setup_scraper_with_limits(PLATFORM_NAME, estimated_leads, SEARCH_TERM)
    
    if not can_proceed:
        print(f"❌ {message}")
        return []
    
    print(f"✅ {message}")
    print(f"👤 Running as: {username}")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    
    with sync_playwright() as p:
        print("🔐 Launching YouTube scraper...")
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            storage_state=storage_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        try:
            # Get search URL based on search term
            search_url = get_search_url_for_term(SEARCH_TERM)
            print(f"🔍 Searching for channels: '{SEARCH_TERM}'")
            print(f"📍 URL: {search_url}")
            
            page.goto(search_url, timeout=EXTRACTION_TIMEOUT * 1000)
            time.sleep(3)
            
            # Check if we're on YouTube
            if 'youtube.com' not in page.url.lower():
                print("🚨 Failed to load YouTube search!")
                print("💡 Check your youtube_auth.json authentication")
                browser.close()
                return []
            
            print("✅ Successfully loaded YouTube search results")
            
            # Scroll to load more results with config-based delays
            print(f"📜 Scrolling {MAX_SCROLLS} times to load more channels...")
            for i in range(MAX_SCROLLS):
                print(f"  🔄 Scroll {i + 1}/{MAX_SCROLLS}")
                page.mouse.wheel(0, 1200)
                time.sleep(random.uniform(DELAY_BETWEEN_SCROLLS, DELAY_BETWEEN_SCROLLS + 1))
                
                # Check if we hit "Show more" button and click it
                try:
                    show_more = page.query_selector('button:has-text("Show more")')
                    if show_more and show_more.is_visible():
                        print("  ↗️ Clicking 'Show more' button")
                        show_more.click()
                        time.sleep(2)
                except:
                    pass
            
            print("⏳ Waiting for content to stabilize...")
            time.sleep(3)
            
            # Extract channels (raw leads)
            raw_leads = extract_youtube_channels(page)
            
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
            
            if len(unique_leads) > 20:
                print(f"🎉 EXCELLENT: {len(unique_leads)} leads (target exceeded!)")
            elif len(unique_leads) > 10:
                print(f"✅ GOOD: {len(unique_leads)} leads")
            elif len(unique_leads) > 5:
                print(f"⚠️ MODERATE: {len(unique_leads)} leads")
            else:
                print(f"⚠️ LOW: {len(unique_leads)} leads")
            
            leads = unique_leads

            # 🚀 FIXED: Finalize results with usage tracking - correct username variable
            if leads:
                try:
                    finalized_leads = finalize_scraper_results(PLATFORM_NAME, leads, SEARCH_TERM, username)
                    leads = finalized_leads
                    print("✅ Results finalized and usage tracked")
                except Exception as e:
                    print(f"⚠️ Error finalizing results: {e}")
                    # Continue with original leads if finalization fails
            
            # Save results to multiple files
            if leads or (raw_leads and SAVE_RAW_LEADS):
                output_file = f"youtube_leads_{username}_{timestamp}.csv"
                fieldnames = ['name', 'handle', 'bio', 'url', 'platform', 'dm', 'subscribers', 'subscriber_count', 'video_count', 'description', 'channel_url', 'search_term', 'extraction_method', 'relevance_score']
                
                files_saved = save_leads_to_files(
                    leads=leads,
                    raw_leads=raw_leads,
                    username=username,
                    timestamp=timestamp,
                    platform_name=PLATFORM_NAME,
                    csv_dir=CSV_DIR,          # uses your existing location
                    save_raw=SAVE_RAW_LEADS,  # if you have this flag
)
                
                # Save processed results to main CSV
                if leads:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(leads)
                    files_saved.append(output_file)
                
                # Save raw results if enabled and different from processed
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    raw_filename = f"youtube_leads_raw_{username}_{timestamp}.csv"
                    raw_path = CSV_DIR / raw_filename
                    with open(raw_filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(raw_leads)
                    files_saved.append(raw_filename)
                    print(f"📋 Raw leads saved to {raw_filename}")
                
                print(f"\n✅ Successfully saved {len(leads)} leads")
                print(f"🔍 Files saved: {', '.join(files_saved)}")
                print(f"🎯 Performance target: 10+ leads - {'✅ ACHIEVED' if len(leads) >= 10 else '❌ MISSED'}")
                
                # Upload to Google Sheets using existing integration
                try:
                    from sheets_writer import write_leads_to_google_sheet
                    from daily_emailer import send_daily_leads_email
                    
                    # Format sheet name and timestamp
                    sheet_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    sheet_name = f"{PLATFORM_NAME.capitalize()} Leads {sheet_timestamp}"
                    
                    print("📝 Writing to Google Sheets...")
                    write_leads_to_google_sheet(leads)
                    print("✅ Successfully uploaded to Google Sheets")
                    
                    print("📤 Sending leads via email...")
                    send_daily_leads_email()
                    print("✅ Daily leads email sent!")
                    
                except ImportError:
                    print("📦 sheets_writer.py or daily_emailer.py not found - export features skipped")
                except Exception as e:
                    print(f"⚠️ Export/email error: {e}")
                
                # Show sample results
                if leads:
                    print(f"\n🎉 Sample processed results:")
                    for i, lead in enumerate(leads[:3]):
                        print(f"  {i+1}. {lead['name']}")
                        print(f"     Subscribers: {lead['subscribers']}")
                        print(f"     Bio: {lead['bio'][:50]}...")
                        print(f"     Relevance Score: {lead.get('relevance_score', 'N/A')}")
                        print(f"     DM: {lead['dm'][:50]}...")
                        print()
                
                if raw_leads and SAVE_RAW_LEADS and len(raw_leads) != len(leads):
                    print(f"\n📋 Raw leads preserved: {len(raw_leads)} total")
                    
            else:
                print("⚠️ No channels extracted")
                print("💡 Possible issues:")
                print("   - YouTube changed their page structure")
                print("   - Search term may be too specific")
                print("   - Need to refresh youtube_auth.json authentication")
                print("   - Try different search terms")
                leads = []
                
        except Exception as e:
            print(f"🚨 Error: {e}")
            import traceback
            traceback.print_exc()
            leads = []
        finally:
            # Keep browser open briefly to see final state
            print("🔍 Keeping browser open for 5 seconds...")
            time.sleep(5)
            browser.close()
            
        return leads

if __name__ == "__main__":
    print(f"🚀 YouTube Channel Scraper - Smart Deduplication Version")
    print(f"🔍 Search term: '{SEARCH_TERM}'")
    print(f"📜 Max scrolls: {MAX_SCROLLS}")
    print(f"👥 Min subscribers: {MIN_SUBSCRIBERS}")
    print(f"🛡️ Features:")
    print(f"  • Smart user-aware deduplication")
    print(f"  • Enhanced result tracking")
    print(f"  • Raw lead preservation")
    print()
    print(f"🔄 Deduplication: {DEDUP_MODE}")
    print(f"💾 Save raw leads: {SAVE_RAW_LEADS}")
    print()
    
    results = main()
    
    if results and len(results) >= 10:
        print(f"🎉 YOUTUBE SUCCESS: YouTube scraper completed with {len(results)} leads!")
    elif results:
        print(f"✅ YouTube scraper completed with {len(results)} leads")
    else:
        print(f"❌ YouTube scraper completed with 0 leads")