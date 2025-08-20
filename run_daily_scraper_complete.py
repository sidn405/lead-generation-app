#!/usr/bin/env python3
"""
Complete Empire Scraper - Called by Frontend App
Runs selected platforms based on user plan and frontend settings
"""
from streamlit_config_utils import ensure_client_config_exists
import json
import os
# EMERGENCY FIX: Prevent subprocess recursion
import sys
if hasattr(sys, '_subprocess_patched'):
    print("[WARNING] Subprocess already patched, skipping")
else:
    sys._subprocess_patched = True
    print("[OK] Subprocess patch protection enabled")
import subprocess
from datetime import datetime

# ✅ FIXED: Import centralized config properly
from config_loader import get_platform_config, config_loader

def get_user_from_environment():
    """Get user info from environment instead of session state"""
    username = os.getenv('SCRAPER_USERNAME')
    if not username:
        print("Warning: No username in environment")
        return None
    return username

# ✅ CRITICAL FIX: Set UTF-8 encoding for all Python operations on Windows
if sys.platform == "win32":
    # Set environment variables for UTF-8 encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'
    
    # Fix standard streams
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def debug_credit_consumption():
    """Debug why credits aren't being consumed"""
    
    print("🔍 DEBUGGING CREDIT CONSUMPTION")
    print("=" * 50)
    
    try:
        from postgres_credit_system import credit_system
        
        # Check current user status
        username = os.environ.get('SCRAPER_USERNAME', 'unknown')
        print(f"👤 Username: {username}")
        
        user_info = credit_system.get_user_info(username)
        if user_info:
            print(f"💎 Current credits: {user_info.get('credits', 0)}")
            print(f"🎯 Plan: {user_info.get('plan', 'unknown')}")
            print(f"📊 Total leads generated: {user_info.get('total_leads_generated', 0)}")
        else:
            print("❌ User not found in credit system")
        
        # Check if consume_user_resources is being called
        print(f"\n🔧 Checking resource consumption logic...")
        
        # Test credit consumption
        test_leads = [{'name': 'test1'}, {'name': 'test2'}]  # Mock leads
        print(f"🧪 Testing consumption with {len(test_leads)} test leads...")
        
        consumption_result = consume_user_resources(username, test_leads, 'instagram')
        print(f"🎯 Consumption result: {consumption_result}")
        
        # Check updated credits
        updated_user_info = credit_system.get_user_info(username)
        if updated_user_info:
            print(f"💎 Updated credits: {updated_user_info.get('credits', 0)}")
        
    except Exception as e:
        print(f"❌ Credit debug error: {e}")
        import traceback
        traceback.print_exc()

def fix_credit_consumption_in_parallel():
    """Fix credit consumption in parallel execution"""
    
    parallel_fix = '''
# Add this to your parallel_scraper_runner.py or wherever parallel execution happens

def ensure_credit_consumption_after_parallel(username, all_results):
    """Ensure credits are consumed after parallel execution completes"""
    
    print("💎 POST-PARALLEL CREDIT CONSUMPTION")
    print("=" * 40)
    
    try:
        from postgres_credit_system import credit_system
        
        total_consumed = 0
        
        for platform, results in all_results.items():
            if results and len(results) > 0:
                leads_count = len(results)
                print(f"🔧 Consuming {leads_count} credits for {platform}...")
                
                # Try to consume credits
                if user_info := credit_system.get_user_info(username):
                    plan = user_info.get('plan', 'demo')
                    
                    if plan != 'demo':  # Paid users
                        success = credit_system.consume_credits(username, leads_count, leads_count, platform)
                        if success:
                            total_consumed += leads_count
                            print(f"✅ {platform}: {leads_count} credits consumed")
                        else:
                            print(f"❌ {platform}: Failed to consume credits")
                    else:
                        print(f"📱 {platform}: Demo user - no credit consumption needed")
        
        # Force save data
        credit_system.save_data()
        print(f"💾 Credit data saved. Total consumed: {total_consumed}")
        
        # Verify consumption
        updated_info = credit_system.get_user_info(username)
        if updated_info:
            remaining = updated_info.get('credits', 0)
            print(f"💎 Remaining credits: {remaining}")
            return remaining
        
    except Exception as e:
        print(f"❌ Credit consumption error: {e}")
        return None

# Call this function after parallel execution completes
# In your main() function or parallel runner, add:
# remaining_credits = ensure_credit_consumption_after_parallel(username, all_results)
    '''
    
    with open('parallel_credit_fix.py', 'w', encoding='utf-8') as f:
        f.write(parallel_fix)
    
    print("💾 Parallel credit fix saved to: parallel_credit_fix.py")

