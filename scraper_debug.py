# scraper_debug.py
import os
from datetime import datetime

def debug_page_content(page, platform_name):
    """Debug what's actually on any scraper page"""
    print(f"\n=== {platform_name.upper()} PAGE DEBUG ===")
    
    try:
        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        
        # Check for login/auth issues
        body_text = page.inner_text('body').lower()
        if any(indicator in body_text for indicator in ['log in', 'sign up', 'login', 'challenge']):
            print("WARNING: Authentication issue detected")
        
        # Count elements
        print(f"Total links: {len(page.query_selector_all('a'))}")
        print(f"Profile-like links: {len(page.query_selector_all('a[href^=\"/\"]'))}")
        
        return True
        
    except Exception as e:
        print(f"Debug error: {e}")
        return False

def sample_page_links(page, max_samples=10):
    """Sample actual links found on page"""
    try:
        links = page.query_selector_all('a[href^="/"]')[:max_samples]
        print(f"\nSample hrefs found ({len(links)}):")
        
        for i, link in enumerate(links):
            href = link.get_attribute('href')
            text = link.inner_text()[:50] if link.inner_text() else "(no text)"
            print(f"  {i+1}. {href} | {text}")
            
    except Exception as e:
        print(f"Link sampling error: {e}")

def save_debug_screenshot(page, platform_name, suffix="debug"):
    """Save screenshot for debugging"""
    try:
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{platform_name}_{suffix}_{timestamp}.png"
        page.screenshot(path=filename)
        print(f"Debug screenshot saved: {filename}")
        return filename
    except Exception as e:
        print(f"Screenshot error: {e}")
        return None

def log_extraction_results(results, platform_name):
    """Log extraction results for debugging"""
    print(f"\n=== {platform_name.upper()} EXTRACTION RESULTS ===")
    print(f"Total leads extracted: {len(results)}")
    
    if results:
        print("Sample results:")
        for i, lead in enumerate(results[:3]):
            print(f"  {i+1}. {lead.get('name', 'No name')} | {lead.get('handle', 'No handle')}")
    else:
        print("No leads extracted - check selectors and authentication")