def fix_dashboard_sync():
    """Fix dashboard not updating with latest results"""
    
    dashboard_fix = '''
# Add this to your dashboard/stats update system

def update_empire_command_center(username, latest_results):
    """Update Empire Command Center with latest scraping results"""
    
    print("📊 UPDATING EMPIRE COMMAND CENTER")
    print("=" * 40)
    
    try:
        # Load existing empire stats
        empire_stats_file = f"empire_stats_{username}.json"
        
        if os.path.exists(empire_stats_file):
            with open(empire_stats_file, 'r') as f:
                empire_stats = json.load(f)
        else:
            # Create new empire stats
            empire_stats = {
                'total_empire': 0,
                'platforms': {
                    'twitter': 0, 'linkedin': 0, 'facebook': 0, 'tiktok': 0,
                    'instagram': 0, 'youtube': 0, 'medium': 0, 'reddit': 0
                },
                'last_updated': None,
                'sessions': []
            }
        
        # Add latest session results
        session_total = 0
        session_data = {
            'timestamp': datetime.now().isoformat(),
            'search_term': os.environ.get('FRONTEND_SEARCH_TERM', 'unknown'),
            'results': {}
        }
        
        for platform, results in latest_results.items():
            leads_count = len(results) if results else 0
            
            # Update platform totals
            empire_stats['platforms'][platform] = empire_stats['platforms'].get(platform, 0) + leads_count
            session_total += leads_count
            session_data['results'][platform] = leads_count
            
            print(f"📈 {platform.title()}: +{leads_count} leads (total: {empire_stats['platforms'][platform]})")
        
        # Update total empire
        empire_stats['total_empire'] += session_total
        empire_stats['last_updated'] = datetime.now().isoformat()
        empire_stats['sessions'].append(session_data)
        
        # Keep only last 10 sessions
        empire_stats['sessions'] = empire_stats['sessions'][-10:]
        
        # Save updated stats
        with open(empire_stats_file, 'w') as f:
            json.dump(empire_stats, f, indent=2)
        
        print(f"✅ Empire stats updated!")
        print(f"📊 Session total: {session_total}")
        print(f"🏆 Empire total: {empire_stats['total_empire']}")
        
        # Also update the global dashboard file if it exists
        if os.path.exists('dashboard_data.json'):
            try:
                with open('dashboard_data.json', 'r') as f:
                    dashboard_data = json.load(f)
                
                dashboard_data['total_leads'] = empire_stats['total_empire']
                dashboard_data['platforms'] = empire_stats['platforms']
                dashboard_data['last_session'] = session_data
                dashboard_data['last_updated'] = datetime.now().isoformat()
                
                with open('dashboard_data.json', 'w') as f:
                    json.dump(dashboard_data, f, indent=2)
                
                print("✅ Dashboard data updated!")
                
            except Exception as e:
                print(f"⚠️ Dashboard update error: {e}")
        
        return empire_stats
        
    except Exception as e:
        print(f"❌ Empire stats update error: {e}")
        return None

# Call this function after each scraping session
# In your main() function, add:
# update_empire_command_center(username, all_results)
    '''
    
    with open('dashboard_sync_fix.py', 'w', encoding='utf-8') as f:
        f.write(dashboard_fix)
    
    print("📊 Dashboard sync fix saved to: dashboard_sync_fix.py")

def create_integrated_fix():
    """Create integrated fix for both issues"""
    
    integrated_fix = '''
# Integrated fix for run_daily_scraper_complete.py
# Add this at the end of your main() function

def finalize_scraping_session(username, user_plan, all_results, search_term):
    """Finalize scraping session - handle credits and dashboard updates"""
    
    print("\\n" + "="*60)
    print("🎯 FINALIZING SCRAPING SESSION")
    print("="*60)
    
    # Step 1: Ensure credit consumption
    if isinstance(all_results, dict):
        total_leads = sum(len(results) if results else 0 for results in all_results.values())
        
        if total_leads > 0:
            print(f"💎 Processing {total_leads} leads for credit consumption...")
            
            try:
                from postgres_credit_system import credit_system
                
                # Consume credits for each platform
                total_consumed = 0
                for platform, results in all_results.items():
                    if results and len(results) > 0:
                        leads_count = len(results)
                        
                        # Get fresh user info
                        user_info = credit_system.get_user_info(username)
                        if user_info and user_info.get('plan') != 'demo':
                            success = credit_system.consume_credits(username, leads_count, leads_count, platform)
                            if success:
                                total_consumed += leads_count
                                print(f"✅ {platform}: {leads_count} credits consumed")
                            else:
                                print(f"❌ {platform}: Credit consumption failed")
                
                # Force save credit data
                credit_system.save_data()
                print(f"💾 Credits saved. Total consumed: {total_consumed}")
                
                # Show remaining credits
                updated_info = credit_system.get_user_info(username)
                if updated_info:
                    remaining = updated_info.get('credits', 0)
                    print(f"💎 Remaining credits: {remaining}")
                
            except Exception as e:
                print(f"❌ Credit finalization error: {e}")
    
    # Step 2: Update dashboard/empire stats
    try:
        # Update empire command center
        print(f"📊 Updating Empire Command Center...")
        
        empire_stats_file = f"empire_stats_{username}.json"
        
        # Load or create empire stats
        if os.path.exists(empire_stats_file):
            with open(empire_stats_file, 'r') as f:
                empire_stats = json.load(f)
        else:
            empire_stats = {
                'total_empire': 0,
                'platforms': {},
                'last_updated': None,
                'current_session': {}
            }
        
        # Update with latest results
        session_total = 0
        current_session = {
            'timestamp': datetime.now().isoformat(),
            'search_term': search_term,
            'results': {}
        }
        
        for platform, results in all_results.items():
            leads_count = len(results) if results else 0
            
            # Update platform totals
            empire_stats['platforms'][platform] = empire_stats['platforms'].get(platform, 0) + leads_count
            session_total += leads_count
            current_session['results'][platform] = leads_count
        
        # Update totals
        empire_stats['total_empire'] += session_total
        empire_stats['current_session'] = current_session
        empire_stats['last_updated'] = datetime.now().isoformat()
        
        # Save empire stats
        with open(empire_stats_file, 'w') as f:
            json.dump(empire_stats, f, indent=2)
        
        print(f"✅ Empire stats updated!")
        print(f"📊 Session: {session_total} leads")
        print(f"🏆 Total Empire: {empire_stats['total_empire']} leads")
        
        # Trigger dashboard refresh (if using Streamlit)
        refresh_file = f"refresh_dashboard_{username}.trigger"
        with open(refresh_file, 'w') as f:
            f.write(datetime.now().isoformat())
        
        print(f"🔄 Dashboard refresh triggered")
        
    except Exception as e:
        print(f"❌ Dashboard update error: {e}")
    
    print("="*60)
    print("🎉 SESSION FINALIZATION COMPLETE")
    print("="*60)

    '''
# Replace emoji with plain text for Windows compatibility - EXTENDED VERSION
class SafeWriter:
    def __init__(self, original_writer):
        self.original_writer = original_writer
    
    def write(self, text):
        # Comprehensive emoji replacement for Windows console
        emoji_map = {
            '🚀': '[ROCKET]', '❌': '[ERROR]', '✅': '[OK]', '🧪': '[TEST]',
            '📋': '[CLIPBOARD]', '⚠️': '[WARNING]', '🔍': '[SEARCH]', 
            '📜': '[SCROLL]', '🔧': '[WRENCH]', '🎯': '[TARGET]',
            '💎': '[DIAMOND]', '📱': '[MOBILE]', '🔄': '[REFRESH]',
            '⏱️': '[TIMER]', '📊': '[CHART]', '🎉': '[PARTY]',
            '⏰': '[CLOCK]', '💾': '[SAVE]', '📁': '[FOLDER]',
            '👤': '[USER]', '💡': '[BULB]', '🏆': '[TROPHY]',
            '🌟': '[STAR]', '🔥': '[FIRE]', '💪': '[MUSCLE]',
            '🎊': '[CONFETTI]', '📈': '[UP]', '📉': '[DOWN]',
            '🔒': '[LOCK]', '🔓': '[UNLOCK]', '⚡': '[LIGHTNING]',
            '🌈': '[RAINBOW]', '📝': '[MEMO]', '📄': '[PAGE]',
            '💼': '[BRIEFCASE]', '👋': '[WAVE]', '👍': '[THUMBS_UP]',
            '👎': '[THUMBS_DOWN]', '🙌': '[RAISED_HANDS]', '🔔': '[BELL]',
            '🔕': '[MUTED]', '📢': '[SPEAKER]', '📣': '[MEGAPHONE]',
            '💬': '[SPEECH]', '💭': '[THOUGHT]', '🗨️': '[LEFT_SPEECH]',
            '🗯️': '[RIGHT_ANGER]', '💫': '[DIZZY]', '💥': '[BOOM]',
            '🌪️': '[TORNADO]', '☀️': '[SUN]', '🌙': '[MOON]',
            '⭐': '[WHITE_STAR]', '🌠': '[SHOOTING_STAR]'
        }
        
        safe_text = text
        for emoji, replacement in emoji_map.items():
            safe_text = safe_text.replace(emoji, replacement)
        
        # Handle any remaining problematic Unicode characters
        safe_text = safe_text.encode('ascii', errors='replace').decode('ascii')
        
        return self.original_writer.write(safe_text)
    
    def flush(self):
        return self.original_writer.flush()

# Apply SafeWriter only if we're on Windows and haven't already patched
if sys.platform == "win32" and not isinstance(sys.stdout, SafeWriter):
    sys.stdout = SafeWriter(sys.stdout)
    sys.stderr = SafeWriter(sys.stderr)

def safe_subprocess_run(*args, **kwargs):
    """Safe subprocess runner that handles Unicode properly on Windows"""
    try:
        # Ensure UTF-8 encoding
        kwargs.setdefault('encoding', 'utf-8')
        kwargs.setdefault('errors', 'replace')
        kwargs.setdefault('text', True)
        
        # Set UTF-8 environment
        env = kwargs.get('env', os.environ.copy())
        env.update({
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONUTF8': '1',
            'PYTHONLEGACYWINDOWSSTDIO': '0'
        })
        kwargs['env'] = env
        
        return subprocess.run(*args, **kwargs)
    
    except UnicodeDecodeError as e:
        print(f"[WARNING] Unicode decode error in subprocess: {e}")
        # Retry with Latin-1 encoding as fallback
        kwargs['encoding'] = 'latin-1'
        try:
            return subprocess.run(*args, **kwargs)
        except Exception as e2:
            print(f"[ERROR] Subprocess failed completely: {e2}")
            return None
    except Exception as e:
        print(f"[ERROR] Subprocess error: {e}")
        return None

def get_available_platforms_by_plan(user_plan):
    """Get platforms available for user's plan from centralized config"""
    usage_limits = config_loader.get_usage_limits(user_plan)
    return usage_limits.get('platforms_allowed', ['twitter', 'facebook'])

def get_available_platforms_by_plan(user_plan):
    """Get platforms available for user's plan - UPDATED with demo support"""
    
    # Define platform access by plan (including demo)
    plan_platforms = {
        'demo': ['twitter'],  # Demo: Only Twitter
        'starter': ['twitter', 'facebook'],  # Starter: 2 platforms
        'pro': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube'],  # Pro: 6 platforms
        'ultimate': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube', 'medium', 'reddit']  # Ultimate: All 8
    }
    
    # Get platforms for this plan
    available_platforms = plan_platforms.get(user_plan, ['twitter'])  # Default to demo if unknown
    
    print(f"📋 Plan '{user_plan}' allows platforms: {available_platforms}")
    return available_platforms

def check_user_authorization(username, user_plan, estimated_leads, platform):
    """Check if user is authorized to generate estimated leads"""
    
    if not username or username == 'anonymous':
        print(f"⚠️ No username provided for authorization")
        return False, "No username provided"
    
    try:
        # Import credit system
        from postgres_credit_system import credit_system
        
        print(f"🔍 check_user_limits for {username}:")
        print(f"   Force auth: {os.environ.get('FORCE_AUTHORIZATION', 'True')}")
        print(f"   Plan override: {os.environ.get('PLAN_OVERRIDE', '')}")
        print(f"   User plan: {user_plan}")
        print(f"   Limit override: {os.environ.get('SESSION_LIMIT_OVERRIDE', '')}")
        print(f"   Estimated leads: {estimated_leads}")
        
        # ✅ NEW: Check for demo override first
        demo_override = os.environ.get('DEMO_OVERRIDE', 'false').lower() == 'true'
        if demo_override and user_plan == 'demo':
            print(f"🚀 DEMO OVERRIDE ENABLED for {username}")
            return True, f"✅ Demo user authorized (override enabled)"
        
        # Check for environment overrides (Pro/Ultimate users)
        force_auth = os.environ.get('FORCE_AUTHORIZATION', 'false').lower() == 'true'
        plan_override = os.environ.get('PLAN_OVERRIDE', '')
        
        if force_auth and plan_override in ['pro', 'ultimate']:
            print(f"🚀 AUTHORIZATION OVERRIDE for {plan_override} user")
            return True, f"✅ {plan_override.title()} user authorized (override)"
        
        # ✅ NEW: Extended override to include demo
        if force_auth and plan_override == 'demo':
            print(f"🚀 AUTHORIZATION OVERRIDE for demo user")
            return True, f"✅ Demo user authorized (force override)"
        
        # Get user info from credit system
        user_info = credit_system.get_user_info(username)
        if not user_info:
            print(f"❌ User {username} not found in credit system")
            return False, f"User {username} not found"
        
        actual_plan = user_info.get('plan', 'demo')
        print(f"📋 Checking auth system status for {username}")
        
        # DEMO USER AUTHORIZATION
        if actual_plan == 'demo':
            can_demo, remaining = credit_system.can_use_demo(username)
            
            print(f"📱 Demo user authorization:")
            print(f"   Can use demo: {can_demo}")
            print(f"   Demo remaining: {remaining}")
            print(f"   Estimated leads: {estimated_leads}")
            
            if not can_demo:
                return False, f"❌ Demo leads exhausted"
            
            if estimated_leads > remaining:
                # Limit demo users to their remaining leads
                print(f"⚠️ Limiting demo user to {remaining} leads (requested {estimated_leads})")
                return True, f"✅ Demo authorized for {remaining} leads (limited)"
            
            return True, f"✅ Demo authorized for {estimated_leads} leads"
        
        # PAID USER AUTHORIZATION
        else:
            can_proceed, message, current_credits = credit_system.check_credits(username, estimated_leads)
            
            print(f"💎 Paid user authorization:")
            print(f"   Plan: {actual_plan}")
            print(f"   Credits available: {current_credits}")
            print(f"   Estimated leads: {estimated_leads}")
            print(f"   Can proceed: {can_proceed}")
            
            if not can_proceed:
                return False, f"❌ Insufficient credits: {message}"
            
            return True, f"✅ Authorized for {estimated_leads} leads"
    
    except Exception as e:
        print(f"❌ Authorization error: {str(e)}")
        return False, f"Authorization error: {str(e)}"

def get_safe_estimate_for_user(platform, max_scrolls, username, user_plan):
    """Get safe estimate that respects user limits"""
    
    # Base platform multipliers
    platform_multipliers = {
        'twitter': 2,
        'facebook': 8,
        'linkedin': 1.5,
        'youtube': 2,
        'tiktok': 6,
        'instagram': 2,
        'medium': 1,
        'reddit': 1
    }
    
    # Calculate base estimate
    base_estimate = max_scrolls * platform_multipliers.get(platform, 1)
    
    # Apply plan-specific limits
    if user_plan == 'demo':
        try:
            from postgres_credit_system import credit_system
            user_info = credit_system.get_user_info(username)
            
            if user_info:
                can_demo, remaining = credit_system.can_use_demo(username)
                # Demo users: never more than remaining demo leads, max 5 total
                safe_estimate = min(base_estimate, remaining, 5)
                
                print(f"📱 Demo estimate calculation:")
                print(f"   Base: {base_estimate}")
                print(f"   Remaining: {remaining}")
                print(f"   Safe: {safe_estimate}")
                
                return safe_estimate
        except Exception as e:
            print(f"⚠️ Demo calculation error: {e}")
            return min(base_estimate, 5)  # Fallback to max 5 for demo
    
    # For paid users, use base estimate (they have higher limits)
    return base_estimate

def consume_user_resources(username, leads_generated, platform):
    """Consume credits or demo leads after successful scraping"""
    
    if not username or username == 'anonymous' or not leads_generated:
        return True  # Skip consumption for anonymous or empty results
    
    try:
        from postgres_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if not user_info:
            print(f"⚠️ Could not find user {username} for resource consumption")
            return False
        
        user_plan = user_info.get('plan', 'demo')
        leads_count = len(leads_generated)
        
        if user_plan == 'demo':
            # Consume demo leads
            consumed = 0
            for _ in range(leads_count):
                if credit_system.consume_demo_lead(username):
                    consumed += 1
                else:
                    break
            
            print(f"📱 Demo consumption: {consumed} demo leads used for {platform}")
            return consumed > 0
        
        else:
            # Consume regular credits
            success = credit_system.consume_credits(username, leads_count, leads_count, platform)
            
            if success:
                print(f"💎 Consumed {leads_count} credits for {platform}")
            else:
                print(f"❌ Failed to consume credits for {platform}")
            
            return success
    
    except Exception as e:
        print(f"⚠️ Resource consumption error: {e}")
        return False

def run_platform_scraper(platform):
    """Run a specific platform scraper with proper authorization - FIXED"""
    try:
        print(f"\n[ROCKET] Running {platform.title()} scraper...")

        # Get user info
        username = get_user_from_environment()
        user_plan = get_user_from_environment()
        
        # ✅ FIXED: Get config properly
        search_term = None
        max_scrolls = None
        
        # Try client config first
        client_config_file = f"client_configs/{username}_config.json"
        if os.path.exists(client_config_file):
            try:
                with open(client_config_file, 'r') as f:
                    client_config = json.load(f)
                
                search_term = client_config.get('global_settings', {}).get('search_term')
                max_scrolls = client_config.get('global_settings', {}).get('max_scrolls')
                
                print(f"📋 Using CLIENT config for {username}:")
                print(f"  Search: '{search_term}'")
                print(f"  Scrolls: {max_scrolls}")
                
            except Exception as e:
                print(f"⚠️ Error reading client config: {e}")
        
        # Fallback to global config
        if not search_term or not max_scrolls:
            try:
                config = get_platform_config(platform)
                if not search_term:
                    search_term = config.get('search_term', 'crypto trader')
                if not max_scrolls:
                    max_scrolls = config.get('max_scrolls', 9)
                
                print(f"📋 Using GLOBAL config fallback:")
                print(f"  Search: '{search_term}'")
                print(f"  Scrolls: {max_scrolls}")
                
            except Exception as e:
                print(f"⚠️ Error reading global config: {e}")
                # Final fallbacks
                search_term = 'crypto trader'
                max_scrolls = 9
        
        # Check frontend override
        frontend_search_term = os.environ.get('FRONTEND_SEARCH_TERM', '')
        if frontend_search_term:
            search_term = frontend_search_term
            print(f"🔄 Frontend override: '{search_term}'")
        
        # Ensure client config exists
        if not ensure_client_config_exists(username):
            print(f"❌ Failed to ensure client config for {username}")
            return []
        
        print(f"📋 {platform.title()} Final Config:")
        print(f"  Search term: '{search_term}'")
        print(f"  Max scrolls: {max_scrolls}")
        
        # Calculate safe estimate for this user
        estimated_leads = get_safe_estimate_for_user(platform, max_scrolls, username, user_plan)
        
        # Check authorization BEFORE running scraper
        authorized, auth_message = check_user_authorization(username, user_plan, estimated_leads, platform)
        
        if not authorized:
            print(f"❌ {platform.title()} scraper blocked: {auth_message}")
            return []
        
        print(f"✅ {platform.title()} scraper authorized: {auth_message}")
        
        # SET ENVIRONMENT VARIABLES TO BYPASS INDIVIDUAL SCRAPER AUTH
        os.environ['BYPASS_INDIVIDUAL_AUTH'] = 'true'
        os.environ['AUTHORIZED_LEADS'] = str(estimated_leads)
        os.environ['PRE_AUTHORIZED_USER'] = username
        os.environ['FRONTEND_SEARCH_TERM'] = search_term  # ✅ Pass search term to scraper
        
        # Rest of your existing scraper import and execution code...
        results = []
        
        if platform == 'twitter':
            from twitter_scraper import login_and_scrape
            results = login_and_scrape()
        elif platform == 'facebook':
            from facebook_scraper import main as facebook_main
            results = facebook_main()
        elif platform == 'instagram':
            from instagram_scraper import main as instagram_main
            results = instagram_main()
        elif platform == 'linkedin':
            from linkedin_scraper import run_linkedin_scraper_with_manual_fallback
            results = run_linkedin_scraper_with_manual_fallback()
        elif platform == 'tiktok':
            from tiktok_scraper import main as tiktok_main
            results = tiktok_main()
        elif platform == 'youtube':
            from youtube_scraper import main as youtube_main
            results = youtube_main()
        elif platform == 'medium':
            from medium_scraper_ec import main as medium_main
            results = medium_main()
        elif platform == 'reddit':
            from reddit_scraper_ec import main as reddit_main
            results = reddit_main()
        else:
            print(f"❌ Unknown platform: {platform}")
            return []
        
        # Clean up environment variables
        cleanup_env_vars = ['BYPASS_INDIVIDUAL_AUTH', 'AUTHORIZED_LEADS', 'PRE_AUTHORIZED_USER']
        for var in cleanup_env_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Process results
        if results:
            consumption_success = consume_user_resources(username, results, platform)
            print(f"✅ {platform.title()}: {len(results)} leads scraped")
            return results
        else:
            print(f"✅ {platform.title()}: 0 leads scraped")
            return []
        
    except ImportError as e:
        print(f"❌ Could not import {platform} scraper: {e}")
        return []
    except Exception as e:
        print(f"❌ Error running {platform} scraper: {e}")
        import traceback
        traceback.print_exc()
        return []

def run_all_platform_scrapers(platforms):
    """Run scrapers for specified platforms"""
    
    all_results = {}
    total_leads = 0
    
    for platform in platforms:
        try:
            results = run_platform_scraper(platform)
            all_results[platform] = results
            total_leads += len(results) if results else 0
            
            # Add delay between platforms to avoid rate limiting
            if platform != platforms[-1]:  # Don't delay after last platform
                print(f"⏱️ Waiting 30 seconds before next platform...")
                import time
                time.sleep(30)
                
        except Exception as e:
            print(f"❌ Error with {platform}: {e}")
            all_results[platform] = []
            continue
    
    print(f"\n📊 FINAL SUMMARY:")
    print(f"🎯 Total leads across all platforms: {total_leads}")
    for platform, results in all_results.items():
        count = len(results) if results else 0
        print(f"  {platform.title()}: {count} leads")
    
    return all_results

def get_user_from_environment():
    """Get user info from environment instead of session state"""
    username = os.getenv('SCRAPER_USERNAME')
    user_plan = os.getenv('SCRAPER_USER_PLAN') 
    credits = os.getenv('SCRAPER_CREDITS')
    
    if not username:
        print("Warning: No username in environment variables")
        return None, None, 0
    
    return username, user_plan, int(credits) if credits else 0

def get_username_from_env():
    """Get username from environment variables"""
    return os.environ.get('SCRAPER_USERNAME', 'anonymous')

def determine_platforms_to_run(user_plan):
    """Determine which platforms to run based on frontend selections and user plan"""
    
    # Get available platforms for this plan from centralized config
    available_platforms = get_available_platforms_by_plan(user_plan)
    
    # Get selected platforms from environment variable (passed by frontend)
    selected_platforms_env = os.environ.get('SELECTED_PLATFORMS', '')
    
    if selected_platforms_env:
        # Parse the selected platforms from frontend
        requested_platforms = [p.strip().lower() for p in selected_platforms_env.split(',') if p.strip()]
        
        # Only run platforms that are both selected AND available for the user's plan
        final_platforms = [p for p in requested_platforms if p in available_platforms]
        
        print(f"🎯 Frontend requested: {', '.join(requested_platforms)}")
        print(f"✅ Plan allows: {', '.join(available_platforms)}")
        print(f"🚀 Will run: {', '.join(final_platforms)}")
        
        return final_platforms
    else:
        # Fallback: run all available platforms if no selection provided
        print(f"⚠️ No platform selection provided, running all available for {user_plan} plan")
        return available_platforms

def update_search_term_if_provided():
    """Update global search term if provided by frontend"""
    frontend_search_term = os.environ.get('FRONTEND_SEARCH_TERM', '')
    
    if frontend_search_term:
        print(f"🔄 Updating search term from frontend: '{frontend_search_term}'")
        
        # Update the global search term in centralized config
        success = config_loader.update_global_setting('search_term', frontend_search_term)
        
        if success:
            print(f"✅ Search term updated globally to: '{frontend_search_term}'")
            return frontend_search_term
        else:
            print(f"❌ Failed to update search term")
            return None
    
    return None

# Add this function to your run_daily_scraper_complete.py

def suggest_better_search_terms(original_term, platforms):
    """Generate dynamic search suggestions based on the original search term"""
    
    print(f"\n[TARGET] SEARCH OPTIMIZATION SUGGESTIONS:")
    print(f"No matches found for: '{original_term}'")
    print(f"[SEARCH] Try these alternative approaches:")
    
    # Extract keywords from original term
    keywords = original_term.lower().split()
    
    # Generate variations based on the original term
    suggestions = []
    
    # Strategy 1: Broader terms (remove one keyword)
    if len(keywords) > 1:
        for i, word in enumerate(keywords):
            broader_term = ' '.join([w for j, w in enumerate(keywords) if j != i])
            suggestions.append(f"Broader: '{broader_term}'")
    
    # Strategy 2: Add descriptive words
    descriptors = ['professional', 'expert', 'specialist', 'coach', 'trainer', 'consultant']
    for desc in descriptors[:2]:  # Limit to 2
        new_term = f"{desc} {original_term}"
        suggestions.append(f"Professional: '{new_term}'")
    
    # Strategy 3: Industry variations
    if 'fitness' in original_term.lower():
        variations = [
            original_term.replace('fitness', 'wellness'),
            original_term.replace('fitness', 'health'),
            original_term.replace('fitness', 'trainer'),
            f"{original_term} coach",
            f"{original_term} instructor"
        ]
    elif 'mom' in original_term.lower() or 'mommy' in original_term.lower():
        variations = [
            original_term.replace('mommy', 'mom'),
            original_term.replace('mom', 'mother'),
            f"parenting {' '.join(keywords[1:])}",  # Remove 'mommy/mom'
            f"family {' '.join(keywords[1:])}"
        ]
    elif 'business' in original_term.lower():
        variations = [
            original_term.replace('business', 'entrepreneur'),
            original_term.replace('business', 'startup'),
            f"{original_term} owner",
            f"{original_term} consultant"
        ]
    elif 'tech' in original_term.lower() or 'software' in original_term.lower():
        variations = [
            original_term.replace('tech', 'technology'),
            original_term.replace('software', 'developer'),
            f"{original_term} engineer",
            f"{original_term} specialist"
        ]
    else:
        # Generic variations for any niche
        variations = [
            f"{original_term} expert",
            f"{original_term} coach", 
            f"{original_term} specialist",
            f"professional {original_term}"
        ]
    
    # Add variations to suggestions
    for var in variations[:3]:  # Limit to 3 variations
        suggestions.append(f"Variation: '{var}'")
    
    # Strategy 4: Single keyword alternatives
    if len(keywords) > 1:
        for keyword in keywords:
            suggestions.append(f"Single word: '{keyword}'")
    
    # Display suggestions
    print(f"\n[CLIPBOARD] PLATFORM-SPECIFIC SUGGESTIONS:")
    
    # Show top suggestions for each platform
    for platform in platforms:
        print(f"  [TARGET] {platform.title()}:")
        
        if platform == 'twitter':
            # Twitter works well with hashtag-style terms
            twitter_suggestions = [
                f"#{keywords[0]}" if keywords else original_term,
                f"{keywords[0]} life" if keywords else f"{original_term} life",
                f"{keywords[0]} community" if keywords else f"{original_term} community"
            ]
            for sugg in twitter_suggestions[:2]:
                print(f"    • '{sugg}'")
                
        elif platform == 'linkedin':
            # LinkedIn works well with professional terms
            linkedin_suggestions = [
                f"{original_term} professional",
                f"{original_term} specialist", 
                f"{keywords[0]} expert" if keywords else f"{original_term} expert"
            ]
            for sugg in linkedin_suggestions[:2]:
                print(f"    • '{sugg}'")
                
        elif platform == 'facebook':
            # Facebook works well with community/group terms
            facebook_suggestions = [
                f"{original_term} group",
                f"{original_term} community",
                f"{keywords[0]} moms" if 'fitness' in original_term else f"{original_term} tips"
            ]
            for sugg in facebook_suggestions[:2]:
                print(f"    • '{sugg}'")
                
        elif platform == 'instagram':
            # Instagram works well with lifestyle terms
            instagram_suggestions = [
                f"{original_term} lifestyle",
                f"{keywords[0]}gram" if keywords else original_term,
                f"{original_term} motivation"
            ]
            for sugg in instagram_suggestions[:2]:
                print(f"    • '{sugg}'")
        else:
            # Generic suggestions for other platforms
            generic_suggestions = suggestions[:2]
            for sugg in generic_suggestions:
                clean_sugg = sugg.split(": '")[1].rstrip("'") if ": '" in sugg else sugg
                print(f"    • '{clean_sugg}'")
    
    print(f"\n[WRENCH] GENERAL SEARCH TIPS:")
    print(f"  • Try broader terms (fewer words)")
    print(f"  • Add professional descriptors ('coach', 'expert', 'professional')")
    print(f"  • Use variations of keywords ('{keywords[0]}' → related terms)")
    print(f"  • Check spelling and try synonyms")
    print(f"  • Consider the platform's typical language style")
    
    print(f"\n[REFRESH] NEXT STEPS:")
    print(f"  1. Copy one of the suggested terms above")
    print(f"  2. Go back to the frontend app") 
    print(f"  3. Enter the new search term")
    print(f"  4. Run the scraper again")

# Update your report_final_results function to call this:
def report_final_results(all_results, platforms, search_term):
    """Report final results with dynamic search suggestions for any niche"""
    
    if isinstance(all_results, dict):
        total_leads = sum(len(results) if results else 0 for results in all_results.values())
        platforms_with_leads = sum(1 for results in all_results.values() if results and len(results) > 0)
        platforms_attempted = len([p for p in platforms if p in all_results])
    else:
        total_leads = 0
        platforms_with_leads = 0
        platforms_attempted = len(platforms)
        all_results = {}
    
    print(f"\n[PARTY] SCRAPING SESSION COMPLETE!")
    print(f"[CLOCK] Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[CHART] Total leads collected: {total_leads}")
    
    if total_leads > 0:
        print(f"[OK] Successful platforms: {platforms_with_leads}/{platforms_attempted}")
        print(f"\n[CLIPBOARD] RESULTS BY PLATFORM:")
        
        for platform in platforms:
            results = all_results.get(platform, [])
            count = len(results) if results else 0
            if count > 0:
                print(f"  [OK] {platform.title()}: {count} leads")
            else:
                print(f"  [SEARCH] {platform.title()}: No matches found")
    
    else:
        # Zero leads - provide dynamic suggestions based on actual search term
        print(f"\n[CLIPBOARD] RESULTS BY PLATFORM:")
        for platform in platforms:
            results = all_results.get(platform, [])
            print(f"  [SEARCH] {platform.title()}: No matches for '{search_term}'")
        
        # ✅ FIXED: Call the suggestions function properly
        suggest_better_search_terms(search_term, platforms)

def finalize_scraping_session(username, user_plan, all_results, search_term):
    """Fix credits and dashboard sync"""
    
    print(f"\n🎯 FINALIZING SESSION...")
    
    # Step 1: Force credit consumption
    if isinstance(all_results, dict):
        total_leads = sum(len(results) if results else 0 for results in all_results.values())
        
        if total_leads > 0 and user_plan != 'demo':
            try:
                from postgres_credit_system import credit_system
                
                # Get current credits
                user_info = credit_system.get_user_info(username)
                current_credits = user_info.get('credits', 0) if user_info else 0
                print(f"💎 Current credits: {current_credits}")
                
                # Consume credits for this session
                success = credit_system.consume_credits(username, total_leads, 'session')
                
                if success:
                    credit_system.save_data()  # Force save
                    
                    # Verify consumption
                    updated_info = credit_system.get_user_info(username)
                    new_credits = updated_info.get('credits', 0) if updated_info else 0
                    consumed = current_credits - new_credits
                    
                    print(f"✅ Credits consumed: {consumed}")
                    print(f"💎 Remaining credits: {new_credits}")
                else:
                    print(f"❌ Credit consumption failed")
                    
            except Exception as e:
                print(f"❌ Credit error: {e}")
    
    # Step 2: Update dashboard data
    try:
        dashboard_data = {
            'timestamp': datetime.now().isoformat(),
            'username': username,
            'search_term': search_term,
            'total_leads': sum(len(results) if results else 0 for results in all_results.values()),
            'platforms': all_results,
            'session_complete': True
        }
        
        # Save session data for dashboard
        with open('latest_session.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        # Update empire totals
        empire_file = f'empire_totals_{username}.json'
        if os.path.exists(empire_file):
            with open(empire_file, 'r') as f:
                empire_totals = json.load(f)
        else:
            empire_totals = {'total_empire': 0, 'platforms': {}}
        
        # Add this session's results
        for platform, results in all_results.items():
            count = len(results) if results else 0
            empire_totals['platforms'][platform] = empire_totals['platforms'].get(platform, 0) + count
            empire_totals['total_empire'] += count
        
        empire_totals['last_updated'] = datetime.now().isoformat()
        
        with open(empire_file, 'w') as f:
            json.dump(empire_totals, f, indent=2)
        
        print(f"📊 Dashboard updated!")
        print(f"🏆 Total Empire: {empire_totals['total_empire']}")
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

# Update your main() function to include this:
def main():
    """Main function with universal niche support"""
    
    try:
        print("[ROCKET] Lead Generator Empire - Complete Scraper")
        print("=" * 60)
        
        # Get user info and search term
        user_plan = get_user_from_environment()
        username = get_user_from_environment()
        search_term = os.environ.get('FRONTEND_SEARCH_TERM', 'business coach')  # Generic default
        
        print(f"[USER] User: {username}")
        print(f"[TARGET] Plan: {user_plan}")
        print(f"[SEARCH] Search term: '{search_term}'")
        print(f"[TARGET] Niche: Any industry/vertical supported")
        
        platforms = determine_platforms_to_run(user_plan)
        print(f"[ROCKET] Platforms: {', '.join(platforms)}")
        print("=" * 60)
        
        if not platforms:
            print("[ERROR] No platforms available for your plan!")
            return 1
        
        # Run scrapers
        print(f"[ROCKET] Starting scraping for '{search_term}' niche...")
        print(f"[CLOCK] Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            from parallel_scraper_runner import run_parallel_scrapers
            
            all_results = run_parallel_scrapers(
                platforms=platforms,
                search_term=search_term,
                max_scrolls=9,
                username=username,
                user_plan=user_plan
            )
            
            print(f"[OK] Parallel execution completed successfully!")
            
        except ImportError:
            print("[WARNING] Parallel runner not available, using sequential execution...")
            all_results = run_all_platform_scrapers(platforms)
        
        # ✅ FIXED: Use the updated reporting function
        report_final_results(all_results, platforms, search_term)
        
        # Save session summary
        try:
            if isinstance(all_results, dict):
                total_leads = sum(len(results) if results else 0 for results in all_results.values())
            else:
                total_leads = 0
                
            summary = {
                'timestamp': datetime.now().isoformat(),
                'user': username,
                'plan': user_plan,
                'search_term': search_term,
                'niche': search_term,
                'platforms_run': platforms,
                'total_leads': total_leads,
                'results_by_platform': {k: len(v) if v else 0 for k, v in all_results.items()} if isinstance(all_results, dict) else {},
                'execution_mode': 'parallel',
                'status': 'success_with_leads' if total_leads > 0 else 'success_no_matches',
                'suggestions_provided': total_leads == 0
            }
            
            with open('scraping_session_summary.json', 'w') as f:
                json.dump(summary, f, indent=2)
            
            print(f"[SAVE] Session summary saved to: scraping_session_summary.json")
            
        except Exception as e:
            print(f"[WARNING] Could not save session summary: {e}")
        
        # ✅ ALWAYS run finalization after scraping
        print(f"🎯 Starting finalization for user: {username}")
        finalize_scraping_session(username, user_plan, all_results, search_term)
        
        # ✅ IMPORTANT: Return 0 even for zero leads (it's not an error)
        return 0
        
    except Exception as e:
        print(f"[ERROR] Scraping session failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

print("[OK] Universal niche search suggestions system loaded")

# ✅ ALSO FIX: Update parallel_scraper_runner.py to respect environment

def update_parallel_runner_for_environment():
    """Code to add to parallel_scraper_runner.py"""
    
    # Remove emojis from the parallel_fix string for Windows compatibility
    parallel_fix = '''
# Add this to your parallel_scraper_runner.py in the setup_environment method

def setup_environment(self):
    """Setup environment variables for all scrapers"""
    env = os.environ.copy()
    
    # CRITICAL: Pass search term to individual scrapers
    env.update({
        'SCRAPER_USERNAME': self.username,
        'USER_PLAN': self.user_plan,
        'FRONTEND_SEARCH_TERM': self.search_term,  # Ensure this is passed
        'FORCE_AUTHORIZATION': 'true',
        'PLAN_OVERRIDE': self.user_plan,
        'BYPASS_INDIVIDUAL_AUTH': 'true',
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONUTF8': '1'
    })
    
    print(f"[WRENCH] Environment setup for scrapers:")
    print(f"  FRONTEND_SEARCH_TERM: '{self.search_term}'")
    print(f"  SCRAPER_USERNAME: '{self.username}'")
    print(f"  USER_PLAN: '{self.user_plan}'")
    
    return env
'''
    
    print("[CLIPBOARD] PARALLEL RUNNER UPDATE:")
    print(parallel_fix)
    
    # Save to file with UTF-8 encoding to handle any remaining Unicode characters
    try:
        with open("parallel_runner_env_fix.txt", 'w', encoding='utf-8') as f:
            f.write(parallel_fix)
        
        print("[FOLDER] Fix saved to: parallel_runner_env_fix.txt")
    except Exception as e:
        print(f"[ERROR] Could not save file: {e}")
        # Fallback: save without emojis
        try:
            with open("parallel_runner_env_fix.txt", 'w') as f:
                f.write(parallel_fix)
            print("[OK] Fix saved to: parallel_runner_env_fix.txt (fallback)")
        except Exception as e2:
            print(f"[ERROR] Fallback save also failed: {e2}")

# Quick test function to verify variables are working
def test_variable_resolution():
    """Test that search_term and max_scrolls can be resolved"""
    
    print("🧪 Testing variable resolution...")
    
    username = get_user_from_environment()
    print(f"Username: {username}")
    
    # Test client config
    client_config_file = f"client_configs/{username}_config.json"
    if os.path.exists(client_config_file):
        try:
            with open(client_config_file, 'r') as f:
                client_config = json.load(f)
            
            search_term = client_config.get('global_settings', {}).get('search_term')
            max_scrolls = client_config.get('global_settings', {}).get('max_scrolls')
            
            print(f"✅ Client config found:")
            print(f"  Search term: '{search_term}'")
            print(f"  Max scrolls: {max_scrolls}")
            
        except Exception as e:
            print(f"❌ Client config error: {e}")
    else:
        print(f"❌ Client config not found: {client_config_file}")
    
    # Test global config
    try:
        global_config = config_loader.get_global_config()
        global_search = global_config.get('search_term')
        global_scrolls = global_config.get('max_scrolls')
        
        print(f"✅ Global config:")
        print(f"  Search term: '{global_search}'")
        print(f"  Max scrolls: {global_scrolls}")
        
    except Exception as e:
        print(f"❌ Global config error: {e}")
    
    # Test environment
    frontend_search = os.environ.get('FRONTEND_SEARCH_TERM', '')
    print(f"✅ Environment:")
    print(f"  Frontend search: '{frontend_search}'")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--debug-credits':
        debug_credit_consumption()
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--generate-fixes':
        fix_credit_consumption_in_parallel()
        fix_dashboard_sync() 
        create_integrated_fix()
        sys.exit(0)
    
    # Normal execution
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Empire conquest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)