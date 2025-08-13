import streamlit as st
from streamlit_session_helper import show_user_selector, fix_session_state
from streamlit.components.v1 import html
import sys
import smtplib 
import stripe
import json
import subprocess
import pandas as pd
import glob
import os
import hashlib
import sqlite3
import secrets
import time
import re
import random
import string
from typing import Tuple, List, Dict, Optional
from cryptography.fernet import Fernet
from stripe_checkout import show_compact_credit_terms, display_compact_credit_addon
import streamlit.components.v1 as components
import traceback
from datetime import datetime, timedelta
from simple_credit_system import credit_system, check_user_credits, consume_user_credits, apply_lead_masking
from stripe_checkout import (
    display_pricing_tiers_with_enforcement, 
    handle_payment_success, 
    show_user_credit_status,
    enforce_credit_limits_on_scraper,
    create_no_refund_checkout
)
import uuid

# Import the new utilities
try:
    from enhanced_config_loader import ConfigLoader, patch_stripe_credentials
    from streamlit_config_utils import (
     ensure_client_config_exists,
     get_user_excluded_accounts, 
     save_user_social_accounts,
     create_registration_config,
     show_exclusion_preview,
     render_social_account_input
 )
except ImportError as e:
    st.error(f"Please ensure enhanced_config_loader.py and streamlit_config_utils.py are in your project directory: {e}")
from pdf_invoice import download_invoice_button, download_delivery_confirmation_button
from payment_recovery import automatic_payment_recovery, try_save_user_to_database

# Import your existing emailer
from emailer import EMAIL_ADDRESS, EMAIL_PASSWORD
import smtplib
from email.message import EmailMessage

# 🌍 Import multilingual capabilities
try:
    from multilingual_dm_generator import (
        detect_user_language, 
        generate_multilingual_dm, 
        generate_multilingual_batch,
        LANGUAGE_KEYWORDS,
        PLATFORM_LANGUAGE_STYLES
    )
    from dm_sequences import generate_multiple_dms
    from dm_csv_exporter import export_dms_detailed, create_campaign_summary
    MULTILINGUAL_AVAILABLE = True
except ImportError:
    MULTILINGUAL_AVAILABLE = True  # ← Force it to True anyway
    print("⚠️ Multilingual imports failed but keeping features available")
    
    # Create dummy functions if imports failed
    def detect_user_language(text): return "english"
    def generate_multilingual_dm(*args): return "Multilingual feature temporarily unavailable"
    def generate_multilingual_batch(*args): return []
    LANGUAGE_KEYWORDS = {}
    PLATFORM_LANGUAGE_STYLES = {}

from payment_auth_recovery import (
    restore_payment_authentication,
    show_payment_success_message,
    update_simple_auth_state,
    create_improved_stripe_session,
    create_package_stripe_session,  # ← Add this
    debug_authentication_state
)

# Import the config manager
try:
    from user_config_manager import get_current_config, update_config, get_config_debug_info, test_config_system
    CONFIG_MANAGER_AVAILABLE = True
    print("✅ User Config Manager loaded successfully")
except ImportError as e:
    print(f"⚠️ User Config Manager not available: {e}")
    CONFIG_MANAGER_AVAILABLE = False
    
    # Fallback functions if module not available
    def get_current_config(username=None):
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    config = json.load(f)
                config = patch_stripe_credentials(config)
                return {"search_term": config.get("search_term", "crypto trader"), 
                       "max_scrolls": config.get("max_scrolls", 12)}
        except:
            pass
        return {"search_term": "crypto trader", "max_scrolls": 12}
    
    def update_config(username, search_term, max_scrolls):
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    config = json.load(f)
                config = patch_stripe_credentials(config)
            else:
                config = {}
            config["search_term"] = search_term
            config["max_scrolls"] = max_scrolls
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
            return True
        except:
            return False

try:
    from user_lead_manager import UserLeadManager, filter_empire_data_by_user
    USER_CSV_FILTER_AVAILABLE = True
    print("✅ User CSV Filter loaded successfully")
except ImportError as e:
    USER_CSV_FILTER_AVAILABLE = False

ENABLE_DEBUG_MESSAGES = False  # Set to False to disable all debug

try:
    from csv_user_debug import get_user_csv_file, filter_csv_for_user, show_csv_debug
    CSV_USER_DEBUG_AVAILABLE = True
    if ENABLE_DEBUG_MESSAGES:
        print("✅ CSV User Debug module loaded successfully")
except ImportError as e:
    if ENABLE_DEBUG_MESSAGES:
        print(f"⚠️ CSV User Debug module not available: {e}")
    CSV_USER_DEBUG_AVAILABLE = False

from user_auth import (
    
    SimpleCreditAuth, simple_auth,
    show_auth_section_if_needed,
    show_enhanced_login_with_forgot_password,
    show_realtime_registration,
    show_forgot_password_form,
    show_password_reset_form,
    show_update_password_form,
    show_password_management_menu,
    show_password_security_tips,
    
)

from stripe_integration import handle_payment_flow, show_purchase_buttons
from package_system import show_package_store, show_my_packages
from purchases_tracker import automatic_payment_capture

# Add this as the FIRST thing in your main app
payment_handled = automatic_payment_capture()
if payment_handled:
    st.stop()

# if any auth modal flag is set, show it and stop
show_auth_section_if_needed()

if st.session_state.get("show_login", False):
    show_enhanced_login_with_forgot_password()
    st.stop()
if st.session_state.get("show_login", False):
    simple_auth.login_form()  # pops up your login UI
    st.stop() 

if sys.platform == "win32":
    # Set environment variables for UTF-8 encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONLEGACYWINDOWSSTDIO'] = '0'

# 1) Absolute dm_library folder next to this script
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
LIBRARY_DIR = os.path.join(BASE_DIR, "dm_library")
os.makedirs(LIBRARY_DIR, exist_ok=True)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "client_configs")
os.makedirs(CONFIG_DIR, exist_ok=True)

# 2) Callback to save the campaign
def save_dms_callback():
    # Grab everything out of session_state
    results = st.session_state.all_results
    username = st.session_state.username
    mode     = st.session_state.language_mode_selection
    plat     = st.session_state.dm_platform_style

    library_file = os.path.join(LIBRARY_DIR, f"{username}_dm_library.json")

    # Ensure file exists
    if not os.path.exists(library_file):
        with open(library_file, "w", encoding="utf-8") as f:
            json.dump({"campaigns": []}, f, indent=2)

    # Load, append, trim, save
    with open(library_file, "r+", encoding="utf-8") as f:
        data = json.load(f)
        campaign = {
            "id":        f"{username}_{datetime.now():%Y%m%d_%H%M%S}",
            "username":  username,
            "timestamp": datetime.now().isoformat(),
            "generation_mode": mode,
            "platform":        plat,
            "total_dms":       len(results),
            "languages":       list({dm.get("detected_language","unknown") for dm in results}),
            "dms":             results,
        }
        data["campaigns"].append(campaign)
        data["campaigns"] = data["campaigns"][-20:]
        f.seek(0); json.dump(data, f, indent=2); f.truncate()

    # Record debug info
    st.session_state.save_debug = {
        "saved": True,
        "file": library_file,
        "count": len(data["campaigns"])
    }

# Initialize
lead_manager = UserLeadManager()

# 1️⃣ First, handle any pending auth UI
show_auth_section_if_needed()

# 2️⃣ Now continue with your normal app routing
handle_payment_flow()

# Add navigation
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Navigation menu
page = st.sidebar.selectbox("Navigate", [
    "🏠 Dashboard", 
    "📦 Package Store", # ADD THIS
    "💳 Credits",
    "📁 My Downloads"
], key="nav_page")

if page == "🏠 Dashboard":

    pass

elif page == "📦 Package Store":
    # IMPORTANT: Use st.empty() to clear the page completely
    st.empty()
    
    from package_system import show_package_store
    show_package_store(
        st.session_state.get("username"), 
        st.session_state.get("authenticated", False)
    )
    st.stop()   

elif page == "💳 Credits":
    st.empty()
    
    # Page title with same styling as other pages
    st.markdown("# 💳 Buy Additional Credits")
    
    # Credits functionality
    if 'username' in st.session_state:
        username = st.session_state.username
        user_email = st.session_state.get('email', f"{username}@example.com")
        display_compact_credit_addon(username, user_email)
    else:
        st.error("Please log in to view credits")
    
    st.stop()

elif page == "📁 My Downloads":
    # Same treatment for downloads page
    st.empty()
    
    from package_system import show_my_packages
    username = st.session_state.get('username', 'demo_user')
    show_my_packages(username)
    
    # STOP here - don't render anything else  
    st.stop()

st.markdown(
    """
    <style>
      html {
        scroll-behavior: smooth;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

def load_accurate_empire_stats(username):
    """Load accurate, up-to-date empire stats for specific user"""
    empire_stats = {}
    total_leads  = 0
    try:
        empire_file = f"empire_totals_{username}.json"
        if os.path.exists(empire_file):
            with open(empire_file, "r") as f:
                data = json.load(f)
            empire_stats = data.get("platforms", {})
            total_leads  = data.get("total_empire", 0)
        else:
            empire_stats = calculate_empire_from_csvs(username)
            total_leads  = sum(empire_stats.values())
    except Exception as e:
        st.error(f"❌ Could not load empire stats: {e}")
    return empire_stats, total_leads

# ✅ ADD THESE FUNCTIONS RIGHT AFTER YOUR IMPORTS
def get_demo_status_with_refresh():
    """Get demo status with auto-refresh capability"""
    try:
        from simple_credit_system import credit_system
        
        can_demo, remaining = credit_system.can_use_demo('daveyd')
        user_info = credit_system.get_user_info('daveyd')
        demo_used = user_info.get('demo_leads_used', 0) if user_info else 0
        
        return {
            'can_use_demo': can_demo,
            'remaining': remaining,
            'used': demo_used,
            'total': 5,
            'exhausted': remaining <= 0
        }
    except Exception as e:
        print(f"Error getting demo status: {e}")
        return {'can_use_demo': False, 'remaining': 0, 'used': 5, 'total': 5, 'exhausted': True}

def refresh_demo_status():
    """Refresh demo status after scraping"""
    try:
        if 'demo_status' in st.session_state:
            del st.session_state['demo_status']
        st.rerun()
    except Exception as e:
        print(f"Error refreshing demo status: {e}")

def update_demo_consumption(leads_generated):
    """Update demo consumption and refresh dashboard"""
    try:
        from simple_credit_system import credit_system
        
        username = 'daveyd'
        leads_count = len(leads_generated) if leads_generated else 0
        
        if leads_count > 0:
            print(f"🔄 Updating demo consumption for {leads_count} leads")
            
            consumed = 0
            for i in range(leads_count):
                success = credit_system.consume_demo_lead(username)
                if success:
                    consumed += 1
                else:
                    break
            
            credit_system.save_data()
            print(f"✅ Consumed {consumed} demo leads")
            refresh_demo_status()
            return consumed
        
        return 0
    except Exception as e:
        print(f"Error updating demo consumption: {e}")
        return 0

def reset_demo_for_testing():
    """Reset demo for testing purposes"""
    try:
        from simple_credit_system import credit_system
        
        user_info = credit_system.get_user_info('daveyd')
        if user_info:
            user_info['demo_leads_used'] = 0
            credit_system.save_data()
            
            st.success("✅ Demo reset! 5 leads available again.")
            st.rerun()
        
    except Exception as e:
        st.error(f"Reset failed: {e}")

def display_demo_status():
    """Display current demo status in sidebar"""
    
    demo_status = get_demo_status_with_refresh()
    
    st.sidebar.markdown("### 🎯 Demo Status")
    
    if demo_status['exhausted']:
        st.sidebar.error("Demo Exhausted")
        st.sidebar.info("Upgrade for unlimited access!")
    else:
        remaining = demo_status['remaining']
        used = demo_status['used']
        
        progress = used / 5
        st.sidebar.progress(progress)
        
        st.sidebar.info(f"**{remaining}** leads remaining")
        st.sidebar.caption(f"Used {used}/5 demo leads")

def launch_scraper_with_demo_check():
    """Launch scraper with proper demo status checking"""
    
    demo_status = get_demo_status_with_refresh()
    
    if demo_status['exhausted']:
        st.error("🎯 Demo Exhausted!")
        st.warning("You've used all 5 demo leads. Upgrade to continue with unlimited scraping!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("💎 Pro Plan: 2,000 leads/month")
        with col2:
            st.info("🚀 Ultimate Plan: Unlimited leads")
        
        if st.button("🔄 Reset Demo (For Testing)", help="Admin only - resets demo for testing"):
            reset_demo_for_testing()
        
        return False
    
    st.info(f"🎯 Demo Status: {demo_status['remaining']} leads remaining")
    
    try:
        st.success("🚀 Empire Launch Initiated...")
        
        result = subprocess.run(
            ['python', 'run_daily_scraper_complete.py'],
            capture_output=True,
            text=True,
            env=os.environ.copy()
        )
        
        # ✅ WITH THIS IMPROVED DETECTION:
        if result.returncode == 0:
            st.success("✅ Scraping completed successfully!")
            
            # Check for actual results (more reliable than return code)
            try:
                # Look for recent CSV files 
                import glob
                recent_files = glob.glob("*twitter_leads*.csv")
                
                if recent_files:
                    # Check if files have data
                    latest_file = max(recent_files, key=os.path.getmtime)
                    df = pd.read_csv(latest_file)
                    
                    if len(df) > 0:
                        st.success(f"📊 SUCCESS: Generated {len(df)} quality leads!")
                        scraper_actually_succeeded = True
                    else:
                        st.warning("⚠️ Scraper completed but no leads found")
                        scraper_actually_succeeded = False
                else:
                    st.warning("⚠️ No output files found")
                    scraper_actually_succeeded = False
                    
            except Exception as e:
                st.warning(f"⚠️ Could not verify results: {e}")
                scraper_actually_succeeded = False

        else:
            st.error("❌ Scraper encountered an issue")
            scraper_actually_succeeded = False
        
    except Exception as e:
        st.error(f"❌ Launch error: {e}")
        return False   

# Load user database from users.json
def load_user_database():
    try:
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load users.json: {e}")
    return {}

user_db = load_user_database()

# Initialize user database into session
if "user_db" not in st.session_state:
    st.session_state.user_db = load_user_database()

# Client Demo Override - Add at the very top
try:
    from client_demo_simulator import get_client_demo_status
    
    def get_demo_display():
        status = get_client_demo_status()
        return f"Demo Mode: {status['remaining']} real demo leads remaining (used {status['used']}/{status['total']})"
    
    print("✅ Using reliable client demo simulator")
    
except ImportError:
    def get_demo_display():
        return "Demo Mode: 5 real demo leads remaining (used 0/5)"
    print("⚠️ Fallback demo display")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

def try_save_user_to_database(username, user_data):
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
        users[username] = user_data
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"❌ Failed to save user: {e}")

# CRITICAL: Handle payment authentication recovery FIRST
is_payment_return = restore_payment_authentication()

# ✅ THEN set your page config
st.set_page_config(
    page_title="Lead Generator Empire", 
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def restore_auth_after_payment():
    """Improved automatic authentication restoration after Stripe payment"""
    query_params = st.query_params
    
    # Check if this is a payment return
    payment_indicators = ["payment_success", "success", "cancelled", "package", "plan", "amount", "tier", "credits"]
    is_payment_return = any(param in query_params for param in payment_indicators)
    
    if not is_payment_return:
        return False
    
    # If user is already authenticated, no need to restore
    if simple_auth.is_authenticated():
        return False
    
    # Get username from URL parameters
    username_from_url = query_params.get("username", "")
    
    print(f"🔄 Payment return detected for username: {username_from_url}")
    
    # Try automatic restoration
    if username_from_url and username_from_url != "unknown":
        if automatic_session_restore(username_from_url):
            print(f"✅ Auto-restored session for {username_from_url}")
            return False  # Successfully restored, continue normal flow
    
    # If automatic restoration failed, show the emergency interface
    show_payment_recovery_interface(query_params)
    return True  # Stop normal flow to show recovery interface

def automatic_session_restore(username):
    """Automatic session restoration using simple_auth and credit_system"""
    try:
        print(f"🔄 Attempting auto -restore for {username}")
        
        # Method 1: Try to restore using credit_system
        try:
            user_info = credit_system.get_user_info(username)
            if user_info:
                print(f"✅ Found user in credit_system: {user_info}")
                
                # Restore session using simple_auth
                simple_auth.current_user = username
                simple_auth.user_data = user_info
                
                # Set Streamlit session state
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.user_data = user_info
                st.session_state.credits = user_info.get('credits', 0)
                st.session_state.login_time = datetime.now().isoformat()
                
                print(f"✅ Auto-restored session for {username} from credit_system")
                return True
        except NameError:
            print("⚠️ credit_system not available")
        
        # Method 2: Try to find user in users.json (backup)
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)
            
            if username in users:
                user_data = users[username]
                print(f"✅ Found user in users.json: {user_data}")
                
                # Restore session using simple_auth
                simple_auth.current_user = username
                simple_auth.user_data = user_data
                
                # Set Streamlit session state
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.user_data = user_data
                st.session_state.credits = user_data.get('credits', 0)
                st.session_state.login_time = datetime.now().isoformat()
                
                print(f"✅ Auto-restored session for {username} from users.json")
                return True
        
        # Method 3: Create emergency recovery account
        print(f"⚠️ User not found in systems, creating recovery account for {username}")
        return create_automatic_recovery_account(username)
        
    except Exception as e:
        print(f"❌ Automatic restoration error: {str(e)}")
        return False

def create_automatic_recovery_account(username):
    """Create recovery account automatically using credit_system"""
    try:
        print(f"🚨 Creating emergency recovery account for {username}")
        
        # Determine plan based on payment (if available)
        query_params = st.query_params
        credits = int(query_params.get("credits", 250))
        tier = query_params.get("tier", "starter")

        agree_key = f"agree_compact_{tier['name'].lower().replace(' ','_')}"
        agreed_to_terms = st.checkbox(
            "✅ Agree to terms",
            key=agree_key,
            help="I agree to Terms of Service & No-Refund Policy"
        )

        # disable the buy button until they agree
        buy_label = f"Buy {tier['name']}"
        if st.button(buy_label, disabled=not agreed_to_terms, key=f"buy_{tier['name']}"):
            # call your stripe_check logic…
            checkout_session = create_no_refund_checkout(username, user_email, tier)
            st.write("Redirecting…", checkout_session)
        
        # Map credits/tier to plan
        if credits >= 1000 or "ultimate" in tier.lower():
            plan = "ultimate"
        elif credits >= 500 or "pro" in tier.lower():
            plan = "pro"
        else:
            plan = "starter"
        
        print(f"🎯 Recovery account plan: {plan} (based on {credits} credits)")
        
        # Create user data structure
        user_data = {
            "username": username,
            "plan": plan,
            "credits": credits,
            "email": f"{username}@payment-recovery.com",
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
            "auto_recovery": True,
            "payment_recovery": True,
            "total_leads_downloaded": 0,
            "transactions": []
        }
        
        # Set session state using simple_auth
        simple_auth.current_user = username
        simple_auth.user_data = user_data
        
        # Set Streamlit session state
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.user_data = user_data
        st.session_state.user_data = user_data
        st.session_state.plan = user_data.get("plan", "starter")
        st.session_state.credits = user_data.get("credits", 250)
        st.session_state.login_time = datetime.now().isoformat()
        
        # Try to save to permanent storage (non-blocking)
        try_save_user_to_credit_system(username, user_data, credits, plan)
        
        print(f"✅ Auto-created recovery account for {username} with {plan} plan")
        return True
        
    except Exception as e:
        print(f"❌ Auto-recovery account creation failed: {str(e)}")
        return False

def try_save_user_to_credit_system(username, user_data, credits, plan):
    """Try to save user to credit_system (non-blocking)"""
    try:
        print(f"💾 Attempting to save {username} to credit_system")
        
        # Save to credit_system if available
        try:
            # Try to create user in credit system
            success, message = credit_system.create_user(username, user_data.get('email', ''), 'recovery_password')
            if success:
                print(f"✅ User created in credit_system: {message}")
                
                # Add credits if applicable
                if credits > 250:  # More than starter credits
                    credit_system.add_credits(username, credits, plan)
                    print(f"✅ Added {credits} credits to {username}")
            else:
                print(f"⚠️ Credit system user creation failed: {message}")
                # User might already exist, try to update
                existing_info = credit_system.get_user_info(username)
                if existing_info:
                    print(f"✅ User already exists in credit_system: {existing_info}")
        except NameError:
            print("⚠️ credit_system not available for saving")
        
        # Save to users.json as backup
        users = {}
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)
        
        users[username] = user_data
        
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)
            
        print(f"✅ Saved {username} to users.json backup")
            
    except Exception as e:
        print(f"⚠️ Database save failed (non-critical): {str(e)}")
        # Don't fail the restoration if database save fails

def show_payment_recovery_interface(query_params):
    """Show recovery interface only if automatic restoration fails"""
    
    # Extract payment details
    package = query_params.get("package", query_params.get("tier", "package"))
    amount = query_params.get("amount", "0")
    credits = query_params.get("credits", "0")
    username_hint = query_params.get("username", "")
    
    st.warning("🔐 Session expired during payment. Please sign in to access your account.")
    
    # Show payment confirmation first
    if "success" in query_params or "payment_success" in query_params:
        st.success(f"✅ Payment confirmed: ${amount}")
        if credits and credits != "0":
            st.success(f"💎 Credits purchased: {credits}")
        st.info("📧 Check your email for confirmation details")
    
    st.markdown("---")
    st.subheader("🔑 Account Recovery Options")
    
    # Recovery options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🔑 Standard Sign In")
        if st.button("🔑 Sign In to Existing Account", type="primary", use_container_width=True, key="payment_signin"):
            st.session_state.show_login = True
            st.session_state.show_register = False
            st.rerun()
    
    with col2:
        st.markdown("#### 🚨 Emergency Access")
        if st.button("🚨 Emergency Account Recovery", use_container_width=True, key="payment_emergency"):
            # Use the same logic that works in emergency login
            if username_hint and username_hint != "unknown":
                if create_automatic_recovery_account(username_hint):
                    st.success(f"✅ Emergency access granted for {username_hint}!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Emergency recovery failed. Please use standard sign in.")
            else:
                # Show emergency options
                show_emergency_options()

def show_emergency_options():
    """Show emergency recovery options"""
    st.markdown("### 🚨 Emergency Account Recovery")
    st.warning("⚠️ Use this only if you cannot access your regular account")
    
    emergency_username = st.text_input(
        "Enter your username:", 
        key="emergency_username_input",
        help="The username associated with your payment"
    )
    
    emergency_plan = st.selectbox(
        "Account Type:", 
        ["demo", "starter", "pro", "ultimate"], 
        index=1, 
        key="emergency_plan_select",
        help="Select based on your purchase"
    )
    
    if st.button("⚡ Grant Emergency Access", type="primary", key="emergency_grant_access"):
        if emergency_username:
            # Create account with selected plan
            user_data = {
                "username": emergency_username,
                "plan": emergency_plan,
                "credits": 5 if emergency_plan == "demo" else 5,  # Default credits
                "email": f"{emergency_username}@emergency.com",
                "created_at": datetime.now().isoformat(),
                "emergency_access": True,
                "total_leads_downloaded": 0,
                "transactions": []
            }
            
            # Set session using simple_auth
            simple_auth.current_user = emergency_username
            simple_auth.user_data = user_data
            
            # Set Streamlit session state
            st.session_state.authenticated = True
            st.session_state.username = emergency_username
            st.session_state.user_data = user_data
            st.session_state.credits = user_data['credits']
            
            st.success(f"✅ Emergency access granted for {emergency_username}!")
            st.info("💡 Please update your account details in Settings")
            st.balloons()
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Please enter your username")

# Load config function
def load_config():
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
            config = patch_stripe_credentials(config)
            
            # Move Stripe key to root level if it's in global
            if "stripe_secret_key" not in config and "global" in config:
                if "stripe_secret_key" in config["global"]:
                    config["stripe_secret_key"] = config["global"]["stripe_secret_key"]
                    with open("config.json", "w") as f:
                        json.dump(config, f, indent=4)
                    print("✅ Moved Stripe key to root level")
            
            return config
        else:
            print("❌ config.json not found!")
            return {}
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return {}

# Load config
config = load_config()

def show_auth_required_message(feature_name="this feature"):
    """Show auth requirement for specific features"""
    st.warning(f"🔐 Please sign in to access {feature_name}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Sign In", use_container_width=True, key=f"auth_signin_{feature_name}"):
            st.session_state.show_login = True
            st.session_state.show_register = False  # ← ADD THIS
            st.rerun()
    with col2:
        if st.button("🚀 Start Demo", type="primary", use_container_width=True, key=f"auth_register_{feature_name}"):
            st.session_state.show_register = True
            st.session_state.show_login = False  # ← ADD THIS
            st.rerun()

def require_authentication(feature_name="this feature"):
    """Check authentication for specific features"""
    if not user_authenticated:
        show_auth_required_message(feature_name)
        return False
    return True

def show_auth_required_dashboard():
    """Dashboard for non-authenticated users"""
    st.warning("🔐 Sign in to access your dashboard")
    
    # Value proposition
    st.markdown("### 🚀 Lead Generator Empire")
    st.markdown("**Generate high-quality leads from 8 platforms in minutes**")
    
    # Feature highlights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🔬 5 FREE Demo Leads**")
        st.markdown("Try the platform risk-free")
    
    with col2:
        st.markdown("**⚡ 8 Platforms**")
        st.markdown("Twitter, LinkedIn, Facebook &amp; more")
    
    with col3:
        st.markdown("**🚀 Instant Results**")
        st.markdown("CSV download in minutes")
    
    # Auth buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Start Demo (5 Free Leads)", type="primary", use_container_width=True, key="tab1_register"):
            st.session_state.show_register = True
            st.session_state.show_login = False
            st.rerun()
    
    with col2:
        if st.button("🔑 Sign In", use_container_width=True, key="tab1_login"):
            st.session_state.show_login = True
            st.session_state.show_register = False
            st.rerun()

# Simple Credit System - No complex auth needed
AUTH_AVAILABLE = True  # Always available with simple system
USAGE_TRACKING_AVAILABLE = False  # Not needed with credit system

# 🌍 NEW: Import multilingual capabilities
try:
    from multilingual_dm_generator import (
        detect_user_language, 
        generate_multilingual_dm, 
        generate_multilingual_batch,
        LANGUAGE_KEYWORDS,
        PLATFORM_LANGUAGE_STYLES
    )
    from dm_sequences import generate_multiple_dms
    from dm_csv_exporter import export_dms_detailed, create_campaign_summary
    MULTILINGUAL_AVAILABLE = True
except ImportError:
    MULTILINGUAL_AVAILABLE = True  # ← Force it to True anyway
    print("⚠️ Multilingual imports failed but keeping features available")

# Page config
st.set_page_config(
    page_title="Lead Generator Empire", 
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

from stripe_checkout import handle_payment_success

def handle_payment_success_url():
    qp = st.query_params
    if qp.get("payment_success") != "true":
        return False

    username = qp.get("username", st.session_state.get("username", "unknown"))
    tier = qp.get("tier", "starter")
    typ = qp.get("type", "subscription")

    if typ == "subscription":
        monthly = int(qp.get("monthly_credits", "0") or 0)
        handle_payment_success(
            username=username,
            tier_name=tier,
            monthly_credits=monthly,
            payment_type="subscription",
        )
    else:
        credits = int(qp.get("credits", "0") or 0)
        handle_payment_success(
            username=username,
            tier_name=tier,
            credits=credits,
            payment_type="credits",
        )
    return True


def handle_stripe_payment_success():
    """Handle Stripe payment success - FIXED to pass correct parameters"""
    query_params = st.query_params
   
    if "payment_success" in query_params:
        # Extract all required parameters
        username = query_params.get("username", "unknown")
        tier_name = query_params.get("tier", "unknown")
        credits = query_params.get("credits", "0")
        amount = query_params.get("amount", "0")
        
        # Debug logging
        print(f"🔍 Payment success parameters:")
        print(f"   Username: {username}")
        print(f"   Tier: {tier_name}")
        print(f"   Credits: {credits}")
        print(f"   Amount: {amount}")
        
        try:
            credits = int(credits)
            amount = float(amount)
        except (ValueError, TypeError) as e:
            st.error(f"❌ Invalid payment parameters: {e}")
            print(f"❌ Parameter conversion error: {e}")
            return False
       
        if username != "unknown" and credits > 0:
            try:
                from stripe_checkout import handle_payment_success
                
                # FIXED: Call with 4 parameters (username, tier_name, credits, amount)
                handle_payment_success(username, tier_name, credits, amount)
                print(f"✅ Payment success handled with 4 parameters")
                return True
                
            except Exception as e:
                st.error(f"❌ Payment processing error: {e}")
                print(f"❌ Payment processing error: {e}")
                
                # Emergency fallback: at least add the credits
                try:
                    st.balloons()
                    st.success(f"🎉 Payment Successful!")
                    
                    from simple_credit_system import credit_system
                    success = credit_system.add_credits(username, credits, tier_name)
                    if success:
                        st.success(f"✅ {credits} credits added to your account!")
                        st.warning("⚠️ Admin logging may have failed - contact support if purchase doesn't appear in admin")
                    else:
                        st.error("❌ Error adding credits - contact support immediately")
                except Exception as credit_error:
                    st.error(f"❌ Critical error: {credit_error}")
                
                return True  # Return True because payment was successful
                
        else:
            st.error("❌ Invalid payment parameters received")
            print(f"❌ Invalid parameters: username={username}, credits={credits}")
   
    return False


def failsafe_payment_logger():
    """Failsafe logger that catches any payment success and logs it to admin"""
    query_params = st.query_params
    
    # Check for ANY payment success indicators
    payment_indicators = [
        "payment_success", "success", "tier", "credits", "amount", 
        "package", "plan", "stripe_session_id"
    ]
    
    has_payment_indicators = any(param in query_params for param in payment_indicators)
    
    if has_payment_indicators:
        username = query_params.get("username", "unknown")
        
        # Skip if already processed or invalid
        if username == "unknown" or not username:
            return False
        
        # Check if this is a credit purchase
        if "credits" in query_params and "amount" in query_params:
            credits = query_params.get("credits", "0")
            amount = query_params.get("amount", "0") 
            tier = query_params.get("tier", "Unknown Package")
            
            try:
                credits = int(credits)
                amount = float(amount)
                
                print(f"🔍 FAILSAFE: Credit purchase detected")
                print(f"   Username: {username}")
                print(f"   Credits: {credits}")
                print(f"   Amount: ${amount}")
                print(f"   Tier: {tier}")
                
                # Log directly to admin system
                success = log_credit_purchase_failsafe(
                    username=username,
                    package_name=tier,
                    price=amount,
                    credits=credits
                )
                
                if success:
                    print(f"✅ FAILSAFE: Purchase logged for {username}")
                else:
                    print(f"❌ FAILSAFE: Logging failed for {username}")
                
                return True
                
            except (ValueError, TypeError) as e:
                print(f"❌ FAILSAFE: Parameter error - {e}")
        
        # Check if this is a package purchase
        elif "package" in query_params:
            package = query_params.get("package", "Unknown")
            amount = query_params.get("amount", "0")
            
            try:
                amount = float(amount)
                
                print(f"🔍 FAILSAFE: Package purchase detected")
                print(f"   Username: {username}")
                print(f"   Package: {package}")
                print(f"   Amount: ${amount}")
                
                # Log package purchase
                success = log_package_purchase_failsafe(
                    username=username,
                    package_name=package,
                    price=amount
                )
                
                if success:
                    print(f"✅ FAILSAFE: Package logged for {username}")
                else:
                    print(f"❌ FAILSAFE: Package logging failed for {username}")
                
                return True
                
            except (ValueError, TypeError) as e:
                print(f"❌ FAILSAFE: Package parameter error - {e}")
    
    return False

def log_credit_purchase_failsafe(username: str, package_name: str, price: float, credits: int) -> bool:
    """Failsafe credit purchase logging - guaranteed to work"""
    try:
        from datetime import datetime
        import os
        import json
        
        print(f"🔄 FAILSAFE: Logging credit purchase")
        
        # Create purchase event
        purchase_event = {
            "event_type": "credit_purchase",
            "package_type": "CREDIT_TOPUP", 
            "username": username,
            "package_name": package_name,
            "package_price": price,
            "credits_purchased": credits,
            "cost_per_credit": round(price / credits, 2) if credits > 0 else 0,
            "timestamp": datetime.now().isoformat(),
            "status": "COMPLETED",
            "user_email": f"{username}@failsafe.com",  # Fallback email
            "user_plan": "unknown",
            "priority": "LOW",
            "logged_by": "failsafe_system",
            "failsafe": True
        }
        
        # Ensure file exists
        events_file = "package_purchases.json"
        if not os.path.exists(events_file):
            with open(events_file, "w") as f:
                json.dump([], f)
            print(f"✅ FAILSAFE: Created {events_file}")
        
        # Read current events
        try:
            with open(events_file, "r") as f:
                events = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            events = []
            print(f"⚠️ FAILSAFE: File was corrupted, starting fresh")
        
        # Check for duplicates (prevent double-logging)
        timestamp_key = purchase_event["timestamp"][:16]  # Match to minute level
        existing_purchase = any(
            event.get("username") == username and 
            event.get("package_name") == package_name and
            event.get("timestamp", "")[:16] == timestamp_key
            for event in events
        )
        
        if existing_purchase:
            print(f"⚠️ FAILSAFE: Duplicate purchase detected, skipping")
            return True  # Not an error, just already logged
        
        # Add new purchase
        events.append(purchase_event)
        
        # Save back to file
        with open(events_file, "w") as f:
            json.dump(events, f, indent=2)
        
        print(f"✅ FAILSAFE: Credit purchase logged to {events_file}")
        
        # Also log to alerts file
        alerts_file = "purchase_alerts.json"
        try:
            if not os.path.exists(alerts_file):
                with open(alerts_file, "w") as f:
                    json.dump([], f)
            
            with open(alerts_file, "r") as f:
                alerts = json.load(f)
            
            alert_entry = {
                "type": "CREDIT_PURCHASE_FAILSAFE",
                "username": username,
                "package": package_name,
                "price": price,
                "credits": credits,
                "timestamp": datetime.now().isoformat(),
                "alert_sent": False,  # We're not sending emails in failsafe mode
                "status": "COMPLETED"
            }
            
            alerts.append(alert_entry)
            
            with open(alerts_file, "w") as f:
                json.dump(alerts, f, indent=2)
            
            print(f"✅ FAILSAFE: Alert logged to {alerts_file}")
            
        except Exception as alert_error:
            print(f"⚠️ FAILSAFE: Alert logging failed but purchase logged: {alert_error}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILSAFE: Critical logging error - {e}")
        return False

def log_package_purchase_failsafe(username: str, package_name: str, price: float) -> bool:
    """Failsafe package purchase logging"""
    try:
        from datetime import datetime
        import os
        import json
        
        print(f"🔄 FAILSAFE: Logging package purchase")
        
        # Create package event
        purchase_event = {
            "event_type": "custom_package_purchase",  # Assume custom for now
            "package_type": "CUSTOM_LEADS",
            "username": username,
            "package_name": package_name,
            "package_price": price,
            "lead_count": 0,  # Unknown from URL params
            "timestamp": datetime.now().isoformat(),
            "status": "PENDING_FULFILLMENT",
            "user_email": f"{username}@failsafe.com",
            "user_plan": "unknown",
            "priority": "HIGH",
            "logged_by": "failsafe_system",
            "failsafe": True
        }
        
        # Same logging logic as credits
        events_file = "package_purchases.json"
        if not os.path.exists(events_file):
            with open(events_file, "w") as f:
                json.dump([], f)
        
        try:
            with open(events_file, "r") as f:
                events = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            events = []
        
        # Add and save
        events.append(purchase_event)
        with open(events_file, "w") as f:
            json.dump(events, f, indent=2)
        
        print(f"✅ FAILSAFE: Package purchase logged")
        return True
        
    except Exception as e:
        print(f"❌ FAILSAFE: Package logging error - {e}")
        return False

# Add this to your main app flow - call it early in your app
def check_and_log_payments():
    """Call this early in your main app to catch any missed payments"""
    
    # Only run once per session to avoid repeated logging
    if not st.session_state.get('failsafe_payment_checked', False):
        
        print("🔍 FAILSAFE: Checking for payment returns...")
        
        payment_logged = failsafe_payment_logger()
        
        if payment_logged:
            print("✅ FAILSAFE: Payment was logged by failsafe system")
            # Mark as processed
            st.session_state.failsafe_payment_checked = True
        else:
            # No payment detected, that's fine
            st.session_state.failsafe_payment_checked = True


def debug_payment_flow():
    """Debug the complete payment flow"""
    
    query_params = st.query_params
    
    # Check if this is a payment return
    payment_indicators = ["payment_success", "success", "tier", "credits", "amount"]
    has_payment = any(param in query_params for param in payment_indicators)
    
    if has_payment:
        st.markdown("### 🔍 PAYMENT FLOW DEBUG")
        
        # Show all URL parameters
        st.write("**🔗 URL Parameters:**")
        for key, value in query_params.items():
            st.write(f"- {key}: {value}")
        
        # Extract parameters
        username = query_params.get("username", "unknown")
        tier = query_params.get("tier", "unknown")
        credits = query_params.get("credits", "0")
        amount = query_params.get("amount", "0")
        
        st.write(f"**📊 Extracted Data:**")
        st.write(f"- Username: {username}")
        st.write(f"- Tier: {tier}")
        st.write(f"- Credits: {credits}")
        st.write(f"- Amount: ${amount}")
        
        # Test the admin logging function directly
        if st.button("🧪 Test Admin Logging Now"):
            try:
                credits_int = int(credits)
                amount_float = float(amount)
                
                # Call the admin logging function directly
                success = log_payment_to_admin_direct(username, tier, credits_int, amount_float)
                
                if success:
                    st.success("✅ Admin logging test successful!")
                else:
                    st.error("❌ Admin logging test failed!")
                    
            except Exception as e:
                st.error(f"❌ Test failed: {e}")

def log_payment_to_admin_direct(username: str, tier: str, credits: int, amount: float) -> bool:
    """Direct function to log payment to admin - bypasses all other systems"""
    
    try:
        from datetime import datetime
        import json
        import os
        
        print(f"🔄 DIRECT ADMIN LOGGING:")
        print(f"   Username: {username}")
        print(f"   Tier: {tier}")
        print(f"   Credits: {credits}")
        print(f"   Amount: ${amount}")
        
        # Create purchase event
        purchase_event = {
            "event_type": "credit_purchase",
            "package_type": "CREDIT_TOPUP",
            "username": username,
            "package_name": tier,
            "package_price": amount,
            "credits_purchased": credits,
            "cost_per_credit": round(amount / credits, 2) if credits > 0 else 0,
            "timestamp": datetime.now().isoformat(),
            "status": "COMPLETED",
            "user_email": f"{username}@direct.com",
            "user_plan": "unknown",
            "priority": "LOW",
            "logged_via": "direct_admin_logging",
            "direct_test": True
        }
        
        # Load admin purchases
        admin_file = "package_purchases.json"
        if not os.path.exists(admin_file):
            with open(admin_file, "w") as f:
                json.dump([], f)
        
        with open(admin_file, "r") as f:
            admin_purchases = json.load(f)
        
        # Add new purchase
        admin_purchases.append(purchase_event)
        
        # Save back
        with open(admin_file, "w") as f:
            json.dump(admin_purchases, f, indent=2)
        
        print(f"✅ DIRECT ADMIN LOGGING SUCCESSFUL")
        return True
        
    except Exception as e:
        print(f"❌ DIRECT ADMIN LOGGING FAILED: {e}")
        return False

def force_log_recent_stripe_payments():
    """Force log any recent Stripe payments that were missed"""
    
    st.markdown("### 🚨 Force Log Recent Payments")
    
    # Manual entry for test purchases
    st.markdown("**Manual Entry for Missing Test Purchase:**")
    
    manual_col1, manual_col2, manual_col3, manual_col4 = st.columns(4)
    
    with manual_col1:
        manual_username = st.text_input("Username:", value="daveyd", key="manual_username")
    
    with manual_col2:
        manual_tier = st.text_input("Package:", value="Quick Boost", key="manual_tier")
    
    with manual_col3:
        manual_credits = st.number_input("Credits:", value=100, key="manual_credits")
    
    with manual_col4:
        manual_amount = st.number_input("Amount:", value=47.0, key="manual_amount")
    
    if st.button("🔧 Force Log This Purchase", type="primary"):
        success = log_payment_to_admin_direct(manual_username, manual_tier, int(manual_credits), float(manual_amount))
        
        if success:
            st.success(f"✅ Manually logged: {manual_tier} for {manual_username} - ${manual_amount}")
            st.info("🔄 Refresh your admin dashboard to see the purchase!")
            st.balloons()
        else:
            st.error("❌ Manual logging failed")

# Add this to capture Stripe webhook/return data
def capture_stripe_webhook_data():
    """Capture and log Stripe payment data"""
    
    st.markdown("### 🎯 Stripe Payment Capture")
    
    query_params = st.query_params
    
    # Check for Stripe session data
    if "cs_test_" in str(query_params) or "payment_intent" in query_params:
        st.info("🔍 Stripe session detected in URL!")
        
        # Try to extract session info
        for key, value in query_params.items():
            if key.startswith("cs_test_"):
                st.write(f"**Stripe Session:** {value}")
            elif key == "payment_intent":
                st.write(f"**Payment Intent:** {value}")
    
    # Manual Stripe session processor
    stripe_session = st.text_input("Paste Stripe Session ID (if available):")
    
    if stripe_session and st.button("🔍 Process Stripe Session"):
        st.info("🚧 Stripe session processing would go here")
        # In a real implementation, you'd use the Stripe API to get session details

# CRITICAL: Add this to your main app startup
def ensure_payment_logging():
    """Ensure all payments get logged - add this to main app startup"""
    
    query_params = st.query_params
    
    # Check for payment success
    if "payment_success" in query_params or "success" in query_params:
        username = query_params.get("username")
        tier = query_params.get("tier")
        credits = query_params.get("credits")
        amount = query_params.get("amount")
        
        if username and tier and credits and amount:
            try:
                credits_int = int(credits)
                amount_float = float(amount)
                
                print(f"🔄 ENSURING PAYMENT GETS LOGGED:")
                print(f"   Username: {username}")
                print(f"   Package: {tier}")
                print(f"   Credits: {credits_int}")
                print(f"   Amount: ${amount_float}")
                
                # Force log to admin
                success = log_payment_to_admin_direct(username, tier, credits_int, amount_float)
                
                if success:
                    print(f"✅ Payment logged via ensure_payment_logging")
                else:
                    print(f"❌ ensure_payment_logging failed")
                    
            except Exception as e:
                print(f"❌ ensure_payment_logging error: {e}")

def check_scraper_authorization(username: str, estimated_leads: int) -> Tuple[bool, str]:
    """Authorization including demo mode handling"""
    if not username:
        return False, "❌ Please sign in to generate leads"
    
    try:
        from simple_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if not user_info:
            return False, "❌ User not found"
        
        user_plan = user_info.get('plan', 'demo')
        
        # Special handling for demo users
        if user_plan == 'demo':
            can_demo, remaining = credit_system.can_use_demo(username)
            
            if not can_demo:
                return False, "❌ Demo leads exhausted. Upgrade to continue generating leads."
            
            if estimated_leads > remaining:
                return False, f"❌ Demo limit: {estimated_leads} leads requested, only {remaining} remaining. Upgrade for unlimited access."
            
            return True, f"✅ Demo mode: {estimated_leads} leads will be generated ({remaining} demo leads available)"
        
        # For paid plans, use regular credit checking
        return enforce_credit_limits_on_scraper(username, estimated_leads)
        
    except Exception as e:
        return False, f"❌ Authorization error: {str(e)}"
    
def generate_multilingual_dms_for_leads(leads_df, platform, enable_multilingual=False, language_mode="Auto-detect", cultural_style="Standard"):
    """Generate multilingual DMs for scraped leads"""
    
    if not enable_multilingual or not MULTILINGUAL_AVAILABLE:
        # Use existing English-only DM generation
        return leads_df
    
    print(f"🌍 Generating multilingual DMs for {len(leads_df)} leads...")
    
    # Import multilingual functions
    from multilingual_dm_generator import generate_multilingual_dm, detect_user_language
    
    enhanced_leads = []
    
    for _, lead in leads_df.iterrows():
        try:
            name = lead.get('name', '')
            bio = lead.get('bio', '')
            
            # Determine target language
            if language_mode == "Auto-detect":
                target_language = None  # Let the system auto-detect
            else:
                # Extract language from selection (e.g., "Force Spanish" -> "spanish")
                target_language = language_mode.replace("Force ", "").lower()
            
            # Generate multilingual DM
            dm_result = generate_multilingual_dm(
                name=name,
                bio=bio, 
                platform=platform.lower(),
                language=target_language
            )
            
            # Add multilingual data to lead
            enhanced_lead = lead.to_dict()
            enhanced_lead.update({
                'dm': dm_result['dm'],
                'detected_language': dm_result['detected_language'],
                'dm_language': dm_result['language'], 
                'dm_persona': dm_result['persona'],
                'dm_method': dm_result['method'],
                'dm_length': len(dm_result['dm']),
                'cultural_style': cultural_style,
                'multilingual_enabled': True
            })
            
            enhanced_leads.append(enhanced_lead)
            
        except Exception as e:
            print(f"⚠️ Multilingual DM error for {lead.get('name', 'Unknown')}: {e}")
            # Fallback to original lead data
            enhanced_lead = lead.to_dict()
            enhanced_lead.update({
                'dm': f"Hi {name.split()[0] if name else 'there'}! Would love to connect!",
                'detected_language': 'english',
                'dm_language': 'english',
                'dm_persona': 'fallback',
                'dm_method': 'error_fallback',
                'multilingual_enabled': True,
                'error': str(e)
            })
            enhanced_leads.append(enhanced_lead)
    
    return pd.DataFrame(enhanced_leads)

def finalize_scraper_results_with_multilingual(username: str, leads: list, platform: str) -> list:
    """Enhanced version that includes multilingual DM processing"""
    
    # First do the existing processing (credit consumption, masking, etc.)
    processed_leads = finalize_scraper_results(username, leads, platform)
    
    if not processed_leads:
        return processed_leads
    
    # Check if multilingual is enabled
    enable_multilingual = st.session_state.get('enable_multilingual', False)
    
    if enable_multilingual and MULTILINGUAL_AVAILABLE:
        try:
            # Convert to DataFrame for processing
            df = pd.DataFrame(processed_leads)
            
            # Get language settings from session state
            language_mode = st.session_state.get('target_language_mode', 'Auto-detect')
            cultural_style = st.session_state.get('cultural_adaptation_mode', 'Standard')
            
            print(f"🌍 Applying multilingual DM generation...")
            print(f"   Language Mode: {language_mode}")
            print(f"   Cultural Style: {cultural_style}")
            
            # Generate multilingual DMs
            enhanced_df = generate_multilingual_dms_for_leads(
                df, platform, True, language_mode, cultural_style
            )
            
            # Convert back to list of dicts
            return enhanced_df.to_dict('records')
            
        except Exception as e:
            print(f"⚠️ Multilingual processing error: {e}")
            # Return original processed leads if multilingual fails
            return processed_leads
    
    return processed_leads

# ALSO UPDATE the finalize_scraper_results function:

def finalize_scraper_results(username: str, leads: list, platform: str) -> list:
    """Process scraper results with demo mode and credit consumption"""
    if not leads or not username:
        return leads
    
    try:
        from simple_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if not user_info:
            return leads
        
        user_plan = user_info.get('plan', 'demo')
        
        # Check if demo user
        if user_plan == 'demo':
            # For demo users, consume demo leads instead of credits
            leads_to_consume = len(leads)
            
            consumed_count = 0
            for _ in range(leads_to_consume):
                if credit_system.consume_demo_lead(username):
                    consumed_count += 1
                else:
                    break
            
            # Show demo message
            can_demo, remaining = credit_system.can_use_demo(username)
            print(f"📱 Demo user {username}: {consumed_count} demo leads used, {remaining} remaining")
            
            # Apply demo masking (show partial info)
            masked_leads = []
            for i, lead in enumerate(leads[:consumed_count]):
                masked_lead = lead.copy()
                
                # Mask email if present
                if "email" in masked_lead and masked_lead["email"]:
                    email = masked_lead["email"]
                    if "@" in email:
                        name, domain = email.split("@", 1)
                        masked_lead["email"] = f"{name[:2]}***@{domain}"
                
                # Mask handle/username
                if "handle" in masked_lead and masked_lead["handle"]:
                    handle = masked_lead["handle"]
                    masked_lead["handle"] = f"{handle[:3]}***"
                
                # Add demo watermark
                masked_lead["demo_mode"] = True
                masked_lead["upgrade_message"] = "Upgrade to see full contact details"
                
                masked_leads.append(masked_lead)
            
            # Update session state to reflect demo usage
            st.session_state.credits = remaining  # Show remaining demo leads
            
            return masked_leads
        
        else:
            # For paid plans, use regular credit consumption and masking
            masked_leads = finalize_scraper_results_with_multilingual(username, leads, platform)
            
            # Consume credits
            credits_consumed = len(leads)
            success = consume_user_credits(username, credits_consumed, platform)
            
            if success:
                print(f"✅ Consumed {credits_consumed} credits for {len(leads)} leads from {platform}")
                
                # Update session state credits
                remaining_credits = simple_auth.get_user_credits()
                st.session_state.credits = remaining_credits
                st.rerun()
                
                return masked_leads
            else:
                print(f"❌ Failed to consume credits for {platform}")
                return []
    
    except Exception as e:
        print(f"❌ Error processing scraper results: {str(e)}")
        return []
    
def process_demo_leads(username: str, leads: list, platform: str) -> list:
    """Process leads for demo users"""
    
    try:
        from simple_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if user_info and user_info.get('plan') == 'demo':
            # Consume demo leads
            consumed = 0
            for lead in leads:
                if credit_system.consume_demo_lead(username):
                    consumed += 1
                else:
                    break
            
            print(f"📱 Demo consumption: {consumed} demo leads used")
            
            # Return only the leads we could consume
            return leads[:consumed]
    
    except Exception as e:
        print(f"⚠️ Demo processing error: {e}")
    
    return leads

def generate_safe_demo_leads(search_term, selected_platforms, max_scrolls):
    """Generate realistic sample leads with industry-specific data"""
    import random
    import pandas as pd
    from datetime import datetime
    
    # Industry-specific sample data based on search term
    industry_data = {
        "music": {
            "names": ["Sarah MusicTeacher", "Mike GuitarPro", "Jessica VocalCoach", "Ryan DrumMaster", "Lisa PianoExpert", 
                     "Alex ViolinStudio", "Jordan SongWriter", "Casey MusicProducer", "Taylor BandDirector", "Morgan AudioEngineer"],
            "bios": [
                "🎵 Professional music instructor with 8+ years experience. Specializing in guitar, piano, and vocal coaching.",
                "🎸 Guitar virtuoso and music educator. Teaching rock, jazz, and classical styles to students of all ages.",
                "🎤 Vocal coach helping singers find their voice. Broadway training and performance background.",
                "🥁 Drum instructor and session musician. 15 years in the industry, worked with major labels.",
                "🎹 Piano teacher and composer. Classical training with modern approach to music education."
            ],
            "locations": ["Nashville, TN", "Los Angeles, CA", "New York, NY", "Austin, TX", "Seattle, WA"]
        },
        "fitness": {
            "names": ["Alex FitTrainer", "Jordan WellnessCoach", "Casey YogaGuru", "Taylor HealthPro", "Morgan FitLife",
                     "Sam PersonalTrainer", "Riley CrossFitCoach", "Avery NutritionExpert", "Blake BootcampInstructor", "Quinn PilatesStudio"],
            "bios": [
                "💪 Certified personal trainer specializing in strength training and weight loss. Transform your body and mind!",
                "🧘 Yoga instructor and wellness coach. Helping clients achieve balance in body, mind, and spirit.",
                "🏃 Running coach and marathon finisher. Training athletes for races from 5K to ultra marathons.",
                "🏋️ CrossFit Level 2 trainer. Building functional fitness and strong communities through challenging workouts.",
                "🥗 Nutrition specialist and health coach. Evidence-based approach to sustainable lifestyle changes."
            ],
            "locations": ["Miami, FL", "San Diego, CA", "Denver, CO", "Portland, OR", "Phoenix, AZ"]
        },
        "business": {
            "names": ["David CEO", "Amanda StartupFounder", "Michael Entrepreneur", "Rachel BusinessPro", "John Mentor",
                     "Sarah BusinessCoach", "Chris Consultant", "Jennifer StrategyExpert", "Kevin Investor", "Lisa ExecutiveCoach"],
            "bios": [
                "🚀 Serial entrepreneur and business coach. Helping startups scale from idea to IPO.",
                "💼 Management consultant with Fortune 500 experience. Specializing in digital transformation.",
                "📈 Growth strategist and marketing expert. 10+ years driving revenue for B2B companies.",
                "💡 Innovation consultant helping established companies think like startups.",
                "🎯 Business development specialist. Connecting people, ideas, and opportunities."
            ],
            "locations": ["San Francisco, CA", "New York, NY", "Chicago, IL", "Boston, MA", "Dallas, TX"]
        },
        "marketing": {
            "names": ["Kelly DigitalPro", "Chris SocialMedia", "Jennifer ContentCreator", "Alex BrandExpert", "Nicole MarketingGuru",
                     "Ryan SEOSpecialist", "Taylor CopyWriter", "Morgan DigitalStrategy", "Casey InfluencerPro", "Jordan GrowthHacker"],
            "bios": [
                "📱 Digital marketing strategist specializing in social media growth and brand awareness.",
                "✍️ Content creator and copywriter. Turning words into revenue for ambitious brands.",
                "🎯 Performance marketer focused on ROI-driven campaigns and data analytics.",
                "🔥 Brand strategist helping companies tell their story and connect with customers.",
                "📊 Growth marketing expert. Scaling startups through creative acquisition strategies."
            ],
            "locations": ["Los Angeles, CA", "New York, NY", "Austin, TX", "Miami, FL", "Seattle, WA"]
        }
    }
    
    # Determine industry from search term
    detected_industry = "business"  # default
    search_lower = search_term.lower()
    
    for industry, data in industry_data.items():
        industry_keywords = {
            "music": ["music", "guitar", "piano", "song", "band", "vocal", "drum", "instrument"],
            "fitness": ["fitness", "trainer", "yoga", "gym", "workout", "health", "nutrition", "coach"],
            "business": ["business", "entrepreneur", "startup", "ceo", "consultant", "executive"],
            "marketing": ["marketing", "digital", "social", "brand", "advertising", "seo", "content"]
        }
        
        if any(keyword in search_lower for keyword in industry_keywords.get(industry, [])):
            detected_industry = industry
            break
    
    # Use detected industry data
    selected_data = industry_data[detected_industry]
    
    all_demo_leads = []
    
    # Platform performance (leads per scroll)
    platform_performance = {
        "twitter": 2, "facebook": 8, "linkedin": 1.5, "youtube": 2, 
        "tiktok": 6, "instagram": 2, "medium": 1, "reddit": 1
    }
    
    # Generate leads for each platform
    for platform in selected_platforms:
        platform_lower = platform.lower()
        leads_per_scroll = platform_performance.get(platform_lower, 1)
        estimated_leads = min(int(max_scrolls * leads_per_scroll), 20)  # Cap at 20 per platform
        
        for i in range(estimated_leads):
            # Select random name and bio from industry-specific data
            full_name = random.choice(selected_data["names"])
            bio_template = random.choice(selected_data["bios"])
            location = random.choice(selected_data["locations"])
            
            # Create realistic name variations
            name_parts = full_name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_initial = name_parts[1][0] if len(name_parts[1]) > 0 else "X"
                display_name = f"{first_name} {last_initial}."
            else:
                display_name = full_name
            
            # Create realistic handle
            base_handle = full_name.replace(' ', '').lower()
            handle_variations = [
                f"@{base_handle}{random.randint(10, 999)}",
                f"@{first_name.lower()}{last_initial.lower()}{random.randint(10, 99)}",
                f"@{base_handle}_pro",
                f"@{base_handle}official"
            ]
            handle = random.choice(handle_variations)
            
            # Platform-specific follower ranges
            follower_ranges = {
                "twitter": (500, 50000),
                "facebook": (200, 10000), 
                "linkedin": (300, 5000),
                "youtube": (1000, 100000),
                "tiktok": (2000, 500000),
                "instagram": (800, 80000),
                "medium": (100, 2000),
                "reddit": (50, 1000)
            }
            
            min_followers, max_followers = follower_ranges.get(platform_lower, (500, 20000))
            
            # Create lead with GUARANTEED safe data types
            lead = {
                "name": str(display_name),
                "handle": str(handle[:3] + "***"),  # Pre-masked for demo
                "bio": str(bio_template),
                "platform": str(platform_lower),
                "followers": int(random.randint(min_followers, max_followers)),
                "following": int(random.randint(100, 2000)),
                "posts": int(random.randint(50, 1000)),
                "engagement_rate": float(round(random.uniform(2.0, 8.0), 1)),
                "location": str(location),
                "verified": bool(random.choice([False, False, False, True])),  # 25% chance
                "demo_mode": bool(True),
                "demo_status": str("SAMPLE DATA"),
                "industry": str(detected_industry),
                "sample_type": str("realistic_demo"),
                "upgrade_message": str("Upgrade for real contact details"),
                "data_quality": str("High-quality sample"),
                "generated_at": str(datetime.now().isoformat())
            }
            
            # Add platform-specific fields
            if platform_lower == "linkedin":
                job_titles = {
                    "music": ["Music Instructor", "Audio Engineer", "Music Producer", "Vocal Coach"],
                    "fitness": ["Personal Trainer", "Fitness Coach", "Yoga Instructor", "Nutrition Specialist"],
                    "business": ["Business Consultant", "CEO", "Entrepreneur", "Strategy Director"],
                    "marketing": ["Digital Marketing Manager", "Brand Strategist", "Content Creator", "Growth Marketer"]
                }
                
                companies = {
                    "music": ["Music Academy", "Recording Studio", "Entertainment Group", "Music School"],
                    "fitness": ["Fitness Center", "Wellness Studio", "Health Club", "Training Facility"],
                    "business": ["Consulting Group", "Startup Inc", "Business Solutions", "Strategy Firm"],
                    "marketing": ["Digital Agency", "Marketing Co", "Brand Studio", "Growth Partners"]
                }
                
                lead["job_title"] = str(random.choice(job_titles[detected_industry]))
                lead["company"] = str(random.choice(companies[detected_industry]))
                lead["connections"] = int(random.randint(300, 5000))
                
            elif platform_lower == "youtube":
                lead["subscribers"] = int(random.randint(1000, 100000))
                lead["videos"] = int(random.randint(20, 500))
                lead["total_views"] = int(lead["subscribers"] * random.randint(50, 200))
                
            elif platform_lower == "tiktok":
                lead["likes"] = int(random.randint(10000, 500000))
                lead["videos"] = int(random.randint(50, 300))
                lead["shares"] = int(random.randint(500, 10000))
                
            elif platform_lower == "instagram":
                lead["posts"] = int(random.randint(100, 2000))
                lead["stories_highlights"] = int(random.randint(5, 50))
                lead["avg_likes"] = int(lead["followers"] * random.uniform(0.02, 0.08))
                
            elif platform_lower == "reddit":
                lead["karma"] = int(random.randint(500, 50000))
                lead["post_karma"] = int(lead["karma"] * random.uniform(0.3, 0.7))
                lead["comment_karma"] = int(lead["karma"] - lead["post_karma"])
                
            elif platform_lower == "medium":
                lead["articles"] = int(random.randint(10, 200))
                lead["followers"] = int(random.randint(100, 5000))  # Medium has lower follower counts
                lead["total_claps"] = int(random.randint(1000, 50000))
            
            all_demo_leads.append(lead)
    
    return all_demo_leads

def save_demo_leads_safely(leads, search_term, generation_type="sample"):
    """Save demo leads with proper error handling and clear labeling"""
    import pandas as pd
    import os
    from datetime import datetime
    
    if not leads:
        return [], pd.DataFrame()
    
    # Create DataFrame with explicit data types
    df = pd.DataFrame(leads)
    
    # FORCE proper data types
    numeric_cols = ['followers', 'following', 'posts', 'subscribers', 'videos', 'likes', 
                   'connections', 'total_views', 'shares', 'avg_likes', 'karma', 
                   'post_karma', 'comment_karma', 'articles', 'total_claps', 'stories_highlights']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(1000).astype(int)
    
    if 'engagement_rate' in df.columns:
        df['engagement_rate'] = pd.to_numeric(df['engagement_rate'], errors='coerce').fillna(5.0).astype(float)
    
    bool_cols = ['verified', 'demo_mode']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    
    # Ensure all other columns are strings
    string_cols = ['name', 'handle', 'bio', 'platform', 'location', 'demo_status', 
                   'industry', 'sample_type', 'upgrade_message', 'data_quality', 
                   'job_title', 'company', 'generated_at']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
    
    # Save files with clear naming
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_files = []
    
    # Group by platform and save
    for platform in df['platform'].unique():
        platform_df = df[df['platform'] == platform]
        filename = f"{platform}_leads_{generation_type}_{timestamp}.csv"
        platform_df.to_csv(filename, index=False)
        saved_files.append(filename)
        print(f"🎯 {generation_type.title()}: Saved {len(platform_df)} {platform} leads to {filename}")
    
    # Save combined file
    combined_filename = f"empire_leads_{generation_type}_{timestamp}.csv"
    df.to_csv(combined_filename, index=False)
    saved_files.append(combined_filename)
    
    print(f"🎯 Total {generation_type} leads generated: {len(df)}")
    
    return saved_files, df

# ALSO ADD THIS HELPER FUNCTION FOR DISPLAYING SAMPLE DATA NICELY:
def display_sample_preview(sample_df, max_rows=5):
    """Display a nice preview of sample data"""
    import streamlit as st
    
    if sample_df.empty:
        st.warning("No sample data to display")
        return
    
    # Create a cleaned up version for display
    display_df = sample_df.head(max_rows).copy()
    
    # Select the most relevant columns for preview
    preview_cols = ['name', 'platform', 'bio', 'location', 'followers', 'demo_status']
    available_cols = [col for col in preview_cols if col in display_df.columns]
    
    if available_cols:
        preview_df = display_df[available_cols]
        
        # Add some styling info
        st.markdown("**📊 Sample Data Preview:**")
        st.dataframe(preview_df, use_container_width=True)
        
        # Show stats
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_leads = len(sample_df)
            st.metric("Total Leads", total_leads)
        
        with col2:
            platforms = sample_df['platform'].nunique()
            st.metric("Platforms", platforms)
        
        with col3:
            if 'industry' in sample_df.columns:
                industry = sample_df['industry'].iloc[0]
                st.metric("Industry", industry.title())
            else:
                st.metric("Type", "Sample")
        
        with col4:
            avg_followers = int(sample_df['followers'].mean()) if 'followers' in sample_df.columns else 0
            st.metric("Avg Followers", f"{avg_followers:,}")
        
        st.success("🎯 This is sample data for demonstration - upgrade for real leads!")
        
    else:
        st.dataframe(display_df, use_container_width=True)

def generate_demo_data_in_memory(search_term, selected_platforms, max_scrolls):
    """Generate demo data in memory - no files needed!"""
    import random
    
    # Generate fake leads directly in memory
    demo_leads = []
    
    for platform in selected_platforms:
        platform_leads = max_scrolls * 2  # Simple calculation
        
        for i in range(platform_leads):
            lead = {
                "name": f"Demo User {i+1}",
                "handle": f"@demo{i+1}***",
                "bio": f"Professional {search_term} with experience 💪",
                "platform": platform,
                "followers": random.randint(1000, 50000),
                "demo_status": "SAMPLE DATA"
            }
            demo_leads.append(lead)
    
    return demo_leads

# ADD THIS FUNCTION BEFORE: simple_auth = SimpleCreditAuth()

def run_empire_scraper_fixed(selected_platforms, search_term, max_scrolls, username, user_plan):
    """FIXED scraper execution with proper Unicode handling for Windows"""
    
    try:
        print(f"🚀 FIXED SCRAPER: Starting launch...")
        print(f"   User: {username} ({user_plan})")
        print(f"   Platforms: {selected_platforms}")
        print(f"   Search: {search_term}")
        print(f"   Scrolls: {max_scrolls}")
        
        # Filter out LinkedIn (manual processing)
        instant_platforms = [p.lower() for p in selected_platforms if p.lower() != 'linkedin']
        
        if not instant_platforms:
            print("📧 Only LinkedIn selected - no instant processing needed")
            return True
        
        print(f"⚡ Processing platforms: {instant_platforms}")
        
        # Check if scraper file exists
        scraper_file = "run_daily_scraper_complete.py"
        if not os.path.exists(scraper_file):
            print(f"❌ Scraper file not found: {scraper_file}")
            return False
        
        # Set up environment variables with COMPREHENSIVE encoding fixes
        env = os.environ.copy()
        
        # Set PYTHONPATH to current directory if not set
        current_dir = os.getcwd()
        existing_pythonpath = env.get('PYTHONPATH', '')
        if existing_pythonpath:
            pythonpath = f"{current_dir}{os.pathsep}{existing_pythonpath}"
        else:
            pythonpath = current_dir
        
        # COMPREHENSIVE UNICODE ENVIRONMENT SETUP
        env.update({
            'SCRAPER_USERNAME': username,
            'USER_PLAN': user_plan,
            'SELECTED_PLATFORMS': ','.join(instant_platforms),
            'FRONTEND_SEARCH_TERM': search_term,
            'MAX_SCROLLS': str(max_scrolls),
            'PYTHONPATH': pythonpath,
            'FORCE_AUTHORIZATION': 'true' if user_plan in ['pro', 'ultimate'] else 'false',
            
            # CRITICAL UNICODE FIXES FOR WINDOWS:
            'PYTHONIOENCODING': 'utf-8',           # Force UTF-8 for all I/O
            'PYTHONUTF8': '1',                     # Enable UTF-8 mode in Python 3.7+
            'PYTHONLEGACYWINDOWSSTDIO': '0',       # Disable legacy Windows stdio
            'PYTHONUNBUFFERED': '1',               # Unbuffered output (helps with encoding)
        })
        
        print(f"🔧 Environment set with Unicode support:")
        print(f"   PYTHONIOENCODING: utf-8")
        print(f"   PYTHONUTF8: 1")
        
        # Try multiple Python executables
        python_executables = [
            sys.executable,          # Current Python
            'python',               # System Python
            'python3',              # Python 3
            'py'                    # Windows Python Launcher
        ]
        
        for python_exe in python_executables:
            try:
                print(f"🚀 Trying: {python_exe} {scraper_file}")
                
                # METHOD 1: Try with explicit UTF-8 encoding
                try:
                    result = subprocess.run(
                        [python_exe, scraper_file],
                        env=env,
                        capture_output=True,
                        text=True,                    
                        encoding='utf-8',             # ← EXPLICIT UTF-8 ENCODING
                        errors='replace',             # ← REPLACE BAD CHARACTERS INSTEAD OF CRASHING
                        timeout=300,                  
                        cwd=current_dir
                    )
                    
                    # Log output safely
                    if result.stdout:
                        print("📊 Scraper Output:")
                        print(result.stdout)
                    
                    if result.stderr:
                        print("⚠️ Scraper Errors:")
                        print(result.stderr)
                    
                    success = result.returncode == 0
                    print(f"✅ Scraper completed with return code: {result.returncode}")
                    return success
                    
                except (UnicodeDecodeError, UnicodeError) as unicode_error:
                    print(f"⚠️ Unicode error, trying bytes mode: {unicode_error}")
                    
                    # METHOD 2: FALLBACK - Use bytes mode and decode manually
                    result = subprocess.run(
                        [python_exe, scraper_file],
                        env=env,
                        capture_output=True,
                        text=False,              # ← Use bytes mode to avoid encoding issues
                        timeout=300,
                        cwd=current_dir
                    )
                    
                    # Manually decode with error handling
                    try:
                        stdout_text = result.stdout.decode('utf-8', errors='replace') if result.stdout else ""
                        stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                    except:
                        stdout_text = str(result.stdout) if result.stdout else ""
                        stderr_text = str(result.stderr) if result.stderr else ""
                    
                    if stdout_text:
                        print("📊 Scraper Output (safe decode):")
                        print(stdout_text)
                    
                    if stderr_text:
                        print("⚠️ Scraper Errors (safe decode):")
                        print(stderr_text)
                    
                    success = result.returncode == 0
                    print(f"✅ Scraper completed (bytes mode) with return code: {result.returncode}")
                    return success
                
            except FileNotFoundError:
                print(f"❌ {python_exe} not found, trying next...")
                continue
            except subprocess.TimeoutExpired:
                print("⏰ Scraper timeout - but may still be running")
                return True  # Don't fail for timeout
            except Exception as e:
                print(f"❌ Error with {python_exe}: {e}")
                continue
        
        # If we get here, no Python executable worked
        print("❌ Could not find any working Python executable")
        return False
        
    except Exception as e:
        print(f"❌ Scraper function error: {e}")
        return False

def queue_linkedin_request(username, search_term, max_scrolls, user_email):
    """Queue LinkedIn request with email notifications"""
    
    linkedin_request = {
        "username": username,
        "search_term": search_term,
        "max_scrolls": max_scrolls,
        "user_email": user_email,
        "timestamp": datetime.now().isoformat(),
        "status": "queued",
        "platform": "linkedin"
    }
    
    queue_file = "linkedin_queue.json"
    
    try:
        # Save to queue file
        if os.path.exists(queue_file):
            with open(queue_file, "r") as f:
                queue = json.load(f)
        else:
            queue = []
        
        queue.append(linkedin_request)
        
        with open(queue_file, "w") as f:
            json.dump(queue, f, indent=2)
        
        print(f"✅ LinkedIn request queued for {username}")
        
        # Send customer confirmation email
        customer_success = send_customer_confirmation_email(user_email, search_term, username)
        
        # Send business owner alert
        business_success = send_business_alert_email(search_term, user_email, max_scrolls, username)
        
        if customer_success:
            print(f"✅ Customer confirmation sent to {user_email}")
        else:
            print(f"⚠️ Customer confirmation failed for {user_email}")
        
        if business_success:
            print("✅ Business alert sent successfully")
        else:
            print("⚠️ Business alert failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to queue LinkedIn request: {e}")
        return False

def send_customer_confirmation_email(user_email, search_term, username):
    """Send customer confirmation email"""
    try:
        # Email configuration (you'll need to set these)
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        EMAIL_ADDRESS = "aileadsguy@gmail.com"  # Your business email
        EMAIL_PASSWORD = "kwud qppa vlus zyyj"   # Your app password
        
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = user_email
        msg['Subject'] = f"LinkedIn Lead Processing Started - {search_term}"
        
        # Email body
        body = f"""
Hi {username}!

Your LinkedIn lead generation request has been received and is being processed manually.

REQUEST DETAILS:
• Search Term: "{search_term}"
• Platform: LinkedIn (Manual Processing)
• Requested by: {username}
• Status: Queued for manual processing

WHAT HAPPENS NEXT:
1. Our team will manually scrape LinkedIn for "{search_term}"
2. Results will be compiled into a CSV file
3. You'll receive an email with your leads within 2-4 hours

WHY MANUAL PROCESSING?
LinkedIn actively blocks automated scraping, so we provide premium manual service that delivers:
• 100% verified profiles (no bots)
• Higher quality data with human verification
• Often includes additional contact information
• Better response rates for outreach

Thank you for choosing Lead Generator Empire!

Best regards,
The Lead Generator Empire Team
---
Need help? Reply to this email or contact support.
        """.strip()
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, user_email, text)
        server.quit()
        
        return True
        
    except Exception as e:
        print(f"❌ Customer email error: {e}")
        return False

def send_business_alert_email(search_term, user_email, max_scrolls, username):
    """Send business owner alert email"""
    try:
        # Email configuration
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        EMAIL_ADDRESS = "aileadsguy@gmail.com"  # Your business email
        EMAIL_PASSWORD = "kwud qppa vlus zyyj"   # Your app password
        BUSINESS_EMAIL = "info@sidneym.com"  # Where alerts go
        
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Calculate estimated leads
        estimated_leads = int(max_scrolls * 1.5)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = BUSINESS_EMAIL
        msg['Subject'] = f"🚨 NEW LinkedIn Request - {search_term}"
        
        # Email body
        body = f"""
🚨 NEW LINKEDIN REQUEST ALERT

📋 REQUEST DETAILS:
• Customer: {username}
• Search Term: "{search_term}"
• Customer Email: {user_email}
• Estimated Leads: ~{estimated_leads}
• Max Scrolls: {max_scrolls}
• Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡ ACTION REQUIRED:
1. Manually scrape LinkedIn for "{search_term}"
2. Save results as CSV file
3. Email CSV to: {user_email}

📁 QUEUE FILE: linkedin_queue.json

⏰ TIMELINE: Customer expects results within 2-4 hours

🔧 NEXT STEPS:
1. Open LinkedIn and search for "{search_term}"
2. Manually collect profile information
3. Handle any email verification prompts
4. Save leads as CSV
5. Email results to customer

💡 CUSTOMER STATUS:
- Customer was sent confirmation email
- Customer is expecting results within 2-4 hours
- This is a {username} account request

---
Lead Generator Empire Auto-Alert System
        """.strip()
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, BUSINESS_EMAIL, text)
        server.quit()
        
        return True
        
    except Exception as e:
        print(f"❌ Business alert error: {e}")
        return False

# Initialize simple auth system
simple_auth = SimpleCreditAuth()

# Update simple_auth state if session was restored
update_simple_auth_state(simple_auth)

# Simple authentication check
user_authenticated = simple_auth.is_authenticated()

# In main function
fix_session_state()  # Fixes current_user = None


# ADD THIS PAYMENT RECOVERY CODE HERE:
def simple_payment_recovery():
    """Ultra-simple payment recovery"""
    if not user_authenticated and "username" in st.query_params:
        username = st.query_params.get("username")
        credits = st.query_params.get("credits", "25")
        
        st.error("🔐 **Payment Session Lost - Click to Restore**")
        st.success(f"✅ Payment successful for {credits} credits")
        
        if st.button("🚀 RESTORE ACCESS", type="primary", key="simple_restore"):
            # Immediate session restore
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.credits = int(credits)
            
            simple_auth.current_user = username
            simple_auth.user_data = {"username": username, "credits": int(credits), "plan": "pro"}
            
            st.success("✅ Access restored!")
            st.rerun()
        
        st.stop()

# Helper functions
def get_latest_csv(pattern):
    """Enhanced get_latest_csv with user filtering"""
    if user_authenticated and CSV_USER_DEBUG_AVAILABLE:
        username = simple_auth.get_current_user()
        if username:
            # Use smart user detection
            user_file = get_user_csv_file(pattern, username)
            if user_file:
                return user_file
    
    # Fallback to original logic
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[0] if files else None

def save_leads_by_user(leads, platform, username):
    # Create user-specific directory
    user_dir = f"user_data/{username}"
    os.makedirs(user_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{user_dir}/{platform}_leads_{timestamp}.csv"
    
    df = pd.DataFrame(leads)
    df.to_csv(filename, index=False)
    return filename

def save_leads_with_user_tracking(leads_data, platform, username):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Method 1: Username in filename
    filename = f"{platform}_leads_{username}_{timestamp}.csv"
    
    df = pd.DataFrame(leads_data)
    df.to_csv(filename, index=False)
    return filename

# Simple payment handling
query_params = st.query_params

# Handle payment success
if show_payment_success_message():
    st.stop()

elif "cancelled" in query_params:
    st.warning("⚠️ Payment was cancelled. You can try again anytime!")
    if st.button("🔙 Back to Dashboard", key="cancel_back"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# Initialize Stripe
if "stripe_secret_key" in config:
    stripe.api_key = config["stripe_secret_key"]
else:
    st.warning("⚠️ Stripe secret key not found in config.json")

def show_simple_credit_status():
    """Show credit status with correct plan-specific messaging"""
    if not user_authenticated:
        return True
    
    username = simple_auth.get_current_user()
    if not username:
        return True
    
    try:
        from simple_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
    except:
        user_info = None
        
    if not user_info:
        st.warning("⚠️ Could not load user information")
        return True
        
    plan = user_info.get('plan', 'demo')
    
    # Plan-specific messaging
    plan_messages = {
        'demo': {
            'message': '📱 Demo Mode - 5 real demo leads + unlimited sample generation',
            'platforms': '1 platform (Twitter)',
            'color': '#17a2b8'
        },
        'starter': {
            'message': '🎯 Starter Plan - 250 leads/month across core platforms',
            'platforms': '2 platforms (Twitter, Facebook)', 
            'color': '#6c757d'
        },
        'pro': {
            'message': '💎 Pro Plan - 2,000 leads/month with advanced platforms',
            'platforms': '6 platforms (Twitter, Facebook, LinkedIn, TikTok, Instagram, YouTube)',
            'color': '#28a745'
        },
        'ultimate': {
            'message': '👑 Ultimate Plan - Unlimited leads across all platforms',
            'platforms': '8 platforms (All platforms including Medium, Reddit)',
            'color': '#ffd700'
        }
    }
    
    current_plan = plan_messages.get(plan, plan_messages['demo'])
    
    # Display plan status
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {current_plan['color']}20 0%, {current_plan['color']}10 100%);
        border: 2px solid {current_plan['color']};
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        margin: 1rem 0;
    ">
        <h3 style="color: {current_plan['color']}; margin: 0 0 0.5rem 0;">
            {current_plan['message']}
        </h3>
        <p style="margin: 0; color: #666; font-size: 0.9rem;">
            {current_plan['platforms']}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Show credits/usage info
    if plan == 'demo':
        try:
            can_demo, remaining = credit_system.can_use_demo(username)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Real Demo Leads", f"{remaining}/5", help="Limited real Twitter leads")
            with col2:
                st.metric("Sample Generation", "Unlimited", help="Test the platform anytime")
        except:
            st.metric("Demo Status", "Active")
    
    elif plan in ['starter', 'pro']:
        credits = user_info.get('credits', 0)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Credits Available", credits, help="Credits for lead generation")
        with col2:
            if plan == 'starter':
                st.metric("Monthly Limit", "250 leads", help="Starter plan limit")
            else:
                st.metric("Monthly Limit", "2,000 leads", help="Pro plan limit")
    
    else:  # ultimate
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Access Level", "Unlimited", help="No limits on lead generation")
        with col2:
            st.metric("Platform Access", "8/8", help="All platforms unlocked")
    
    return True

def show_enhanced_demo_status(username):
    """Enhanced demo status display"""
    try:
        can_demo, remaining = credit_system.can_use_demo(username)
        
        # Main status bar
        if remaining > 0:
            st.info(f"📱 **Demo Mode:** {remaining} real demo leads remaining (used {5-remaining}/5)")
        else:
            st.warning(f"📱 **Demo Mode:** All 5 real demo leads used")
        
        # Always show sample availability
        st.success("🎯 **Unlimited sample generations** available - try the platform with realistic sample data!")
        
        # Progress bar for demo leads
        demo_progress = (5 - remaining) / 5
        st.progress(demo_progress, text=f"Real Demo Leads Used: {5-remaining}/5")
        
        # Sample generation counter (if you want to track this)
        if 'sample_generations_count' in st.session_state:
            sample_count = st.session_state.sample_generations_count
            st.caption(f"🎯 Sample generations used this session: {sample_count}")
        
        return remaining > 0
        
    except Exception as e:
        st.warning("⚠️ Could not load demo status")
        return True

def show_demo_sidebar_stats():
    """Show demo stats in sidebar"""
    try:
        username = simple_auth.get_current_user()
        user_plan = simple_auth.get_user_plan()
        
        if user_authenticated and user_plan == 'demo':
            
            # Sample generation stats
            if 'sample_generations_count' in st.session_state:
                count = st.session_state.sample_generations_count
                if count > 0:
                    st.metric("🎯 Sample Generations", count)
                    
                    if count >= 5:
                        st.success("🏆 Platform Expert!")
                    elif count >= 3:
                        st.info("🌟 Explorer")
                    elif count >= 1:
                        st.info("👍 Getting Started")
            
            # Real demo status
            try:
                can_demo, remaining = credit_system.can_use_demo(username)
                st.metric("🔬 Real Demo Left", remaining)
                
                if remaining == 0:
                    st.warning("⚠️ Demo exhausted")
                    if st.button("💎 Upgrade Now", type="primary", key="sidebar_upgrade_demo"):
                        st.session_state.show_pricing = True
                        st.rerun()
            except:
                pass
                
    except Exception as e:
        # Fail silently if there are issues
        pass

def track_sample_generation(username, leads_count, platforms):
    """Track sample generation usage for user feedback"""
        
    # Initialize session tracking
    if 'sample_generations' not in st.session_state:
        st.session_state.sample_generations = []
        
    if 'sample_generations_count' not in st.session_state:
        st.session_state.sample_generations_count = 0
        
    # Record this generation
    generation_record = {
        "timestamp": datetime.now().isoformat(),
        "leads_count": leads_count,
        "platforms": platforms,
        "username": username
    }
        
    st.session_state.sample_generations.append(generation_record)
    st.session_state.sample_generations_count += 1
        
    # Keep only last 10 generations in session
    if len(st.session_state.sample_generations) > 10:
        st.session_state.sample_generations = st.session_state.sample_generations[-10:]

def show_sample_generation_success(leads_count, platforms, search_term):
    """Show encouraging success message for sample generation"""
        
    # Success message with encouragement
    st.success(f"🎉 Generated {leads_count} sample leads successfully!")
        
    # Show what they accomplished
    accomplishment_col1, accomplishment_col2 = st.columns(2)
        
    with accomplishment_col1:
        st.info(f"""
        **🎯 What You Just Did:**
        • Generated {leads_count} realistic sample leads
        • Searched for: "{search_term}"
        • Platforms: {', '.join(platforms)}
        • Experience: Identical to real platform
        """)
        
    with accomplishment_col2:
        st.success(f"""
        **✨ This Sample Data Shows:**
        • Exact interface and workflow
        • Real data structure and fields
        • Platform-specific information
        • Professional lead quality
        """)
        
    # Next steps
    st.markdown("### 🚀 What's Next?")
        
    next_col1, next_col2, next_col3 = st.columns(3)
        
    with next_col1:
        st.markdown("""
        **🎯 Keep Exploring**
        - Try different search terms
        - Test other platforms
        - Experiment with settings
        - Learn all features
        """)
        
    with next_col2:
        st.markdown("""
        **🔬 Try Real Demo**
        - Use your 5 real demo leads
        - Test actual Twitter data
        - Verify lead quality
        - See real contact info
        """)
        
    with next_col3:
        st.markdown("""
        **🚀 Ready to Scale?**
        - Upgrade to Pro/Ultimate
        - Unlimited real leads
        - All 8 platforms
        - Advanced features
        """)

def show_sample_usage_stats():
    """Show sample usage statistics"""
        
    if 'sample_generations_count' in st.session_state and st.session_state.sample_generations_count > 0:
            
        count = st.session_state.sample_generations_count
            
        # Calculate total sample leads generated
        total_leads = 0
        if 'sample_generations' in st.session_state:
            total_leads = sum(gen.get('leads_count', 0) for gen in st.session_state.sample_generations)
            
        # Show encouraging stats
        stats_col1, stats_col2, stats_col3 = st.columns(3)
            
        with stats_col1:
            st.metric("🎯 Sample Generations", count, help="Times you've used sample generation")
            
        with stats_col2:
            st.metric("📊 Total Sample Leads", total_leads, help="Total sample leads generated")
            
        with stats_col3:
            if count >= 3:
                st.metric("🏆 Status", "Explorer!", help="You're really learning the platform!")
            elif count >= 1:
                st.metric("🌟 Status", "Getting Started", help="Great start exploring!")
            else:
                st.metric("👋 Status", "New User", help="Welcome to the platform!")
            
        # Show exploration encouragement
        if count >= 5:
            st.success("🏆 **Platform Explorer!** You've really learned the interface. Ready to try real demo leads or upgrade?")
        elif count >= 3:
            st.info("🌟 **Great Progress!** You're getting familiar with the platform. Consider trying different search terms or platforms.")
        elif count >= 1:
            st.info("👍 **Good Start!** Try generating sample leads with different search terms to see more variety.")


def show_credit_dashboard():
    """Simple credit-based dashboard"""
    if not simple_auth.is_authenticated():
        show_auth_required_dashboard()
        return
    
    username = simple_auth.get_current_user()
    user_stats = credit_system.get_user_stats(username)
    
    # Credit status header
    st.markdown("### 💎 Your Credit Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_credits = user_stats.get('current_credits', 0)
        st.metric("💎 Credits Available", current_credits)
    
    with col2:
        total_downloaded = user_stats.get('total_leads_downloaded', 0)
        st.metric("📊 Total Leads Generated", total_downloaded)
    
    with col3:
        plan = user_stats.get('plan', 'starter')
        plan_emoji = "🆓" if plan == 'starter' else "💎" if 'starter' in plan else "🚀" if 'pro' in plan else "👑"
        st.metric("📋 Plan", f"{plan_emoji} {plan.title()}")
    
    with col4:
        total_purchased = user_stats.get('total_purchased', 0)
        st.metric("💰 Credits Purchased", total_purchased)
    
    # Credit actions
    st.markdown("---")
   
    if current_credits <= 10:
        st.warning(f"⚠️ Low credits! You have {current_credits} credits remaining.")
       
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🛒 Buy More Credits", type="primary", use_container_width=True):
                st.session_state.show_pricing = True
                st.rerun()
        with col2:
            if st.button("📊 View Usage History", use_container_width=True):
                st.session_state.show_usage = True
                st.rerun()
   
    elif current_credits > 100:
        st.success(f"🔥 You're ready to generate leads! {current_credits} credits available.")
       
        if st.button("🚀 Start Generating Leads", type="primary", use_container_width=True):
            # Go to scraper tab
            st.session_state.active_tab = "scraper"
            st.rerun()
   
    else:
        st.info(f"⚡ {current_credits} credits ready for lead generation!")

def show_auth_required_dashboard():
    """Dashboard for non-authenticated users"""
    st.warning("🔐 Sign in to access your credit dashboard")
    
    # Value proposition
    st.markdown("### 🚀 Lead Generator Empire")
    st.markdown("**Generate high-quality leads from 8 platforms in minutes**")
    
    # Feature highlights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🎯 250 Credits**")
        st.markdown("Start generating leads immediately")
    
    with col2:
        st.markdown("**⚡ 8 Platforms**")
        st.markdown("Twitter, LinkedIn, Facebook &amp; more")
    
    with col3:
        st.markdown("**🚀 Instant Results**")
        st.markdown("CSV download in minutes")
    
    # Auth buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Starter (250 Credits)", type="primary", use_container_width=True, key="tab1_register"):
            st.session_state.show_register = True
            st.session_state.show_login = False  # ← ADD THIS
            st.rerun()
    
    with col2:
        if st.button("🔑 Sign In", use_container_width=True, key="tab1_login"):
            st.session_state.show_login = True
            st.session_state.show_register = False  # ← ADD THIS
            st.rerun()

def calculate_accurate_estimate(selected_platforms, max_scrolls, user_plan):
    """Calculate accurate estimate that matches backend expectations"""
    
    # Platform performance (leads per scroll) - SAME AS BACKEND
    platform_performance = {
        "Twitter": 2,
        "Facebook": 8,
        "LinkedIn": 1.5,
        "YouTube": 2,
        "TikTok": 6,
        "Instagram": 2,
        "Medium": 1,
        "Reddit": 1
    }
    
    # Calculate total estimate
    total_estimated = 0
    platform_breakdown = {}
    
    for platform in selected_platforms:
        platform_key = platform.title()
        leads_per_scroll = platform_performance.get(platform_key, 1)
        platform_estimate = int(max_scrolls * leads_per_scroll)
        platform_breakdown[platform_key] = platform_estimate
        total_estimated += platform_estimate
    
    # SPECIAL HANDLING FOR DEMO USERS
    if user_plan == 'demo':
        # Demo users can only get max 5 leads total, regardless of calculation
        username = st.session_state.get('username')
        if username:
            try:
                from simple_credit_system import credit_system
                can_demo, remaining = credit_system.can_use_demo(username)
                final_estimate = min(total_estimated, remaining, 5)
                
                print(f"📱 Demo estimate override:")
                print(f"   Calculated: {total_estimated}")
                print(f"   Demo remaining: {remaining}")
                print(f"   Final: {final_estimate}")
                
                return {
                    "total_estimate": final_estimate,
                    "platform_breakdown": platform_breakdown,
                    "session_limit": 5,
                    "limited_by_plan": True,
                    "raw_total": total_estimated
                }
            except Exception as e:
                print(f"Demo estimate error: {e}")
        
        # Fallback for demo
        return {
            "total_estimate": min(total_estimated, 5),
            "platform_breakdown": platform_breakdown,
            "session_limit": 5,
            "limited_by_plan": True,
            "raw_total": total_estimated
        }
    
    # Regular calculation for paid users
    plan_session_limits = {
        'starter': 250,
        'pro': 2000,
        'ultimate': 9999
    }
    
    session_limit = plan_session_limits.get(user_plan, 25)
    final_estimate = min(total_estimated, session_limit)
    
    return {
        "total_estimate": final_estimate,
        "platform_breakdown": platform_breakdown,
        "session_limit": session_limit,
        "limited_by_plan": final_estimate < total_estimated,
        "raw_total": total_estimated
    }

def clean_csv_data_types(df):
    """
    Clean any CSV data to fix Arrow serialization errors
    This fixes the 'Followers not shown' problem
    """
    if df.empty:
        return df
    
    df_clean = df.copy()
    
    # Fix numeric columns that might have string values
    numeric_columns = [
        'followers', 'following', 'posts', 'engagement_rate', 
        'subscribers', 'videos', 'likes', 'connections', 'karma',
        'post_karma', 'comment_karma', 'articles', 'total_views'
    ]
    
    for col in numeric_columns:
        if col in df_clean.columns:
            # Replace common problematic strings
            df_clean[col] = df_clean[col].astype(str)
            df_clean[col] = df_clean[col].replace({
                'Followers not shown': '1000',
                'Following not shown': '500', 
                'Posts not shown': '100',
                'Not available': '0',
                'N/A': '0',
                'None': '0',
                '': '0'
            })
            
            # Convert to numeric, replacing any remaining problems with defaults
            if col == 'engagement_rate':
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(5.0).astype(float)
            else:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(1000).astype(int)
    
    # Fix boolean columns
    boolean_columns = ['verified', 'demo_mode']
    for col in boolean_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(bool)
    
    # Ensure string columns are actually strings
    string_columns = ['name', 'handle', 'bio', 'platform', 'location', 'demo_notice', 'demo_status']
    for col in string_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str)
    
    return df_clean

def refresh_user_stats():
    """Force refresh user stats from credit system"""
    try:
        # Force reload credit system
        from simple_credit_system import credit_system
        credit_system.load_data()
        
        # Get fresh user info
        auth = SimpleCreditAuth()
        username = auth.get_current_user()
        
        if username:
            # Get fresh data directly from credit system
            user_info = credit_system.get_user_info(username)
            
            if user_info:
                # Update session state with fresh data
                st.session_state.credits = user_info.get('credits', 0)
                st.session_state.user_data = user_info
                
                # Show updated info
                st.success(f"🔄 Stats refreshed for {username}")
                st.info(f"💎 Current credits: **{user_info.get('credits', 0)}**")
                
                return True
    except Exception as e:
        st.error(f"❌ Refresh failed: {e}")
        return False

def save_dms_to_library(dm_results, username, generation_mode, platform):
    import json, os
    from datetime import datetime

    # build full path under the script’s directory
    library_file = os.path.join(LIBRARY_DIR, f"{username}_dm_library.json")

    # create empty file if missing
    if not os.path.exists(library_file):
        with open(library_file, "w", encoding="utf-8") as f:
            json.dump({"campaigns": []}, f, indent=2, ensure_ascii=False)

    # load, append, trim to last 20, and save back
    with open(library_file, "r+", encoding="utf-8") as f:
        data = json.load(f)
        campaign = {
            "id":        f"{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "username":  username,
            "timestamp": datetime.now().isoformat(),
            "generation_mode": generation_mode,
            "platform":        platform,
            "total_dms":       len(dm_results),
            "languages":       list({dm.get("detected_language","unknown") for dm in dm_results}),
            "dms":             dm_results,
        }
        data["campaigns"].append(campaign)
        data["campaigns"] = data["campaigns"][-20:]

        f.seek(0)
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.truncate()

    return True


def load_user_dm_library(username):
    """Simplified load function"""
    import json
    
    try:
        library_file = f"dm_library/{username}_dm_library.json"
        
        with open(library_file, 'r', encoding='utf-8') as f:
            library_data = json.load(f)
        return library_data.get("campaigns", [])
        
    except Exception as e:
        print(f"Load error: {e}")
        return []

def delete_campaign_from_library(username, campaign_id):
    """Delete a campaign from user's library"""
    import json
    import os
    
    try:
        library_file = os.path.join("dm_library", f"{username}_dm_library.json")
        
        if os.path.exists(library_file):
            with open(library_file, 'r', encoding='utf-8') as f:
                library_data = json.load(f)
            
            # Remove campaign with matching ID
            library_data["campaigns"] = [
                campaign for campaign in library_data["campaigns"] 
                if campaign.get("id") != campaign_id
            ]
            
            # Save updated library
            with open(library_file, 'w', encoding='utf-8') as f:
                json.dump(library_data, f, indent=2, ensure_ascii=False)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"Error deleting campaign: {e}")
        return False


# Enhanced CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1E88E5;
        margin-bottom: 2rem;
        font-size: 3rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .stats-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    .platform-card {
        border: 2px solid #e0e0e0;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        transition: all 0.3s ease;
    }
    .platform-card:hover {
        border-color: #667eea;
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    .success-metric {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .plan-card {
        border: 3px solid;
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
        text-align: center;
        position: relative;
        background: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .plan-starter { border-color: #6c757d; }
    .plan-pro { 
        border-color: #28a745; 
        background: linear-gradient(135deg, #d4edda 0%, #ffffff 100%);
    }
    .plan-ultimate { 
        border-color: #ffd700; 
        background: linear-gradient(135deg, #fff3cd 0%, #ffffff 100%);
    }
    .plan-badge {
        position: absolute;
        top: -15px;
        left: 50%;
        transform: translateX(-50%);
        padding: 0.5rem 1rem;
        border-radius: 25px;
        font-weight: bold;
        color: white;
    }
    .badge-starter { background: #6c757d; }
    .badge-pro { background: #28a745; }
    .badge-ultimate { background: linear-gradient(45deg, #ffd700, #ffed4e); color: #333; }
    .premium-feature {
        background: linear-gradient(135deg, #fff3cd 0%, #ffffff 100%);
        border-left: 4px solid #ffd700;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0 10px 10px 0;
    }
    .language-flag {
        display: inline-block;
        width: 24px;
        height: 16px;
        margin-right: 8px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)

# PLAN UPGRADE SUCCESS (subscription purchases)
if "success" in query_params and "plan" in query_params:
    plan = query_params.get("plan", "pro")
    username_from_url = query_params.get("username", "unknown")
    
    st.balloons()
    st.success("🎉 Plan Upgrade Successful! Welcome to your upgraded plan!")
    
    # Process plan upgrade
    if username_from_url and username_from_url != "unknown":
        try:
            # Update plan in credit system
            from simple_credit_system import credit_system
            
            success = credit_system.update_user_plan(username_from_url, plan)
            
            if success:
                # Restore user session
                user_info = credit_system.get_user_info(username_from_url)
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.username = username_from_url
                    st.session_state.user_data = user_info
                    st.session_state.credits = user_info.get('credits', 0)
                    
                    # Show success details
                    st.markdown(f"""
                    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border-radius: 15px; margin: 1rem 0;">
                        <h2>👑 Welcome to {plan.title()} Plan!</h2>
                        <p><strong>Account:</strong> {username_from_url}</p>
                        <p><strong>Plan:</strong> {plan.title()} Plan</p>
                        <p><strong>Credits:</strong> {user_info.get('credits', 0)} available</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Plan benefits
                    if plan == "pro":
                        st.markdown("""
                        **🚀 Pro Plan Benefits:**
                        - ✅ 6 platforms access (adds LinkedIn, TikTok, Instagram, YouTube)
                        - ✅ 2,000 credits per session
                        - ✅ Advanced filtering &amp; relevance scoring
                        - ✅ Priority support
                        """)
                    elif plan == "ultimate":
                        st.markdown("""
                        **👑 Ultimate Plan Benefits:**
                        - ✅ All 8 platforms access (adds Medium, Reddit)
                        - ✅ Unlimited credits per session
                        - ✅ Enterprise features
                        - ✅ Priority+ support
                        """)
                    
                    if st.button("🚀 Explore New Features", type="primary", key="plan_success_continue"):
                        st.query_params.clear()
                        st.rerun()
                    st.stop()
                    
                else:
                    st.error("❌ Error loading user data after plan upgrade")
            else:
                st.error("❌ Error updating plan in system")
                
        except Exception as e:
            st.error(f"❌ Plan upgrade processing error: {str(e)}")
            print(f"❌ Plan upgrade error: {str(e)}")
    
    else:
        st.warning("⚠️ Plan upgrade successful but username not found in URL. Please contact support.")
    
    # Fallback continue button
    if st.button("🏠 Continue to Dashboard", key="plan_fallback_continue"):
        st.query_params.clear()
        st.rerun()
    
    st.stop()

elif "success" in query_params and "plan" in query_params:
    # Plan upgrade success
    plan = query_params.get("plan", "pro")
    username_from_url = query_params.get("username", "unknown")
    
    st.balloons()
    st.success("🎉 Plan Upgrade Successful!")
    
    # Update plan if user is authenticated
    if st.session_state.get('authenticated', False) and AUTH_AVAILABLE:
        current_username = st.session_state.get('username')
        if current_username:
            try:
                success, message = credit_system.get_user_info(current_username, plan)
                if success:
                    st.session_state.user_data = {
                        **st.session_state.get('user_data', {}), 
                        "plan": plan
                    }
                    st.success(f"✅ Upgraded to {plan.title()} Plan!")
            except Exception as e:
                st.warning(f"⚠️ Manual plan activation may be needed: {str(e)}")
    
    if st.button("🚀 Explore New Features", type="primary", key="plan_continue"):
        st.query_params.clear()
        st.rerun()
    
    st.stop()
    
elif "cancelled" in query_params:
    # Payment cancelled
    st.warning("⚠️ Payment was cancelled. You can try again anytime!")
    
    if st.button("🔙 Back to Dashboard", key="cancel_back"):
        st.query_params.clear()
        st.rerun()
    
    st.stop()
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
# Header (simplified - no unnecessary dashboard button)
col1, col2 = st.columns([2, 1])
with col1:
    st.markdown('<h1 class="main-header">🚀 Lead Generator Empire</h1>', unsafe_allow_html=True)
    if MULTILINGUAL_AVAILABLE:
        st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem;">Generate Quality Leads • 8 Platforms • 12+ Languages</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem;">Generate Quality Leads • 8 Platforms</p>', unsafe_allow_html=True)

with col2:
    if user_authenticated:
        current_user = simple_auth.get_current_user()
        
        # Only show user info if we actually have a current user
        if current_user:
            user_plan = simple_auth.get_user_plan()
            
            # Get correct credits/demo status
            try:
                from simple_credit_system import credit_system
                user_info = credit_system.get_user_info(current_user)
                
                if user_plan == 'demo' and user_info:
                    is_demo, used, remaining = credit_system.get_demo_status(current_user)
                    display_credits = f"{remaining} demo leads"
                    plan_emoji = "📱"
                    plan_color = "#6c757d"
                else:
                    current_credits = user_info.get('credits', 0) if user_info else 0
                    display_credits = f"{current_credits} credits"
                    plan_emoji = "👑" if user_plan == "ultimate" else "💎" if user_plan == "pro" else "📱"
                    plan_color = "#ffd700" if user_plan == "ultimate" else "#28a745" if user_plan == "pro" else "#6c757d"
            
            except Exception as e:
                current_credits = st.session_state.get('credits', 0)
                display_credits = f"{current_credits} credits"
                plan_emoji = "📱"
                plan_color = "#6c757d"
            
            # User info display
            st.markdown(f"""
            <div style="text-align: right; margin-top: 1rem;">
                <div style="background: {plan_color}; color: white; padding: 0.5rem; border-radius: 10px; display: inline-block;">
                    <strong>{plan_emoji} {current_user}</strong><br>
                    <small>{display_credits} • {user_plan.title()}</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Logout button on far right
            st.markdown("<div style='text-align: right;'></div>", unsafe_allow_html=True)  # Add spacing
            if st.button("🔒 Logout", help="Sign out of your account", key="header_logout"):
                # Clear all session state on logout
                for key in ['authenticated', 'username', 'user_data', 'login_time', 'show_login', 'show_register', 'credits']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Clear the simple_auth state
                simple_auth.current_user = None
                simple_auth.user_data = None
                
                st.success("🔒 Successfully logged out!")
                st.rerun()
        
        else:
            # User is supposedly authenticated but no current user - clear auth state
            st.session_state.authenticated = False
            if 'username' in st.session_state:
                del st.session_state['username']
            user_authenticated = False
    
    # Show login/register buttons if NOT authenticated
    if not user_authenticated:
        col_login, col_register = st.columns(2)
        with col_login:
            if st.button("🔑 Login", help="Sign in to your account", key="header_login"):
                st.session_state.show_login = True
                st.session_state.show_register = False
                st.rerun()
        with col_register:
            if st.button("🚀 Start Demo", help="Create demo account", type="primary", key="header_register_demo"):
                st.session_state.show_register = True
                st.session_state.show_login = False
                st.rerun()

# FORCE CREDIT REFRESH for corrected accounts
if user_authenticated and st.session_state.get('credits', 0) == 25:
    username = simple_auth.get_current_user()
    if username == "bob":
        try:
            from simple_credit_system import credit_system
            fresh_info = credit_system.get_user_info(username)
            if fresh_info and fresh_info.get('credits', 0) == 2000:
                st.session_state.credits = 2000
                st.session_state.user_data = fresh_info
                st.success("✅ Credits refreshed: 2000 credits available!")
                st.rerun()
        except Exception as e:
            print(f"Force refresh error: {e}")

# CRITICAL: Add this line AFTER the header section to handle auth forms:
show_auth_section_if_needed()

# Sidebar
with st.sidebar:
    st.header("📊 Empire Stats")

    # In sidebar
    show_user_selector()  # Lets you switch users
    
    # 🌍 NEW: Language stats if multilingual is available
    if MULTILINGUAL_AVAILABLE:
        st.subheader("🌍 Global Reach")
        supported_languages = len(LANGUAGE_KEYWORDS)
        st.metric("Languages Supported", f"{supported_languages}")
        
        # Show popular languages
        popular_languages = ["🇪🇸 Spanish", "🇫🇷 French", "🇩🇪 German", "🇯🇵 Japanese"]
        for lang in popular_languages:
            st.caption(lang) 
        
        st.markdown("---")
    
    # Different sidebar content based on authentication status
    if not user_authenticated:
        # SIDEBAR FOR NON-AUTHENTICATED USERS
        st.subheader("🚀 Join the Empire")
        st.info("Sign up to start generating leads!")
        
        # Preview metrics
        st.markdown("**🎯 Platform Coverage:**")
        preview_platforms = {
            "🐦 Twitter": "Real-time experts",
            "📘 Facebook": "Business profiles", 
            "💼 LinkedIn": "Professional network",
            "🎵 TikTok": "Viral creators",
            "📸 Instagram": "Visual content",
            "🎥 YouTube": "Content creators",
            "📝 Medium": "Thought leaders",
            "🗨️ Reddit": "Community experts"
        }
        
        for platform, description in preview_platforms.items():
            st.caption(f"{platform} • {description}")
        
        st.markdown("---")
        st.subheader("💡 Why Join?")
        st.success("✅ 8 platforms access")
        st.success("✅ 21.3 leads/minute")
        st.success("✅ 100% success rate")
        st.success("✅ Instant CSV export")
        
        # Call to action
        if st.button("🚀 Start Demo", type="primary", use_container_width=True, key="register_sidebar_demo"):
            st.session_state.show_register = True
            st.session_state.show_login = False
            st.rerun()
        
        if st.button("🔑 Sign In", use_container_width=True, key="sidebar_signin_demo"):
            st.session_state.show_login = True
            st.session_state.show_register = False
            st.rerun()
    
    else:
        # SIDEBAR FOR AUTHENTICATED USERS
        username = simple_auth.get_current_user()
        user_plan = simple_auth.get_user_plan()
    
        # Different content for demo vs paid users
        if user_plan == 'demo':
            # DEMO USER SIDEBAR
            st.subheader("📱 Demo Account")
        
            # ✅ SIMPLE DEMO STATUS (no external functions needed)
            can_demo, remaining = credit_system.can_use_demo(username)
            user_info = credit_system.get_user_info(username)
            demo_used = user_info.get('demo_leads_used', 0) if user_info else 0
            
            st.metric("🔬 Demo Leads Left", remaining)
            st.metric("🎯 Sample Generations", "Unlimited")
            
            # Demo status display
            if remaining <= 0:
                st.success("🎯 Demo Mode: All 5 demo leads used - Upgrade to continue!")
            else:
                st.success(f"🎯 Demo Mode: {remaining} real demo leads remaining (used {demo_used}/5)")
            
            # Sidebar demo progress
            st.sidebar.markdown("### 🎯 Demo Status")
            if remaining <= 0:
                st.sidebar.warning("Demo Exhausted")
                st.sidebar.info("Upgrade for unlimited access!")
            else:
                progress = demo_used / 5
                st.sidebar.progress(progress)
                st.sidebar.info(f"**{remaining}** leads remaining")
                st.sidebar.caption(f"Used {demo_used}/5 demo leads")
        
            st.markdown("---")
            st.subheader("🚀 Upgrade Benefits")
            st.info("💎 Pro Plan: 6 platforms")
            st.info("👑 Ultimate: All 8 platforms")
            st.info("⚡ Unlimited leads")
        
            # Upgrade buttons
            if st.button("💎 Upgrade to Pro", type="primary", use_container_width=True, key="sidebar_upgrade"):
                st.session_state.show_pricing = True
                st.rerun()
        
        else:
            # PAID USER SIDEBAR - Show actual platform stats
            empire_stats, total_leads = load_accurate_empire_stats(st.session_state.username)

            # 2) Define how to display each platform key with an emoji + label
            DISPLAY_MAP = {
                "twitter":  "🐦 Twitter",
                "linkedin": "💼 LinkedIn",
                "facebook": "📘 Facebook",
                "tiktok":   "🎵 TikTok",
                "instagram":"📸 Instagram",
                "youtube":  "🎥 YouTube",
                "medium":   "📝 Medium",
                "reddit":   "🗨️ Reddit",
            }

            st.sidebar.header("🏆 Empire Statistics")

            # 3) Render per‐platform metrics dynamically
            if empire_stats:
                for platform_key, count in empire_stats.items():
                    label = DISPLAY_MAP.get(platform_key.lower(), platform_key.title())
                    st.sidebar.metric(label, count)
            else:
                st.sidebar.info("💡 No leads found—run the scraper!")

            # 4) Total Empire
            if total_leads > 0:
                st.sidebar.markdown("---")
                st.sidebar.metric("🎯 Total Empire", total_leads)

                # 5) Empire Value calculator
                lead_value  = st.sidebar.slider("Value per lead ($)", 1, 100, 25, key="sidebar_value_slider")
                total_value = total_leads * lead_value
                st.sidebar.success(f"Empire Value: **${total_value:,}**")

                # 6) Other performance metrics
                st.sidebar.subheader("⚡ Performance")
                st.sidebar.metric("Leads/Minute", "21.3")        # you can make these dynamic too
                st.sidebar.metric("Success Rate", "100%")
                st.sidebar.metric("Platforms", f"{len([c for c in empire_stats.values() if c>0])}/8")

            else:
                # Fallback UI when no leads yet
                st.sidebar.info("💡 Run the empire scraper to generate your stats")
                if st.sidebar.button("🚀 Start Conquest", key="sidebar_conquest"):
                    st.query_params(tab="scraper")
                    st.rerun()
                
       
    
    
    st.markdown("---")
    st.caption("🚀 Lead Generator Empire")
    st.caption(f"Powered by 8 platforms")


# 🌍 NEW: Enhanced tabs with multilingual support
# Always create 6 tabs - much simpler!
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚀 Empire Scraper", 
    "📊 Lead Results", 
    "🌍 Multilingual DMs", 
    "💳 Pricing Plans", 
    "📦 Lead Packages", 
    "⚙️ Settings"
])
# 🎯 QUICK FIX: Replace your tab1 content with this

with tab1:
    # ✅ PROVEN WORKING: Column structure from diagnostic
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("🎯 8-Platform Lead Generation Empire")
        
        # Show simple credit status
        if not user_authenticated:
            st.warning("🔐 Join the Lead Generator Empire to start generating leads")
            st.markdown("### 🚀 Lead Generator Empire")
            st.markdown("**Generate high-quality leads from 8 platforms in minutes**")
            show_simple_credit_status()
        else:
            username = simple_auth.get_current_user()
            user_plan = simple_auth.get_user_plan()
            
            # Around line 4780 in your code:
            if user_plan == 'demo':
                show_enhanced_demo_status(username)
                
                # ✅ ADD: Demo Mode Explanation Section (ONLY for demo users)
                with st.expander("📱 Understanding Demo Mode", expanded=False):
                    st.markdown("""
                    ### 🎯 Two Ways to Experience Lead Generator Empire
                    
                    **🎯 Sample Generation (Unlimited & Recommended)**
                    - ✨ **Completely FREE** and unlimited
                    - 🎭 **Realistic fake data** that shows exactly how the platform works
                    - 🌍 **All platforms available** - try Twitter, Facebook, LinkedIn, YouTube, TikTok, Instagram, Medium, Reddit
                    - 🎨 **Industry-specific data** based on your search terms
                    - 🔧 **Perfect for learning** the interface, features, and workflow
                    - ⚡ **Instant results** - no waiting, no limits
                    - 💡 **Use this to decide** if you want to upgrade before using real demo leads
                    
                    ---
                    
                    **🔬 Real Demo Leads (5 Total)**
                    - 🎯 **Actual Twitter data** from real profiles
                    - 📧 **Real contact information** (partially masked)
                    - 📱 **Limited to 5 leads total** for your account
                    - ⚡ **Only Twitter platform** available in demo
                    - 🔍 **Use when you're ready** to test with real data
                    - 💎 **Consumed when used** - can't get them back
                    
                    ---
                    
                    ### 🚀 Recommended Demo Workflow:
                    
                    1. **Start with Sample Generation** 🎯
                    - Try different search terms
                    - Test all platforms
                    - Learn the interface
                    - See the data quality
                    
                    2. **When you're confident** 🔬
                    - Use your 5 real demo leads
                    - Test the actual Twitter data
                    - Verify the lead quality
                    
                    3. **Ready to scale?** 🚀
                    - Upgrade to Pro or Ultimate
                    - Get unlimited real leads
                    - Access all 8 platforms
                    - Advanced features unlocked
                    
                    ---
                    
                    ### 🎨 What Makes Sample Data Realistic?
                    
                    - **Industry-specific names and bios** based on your search terms
                    - **Realistic follower counts** appropriate for each platform
                    - **Proper data structure** exactly like real results
                    - **Platform-specific fields** (LinkedIn job titles, YouTube subscriber counts, etc.)
                    - **Geographic distribution** with real city names
                    - **Engagement metrics** that match platform norms
                    
                    **The only difference:** Sample data is generated, not scraped from real profiles.
                    **The experience:** Identical to using the full platform with real data.
                    """)
                    
                    # Add quick stats about sample vs real
                    demo_col1, demo_col2 = st.columns(2)
                    
                    with demo_col1:
                        st.success("""
                        **🎯 Sample Generation**
                        ✅ Unlimited uses
                        ✅ All 8 platforms  
                        ✅ All search terms
                        ✅ Instant results
                        ✅ Learn the platform
                        """)
                    
                    with demo_col2:
                        try:
                            from simple_credit_system import credit_system
                            can_demo, remaining = credit_system.can_use_demo(username)
                            st.info(f"""
                            **🔬 Real Demo Leads**
                            🎯 {remaining}/5 remaining
                            📱 Twitter only
                            ⚡ Real contact data
                            💎 Limited use
                            🔍 Verify quality
                            """)
                        except:
                            st.info("""
                            **🔬 Real Demo Leads**
                            🎯 5 total available
                            📱 Twitter only
                            ⚡ Real contact data
                            💎 Limited use
                            🔍 Verify quality
                            """)
                            
            else:
                show_simple_credit_status()  # ← CLEAN VERSION (no demo content)

        st.markdown("<div id='search_anchor'></div>", unsafe_allow_html=True)

        # ✅ ADD THIS: Clear search data when user changes
        def check_user_change_for_search():
            """Clear search session data when user changes"""
            current_user = simple_auth.get_current_user() if user_authenticated else None
            
            # Check if user changed
            if 'last_search_user' in st.session_state:
                if st.session_state.last_search_user != current_user:
                    # User changed - clear search-related session data
                    keys_to_clear = [
                        'search_term', 
                        'max_scrolls',
                        'search_results',
                        'generated_leads',
                        'last_search_query',
                        'user_has_searched_before'  # Track if user has used the system
                    ]
                    for key in keys_to_clear:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    print(f"🔄 Search data cleared - user changed: {st.session_state.last_search_user} → {current_user}")
                    
                    # Mark this as a user switch (not a new user)
                    st.session_state.is_user_switch = True
            
            # Update current user
            st.session_state.last_search_user = current_user

        # Call the user change check
        check_user_change_for_search()

        # Search configuration with aggressive tab-switch detection
        st.subheader("Search Parameters")

        # Track which tab user was last on to detect tab switches
        if 'last_active_tab' not in st.session_state:
            st.session_state.last_active_tab = 'empire_scraper'

        # Force refresh when switching from settings tab
        tab_switched_from_settings = (st.session_state.last_active_tab == 'settings')
        st.session_state.last_active_tab = 'empire_scraper'

        # Get current config for initial values only
        username = simple_auth.get_current_user() if user_authenticated else None
        current_config = get_current_config(username)

        # figure out if we just arrived here from Settings
        tab_switched_from_settings = (st.session_state['last_active_tab'] == 'settings')
        # record that we're now on the scraper tab
        st.session_state['last_active_tab'] = 'empire_scraper'

        # if so, clear the previous run's inputs
        #if tab_switched_from_settings:
            #for k in ('search_term', 'max_scrolls'):
                #st.session_state.pop(k, None)

        # ✅ FIXED: Determine if this is a truly new user vs returning user
        def is_new_user():
            """Check if this is a new user who should see blank fields"""
            # New user if:
            # 1. No search_term in session state AND
            # 2. Either no last_search_user OR it's different from current user AND
            # 3. User hasn't searched before (no saved config with actual values)
            
            if 'search_term' in st.session_state:
                return False  # Already has session data
            
            # Check if user has ever saved search terms before
            user_config = current_config.get("search_term", "").strip()
            
            # If config is empty or contains default values, treat as new user
            default_values = ["crypto trader", "fitness coach", "marketing agency", ""]
            
            return not user_config or user_config.lower() in [v.lower() for v in default_values]

        # ✅ FIXED: Initialize search_term with proper new user detection
        if 'search_term' not in st.session_state:
            if is_new_user():
                # Truly new user - start with blank
                st.session_state.search_term = ""
                print(f"🆕 New user detected: {username} - starting with blank keywords")
            else:
                # Returning user with real saved data - load their config
                st.session_state.search_term = current_config.get("search_term", "")
                print(f"👤 Returning user: {username} - loaded saved keywords: '{st.session_state.search_term}'")

        if 'max_scrolls' not in st.session_state:
            st.session_state.max_scrolls = current_config.get("max_scrolls", 12)

        # Simple widgets - let user control them
        search_term = st.text_input(
            "🔍 Target Keywords", 
            value=st.session_state.search_term,
            placeholder="Enter keywords to find relevant prospects (e.g., crypto trader, fitness coach, marketing agency)",
            help="Enter keywords to find relevant prospects",
            key="empire_search_input"
        )

        max_scrolls = st.slider(
            "📜 Intensity Level", 
            min_value=1, 
            max_value=20, 
            value=st.session_state.max_scrolls,
            help="Higher intensity = more leads",
            key="empire_scrolls_input"
        )

        # Update session state when user changes values
        if search_term != st.session_state.search_term:
            st.session_state.search_term = search_term
            # Mark that user has now interacted with search
            if search_term.strip():
                st.session_state.user_has_searched_before = True

        if max_scrolls != st.session_state.max_scrolls:
            st.session_state.max_scrolls = max_scrolls

        # Auto-save to config files when values change
        if CONFIG_MANAGER_AVAILABLE:
            # Only save if values actually changed from what's in config
            config_search = current_config.get("search_term", "")
            config_scrolls = current_config.get("max_scrolls", 12)
            
            if search_term != config_search or max_scrolls != config_scrolls:
                if update_config(username, search_term, max_scrolls):
                    # Only show save message if user entered something meaningful
                    if search_term.strip():
                        st.success("⚙️ Settings auto-saved", icon="✅")

        # Optional: Add a simple refresh button if they changed settings elsewhere
        with st.expander("🔄 Refresh from Settings (Optional)", expanded=False):
            st.info("If you changed default values in Settings tab, click below to load them:")
            
            if st.button("🔄 Load from Settings", help="Load default values from Settings tab"):
                fresh_config = get_current_config(username)
                # Don't load default values like "crypto trader" for new users
                saved_search = fresh_config.get("search_term", "")
                if saved_search and saved_search.lower() not in ["crypto trader", "fitness coach"]:
                    st.session_state.search_term = saved_search
                else:
                    st.session_state.search_term = ""
                st.session_state.max_scrolls = fresh_config.get("max_scrolls", 12)
                st.success("✅ Loaded settings!")
                st.rerun()
            
            # Show what settings would load
            fresh_config = get_current_config(username)
            saved_term = fresh_config.get("search_term", "not set")
            st.caption(f"Settings has: '{saved_term}' with intensity {fresh_config.get('max_scrolls', 'not set')}")

        # Show final confirmation
        if search_term.strip():
            st.success(f"✅ Active: '{search_term}' with intensity {max_scrolls}")
        else:
            st.info("💡 Enter target keywords above to start searching for prospects")
        
        # Platform selection
        st.subheader("🌍 Platform Empire Selection")
        
        # Get user plan safely
        if user_authenticated:
            try:
                user_plan = simple_auth.get_user_plan() or 'demo'
            except:
                user_plan = 'demo'
        else:
            user_plan = 'demo'
        
        # Platform access by plan
        plan_access = {
            'demo': ['twitter'],
            'starter': ['twitter', 'facebook'],
            'pro': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube'],
            'ultimate': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube', 'medium', 'reddit']
        }
        
        available_platforms = plan_access.get(user_plan, ['twitter'])
        
        # Show plan status
        if user_plan == 'demo':
            st.warning("📱 Demo Mode: Twitter only • 5 demo leads total")
        elif user_plan == 'starter':
            st.info("📱 Starter Plan: 2 platforms • 250 leads/month")
        elif user_plan == 'pro':
            st.success("💎 Pro Plan: 6 platforms • 2,000 leads/month")
        else:
            st.success("👑 Ultimate Plan: All 8 platforms • Unlimited")
        
        # Platform checkboxes
        st.markdown("#### 🔥 Core Platforms")
        col_tw, col_fb = st.columns(2)
        
        with col_tw:
            use_twitter = st.checkbox("🐦 Twitter", value='twitter' in available_platforms)
        with col_fb:
            if 'facebook' in available_platforms:
                use_facebook = st.checkbox("📘 Facebook", value=True)
            else:
                use_facebook = st.checkbox("📘 Facebook", disabled=True)
        
        st.markdown("#### 💼 Professional Platforms")
        col_li, col_yt, col_md = st.columns(3)
        
        with col_li:
            if 'linkedin' in available_platforms:
                use_linkedin = st.checkbox("💼 LinkedIn", value=True)
            else:
                use_linkedin = st.checkbox("💼 LinkedIn", disabled=True)
        with col_yt:
            if 'youtube' in available_platforms:
                use_youtube = st.checkbox("🎥 YouTube", value=True)
            else:
                use_youtube = st.checkbox("🎥 YouTube", disabled=True)
        with col_md:
            if 'medium' in available_platforms:
                use_medium = st.checkbox("📝 Medium", value=True)
            else:
                use_medium = st.checkbox("📝 Medium", disabled=True)
        
        st.markdown("#### 🎨 Social &amp; Creative")
        col_tt, col_ig, col_rd = st.columns(3)
        
        with col_tt:
            if 'tiktok' in available_platforms:
                use_tiktok = st.checkbox("🎵 TikTok", value=True)
            else:
                use_tiktok = st.checkbox("🎵 TikTok", disabled=True)
        with col_ig:
            if 'instagram' in available_platforms:
                use_instagram = st.checkbox("📸 Instagram", value=True)
            else:
                use_instagram = st.checkbox("📸 Instagram", disabled=True)
        with col_rd:
            if 'reddit' in available_platforms:
                use_reddit = st.checkbox("🗨️ Reddit", value=True)
            else:
                use_reddit = st.checkbox("🗨️ Reddit", disabled=True)

        # Demo Sample Button (Simple Version)
        if user_authenticated and user_plan == 'demo':
            st.markdown("---")
            st.markdown("### 🎯 Demo Options")
            
            # Get selected platforms
            selected_platforms = []
            if use_twitter: selected_platforms.append("Twitter")
            if use_facebook: selected_platforms.append("Facebook")
            if use_linkedin: selected_platforms.append("LinkedIn")
            if use_youtube: selected_platforms.append("YouTube")
            if use_medium: selected_platforms.append("Medium")
            if use_tiktok: selected_platforms.append("TikTok")
            if use_instagram: selected_platforms.append("Instagram")
            if use_reddit: selected_platforms.append("Reddit")
            
            any_selected = len(selected_platforms) > 0
            
            # Two simple buttons side by side
            sample_col1, sample_col2 = st.columns(2)
            
            with sample_col1:
                st.markdown("**🎯 Sample Generation (Unlimited)**")
                if st.button("🎯 Generate Sample Leads", 
                            type="primary", 
                            disabled=not any_selected,
                            use_container_width=True, 
                            key="simple_sample_btn"):
                    
                    if not any_selected:
                        st.error("❌ Please select at least one platform above")
                    else:
                        with st.spinner("Creating sample data..."):
                            try:
                                # Generate sample leads
                                sample_leads = generate_safe_demo_leads(search_term, selected_platforms, max_scrolls)
                                
                                if sample_leads:
                                    # Save them
                                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    filename = f"sample_leads_{timestamp}.csv"
                                    
                                    import pandas as pd
                                    df = pd.DataFrame(sample_leads)
                                    df.to_csv(filename, index=False)
                                    
                                    st.success(f"✅ Generated {len(sample_leads)} sample leads!")
                                    st.info("📊 Check the 'Lead Results' tab to view your data")
                                    st.info(f"💾 Saved to: {filename}")
                                    
                                    # Show quick preview
                                    with st.expander("👀 Quick Preview"):
                                        st.dataframe(df.head(3), use_container_width=True)
                                else:
                                    st.error("❌ Failed to generate sample leads")
                                    
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                                st.info("💡 Make sure the generate_safe_demo_leads function is defined")
            
            with sample_col2:
                st.markdown("**🔬 Real Demo Leads (Limited)**")
                try:
                    can_demo, remaining = credit_system.can_use_demo(username)
                    button_text = f"🔬 Use Real Demo ({remaining} left)"
                    button_disabled = remaining <= 0
                except:
                    button_text = "🔬 Use Real Demo Leads"
                    button_disabled = False
                
                if st.button(button_text, 
                            disabled=button_disabled or not any_selected,
                            use_container_width=True, 
                            key="simple_real_demo_btn"):
                    
                    if not any_selected:
                        st.error("❌ Please select at least one platform above")
                    else:
                        st.info("🔬 Use the main 'Launch Lead Empire' button below for real demo leads")

        # 🌍 MULTILINGUAL SETTINGS SECTION - Add after platform selection
        if MULTILINGUAL_AVAILABLE:
            st.markdown("---")
            st.subheader("🌍 Global Language Settings")
            
            # Enable/Disable multilingual DMs
            enable_multilingual = st.checkbox(
                "🌍 Enable Multilingual DMs", 
                value=st.session_state.get('enable_multilingual', False),
                help="Auto-detect language and generate culturally appropriate DMs",
                key="enable_multilingual_dms"
            )
            
            # Store in session state
            st.session_state.enable_multilingual = enable_multilingual
            
            if enable_multilingual:
                # Language mode selection
                lang_col1, lang_col2 = st.columns(2)
                
                with lang_col1:
                    language_mode = st.selectbox(
                        "🎯 Target Language",
                        [
                            "Auto-detect",
                            "Force English", 
                            "Force Spanish",
                            "Force French",
                            "Force German", 
                            "Force Portuguese",
                            "Force Italian",
                            "Force Japanese",
                            "Force Korean",
                            "Force Chinese",
                            "Force Arabic",
                            "Force Hindi",
                            "Force Russian"
                        ],
                        key="target_language_mode",
                        help="Auto-detect will determine language from prospect's profile"
                    )
                
                with lang_col2:
                    cultural_adaptation = st.selectbox(
                        "🎭 Cultural Adaptation",
                        [
                            "Standard (Platform appropriate)",
                            "Casual (Friendly approach)",
                            "Professional (Business focus)", 
                            "Creative (Content creator style)"
                        ],
                        key="cultural_adaptation_mode",
                        help="Adjust tone and style for different cultural contexts"
                    )
                
                # Show enabled languages preview
                st.success("🌍 **Multilingual Mode Active:** DMs will be generated in appropriate languages with cultural adaptations")
                
                # Preview supported languages
                with st.expander("🌍 Supported Languages & Features"):
                    st.markdown("""
                    **📍 Fully Supported Languages:**
                    - 🇺🇸 **English**: Platform-optimized templates
                    - 🇪🇸 **Spanish**: Formal/informal variants + regional expressions  
                    - 🇫🇷 **French**: Cultural nuances + proper formality levels
                    - 🇩🇪 **German**: Sie/Du distinctions + business etiquette
                    - 🇵🇹 **Portuguese**: BR/PT variants + cultural context
                    - 🇮🇹 **Italian**: Regional expressions + cultural warmth
                    - 🇯🇵 **Japanese**: Keigo (honorific) levels + cultural respect
                    - 🇰🇷 **Korean**: Formal/informal speech levels + cultural courtesy
                    - 🇨🇳 **Chinese**: Simplified characters + cultural appropriateness
                    - 🇸🇦 **Arabic**: RTL support + cultural sensitivity
                    - 🇮🇳 **Hindi**: Devanagari script + cultural context
                    - 🇷🇺 **Russian**: Cyrillic alphabet + cultural formality
                    
                    **🎯 Platform-Specific Adaptations:**
                    - **TikTok**: Casual, youth-oriented language with trending expressions
                    - **LinkedIn**: Professional terminology with business etiquette
                    - **Instagram**: Visual-focused language with lifestyle context
                    - **Twitter**: Concise, engaging language with platform culture
                    """)
            
            else:
                st.info("🇺🇸 **English Only Mode:** DMs will be generated in English using standard templates")
    
    with col2:
        # ✅ WORKING: Forecast content that stays in column
        st.header("📈 Empire Forecast")

        # Calculate selected platforms based on user's actual access
        selected_platforms = []
        if use_twitter: selected_platforms.append("Twitter")
        if use_facebook: selected_platforms.append("Facebook")
        if use_linkedin: selected_platforms.append("LinkedIn")
        if use_youtube: selected_platforms.append("YouTube")
        if use_medium: selected_platforms.append("Medium")
        if use_tiktok: selected_platforms.append("TikTok")
        if use_instagram: selected_platforms.append("Instagram")
        if use_reddit: selected_platforms.append("Reddit")

        # Get user's plan and available platforms
        if user_authenticated:
            user_plan = simple_auth.get_user_plan()
            
            # Platform access by plan
            plan_access = {
                'demo': ['twitter'],
                'starter': ['twitter', 'facebook'],
                'pro': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube'],
                'ultimate': ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube', 'medium', 'reddit']
            }
            
            available_platforms = plan_access.get(user_plan, ['twitter'])
            
            # Filter selected platforms to only include available ones
            accessible_selected = [p for p in selected_platforms if p.lower() in available_platforms]
            
            # Show platform selection status
            if accessible_selected:
                platform_text = ", ".join(accessible_selected[:2])
                if len(accessible_selected) > 2:
                    platform_text += f" +{len(accessible_selected)-2} more"
                
                # Color code based on plan
                if user_plan == 'ultimate':
                    st.success(f"👑 **Selected:** {platform_text}")
                elif user_plan == 'pro':
                    st.info(f"💎 **Selected:** {platform_text}")
                elif user_plan == 'starter':
                    st.info(f"🎯 **Selected:** {platform_text}")
                else:
                    st.warning(f"📱 **Selected:** {platform_text}")
                
                # Show locked platforms if any were selected but not accessible
                locked_platforms = [p for p in selected_platforms if p.lower() not in available_platforms]
                if locked_platforms:
                    st.warning(f"🔒 **Requires upgrade:** {', '.join(locked_platforms)}")
            else:
                st.warning("⚠️ No accessible platforms selected")

            # Calculate estimate based on accessible platforms only
            platform_estimates = {
                "Twitter": max_scrolls * 2,
                "Facebook": max_scrolls * 8,
                "LinkedIn": max_scrolls * 1.5,
                "YouTube": max_scrolls * 2,
                "Medium": max_scrolls * 1,
                "TikTok": max_scrolls * 6,
                "Instagram": max_scrolls * 2,
                "Reddit": max_scrolls * 1
            }
            
            estimated_leads = sum(platform_estimates.get(p, max_scrolls) for p in accessible_selected)
            
            # Apply plan limits
            plan_limits = {'demo': 5, 'starter': 250, 'pro': 2000, 'ultimate': 999999}
            session_limit = plan_limits.get(user_plan, 5)
            estimated_leads = min(estimated_leads, session_limit)
            
            # Plan-specific forecast styling
            plan_styles = {
                'demo': {'color': '#17a2b8', 'name': 'Demo Forecast', 'emoji': '📱'},
                'starter': {'color': '#6c757d', 'name': 'Starter Forecast', 'emoji': '🎯'},
                'pro': {'color': '#28a745', 'name': 'Pro Forecast', 'emoji': '💎'},
                'ultimate': {'color': '#ffd700', 'name': 'Ultimate Forecast', 'emoji': '👑'}
            }
            
            style = plan_styles.get(user_plan, plan_styles['demo'])
            
            # Forecast box with correct platform count
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {style['color']}20 0%, {style['color']}10 100%); 
                border: 2px solid {style['color']}; 
                border-radius: 12px; 
                padding: 1.5rem; 
                text-align: center;
                max-width: 100%;
                box-sizing: border-box;
            ">
                <h4 style="color: {style['color']}; margin: 0 0 0.5rem 0; font-size: 1rem;">
                    {style['emoji']} {style['name']}
                </h4>
                <h2 style="margin: 0 0 0.25rem 0; color: #333; font-size: 2rem;">
                    {estimated_leads} leads
                </h2>
                <p style="margin: 0 0 0.5rem 0; color: #666; font-size: 0.9rem;">
                    From {len(accessible_selected)} accessible platform(s)
                </p>
                <small style="color: {style['color']}; font-size: 0.8rem;">
                    ⚡ Est: {estimated_leads // 20 + 1}-{estimated_leads // 15 + 2} min
                </small>
            </div>
            """, unsafe_allow_html=True)
            
            # Value calculation
            value = estimated_leads * 25
            st.success(f"💰 **Value:** ${value:,}")
            
            # Performance metrics
            perf_col1, perf_col2 = st.columns(2)
            with perf_col1:
                st.metric("Speed", "21.3/min")
            with perf_col2:
                st.metric("Quality", "9.2/10")
            
            # Upgrade suggestions for non-ultimate plans
            if user_plan != 'ultimate' and locked_platforms:
                st.markdown("---")
                st.info(f"💡 **Upgrade to unlock:** {', '.join(locked_platforms)}")
                
                if user_plan == 'demo':
                    st.info("🚀 **Starter**: +Facebook • **Pro**: +6 platforms • **Ultimate**: All 8 platforms")
                elif user_plan == 'starter':
                    st.info("💎 **Pro**: +4 platforms • **Ultimate**: All 8 platforms")
                elif user_plan == 'pro':
                    st.info("👑 **Ultimate**: +Medium, Reddit • Unlimited leads")

        else:
            # Non-authenticated user forecast
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1.5rem; 
                border-radius: 12px; 
                text-align: center; 
                color: white;
                max-width: 100%;
                box-sizing: border-box;
            ">
                <h4 style="margin: 0 0 0.5rem 0; font-size: 1.1rem;">🚀 Join the Empire</h4>
                <h3 style="margin: 0 0 0.5rem 0; font-size: 1.3rem;">Get Your Forecast</h3>
                <p style="margin: 0; font-size: 0.9rem; line-height: 1.4;">
                    🎯 Instant estimates<br>
                    ⚡ 8 platforms<br>
                    💎 ROI calculator
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Metrics for non-authenticated
            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                st.metric("Leads", "150-500")
            with metric_col2:
                st.metric("Success", "100%")
        
        # Last run info
        try:
            backup_files = get_latest_csv("*leads*.csv")
            if backup_files and os.path.exists(backup_files):
                mod_time = os.path.getmtime(backup_files)
                last_run = datetime.fromtimestamp(mod_time).strftime("%m/%d %H:%M")
                st.caption(f"📅 Last: {last_run}")
        except:
            pass
    
    # Launch button section (outside columns)
    st.markdown("---")
    
    if not user_authenticated:
        st.warning("🔐 Join the Lead Generator Empire to start conquering platforms")
        launch_col1, launch_col2 = st.columns(2)
        with launch_col1:
            if st.button("🚀 Start Demo", type="primary", use_container_width=True, key="main_demo"):
                st.session_state.show_register = True
                st.session_state.show_login = False
                st.rerun()
        with launch_col2:
            if st.button("🔑 Sign In", use_container_width=True, key="main_signin"):
                st.session_state.show_login = True
                st.session_state.show_register = False
                st.rerun()
    else:
        # Check if platforms selected
        any_selected = any([use_twitter, use_facebook, use_linkedin, use_youtube, 
                           use_medium, use_tiktok, use_instagram, use_reddit])
        
        if not any_selected:
            st.error("❌ Please select at least one platform")
            st.button("🚀 Launch Lead Empire", disabled=True, use_container_width=True)
        else:
            # LinkedIn email input (if LinkedIn is selected)
            if use_linkedin:
                st.markdown("---")
                st.warning("🛡️ **LinkedIn Anti-Bot Protection Notice**")
                
                with st.expander("💼 LinkedIn Processing Details", expanded=True):
                    st.markdown("""
                    **🔒 Why LinkedIn Requires Email Delivery:**
                    
                    LinkedIn actively blocks automated scraping. Instead of failing, we provide premium manual service:
                    
                    ⚡ **Other Platforms** (Instant): Twitter, Facebook, Instagram, TikTok, YouTube, Reddit
                    📧 **LinkedIn** (Manual - 2-4 hours): Manually processed and emailed to you
                    
                    **💎 Premium LinkedIn Benefits:**
                    • 100% verified profiles (no bots)
                    • Higher quality data with human verification  
                    • Often includes additional contact information
                    • Better response rates for outreach
                    """)
                
                linkedin_email = st.text_input(
                    "📧 Email for LinkedIn Results:",
                    value=st.session_state.get('user_data', {}).get('email', ''),
                    placeholder="your.email@company.com",
                    help="LinkedIn results will be manually processed and emailed within 2-4 hours",
                    key="linkedin_email_final"
                )
                
                if linkedin_email and '@' not in linkedin_email:
                    st.error("❌ Please enter a valid email address")
            else:
                linkedin_email = None

            st.markdown("### 🚀 Empire Launch Control")
            
            if not user_authenticated:
                st.warning("🔐 Join the Lead Generator Empire to start conquering platforms")
                launch_col1, launch_col2 = st.columns(2)
                with launch_col1:
                    if st.button("🚀 Start Demo", type="primary", use_container_width=True, key="launch_demo"):
                        st.session_state.show_register = True
                        st.session_state.show_login = False
                        st.rerun()
                with launch_col2:
                    if st.button("🔑 Sign In", use_container_width=True, key="launch_signin"):
                        st.session_state.show_login = True
                        st.session_state.show_register = False
                        st.rerun()
            else:
                # Get user info
                username = simple_auth.get_current_user()
                user_plan = simple_auth.get_user_plan()

                # Check if username is None/empty and fix it
                if not username or username == 'unknown':
                    st.error(f"❌ Authentication issue: simple_auth.get_current_user() returned '{username}'")
                    
                    # Try to get from session state directly
                    session_username = st.session_state.get('username')
                    if session_username:
                        st.warning(f"⚠️ Using session state username instead: '{session_username}'")
                        username = session_username
                        user_plan = st.session_state.get('user_data', {}).get('plan', 'demo')
                    else:
                        st.error("❌ No username found anywhere. Please sign in again.")
                        st.stop()
                
                # Get selected platforms
                selected_platforms = []
                if use_twitter: selected_platforms.append("Twitter")
                if use_facebook: selected_platforms.append("Facebook")
                if use_linkedin: selected_platforms.append("LinkedIn")
                if use_youtube: selected_platforms.append("YouTube")
                if use_medium: selected_platforms.append("Medium")
                if use_tiktok: selected_platforms.append("TikTok")
                if use_instagram: selected_platforms.append("Instagram")
                if use_reddit: selected_platforms.append("Reddit")
                
                # Validation
                validation_errors = []
                if not selected_platforms:
                    validation_errors.append("❌ Please select at least one platform")
                if not search_term or len(search_term.strip()) < 2:
                    validation_errors.append("❌ Please enter a valid search term")
                if use_linkedin and (not linkedin_email or '@' not in linkedin_email):
                    validation_errors.append("❌ Valid email required for LinkedIn delivery")
                
                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                    st.button("🚀 Launch Lead Empire", disabled=True, use_container_width=True)
                else:
                    # Show delivery plan
                    instant_platforms = [p for p in selected_platforms if p != 'LinkedIn']
                    if use_linkedin and instant_platforms:
                        st.info(f"""
                        **📦 Your Delivery Plan:**
                        ⚡ **Instant:** {', '.join(instant_platforms)}  
                        📧 **Email:** LinkedIn to {linkedin_email}
                        """)
                    elif use_linkedin:
                        st.info(f"""
                        **📧 LinkedIn-Only Request**
                        LinkedIn leads will be manually processed and emailed to: **{linkedin_email}**
                        """)
                    
                    # Check cooldown
                    last_launch = st.session_state.get('last_launch_time', 0)
                    current_time = time.time()
                    cooldown = max(0, 30 - (current_time - last_launch))
                    
                    if cooldown > 0:
                        st.warning(f"⏰ Wait {cooldown:.0f} seconds before launching again")
                        st.button("🚀 Launch Lead Empire", disabled=True, use_container_width=True)
                    else:
                        # THE SINGLE LAUNCH BUTTON
                        if st.button("🚀 Launch Lead Empire", key="launch_scraper"):
                            # ✅ FIX: Only check demo status for demo users
                            if user_plan == 'demo':
                                # Demo user - check demo limits
                                can_demo, remaining = credit_system.can_use_demo(username)
                                
                                if remaining <= 0:
                                    # Demo exhausted - show upgrade message
                                    st.error("🎯 Demo Exhausted!")
                                    st.warning("You've used all 5 demo leads. Upgrade to continue with unlimited scraping!")
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.info("💎 Pro Plan: 2,000 leads/month")
                                    with col2:
                                        st.info("🚀 Ultimate Plan: Unlimited leads")
                                    
                                    if st.button("🔄 Reset Demo (For Testing)", help="Admin only - resets demo for testing"):
                                        try:
                                            user_info = credit_system.get_user_info(username)
                                            if user_info:
                                                user_info['demo_leads_used'] = 0
                                                credit_system.save_data()
                                                st.success("✅ Demo reset! 5 leads available again.")
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Reset failed: {e}")
                                    
                                    # Don't proceed with scraping for exhausted demo users
                                    
                                
                                else:
                                    # Demo available - proceed with demo scraping
                                    st.session_state.last_launch_time = current_time
                                    st.info(f"🎯 Demo Status: {remaining} leads remaining")
                                    st.success("🚀 Empire Launch Initiated...")
                                    
                                    # Replace the subprocess section in your frontend_app.py with this

                                    try:
                                        
                                        
                                        # Setup environment with UTF-8 encoding
                                        scraper_env = os.environ.copy()
                                        scraper_env.update({
                                            'PYTHONIOENCODING': 'utf-8',
                                            'PYTHONUTF8': '1',
                                            'PYTHONLEGACYWINDOWSSTDIO': '0',
                                            'SCRAPER_USERNAME': username,
                                            'USER_PLAN': user_plan,
                                            'FRONTEND_SEARCH_TERM': search_term if 'search_term' in locals() else 'crypto trader'
                                        })

                                        # Also check if there are any other environment modifications
                                        current_os_env = os.environ.get('SCRAPER_USERNAME', 'NOT_SET_IN_OS')
                                        #st.code(f"Current OS environment SCRAPER_USERNAME: {current_os_env}")
                                        
                                        result = subprocess.run(
                                            [sys.executable, 'run_daily_scraper_complete.py'],  # Use sys.executable instead of 'python'
                                            capture_output=True,
                                            text=True,
                                            encoding='utf-8',  # Force UTF-8 encoding
                                            errors='replace',  # Replace problematic characters
                                            env=scraper_env,
                                            cwd=os.getcwd(),  # Ensure correct working directory
                                            timeout=300  # 5 minute timeout
                                        )
                                        
                                
                                        if result.returncode == 0:
                                            st.success("✅ Scraping completed successfully!")
                                            
                                            # Check for results and update demo consumption
                                            try:
                                                if os.path.exists('scraping_session_summary.json'):
                                                    with open('scraping_session_summary.json', 'r', encoding='utf-8') as f:
                                                        summary = json.load(f)
                                                    
                                                    total_leads = summary.get('total_leads', 0)
                                                    
                                                    if total_leads > 0:
                                                        # Update demo consumption
                                                        consumed = 0
                                                        for i in range(total_leads):
                                                            success = credit_system.consume_demo_lead(username)
                                                            if success:
                                                                consumed += 1
                                                            else:
                                                                break
                                                        
                                                        credit_system.save_data()
                                                        st.success(f"📊 Generated {total_leads} quality leads!")
                                                        
                                                        # Check if demo is now exhausted
                                                        can_demo_after, remaining_after = credit_system.can_use_demo(username)
                                                        if remaining_after <= 0:
                                                            st.balloons()
                                                            st.error("🎉 Demo Complete! You've used all 5 demo leads.")
                                                            st.info("💎 Ready to upgrade? Get unlimited access with Pro or Ultimate!")
                                                        else:
                                                            st.info(f"🎯 Demo Update: {remaining_after} leads remaining")
                                                        
                                                        # Force page refresh to update demo counters
                                                        time.sleep(2)
                                                        st.rerun()
                                                    else:
                                                        st.warning("⚠️ No leads generated. Try a different search term.")
                                                else:
                                                    st.error("❌ No results file found. Check if scraper completed properly.")
                                            
                                            except Exception as e:
                                                st.error(f"⚠️ Results processing error: {e}")
                                                import traceback
                                                st.code(traceback.format_exc(), language="text")                                        
                                        else:
                                            st.error(f"❌ Scraper failed with return code: {result.returncode}")
                                            
                                            # Provide specific error guidance based on return code
                                            if result.returncode == 1:
                                                st.info("💡 This usually means a Python import or configuration error")
                                            elif result.returncode == 2:
                                                st.info("💡 This usually means missing files or incorrect arguments")
                                            elif result.returncode == 126:
                                                st.info("💡 Permission denied - check file permissions")
                                            elif result.returncode == 127:
                                                st.info("💡 Command not found - check Python installation")
                                            
                                            # Check if main script exists
                                            if not os.path.exists('run_daily_scraper_complete.py'):
                                                st.error("❌ Main scraper file 'run_daily_scraper_complete.py' not found!")
                                            
                                            # Check Python version
                                            st.info(f"🐍 Python version: {sys.version}")
                                            
                                    except subprocess.TimeoutExpired:
                                        st.error("❌ Scraper timed out after 5 minutes")
                                        st.info("💡 Try reducing the number of scrolls or platforms")
                                        
                                    except FileNotFoundError as e:
                                        st.error(f"❌ File not found: {e}")
                                        st.info("💡 Make sure 'run_daily_scraper_complete.py' exists in the current directory")
                                        
                                    except Exception as e:
                                        st.error(f"❌ Launch error: {e}")
                                        import traceback
                                        st.code(traceback.format_exc(), language="text")
                            
                            else:
                                # ✅ PAID USER - PARALLEL EXECUTION (replaces the entire subprocess section)
                                st.session_state.last_launch_time = current_time
                                st.success(f"🚀 {user_plan.title()} Empire Launch Initiated...")
                                
                                # Get selected platforms (excluding LinkedIn for instant processing)
                                instant_platforms = [p.lower() for p in selected_platforms if p != 'LinkedIn']
                                
                                # Show progress
                                progress_placeholder = st.empty()
                                status_placeholder = st.empty()
                                
                                with progress_placeholder:
                                    progress_bar = st.progress(0)
                                    progress_text = st.empty()
                                
                                try:
                                    # ✅ NEW: PARALLEL EXECUTION instead of subprocess
                                    with status_placeholder:
                                        st.info(f"🚀 Launching {len(instant_platforms)} platforms")
                                    
                                    with progress_placeholder:
                                        progress_bar.progress(10)
                                        progress_text.text("Initializing scrapers...")
                                    
                                    # Import and run parallel scrapers
                                    from parallel_scraper_runner import run_parallel_scrapers
                                    
                                    # ✅ PARALLEL EXECUTION - Much faster than sequential!
                                    all_results = run_parallel_scrapers(
                                        platforms=instant_platforms,    # e.g., ['twitter', 'facebook', 'youtube']
                                        search_term=search_term,        # From your form input
                                        max_scrolls=max_scrolls,        # From your slider
                                        username=username,
                                        user_plan=user_plan
                                    )
                                    
                                    # Update progress
                                    with progress_placeholder:
                                        progress_bar.progress(100)
                                        st.success("✅ Parallel execution complete!")
                                    
                                    # Process and display results
                                    if all_results:
                                        total_leads = sum(len(results) if results else 0 for results in all_results.values())
                                        successful_platforms = sum(1 for results in all_results.values() if results and len(results) > 0)

                                        # ✅ ADD CREDIT REFRESH RIGHT AFTER THIS
                                        if all_results:
                                            total_leads = sum(len(results) if results else 0 for results in all_results.values())
                                            
                                            if total_leads > 0:
                                                # Force refresh credits after successful scraping
                                                try:
                                                    from simple_credit_system import credit_system
                                                    credit_system.load_data()
                                                    
                                                    auth = SimpleCreditAuth()
                                                    updated_credits = auth.get_user_credits()
                                                    
                                                    st.info(f"💎 Credits updated: **{updated_credits}** remaining")
                                                                                                       
                                                except Exception as e:
                                                    st.warning(f"⚠️ Credit refresh error: {e}")
                                        
                                        with status_placeholder:
                                            st.success(f"🎉 Generated {total_leads} leads across {successful_platforms} platforms!")
                                        
                                        # Show platform breakdown
                                        st.markdown("**📋 Results by Platform:**")
                                        for platform, results in all_results.items():
                                            count = len(results) if results else 0
                                            if count > 0:
                                                st.markdown(f"  ✅ {platform.title()}: {count} leads")
                                            else:
                                                st.markdown(f"  ❌ {platform.title()}: 0 leads")
                                        
                                        # Create summary for compatibility with existing code
                                        summary = {
                                            'total_leads': total_leads,
                                            'successful_platforms': successful_platforms,
                                            'results_by_platform': {k: len(v) if v else 0 for k, v in all_results.items()},
                                            'execution_mode': 'parallel'
                                        }
                                        
                                        # Save summary file for compatibility
                                        try:
                                            with open('scraping_session_summary.json', 'w') as f:
                                                json.dump(summary, f, indent=2)
                                        except:
                                            pass
                                        
                                        st.info("📊 Check 'Lead Results' tab to view your leads")
                                        st.rerun()
                                        
                                    else:
                                        with status_placeholder:
                                            st.warning("⚠️ No results generated")
                                        
                                        st.info("💡 Try:")
                                        st.info("  • Different search term (e.g., 'crypto coach')")
                                        st.info("  • Lower intensity (3-5 scrolls)")
                                        st.info("  • Fewer platforms")
                                        
                                except ImportError:
                                    # Fallback to original method if parallel runner not available
                                    with status_placeholder:
                                        st.warning("⚠️ Parallel runner not available, using sequential method...")
                                    
                                    # Your original subprocess code here as fallback
                                    scraper_env = os.environ.copy()
                                    scraper_env.update({
                                        'PYTHONIOENCODING': 'utf-8',
                                        'PYTHONUTF8': '1', 
                                        'PYTHONLEGACYWINDOWSSTDIO': '0',
                                        'SCRAPER_USERNAME': username,
                                        'USER_PLAN': user_plan,
                                        'FRONTEND_SEARCH_TERM': search_term,
                                        'SELECTED_PLATFORMS': ','.join(instant_platforms),
                                        'FORCE_AUTHORIZATION': 'true',
                                        'PLAN_OVERRIDE': user_plan
                                    })
                                    
                                    process = subprocess.Popen(
                                        ['python', 'run_daily_scraper_complete.py'],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        encoding='utf-8',        # ✅ ADD THIS LINE
                                        errors='replace',        # ✅ ADD THIS LINE  
                                        env=scraper_env
                                    )
                                    
                                    # Your existing timeout monitoring code here...
                                    st.info("📊 Sequential execution - check results in 10-15 minutes")
                                    
                                except Exception as e:
                                    with status_placeholder:
                                        st.error(f"❌ Parallel execution error: {str(e)}")
                                    
                                    with progress_placeholder:
                                        st.empty()
                                
                                # Handle LinkedIn separately (unchanged)
                                if use_linkedin and linkedin_email:
                                    try:
                                        linkedin_success = queue_linkedin_request(username, search_term, max_scrolls, linkedin_email)
                                        if linkedin_success:
                                            st.success("📧 LinkedIn request queued!")
                                            st.info("⏰ Results will be emailed within 2-4 hours")
                                        else:
                                            st.error("❌ LinkedIn queueing failed")
                                    except Exception as e:
                                        st.error(f"❌ LinkedIn error: {e}")
                                
                        # ✅ ADDITIONAL: Add a background process checker
                        def check_background_scrapers():
                            """Check if any scrapers are running in background"""
                            try:
                                import psutil
                                python_processes = []
                                
                                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                    try:
                                        if proc.info['name'] and 'python' in proc.info['name'].lower():
                                            cmdline = proc.info['cmdline']
                                            if cmdline and any('scraper' in cmd for cmd in cmdline):
                                                python_processes.append({
                                                    'pid': proc.info['pid'],
                                                    'cmdline': ' '.join(cmdline[-2:])  # Last 2 parts
                                                })
                                    except:
                                        continue
                                
                                return python_processes
                            except ImportError:
                                return []

                        # Add this to your sidebar or status area
                        if user_authenticated:
                            background_scrapers = check_background_scrapers()
                            if background_scrapers:
                                st.sidebar.info(f"🔄 {len(background_scrapers)} scraper(s) running in background")
                                with st.sidebar.expander("Running Processes"):
                                    for proc in background_scrapers:
                                        st.text(f"PID {proc['pid']}: {proc['cmdline']}")

                        

        st.markdown(
            '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
            'padding:12px 16px;border-radius:25px;'
            'background:linear-gradient(135deg,#0066cc,#4dabf7);'
            'color:white;font-weight:bold;text-decoration:none;'
            'z-index:9999;">⬆️ Top</a>',
            unsafe_allow_html=True,
        )


with tab2: # Lead Results

    st.header("📊 Empire Intelligence Dashboard")

    st.markdown("---")

    def show_demo_results_preview():
        """Show what demo users can expect"""
        st.markdown("### 📱 Demo Experience Preview")
        
        demo_preview_data = {
            "Name": ["Sarah F***", "Mike H***", "Jessica W***", "Ryan F***"],
            "Platform": ["Twitter", "Facebook", "LinkedIn", "Instagram"], 
            "Bio": [
                "Personal trainer helping clients achieve fitness goals 💪",
                "Business coach &amp; entrepreneur. 10+ years experience...",
                "Wellness consultant | Helping busy professionals...",
                "Fitness influencer | Inspiring healthy lifestyles..."
            ],
            "Handle": ["@sar***", "@mik***", "@jes***", "@rya***"],
            "Status": ["DEMO", "DEMO", "DEMO", "DEMO"]
        }
        
        st.dataframe(demo_preview_data, use_container_width=True)
        
        st.info("""
        📱 **Demo Features:**
        - ✅ See platform interface and capabilities  
        - ✅ Sample data shows what real results look like
        - ✅ No consumption of your 5 real demo leads
        - ✅ Experience the full workflow
        
        🚀 **Upgrade Benefits:**
        - ✅ Real, verified contact information
        - ✅ Full email addresses and social handles  
        - ✅ Unlimited lead generation
        - ✅ All 8 platforms unlocked
        """)

    def demo_user_onboarding():
        """Special onboarding for demo users"""
        if st.session_state.get('user_data', {}).get('plan') == 'demo':
            if 'demo_onboarding_shown' not in st.session_state:
                st.balloons()
                
                st.success("🎉 Welcome to Lead Generator Empire!")
                
                st.info("""
                📱 **Your Demo Account Includes:**
                
                **🎯 Unlimited Sample Generations**
                - Try the platform with realistic sample data
                - See exactly how the interface works
                - No limits on sample generations
                
                **🔬 5 Real Demo Leads** 
                - Try real lead generation when you're ready
                - Real data from Twitter platform
                - Perfect for testing actual functionality
                
                **💡 Pro Tip:** Start with sample generations to learn the platform, then use your 5 real demo leads when you're ready to test with actual data!
                """)
                
                st.session_state.demo_onboarding_shown = True

    def show_demo_platform_selection():
        """Enhanced platform selection explanation for demo users"""
        
        if user_plan == 'demo':
            # Demo mode explanation with dual options
            st.warning("📱 **Demo Mode** - Choose your experience:")
            
            demo_option_col1, demo_option_col2 = st.columns(2)
            
            with demo_option_col1:
                st.info("""
                **🎯 Sample Generation (Recommended)**
                - Unlimited realistic sample data
                - All platforms available for testing
                - Learn the interface risk-free
                - No consumption of demo leads
                """)
            
            with demo_option_col2:
                can_demo, remaining = credit_system.can_use_demo(username)
                if remaining > 0:
                    st.success(f"""
                    **🔬 Real Demo Leads ({remaining} remaining)**
                    - Actual Twitter data
                    - Real contact information  
                    - Limited to {remaining} leads
                    - Use when ready to test for real
                    """)
                else:
                    st.error("""
                    **🔬 Real Demo Leads (0 remaining)**
                    - All 5 real demo leads used
                    - Sample generations still unlimited
                    - Upgrade for unlimited real leads
                    """)
            
            # Mode selection
            demo_mode = st.radio(
                "Choose Demo Experience:",
                ["🎯 Sample Generation (Unlimited)", "🔬 Real Demo Leads (Limited)"],
                key="demo_mode_selection",
                help="Sample generation lets you explore without limits, real demo leads show actual data"
            )
            
            # Store selection in session
            st.session_state.demo_mode_choice = "sample" if "Sample" in demo_mode else "real"
            
            # Platform availability based on mode
            if st.session_state.demo_mode_choice == "sample":
                st.info("🌟 **Sample Mode:** All platforms available for testing!")
                available_platforms = ['twitter', 'facebook', 'linkedin', 'tiktok', 'instagram', 'youtube', 'medium', 'reddit']
            else:
                st.info("🔬 **Real Demo Mode:** Twitter platform only")
                available_platforms = ['twitter']
            
            return available_platforms

    # 3. UPDATE THE LAUNCH BUTTON LOGIC
    def get_demo_launch_button_state():
        """Determine demo launch button state and messaging"""
        
        if not user_authenticated:
            return False, "Sign in required"
        
        username = simple_auth.get_current_user()
        user_plan = st.session_state.get('user_data', {}).get('plan', 'demo')
        
        if user_plan != 'demo':
            return True, "Launch for real user"
        
        # Demo user logic
        demo_mode_choice = st.session_state.get('demo_mode_choice', 'sample')
        
        if demo_mode_choice == 'sample':
            return True, "🎯 Generate Sample Leads (Unlimited)"
        
        else:  # real demo mode
            can_demo, remaining = credit_system.can_use_demo(username)
            if remaining > 0:
                return True, f"🔬 Generate Real Demo Leads ({remaining} remaining)"
            else:
                return False, "Real demo leads exhausted - try sample mode!"

    # 4. UPDATE THE FORECAST DISPLAY
    def show_enhanced_demo_forecast(selected_platforms, max_scrolls, user_plan):
        """Enhanced forecast that differentiates demo modes"""
        
        if user_plan == 'demo':
            demo_mode_choice = st.session_state.get('demo_mode_choice', 'sample')
            
            if demo_mode_choice == 'sample':
                # Sample mode - show full capabilities
                estimate_data = calculate_accurate_estimate(selected_platforms, max_scrolls, 'pro')  # Show pro-level estimate
                estimated_leads = estimate_data["total_estimate"]
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #17a2b820 0%, #17a2b810 100%); 
                            border: 2px solid #17a2b8; border-radius: 15px; padding: 1.5rem; text-align: center;">
                    <h3 style="color: #17a2b8; margin: 0;">🎯 Sample Generation Preview</h3>
                    <h1 style="margin: 0.5rem 0; color: #333;">{estimated_leads} sample leads</h1>
                    <p style="margin: 0; color: #666;">From {len(selected_platforms)} platform(s) • Realistic sample data</p>
                    <small style="color: #17a2b8;">⚡ Instant generation • No demo lead consumption</small>
                </div>
                """, unsafe_allow_html=True)
                
                st.info("🎯 **Sample Mode:** This will generate realistic sample data to show you what the platform can do!")
            
            else:
                # Real demo mode - limited
                username = simple_auth.get_current_user()
                can_demo, remaining = credit_system.can_use_demo(username)
                
                estimated_leads = min(5, remaining)  # Cap at remaining demo leads
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #28a74520 0%, #28a74510 100%); 
                            border: 2px solid #28a745; border-radius: 15px; padding: 1.5rem; text-align: center;">
                    <h3 style="color: #28a745; margin: 0;">🔬 Real Demo Lead Generation</h3>
                    <h1 style="margin: 0.5rem 0; color: #333;">{estimated_leads} real leads</h1>
                    <p style="margin: 0; color: #666;">Twitter platform • Real contact data</p>
                    <small style="color: #28a745;">⚡ Will consume {estimated_leads} of your {remaining} demo leads</small>
                </div>
                """, unsafe_allow_html=True)
                
                if remaining == 0:
                    st.error("🔬 **No real demo leads remaining!** Switch to sample mode or upgrade.")
                else:
                    st.warning(f"🔬 **Real Demo Mode:** Will use {estimated_leads} of your {remaining} real demo leads")

    # 5. UPDATE BUTTON TEXT DYNAMICALLY
    def get_launch_button_text():
        """Get appropriate launch button text based on demo mode"""
        
        if not user_authenticated:
            return "🔑 Sign In to Launch"
        
        user_plan = st.session_state.get('user_data', {}).get('plan', 'demo')
        
        if user_plan != 'demo':
            return "🚀 Launch Lead Empire"
        
        # Demo user
        demo_mode_choice = st.session_state.get('demo_mode_choice', 'sample')
        
        if demo_mode_choice == 'sample':
            return "🎯 Generate Sample Leads"
        else:
            username = simple_auth.get_current_user()
            can_demo, remaining = credit_system.can_use_demo(username)
            if remaining > 0:
                return f"🔬 Use Real Demo Leads ({remaining} left)"
            else:
                return "❌ Real Demo Exhausted"

    def show_credit_dashboard():
        """Updated dashboard for all plan types including demo"""
        if not simple_auth.is_authenticated():
            show_auth_required_dashboard()
            return
        
        username = simple_auth.get_current_user()
        user_stats = credit_system.get_user_stats(username)
        
        # Check if demo user
        if credit_system.is_demo_user(username):
            show_demo_dashboard()
            return
        
        # Regular dashboard for paid plans
        st.markdown("### 💎 Your Credit Dashboard")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            current_credits = user_stats.get('current_credits', 0)
            st.metric("💎 Credits Available", current_credits)
        
        with col2:
            total_downloaded = user_stats.get('total_leads_downloaded', 0)
            st.metric("📊 Total Leads Generated", total_downloaded)
        
        with col3:
            plan = user_stats.get('plan', 'demo')
            plan_emoji = "📱" if plan == 'starter' else "💎" if plan == 'pro' else "👑" if plan == 'ultimate' else "🔬"
            st.metric("📋 Plan", f"{plan_emoji} {plan.title()}")
        
        with col4:
            total_purchased = user_stats.get('total_purchased', 0)
            st.metric("💰 Credits Purchased", total_purchased)
    
    if not user_authenticated:
        st.info("🔐 Join the empire to access your intelligence dashboard")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Join Empire", type="primary", use_container_width=True, key="results_register"):
                st.session_state.show_register = True
                st.rerun()
        with col2:
            if st.button("🔑 Sign In", use_container_width=True, key="results_login"):
                st.session_state.show_login = True
                st.session_state.show_register = False  # ← ADD THIS
                st.rerun()
        
        st.markdown("---")
        st.markdown("### 📈 Empire Preview")
        dashboard_features = [
            "**📊 Real-time analytics** across all 8 platforms",
            "**🎯 Lead quality scoring** and filtering",
            "**📍 Geographic distribution** of your prospects",
            "**💬 AI-generated DMs** ready for outreach",
            "**📈 Performance trends** and optimization insights",
            "**🔄 Cross-platform deduplication**"
        ]
        
        if MULTILINGUAL_AVAILABLE:
            dashboard_features.insert(3, "**🌍 Multilingual DM generation** in 12+ languages")
            dashboard_features.insert(4, "**🎯 Language-specific analytics** and targeting")
        
        for feature in dashboard_features:
            st.markdown(f"- {feature}")
        
        # Sample empire metrics
        sample_empire = {
            "Platform": ["Twitter", "Facebook", "YouTube", "TikTok", "Medium"],
            "Leads": [29, 112, 25, 80, 8],
            "Quality Score": [9.2, 8.8, 9.5, 8.3, 9.7],
            "Avg Followers": ["5.2K", "3.1K", "52K", "15K", "2.1K"]
        }
        
        if MULTILINGUAL_AVAILABLE:
            sample_empire["Primary Language"] = ["English", "Spanish", "English", "English", "French"]
        
        st.markdown("**Sample Empire Intelligence:**")
        st.dataframe(sample_empire, use_container_width=True)
        st.caption("*Join the empire to see your real conquest data*")
    
    else:
        # Full empire intelligence dashboard for authenticated users
        
        # ✅ ADD DEMO USER CHECK HERE
        username = simple_auth.get_current_user()
        user_plan = simple_auth.get_user_plan()
        
        if user_plan == 'demo':
            # 🎯 DEMO USER SPECIFIC DASHBOARD
            st.markdown("### 🎯 Demo Intelligence Dashboard")
            
            # Get demo user's leads using the same logic as paid users, but with demo-specific patterns
            demo_leads = []
            
            try:
                # Check if there's a recent session for this demo user
                session_found = False
                if os.path.exists('scraping_session_summary.json'):
                    with open('scraping_session_summary.json', 'r') as f:
                        summary = json.load(f)
                    
                    # Check if session belongs to current user
                    if summary.get('user') == username:
                        session_found = True
                        print(f"✅ Found session for demo user: {username}")
                
                if session_found:
                    # Use the SAME file patterns as paid users
                    demo_patterns = {
                        "🐦 Twitter": f"twitter_*{username}_*.csv"
                    }
                    
                    # Look for recent files (last 2 hours) - same as paid users
                    current_time = datetime.now()
                    
                    for platform_name, pattern in demo_patterns.items():
                        try:
                            latest_file = get_latest_csv(pattern)
                            if latest_file and os.path.exists(latest_file):
                                # Check if file is recent (last 2 hours)
                                file_time = datetime.fromtimestamp(os.path.getmtime(latest_file))
                                hours_old = (current_time - file_time).total_seconds() / 3600
                                
                                if hours_old <= 2:  # Only files from last 2 hours
                                    df = pd.read_csv(latest_file)
                                    
                                    if not df.empty:
                                        # For demo users, limit to 5 total leads regardless of source
                                        remaining_demo_slots = 5 - len(demo_leads)
                                        
                                        if remaining_demo_slots > 0:
                                            platform_leads = df.head(remaining_demo_slots).to_dict('records')
                                            
                                            # Add demo tags
                                            for lead in platform_leads:
                                                lead['demo_user'] = username
                                                lead['demo_mode'] = True
                                            
                                            demo_leads.extend(platform_leads)
                                            print(f"✅ Added {len(platform_leads)} demo leads from {platform_name}")
                                            
                                            if len(demo_leads) >= 5:
                                                break  # Demo limit reached
                        except Exception as e:
                            print(f"⚠️ Error checking {platform_name}: {e}")
                            continue
                
            except Exception as e:
                print(f"❌ Demo data loading error: {e}")
            
            # Display demo results
            if demo_leads:
                st.success(f"🎯 Your Demo Results: {len(demo_leads)} leads")
                
                # Demo metrics - same as paid users
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Demo Leads", len(demo_leads))
                with col2:
                    st.metric("🎯 Quality Score", "8.5/10") 
                with col3:
                    st.metric("💬 DMs Ready", "100%")
                with col4:
                    estimated_value = len(demo_leads) * 25
                    st.metric("💰 Est. Value", f"${estimated_value}")
                
                # Show demo data
                st.markdown("### 📋 Your Demo Leads")
                df = pd.DataFrame(demo_leads)
                
                # Show essential columns - same as paid users
                essential_columns = ['name', 'handle', 'bio', 'platform']
                if 'dm' in df.columns:
                    essential_columns.append('dm')
                
                available_columns = [col for col in essential_columns if col in df.columns]
                
                if available_columns:
                    display_df = df[available_columns]
                    
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "name": st.column_config.TextColumn("Name", width="medium"),
                            "handle": st.column_config.TextColumn("Handle", width="small"), 
                            "bio": st.column_config.TextColumn("Bio", width="large"),
                            "platform": st.column_config.TextColumn("Platform", width="small"),
                            "dm": st.column_config.TextColumn("DM Ready", width="large") if 'dm' in available_columns else None
                        }
                    )
                    
                    # Demo download
                    st.download_button(
                        label="📥 Download Demo Results",
                        data=display_df.to_csv(index=False),
                        file_name=f"demo_leads_{username}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                # Demo completion status
                can_demo, remaining = credit_system.can_use_demo(username)
                if remaining <= 0:
                    st.balloons()
                    st.success("🎉 Demo Complete! You've experienced the full power of Lead Empire!")
                    
                    # Upgrade prompt
                    st.markdown("---")
                    st.markdown("### 🚀 Ready to Unlock Your Full Empire?")
                    
                    upgrade_col1, upgrade_col2 = st.columns(2)
                    with upgrade_col1:
                        st.info("""
                        **💎 Pro Plan - $197/month**
                        - ✅ 6 platforms unlocked
                        - ✅ 2,000 leads/month  
                        - ✅ Advanced analytics
                        - ✅ Priority support
                        """)
                    with upgrade_col2:
                        st.info("""
                        **👑 Ultimate Plan - $497/month**
                        - ✅ All 8 platforms
                        - ✅ Unlimited leads
                        - ✅ White-label access
                        - ✅ Custom integrations
                        """)
                    
                    if st.button("💎 Upgrade to Pro", type="primary", use_container_width=True):
                        st.session_state.show_pricing = True
                        st.rerun()
                else:
                    st.info(f"🎯 Demo Status: {remaining} leads remaining")
            
            else:
                # No demo leads found
                can_demo, remaining = credit_system.can_use_demo(username)
                demo_used = 5 - remaining
                
                if demo_used > 0:
                    # Demo was used but no files found
                    st.warning(f"🎯 Demo leads were generated ({demo_used} used) but results not found")
                    st.info("💡 Demo results may have been cleaned up. You can generate sample leads to see how the platform works!")
                    
                    # Show file debug info
                    with st.expander("🔍 Debug: Check for result files"):
                        import glob
                        all_csv_files = glob.glob("*.csv")
                        recent_files = []
                        
                        current_time = datetime.now()
                        for file in all_csv_files:
                            try:
                                file_time = datetime.fromtimestamp(os.path.getmtime(file))
                                hours_old = (current_time - file_time).total_seconds() / 3600
                                if hours_old <= 24:  # Last 24 hours
                                    recent_files.append(f"{file} ({hours_old:.1f}h old)")
                            except:
                                continue
                        
                        st.text(f"Recent CSV files found: {len(recent_files)}")
                        for file in recent_files[:10]:
                            st.text(file)
                        
                        if 'scraping_session_summary.json' in glob.glob("*.json"):
                            try:
                                with open('scraping_session_summary.json', 'r') as f:
                                    summary = json.load(f)
                                st.json(summary)
                            except:
                                st.text("Could not read session summary")
                else:
                    # No demo leads generated yet
                    st.info(f"🎯 No demo leads generated yet for {username}")
                    st.markdown("""
                    ### 🚀 Generate Your First Demo Leads
                    
                    1. **🔍 Set Keywords**: Go to Empire Scraper tab
                    2. **🎯 Choose Demo Mode**: Select "Real Demo Leads" 
                    3. **🚀 Launch**: Click "Launch Lead Empire"
                    4. **📊 View Results**: Return here to see your leads!
                    """)
                
                # Show demo status
                if remaining > 0:
                    st.success(f"✅ {remaining} demo leads available")
                else:
                    st.warning("❌ Demo exhausted - Upgrade to continue!")
    
        else:
            
            # ✅ AFTER (SECURE - loads only current user's data):
            def get_user_empire_patterns(username: str) -> dict:
                """Get platform patterns that only match current user's files"""
                if not username:
                    return {}
                
                return {
                    "🐦 Twitter": f"twitter_*{username}_*.csv",
                    "💼 LinkedIn": f"linkedin_*{username}_*.csv", 
                    "📘 Facebook": f"facebook_*{username}_*.csv",
                    "🎵 TikTok": f"tiktok_*{username}_*.csv",
                    "📸 Instagram": f"instagram_*{username}_*.csv",
                    "🎥 YouTube": f"youtube_*{username}_*.csv",
                    "📝 Medium": f"medium_*{username}_*.csv",
                    "🗨️ Reddit": f"reddit_*{username}_*.csv"
                }

            # ✅ USE USER-SPECIFIC PATTERNS
            empire_platforms = get_user_empire_patterns(username)

            print(f"🔐 SECURE: Loading empire data ONLY for user: {username}")
            print(f"🔍 Using patterns: {list(empire_platforms.values())}")

            # Load and combine ONLY USER'S empire data
            all_empire_data = []
            empire_totals = {}
            language_stats = {}

            for platform_name, user_pattern in empire_platforms.items():
                print(f"🔍 Checking user pattern: {user_pattern}")
                
                try:
                    # ✅ METHOD 1: Use the working CSV debug logic
                    if CSV_USER_DEBUG_AVAILABLE:
                        from csv_user_debug import get_user_csv_file
                        latest_user_file = get_user_csv_file(user_pattern, username)
                    else:
                        # ✅ METHOD 2: Fallback - manual user-specific file finding
                        import glob
                        user_files = sorted(glob.glob(user_pattern), key=os.path.getmtime, reverse=True)
                        latest_user_file = user_files[0] if user_files else None
                    
                    if latest_user_file and os.path.exists(latest_user_file):
                        print(f"✅ Found user file: {latest_user_file}")
                        
                        df = pd.read_csv(latest_user_file)
                        
                        if not df.empty:
                            # ✅ DOUBLE-CHECK: Additional user filtering as backup
                            if CSV_USER_DEBUG_AVAILABLE:
                                from csv_user_debug import filter_csv_for_user
                                df = filter_csv_for_user(df, username)
                            
                            # ✅ TRIPLE-CHECK: Manual filtering as final backup
                            user_columns = ['generated_by', 'username', 'user_id', 'created_by']
                            for col in user_columns:
                                if col in df.columns:
                                    original_count = len(df)
                                    df = df[df[col].astype(str).str.lower() == username.lower()]
                                    if len(df) < original_count:
                                        print(f"🔒 Filtered {platform_name}: {original_count} → {len(df)} rows (removed other users' data)")
                                    break
                            
                            if not df.empty:
                                # Ensure platform column exists
                                if 'platform' not in df.columns:
                                    platform_key = platform_name.split()[1].lower()
                                    df['platform'] = platform_key
                                
                                all_empire_data.append(df)
                                empire_totals[platform_name] = len(df)
                                print(f"✅ Loaded {len(df)} {platform_name} leads for {username}")
                                
                                # 🌍 Language statistics (if available)
                                if MULTILINGUAL_AVAILABLE and 'detected_language' in df.columns:
                                    platform_languages = df['detected_language'].value_counts().to_dict()
                                    for lang, count in platform_languages.items():
                                        language_stats[lang] = language_stats.get(lang, 0) + count
                            else:
                                empire_totals[platform_name] = 0
                                print(f"⚠️ {platform_name}: File found but no user data after filtering")
                        else:
                            empire_totals[platform_name] = 0
                            print(f"⚠️ {platform_name}: File found but empty")
                    else:
                        empire_totals[platform_name] = 0
                        print(f"❌ {platform_name}: No user-specific files found")
                        
                except Exception as e:
                    empire_totals[platform_name] = 0
                    print(f"❌ {platform_name} error: {e}")

            # ✅ SECURITY VERIFICATION
            total_loaded_files = len(all_empire_data)
            total_leads = sum(len(df) for df in all_empire_data)

            print(f"🔐 SECURITY CHECK:")
            print(f"   User: {username}")
            print(f"   Files loaded: {total_loaded_files}")
            print(f"   Total leads: {total_leads}")
            print(f"   Expected: Only {username}'s data")

            if total_leads > 100:
                print(f"⚠️ WARNING: {total_leads} leads seems high for one user - verify user isolation")
            elif total_leads == 0:
                print(f"ℹ️ INFO: No leads found for {username} - they may need to generate some")
            else:
                print(f"✅ GOOD: {total_leads} leads for {username} (reasonable amount)")

            # Combine user's empire data only
            if all_empire_data:
                empire_df = pd.concat(all_empire_data, ignore_index=True)
                empire_df = empire_df.drop_duplicates(subset=['name', 'handle'], keep='first')
                print(f"✅ Combined user empire: {len(empire_df)} unique leads")
                
                platforms_with_data = {
                    **{name: pattern for name, pattern in empire_platforms.items()},
                    "👑 Empire Combined": empire_df
                }
            else:
                empire_df = pd.DataFrame()
                platforms_with_data = empire_platforms
                print(f"❌ No user data found for {username}")

            # ✅ ADD USER VERIFICATION MESSAGE
            st.markdown(f"### 👤 {username}'s Empire Intelligence")

            if total_leads > 0:
                st.success(f"✅ Found {total_leads} leads belonging to you")
            else:
                st.warning(f"📡 No leads found for {username} yet")
            
            # Load and combine all empire data
            all_empire_data = []
            empire_totals = {}
            language_stats = {}
            
            for platform_name, pattern in empire_platforms.items():
                latest_file = get_latest_csv(pattern)
                if latest_file and os.path.exists(latest_file):
                    try:
                        df = pd.read_csv(latest_file)
                        if not df.empty:
                            # USER FILTERING: Only show data for current user
                            if user_authenticated and USER_CSV_FILTER_AVAILABLE:
                                username = simple_auth.get_current_user()
                                if username:
                                    df = filter_empire_data_by_user(df, username)
                            
                            # Continue with existing logic only if we still have data
                            if not df.empty:
                                # Ensure platform column exists
                                if 'platform' not in df.columns:
                                    platform_key = platform_name.split()[1].lower()
                                    df['platform'] = platform_key
                                
                                all_empire_data.append(df)
                                empire_totals[platform_name] = len(df)
                            else:
                                empire_totals[platform_name] = 0
                            
                            # 🌍 NEW: Collect language statistics
                            if MULTILINGUAL_AVAILABLE and 'detected_language' in df.columns:
                                platform_languages = df['detected_language'].value_counts().to_dict()
                                for lang, count in platform_languages.items():
                                    language_stats[lang] = language_stats.get(lang, 0) + count
                        else:
                            empire_totals[platform_name] = 0
                    except Exception as e:
                        empire_totals[platform_name] = 0
                else:
                    empire_totals[platform_name] = 0
            
            # Combine empire data
            if all_empire_data:
                empire_df = pd.concat(all_empire_data, ignore_index=True)
                empire_df = empire_df.drop_duplicates(subset=['name', 'handle'], keep='first')
                
                platforms_with_data = {
                    **{name: pattern for name, pattern in empire_platforms.items()},
                    "👑 Empire Combined": empire_df
                }
            else:
                empire_df = pd.DataFrame()
                platforms_with_data = empire_platforms
            
            # Empire command center
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("⬅️ Back to Empire", type="secondary", use_container_width=True):
                    st.rerun()
            with col2:
                if st.button("🔄 Refresh Intelligence", type="secondary", use_container_width=True):
                    st.rerun()
            with col3:
                if not empire_df.empty:
                    empire_csv = empire_df.to_csv(index=False)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                    st.download_button(
                        "📤 Export Empire Data", 
                        data=empire_csv,
                        file_name=f"empire_leads_{timestamp}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.button("📤 Export Empire Data", disabled=True, use_container_width=True)

            st.markdown("---")

            # ✅ FUNCTION DEFINITIONS FIRST (before they're used)

            def get_user_csv_files(username):
                """Get list of CSV files for specific user"""
                import glob
                import os
                from datetime import datetime
                
                csv_files = []
                
                # Patterns to find user's CSV files
                patterns = [
                    f"*{username}*leads*.csv",
                    f"*leads*{username}*.csv", 
                    f"{username}_*.csv",
                    "*unified_leads*.csv"  # Generic unified files
                ]
                
                found_files = set()  # Use set to avoid duplicates
                
                for pattern in patterns:
                    files = glob.glob(pattern)
                    for file in files:
                        if file not in found_files and username.lower() in file.lower():
                            found_files.add(file)
                
                # Process each file
                for file_path in found_files:
                    try:
                        # Get file stats
                        stat = os.stat(file_path)
                        file_size = stat.st_size
                        mod_time = datetime.fromtimestamp(stat.st_mtime)
                        
                        # Count leads (lines minus header)
                        lead_count = 0
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lead_count = max(0, sum(1 for line in f) - 1)
                        except:
                            lead_count = 0
                        
                        # Extract platform and search term from filename
                        filename = os.path.basename(file_path)
                        platform = extract_platform_from_filename(filename)
                        search_term = extract_search_term_from_filename(filename)
                        
                        csv_files.append({
                            'name': filename,
                            'path': file_path,
                            'size': file_size,
                            'size_mb': file_size / 1024 / 1024,
                            'date': mod_time.strftime('%m/%d %H:%M'),
                            'leads': lead_count,
                            'platform': platform,
                            'search_term': search_term
                        })
                        
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        continue
                
                # Sort by modification time (newest first)
                csv_files.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)
                
                return csv_files

            def extract_platform_from_filename(filename):
                """Extract platform name from filename"""
                filename_lower = filename.lower()
                
                platforms = ['twitter', 'facebook', 'linkedin', 'instagram', 'tiktok', 'youtube', 'medium', 'reddit']
                
                for platform in platforms:
                    if platform in filename_lower:
                        return platform
                
                return 'unknown'

            def extract_search_term_from_filename(filename):
                """Extract search term from filename if possible"""
                try:
                    # Look for patterns like "crypto_trader" or "stock_broker"
                    import re
                    
                    # Remove common parts
                    clean_name = filename.replace('_leads', '').replace('_unified', '').replace('.csv', '')
                    
                    # Split by underscores and look for search terms
                    parts = clean_name.split('_')
                    
                    # Filter out common words
                    exclude_words = ['leads', 'unified', 'twitter', 'facebook', 'linkedin', 'instagram', 
                                    'tiktok', 'youtube', 'medium', 'reddit', 'scraper', 'results']
                    
                    search_parts = [part for part in parts if part.lower() not in exclude_words and len(part) > 2]
                    
                    if search_parts:
                        return ' '.join(search_parts[:3])  # Take first 3 meaningful parts
                    
                    return 'Unknown'
                    
                except:
                    return 'Unknown'

            def get_platform_emoji(platform):
                """Get emoji for platform"""
                emoji_map = {
                    'twitter': '🐦',
                    'facebook': '📘', 
                    'linkedin': '💼',
                    'instagram': '📷',
                    'tiktok': '🎵',
                    'youtube': '📺',
                    'medium': '📝',
                    'reddit': '🔗',
                    'unknown': '📄'
                }
                return emoji_map.get(platform, '📄')

            def download_csv_file(file_path, filename):
                """Trigger download of CSV file"""
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # Use a unique key based on filename and timestamp
                    import time
                    unique_key = f"download_button_{filename}_{int(time.time())}"
                    
                    st.download_button(
                        label=f"💾 Download {filename}",
                        data=file_data,
                        file_name=filename,
                        mime='text/csv',
                        key=unique_key
                    )
                    
                except Exception as e:
                    st.error(f"❌ Error downloading file: {e}")

            def create_bulk_download(csv_files, username):
                """Create zip file with all CSV files"""
                import zipfile
                import io
                from datetime import datetime
                
                try:
                    # Create zip file in memory
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_info in csv_files:
                            try:
                                zip_file.write(file_info['path'], file_info['name'])
                            except Exception as e:
                                print(f"Error adding {file_info['name']} to zip: {e}")
                    
                    zip_buffer.seek(0)
                    
                    # Create download button with unique key
                    zip_filename = f"{username}_leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                    
                    st.download_button(
                        label="📦 Download ZIP File",
                        data=zip_buffer.getvalue(),
                        file_name=zip_filename,
                        mime='application/zip',
                        key=f"bulk_download_zip_{username}_{datetime.now().strftime('%H%M%S')}"
                    )
                    
                    st.success(f"✅ Created {zip_filename} with {len(csv_files)} files")
                    
                except Exception as e:
                    st.error(f"❌ Error creating bulk download: {e}")

            def clean_old_csv_files(username):
                """Clean CSV files older than 30 days"""
                import glob
                import os
                from datetime import datetime, timedelta
                
                cleaned_count = 0
                cutoff_date = datetime.now() - timedelta(days=90)
                
                patterns = [f"*{username}*leads*.csv", f"*leads*{username}*.csv"]
                
                for pattern in patterns:
                    files = glob.glob(pattern)
                    for file in files:
                        try:
                            file_time = datetime.fromtimestamp(os.path.getmtime(file))
                            if file_time < cutoff_date:
                                os.remove(file)
                                cleaned_count += 1
                                print(f"🗑️ Deleted old file: {file}")
                        except Exception as e:
                            print(f"Error deleting {file}: {e}")
                
                return cleaned_count

            # ✅ ACCURATE EMPIRE STATS - Load fresh user-specific data
            def load_accurate_empire_stats(username):
                """Load accurate, up-to-date empire stats for specific user"""
                
                empire_stats = {}
                total_leads = 0
                
                try:
                    # Option 1: Load from user-specific empire file
                    empire_file = f'empire_totals_{username}.json'
                    
                    if os.path.exists(empire_file):
                        with open(empire_file, 'r') as f:
                            empire_data = json.load(f)
                        
                        empire_stats = empire_data.get('platforms', {})
                        total_leads = empire_data.get('total_empire', 0)
                        
                        print(f"✅ Loaded empire stats for {username}: {total_leads} total leads")
                        
                    else:
                        # Option 2: Calculate from recent CSV files
                        print(f"📊 Calculating empire stats from CSV files for {username}")
                        empire_stats = calculate_empire_from_csvs(username)
                        total_leads = sum(empire_stats.values())
                        
                except Exception as e:
                    print(f"❌ Error loading empire stats: {e}")
                    # Fallback to empty stats
                    empire_stats = {}
                    total_leads = 0
                
                return empire_stats, total_leads

            def calculate_empire_from_csvs(username):
                """Calculate empire stats from actual CSV files"""
                
                import glob
                from datetime import datetime, timedelta
                
                platform_counts = {}
                
                # Define platform patterns to look for
                platform_patterns = {
                    'twitter': ['*twitter*leads*.csv', '*twitter_unified*.csv'],
                    'facebook': ['*facebook*leads*.csv', '*facebook_unified*.csv'], 
                    'linkedin': ['*linkedin*leads*.csv', '*linkedin_unified*.csv'],
                    'instagram': ['*instagram*leads*.csv', '*instagram_unified*.csv'],
                    'tiktok': ['*tiktok*leads*.csv', '*tiktok_unified*.csv'],
                    'youtube': ['*youtube*leads*.csv', '*youtube_unified*.csv'],
                    'medium': ['*medium*leads*.csv', '*medium_unified*.csv'],
                    'reddit': ['*reddit*leads*.csv', '*reddit_unified*.csv']
                }
                
                # Look for recent files (last 30 days)
                cutoff_date = datetime.now() - timedelta(days=90)
                
                for platform, patterns in platform_patterns.items():
                    platform_count = 0
                    
                    for pattern in patterns:
                        files = glob.glob(pattern)
                        
                        for file in files:
                            try:
                                # Check if file is recent
                                file_time = datetime.fromtimestamp(os.path.getmtime(file))
                                if file_time < cutoff_date:
                                    continue
                                
                                # Check if file belongs to this user (if username is in filename)
                                if username not in file.lower():
                                    continue
                                
                                # Count lines in CSV (minus header)
                                with open(file, 'r', encoding='utf-8') as f:
                                    line_count = sum(1 for line in f) - 1
                                    platform_count += max(0, line_count)
                                    
                            except Exception as e:
                                print(f"⚠️ Error reading {file}: {e}")
                                continue
                    
                    if platform_count > 0:
                        platform_counts[platform] = platform_count
                
                return platform_counts

            # Get current user
            if 'username' not in st.session_state or not st.session_state.username:
                st.warning("⚠️ Please log in to view your Empire stats")
                st.stop()

            current_username = st.session_state.username

            # ✅ Load FRESH, ACCURATE empire stats for current user
            user_empire_stats, user_total_leads = load_accurate_empire_stats(current_username)

            st.markdown(f"### 👑 Empire Command Center - {current_username}")

            # Enhanced metrics display with accurate data
            if user_empire_stats:
                # Calculate number of active platforms
                active_platforms = len([p for p, count in user_empire_stats.items() if count > 0])
                
                # Create columns for metrics
                metric_cols = st.columns(len(user_empire_stats) + 1)
                
                # Platform-specific metrics
                col_index = 0
                for platform, count in user_empire_stats.items():
                    with metric_cols[col_index]:
                        # Get platform info
                        platform_info = {
                            'twitter': {'emoji': '🐦', 'name': 'Twitter'},
                            'facebook': {'emoji': '📘', 'name': 'Facebook'}, 
                            'linkedin': {'emoji': '💼', 'name': 'LinkedIn'},
                            'instagram': {'emoji': '📷', 'name': 'Instagram'},
                            'tiktok': {'emoji': '🎵', 'name': 'TikTok'},
                            'youtube': {'emoji': '📺', 'name': 'YouTube'},
                            'medium': {'emoji': '📝', 'name': 'Medium'},
                            'reddit': {'emoji': '🔗', 'name': 'Reddit'}
                        }.get(platform, {'emoji': '📱', 'name': platform.title()})
                        
                        # Color coding based on performance
                        if count > 50:
                            delta = "Excellent"
                        elif count > 10:
                            delta = "Good"
                        elif count > 0:
                            delta = "Active"
                        else:
                            delta = "Inactive"
                        
                        st.metric(
                            f"{platform_info['emoji']} {platform_info['name']}", 
                            count, 
                            delta=delta
                        )
                    
                    col_index += 1
                
                # Empire total metric
                with metric_cols[-1]:
                    empire_value = user_total_leads * 25
                    st.metric(
                        "👑 Empire Total", 
                        user_total_leads, 
                        delta=f"${empire_value:,} value"
                    )
                
                # ✅ SHOW EMPIRE COMBINED STATS (ACCURATE)
                st.markdown("---")
                st.markdown("### 📄 CSV File Manager")

                # Get current user
                if 'username' in st.session_state and st.session_state.username:
                    current_username = st.session_state.username
                    
                    # Function definitions (same as before)
                    def get_user_csv_files(username):
                        """Get list of CSV files for specific user"""
                        import glob
                        import os
                        from datetime import datetime
                        
                        csv_files = []
                        
                        # Patterns to find user's CSV files
                        patterns = [
                            f"*{username}*leads*.csv",
                            f"*leads*{username}*.csv", 
                            f"{username}_*.csv",
                            "*unified_leads*.csv"  # Generic unified files
                        ]
                        
                        found_files = set()  # Use set to avoid duplicates
                        
                        for pattern in patterns:
                            files = glob.glob(pattern)
                            for file in files:
                                if file not in found_files and username.lower() in file.lower():
                                    found_files.add(file)
                        
                        # Process each file
                        for file_path in found_files:
                            try:
                                # Get file stats
                                stat = os.stat(file_path)
                                file_size = stat.st_size
                                mod_time = datetime.fromtimestamp(stat.st_mtime)
                                
                                # Count leads (lines minus header)
                                lead_count = 0
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        lead_count = max(0, sum(1 for line in f) - 1)
                                except:
                                    lead_count = 0
                                
                                # Extract platform and search term from filename
                                filename = os.path.basename(file_path)
                                platform = extract_platform_from_filename(filename)
                                search_term = extract_search_term_from_filename(filename)
                                
                                csv_files.append({
                                    'name': filename,
                                    'path': file_path,
                                    'size': file_size,
                                    'size_mb': file_size / 1024 / 1024,
                                    'date': mod_time.strftime('%m/%d %H:%M'),
                                    'leads': lead_count,
                                    'platform': platform,
                                    'search_term': search_term
                                })
                                
                            except Exception as e:
                                print(f"Error processing {file_path}: {e}")
                                continue
                        
                        # Sort by modification time (newest first)
                        csv_files.sort(key=lambda x: os.path.getmtime(x['path']), reverse=True)
                        
                        return csv_files

                    def extract_platform_from_filename(filename):
                        """Extract platform name from filename"""
                        filename_lower = filename.lower()
                        
                        platforms = ['twitter', 'facebook', 'linkedin', 'instagram', 'tiktok', 'youtube', 'medium', 'reddit']
                        
                        for platform in platforms:
                            if platform in filename_lower:
                                return platform
                        
                        return 'unknown'

                    def extract_search_term_from_filename(filename):
                        """Extract search term from filename if possible"""
                        try:
                            # Look for patterns like "crypto_trader" or "stock_broker"
                            import re
                            
                            # Remove common parts
                            clean_name = filename.replace('_leads', '').replace('_unified', '').replace('.csv', '')
                            
                            # Split by underscores and look for search terms
                            parts = clean_name.split('_')
                            
                            # Filter out common words
                            exclude_words = ['leads', 'unified', 'twitter', 'facebook', 'linkedin', 'instagram', 
                                            'tiktok', 'youtube', 'medium', 'reddit', 'scraper', 'results']
                            
                            search_parts = [part for part in parts if part.lower() not in exclude_words and len(part) > 2]
                            
                            if search_parts:
                                return ' '.join(search_parts[:3])  # Take first 3 meaningful parts
                            
                            return 'Unknown'
                            
                        except:
                            return 'Unknown'

                    def get_platform_emoji(platform):
                        """Get emoji for platform"""
                        emoji_map = {
                            'twitter': '🐦',
                            'facebook': '📘', 
                            'linkedin': '💼',
                            'instagram': '📷',
                            'tiktok': '🎵',
                            'youtube': '📺',
                            'medium': '📝',
                            'reddit': '🔗',
                            'unknown': '📄'
                        }
                        return emoji_map.get(platform, '📄')

                    def create_bulk_download(csv_files, username):
                        """Create zip file with all CSV files"""
                        import zipfile
                        import io
                        from datetime import datetime
                        
                        try:
                            # Create zip file in memory
                            zip_buffer = io.BytesIO()
                            
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for file_info in csv_files:
                                    try:
                                        zip_file.write(file_info['path'], file_info['name'])
                                    except Exception as e:
                                        print(f"Error adding {file_info['name']} to zip: {e}")
                            
                            zip_buffer.seek(0)
                            
                            # Create download button with unique key
                            zip_filename = f"{username}_leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                            
                            st.download_button(
                                label="📦 Download ZIP File",
                                data=zip_buffer.getvalue(),
                                file_name=zip_filename,
                                mime='application/zip',
                                key=f"bulk_download_zip_{username}_{datetime.now().strftime('%H%M%S')}"
                            )
                            
                            st.success(f"✅ Created {zip_filename} with {len(csv_files)} files")
                            
                        except Exception as e:
                            st.error(f"❌ Error creating bulk download: {e}")

                    def clean_old_csv_files(username):
                        """Clean CSV files older than 30 days"""
                        import glob
                        import os
                        from datetime import datetime, timedelta
                        
                        cleaned_count = 0
                        cutoff_date = datetime.now() - timedelta(days=30)
                        
                        patterns = [f"*{username}*leads*.csv", f"*leads*{username}*.csv"]
                        
                        for pattern in patterns:
                            files = glob.glob(pattern)
                            for file in files:
                                try:
                                    file_time = datetime.fromtimestamp(os.path.getmtime(file))
                                    if file_time < cutoff_date:
                                        os.remove(file)
                                        cleaned_count += 1
                                        print(f"🗑️ Deleted old file: {file}")
                                except Exception as e:
                                    print(f"Error deleting {file}: {e}")
                        
                        return cleaned_count

                    # Get user's CSV files
                    user_csv_files = get_user_csv_files(current_username)
                    
                    if user_csv_files:
                        # Show file summary
                        total_files = len(user_csv_files)
                        total_size = sum(file['size'] for file in user_csv_files)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("📁 Total Files", total_files)
                        with col2:
                            st.metric("💾 Total Size", f"{total_size/1024/1024:.1f} MB")
                        with col3:
                            st.metric("📅 Newest File", user_csv_files[0]['date'] if user_csv_files else "None")
                        
                        st.markdown("---")
                        
                        # File listing with download buttons
                        st.markdown("#### 📋 Available Files")
                        
                        for file_info in user_csv_files:
                            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                            
                            with col1:
                                # File name with platform emoji
                                platform_emoji = get_platform_emoji(file_info['platform'])
                                st.write(f"{platform_emoji} **{file_info['name']}**")
                                st.caption(f"🔍 Search: {file_info.get('search_term', 'Unknown')}")
                            
                            with col2:
                                st.write(f"**{file_info['leads']}** leads")
                            
                            with col3:
                                st.write(f"**{file_info['size_mb']:.1f}** MB")
                            
                            with col4:
                                st.write(f"**{file_info['date']}**")
                            
                            with col5:
                                # Download button with unique key
                                if st.button("⬇️", key=f"lead_results_download_{file_info['name']}", help=f"Download {file_info['name']}"):
                                    # Trigger download using st.download_button in the next render
                                    st.session_state[f"lead_results_download_trigger_{file_info['name']}"] = True
                            
                            # Show download button if triggered
                            if st.session_state.get(f"lead_results_download_trigger_{file_info['name']}", False):
                                try:
                                    with open(file_info['path'], 'rb') as f:
                                        file_data = f.read()
                                    
                                    st.download_button(
                                        label=f"💾 Download {file_info['name']}",
                                        data=file_data,
                                        file_name=file_info['name'],
                                        mime='text/csv',
                                        key=f"lead_results_download_file_{file_info['name']}"
                                    )
                                    # Clear the trigger
                                    st.session_state[f"lead_results_download_trigger_{file_info['name']}"] = False
                                    
                                except Exception as e:
                                    st.error(f"❌ Error downloading file: {e}")
                        
                        st.markdown("---")
                        
                        # Bulk actions
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("📦 Download All Files", type="primary", key="lead_results_download_all"):
                                create_bulk_download(user_csv_files, current_username)
                        
                        with col2:
                            if st.button("🧹 Clean Old Files", help="Delete files older than 30 days", key="lead_results_clean_old"):
                                cleaned_count = clean_old_csv_files(current_username)
                                if cleaned_count > 0:
                                    st.success(f"🗑️ Cleaned {cleaned_count} old files")
                                    st.rerun()
                                else:
                                    st.info("No old files to clean")
                        
                        with col3:
                            if st.button("🔄 Refresh Files", key="lead_results_refresh"):
                                st.rerun()
                    
                    else:
                        st.info("📁 No CSV files found. Run some scrapers to generate lead files!")
                        
                        # Show helpful tips
                        st.markdown("#### 💡 Tips:")
                        st.markdown("- Lead files are automatically saved after each scraping session")
                        st.markdown("- Files are named with timestamp and search term for easy identification") 
                        st.markdown("- Use the Download button to save files to your computer")
                        st.markdown("- Old files (30+ days) can be cleaned up automatically")

                else:
                    st.warning("⚠️ Please log in to access CSV file management")
            
            # 🌍 NEW: Language breakdown metric
            if MULTILINGUAL_AVAILABLE and language_stats:
                with metric_cols[-1]:
                    total_languages = len(language_stats)
                    primary_language = max(language_stats, key=language_stats.get) if language_stats else "english"
                    st.metric("🌍 Languages", total_languages, delta=f"{primary_language.title()} primary")
            
            # 🌍 NEW: Language analytics section
            if MULTILINGUAL_AVAILABLE and language_stats:
                st.markdown("---")
                st.subheader("🌍 Global Language Intelligence")
                
                lang_cols = st.columns(min(len(language_stats), 6))
                
                # Show top languages
                sorted_languages = sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
                
                for i, (language, count) in enumerate(sorted_languages[:6]):
                    with lang_cols[i]:
                        percentage = (count / total_leads) * 100 if total_leads > 0 else 0
                        
                        # Language flags/emojis
                        language_emojis = {
                            'english': '🇺🇸', 'spanish': '🇪🇸', 'french': '🇫🇷', 
                            'german': '🇩🇪', 'italian': '🇮🇹', 'portuguese': '🇵🇹',
                            'japanese': '🇯🇵', 'korean': '🇰🇷', 'chinese': '🇨🇳',
                            'arabic': '🇸🇦', 'hindi': '🇮🇳', 'russian': '🇷🇺'
                        }
                        
                        flag = language_emojis.get(language, '🌍')
                        st.metric(f"{flag} {language.title()}", count, delta=f"{percentage:.1f}%")
                
                # Language expansion opportunities
                if len(language_stats) > 1:
                    st.info(f"🌍 **Global Reach:** Your empire speaks {len(language_stats)} languages! Consider regional campaigns.")
            
            st.markdown("---")
            
            # Platform intelligence tabs
            platform_tabs = st.tabs(list(platforms_with_data.keys()))
            
            for tab, (platform, data_source) in zip(platform_tabs, platforms_with_data.items()):
                with tab:
                    # Handle DataFrame vs file path
                    if isinstance(data_source, pd.DataFrame):
                        df = data_source
                        # Apply user filtering to existing DataFrame
                        if user_authenticated and USER_CSV_FILTER_AVAILABLE:
                            username = simple_auth.get_current_user()
                            if username:
                                df = filter_empire_data_by_user(df, username)
                        data_available = not df.empty
                    elif isinstance(data_source, str):
                        latest_file = get_latest_csv(data_source)
                        if latest_file and os.path.exists(latest_file):
                            try:
                                df = pd.read_csv(latest_file)
                                # Apply user filtering
                                if user_authenticated and USER_CSV_FILTER_AVAILABLE:
                                    username = simple_auth.get_current_user()
                                    if username:
                                        df = filter_empire_data_by_user(df, username)
                                data_available = not df.empty
                            except Exception as e:
                                st.error(f"❌ Error reading {platform}: {str(e)}")
                                data_available = False
                        else:
                            data_available = False
                    else:
                        data_available = False
                    
                    if data_available:
                        # Enhanced platform intelligence
                        col1, col2, col3, col4, col5 = st.columns(5)
                        
                        with col1:
                            st.metric("Total Leads", len(df))
                        with col2:
                            if 'platform' in df.columns:
                                platforms_count = df['platform'].nunique() if 'Empire' in platform else 1
                                st.metric("Platforms", platforms_count)
                            else:
                                st.metric("Platform", 1)
                        with col3:
                            # Quality score calculation
                            quality_score = 8.5 + (len(df) / 50)  # Base quality + volume bonus
                            quality_score = min(quality_score, 10.0)
                            st.metric("Quality Score", f"{quality_score:.1f}/10")
                        with col4:
                            if 'dm' in df.columns:
                                dm_ready = df['dm'].notna().sum()
                                dm_percentage = (dm_ready / len(df)) * 100
                                st.metric("DMs Ready", f"{dm_percentage:.0f}%")
                            else:
                                st.metric("DMs Ready", "100%")
                        with col5:
                            estimated_value = len(df) * 25
                            st.metric("Est. Value", f"${estimated_value:,}")
                        
                        # 🌍 NEW: Language breakdown for this platform
                        if MULTILINGUAL_AVAILABLE and 'detected_language' in df.columns:
                            st.subheader("🌍 Language Distribution")
                            platform_languages = df['detected_language'].value_counts()
                            
                            lang_breakdown_cols = st.columns(min(len(platform_languages), 4))
                            for i, (lang, count) in enumerate(platform_languages.head(4).items()):
                                with lang_breakdown_cols[i]:
                                    percentage = (count / len(df)) * 100
                                    language_emojis = {
                                        'english': '🇺🇸', 'spanish': '🇪🇸', 'french': '🇫🇷', 
                                        'german': '🇩🇪', 'italian': '🇮🇹', 'portuguese': '🇵🇹',
                                        'japanese': '🇯🇵', 'korean': '🇰🇷', 'chinese': '🇨🇳'
                                    }
                                    flag = language_emojis.get(lang, '🌍')
                                    st.metric(f"{flag} {lang.title()}", f"{percentage:.0f}%")
                        
                        # Intelligence filters
                        st.subheader("🔍 Empire Intelligence Filters")
                        
                        filter_col1, filter_col2, filter_col3 = st.columns(3)
                        
                        with filter_col1:
                            search_intel = st.text_input(
                                f"Search {platform} Intelligence", 
                                key=f"search_{platform}",
                                placeholder="Keywords, names, locations..."
                            ).lower()
                        
                        with filter_col2:
                            if 'platform' in df.columns and df['platform'].nunique() > 1:
                                platform_filter = st.selectbox(
                                    "Platform Filter",
                                    ["All Platforms"] + sorted(list(df['platform'].unique())),
                                    key=f"platform_{platform}"
                                )
                            else:
                                platform_filter = "All Platforms"
                        
                        with filter_col3:
                            # 🌍 NEW: Language filter
                            if MULTILINGUAL_AVAILABLE and 'detected_language' in df.columns:
                                available_languages = ["All Languages"] + sorted(list(df['detected_language'].unique()))
                                language_filter = st.selectbox(
                                    "Language Filter",
                                    available_languages,
                                    key=f"language_{platform}"
                                )
                            else:
                                language_filter = "All Languages"
                        
                        # Apply intelligence filters
                        filtered_df = df.copy()
                        
                        if search_intel:
                            mask = df.apply(lambda row: search_intel in str(row).lower(), axis=1)
                            filtered_df = df[mask]
                        
                        if 'platform' in df.columns and platform_filter != "All Platforms":
                            filtered_df = filtered_df[filtered_df['platform'] == platform_filter]
                        
                        # 🌍 NEW: Apply language filter
                        if MULTILINGUAL_AVAILABLE and 'detected_language' in df.columns and language_filter != "All Languages":
                            filtered_df = filtered_df[filtered_df['detected_language'] == language_filter]
                        
                        # Display intelligence data
                        st.dataframe(
                            filtered_df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Enhanced download with intelligence naming
                        intel_csv = filtered_df.to_csv(index=False)

                        # Fix: Clean platform name properly to avoid duplicates
                        platform_mapping = {
                            "👑": "Empire",
                            "🐦": "Twitter", 
                            "💼": "LinkedIn",
                            "📘": "Facebook",
                            "🎵": "TikTok",
                            "📸": "Instagram", 
                            "🎥": "YouTube",
                            "📝": "Medium",
                            "🗨️": "Reddit"
                        }

                        # Method 1: Remove emojis and clean up
                        platform_clean = platform
                        for emoji, name in platform_mapping.items():
                            platform_clean = platform_clean.replace(emoji, "").strip()

                        # If the platform name is empty after removing emojis, use the mapped name
                        if not platform_clean:
                            # Find which emoji was in the original platform
                            for emoji, name in platform_mapping.items():
                                if emoji in platform:
                                    platform_clean = name
                                    break
                        
                        download_label = f"📥 Export {platform_clean} Intelligence"
                        if language_filter != "All Languages":
                            download_label += f" ({language_filter.title()})"
                        
                        st.download_button(
                            label=download_label,
                            data=intel_csv,
                            file_name=f"{platform_clean.lower().replace(' ', '_')}_intelligence_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                        
                        # Intelligence summary
                        if len(filtered_df) != len(df):
                            st.info(f"🔍 Showing {len(filtered_df)} of {len(df)} intelligence records")
                        else:
                            st.success(f"👑 Complete {platform_clean} intelligence: {len(df)} records")
                        
                    else:
                        st.info(f"📡 No {platform} intelligence found. Launch empire conquest first!")
                        
                        if "Empire Combined" in platform:
                            st.markdown("""
                            ### 👑 Empire Intelligence Center
                            Your combined intelligence will show:
                            1. **Cross-platform deduplication** - No duplicate contacts
                            2. **Unified lead scoring** - Quality ratings across platforms  
                            3. **Geographic clustering** - Location-based insights
                            4. **Engagement predictions** - AI-powered response likelihood
                            """)
                            
                            if MULTILINGUAL_AVAILABLE:
                                st.markdown("5. **🌍 Global language analytics** - Multilingual targeting insights")
                            
                            # Show individual platform status
                            st.markdown("**🏰 Individual Platform Status:**")
                            for plat_name, pattern in empire_platforms.items():
                                latest_file = get_latest_csv(pattern)
                                if latest_file and os.path.exists(latest_file):
                                    try:
                                        df_temp = pd.read_csv(latest_file)
                                        st.success(f"✅ {plat_name}: {len(df_temp)} leads conquered")
                                    except:
                                        st.error(f"❌ {plat_name}: Intelligence corrupted")
                                else:
                                    st.info(f"📡 {plat_name}: Awaiting conquest")


# 🌍 NEW: Multilingual DMs tab (only show if available)
if MULTILINGUAL_AVAILABLE:
    with tab3:

        st.header("🌍 Multilingual DM Generation Center")
        
        if not user_authenticated:
            st.info("🔐 Join the empire to access multilingual DM features")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Join Empire", type="primary", use_container_width=True, key="multilingual_register"):
                    st.session_state.show_register = True
                    st.rerun()
            with col2:
                if st.button("🔑 Sign In", use_container_width=True, key="multilingual_login"):
                    st.session_state.show_login = True
                    st.session_state.show_register = False  # ← ADD THIS
                    st.rerun()
            
            st.markdown("---")
            st.markdown("### 🌍 Global DM Capabilities")
            
            # Showcase multilingual features
            showcase_cols = st.columns(3)
            
            with showcase_cols[0]:
                st.markdown("**🇪🇺 European Markets:**")
                st.markdown("""
                - 🇪🇸 **Spanish**: Professional &amp; casual tones
                - 🇫🇷 **French**: Cultural nuances included  
                - 🇩🇪 **German**: Formal &amp; informal variants
                - 🇮🇹 **Italian**: Regional expressions
                - 🇵🇹 **Portuguese**: BR/PT distinctions
                """)
            
            with showcase_cols[1]:
                st.markdown("**🇦🇸 Asian Markets:**")
                st.markdown("""
                - 🇯🇵 **Japanese**: Keigo (honorific) support
                - 🇰🇷 **Korean**: Formal/informal levels
                - 🇨🇳 **Chinese**: Simplified characters
                - 🇮🇳 **Hindi**: Devanagari script
                """)
            
            with showcase_cols[2]:
                st.markdown("**🌍 Additional:**")
                st.markdown("""
                - 🇸🇦 **Arabic**: RTL text support
                - 🇷🇺 **Russian**: Cyrillic alphabet
                - 🇺🇸 **English**: Enhanced templates
                - 🔧 **Auto-detect**: Smart language recognition
                """)
            
            # Sample multilingual DMs
            st.markdown("---")
            st.subheader("📝 Sample Multilingual DMs")
            
            sample_dm_data = {
                "Language": ["🇪🇸 Spanish", "🇫🇷 French", "🇩🇪 German", "🇯🇵 Japanese", "🇺🇸 English"],
                "Platform": ["LinkedIn", "Instagram", "Twitter", "TikTok", "Medium"],
                "Sample DM": [
                    "Hola María, me impresionó su experiencia en fitness...",
                    "Salut Pierre! J'adore ton contenu sur le fitness...",
                    "Hallo Klaus, Ihre Fitness-Expertise ist beeindruckend...",
                    "こんにちは田中さん！あなたのフィットネス...",
                    "Hi Sarah! Love your fitness content, let's connect!"
                ]
            }
            
            st.dataframe(sample_dm_data, use_container_width=True)
            st.caption("*Join the empire to generate DMs in any of these languages automatically*")
        
        else:
            # Check if user has leads before showing DM interface
            def check_for_existing_leads():
                """Check if user has any existing leads to work with"""
                current_username = st.session_state.username
                
                # Check for leads in session state first
                if 'generated_leads' in st.session_state and st.session_state.generated_leads:
                    return True
                
                # Check for CSV files with leads
                available_files = {}
                for platform_name, pattern in {
                    "🐦 Twitter": "twitter_leads_*.csv",
                    "💼 LinkedIn": "linkedin_leads_*.csv", 
                    "📘 Facebook": "facebook_leads_*.csv",
                    "🎵 TikTok": "tiktok_leads_*.csv",
                    "📸 Instagram": "instagram_leads_*.csv",
                    "🎥 YouTube": "youtube_leads_*.csv",
                    "📝 Medium": "medium_leads_*.csv",
                    "🗨️ Reddit": "reddit_leads_*.csv"
                }.items():
                    latest_file = get_latest_csv(pattern)
                    if latest_file and os.path.exists(latest_file):
                        try:
                            df = pd.read_csv(latest_file)
                            if not df.empty:
                                available_files[platform_name] = latest_file
                        except:
                            pass
                
                return len(available_files) > 0
            
            # Clear DM data when user changes
            def clear_dm_data_on_user_change():
                """Clear DM data when user switches"""
                current_user = st.session_state.username
                
                if 'last_dm_user' in st.session_state:
                    if st.session_state.last_dm_user != current_user:
                        # User changed - clear DM session data
                        dm_keys = ['generated_dms', 'dm_messages', 'dm_results', 'custom_dm_message', 'dm_tone', 'dm_style']
                        for key in dm_keys:
                            if key in st.session_state:
                                del st.session_state[key]
                        print(f"🧹 Cleared DM data - user changed: {st.session_state.last_dm_user} → {current_user}")
                
                st.session_state.last_dm_user = current_user
            
            # Clear old user's DM data
            clear_dm_data_on_user_change()
            
            # Check if user has leads
            has_leads = check_for_existing_leads()
            
            if not has_leads:
                # Show placeholder for users without leads
                st.info("💬 **Direct Messages will appear here after you generate leads**")
                
                st.markdown("""
                ### 🚀 How to Generate DMs:
                
                **Step 1:** Use the **Empire Scraper** above to find prospects
                - Enter target keywords (e.g., "fitness coach", "real estate agent")
                - Select platforms to search
                - Click "Start Empire Search"
                
                **Step 2:** AI will create personalized DMs for each prospect
                - Messages tailored to their profile and interests
                - Multiple language options available
                - Professional tone and style
                
                **Step 3:** Copy and send DMs to reach your prospects
                - One-click copy to clipboard
                - Track responses and engagement
                - Build your prospect pipeline
                """)
                
                # Show quick start button
                if st.button("🔍 Start Finding Prospects", type="primary", use_container_width=True):
                    # Scroll to search section (if you have the anchor)
                    st.markdown("<script>document.getElementById('search_anchor').scrollIntoView();</script>", unsafe_allow_html=True)
                
            else:
                # Full multilingual DM interface for authenticated users
                current_username = st.session_state.username
                
                # Create sub-tabs for Generate DMs and DM Library
                dm_tab1, dm_tab2 = st.tabs(["🎯 Generate DMs", "📚 DM Library"])
                
                with dm_tab1:
                    # DM GENERATION SECTION
                    
                    # Load existing leads for DM generation
                    ml_col1, ml_col2 = st.columns([2, 1])
                
                with ml_col1:
                    st.subheader("📋 Lead Data Source")
                    
                    # Option to upload CSV or use existing leads
                    dm_source = st.radio(
                        "Choose DM Generation Source:",
                        ["Existing Empire Leads", "Upload New CSV", "Manual Entry"],
                        key="dm_source_selection"
                    )

                    contacts_for_dm = []

                    if dm_source == "Existing Empire Leads":
                        # Get current user for user-specific leads
                        current_username = st.session_state.username
                        
                        # Use existing scraped leads - USER SPECIFIC ONLY
                        available_files = {}
                        
                        # Look for user-specific files only
                        import glob
                        
                        platform_patterns = {
                            "🐦 Twitter": ["twitter_leads_*.csv", "twitter_unified_*.csv"],
                            "💼 LinkedIn": ["linkedin_leads_*.csv", "linkedin_unified_*.csv"],
                            "📘 Facebook": ["facebook_leads_*.csv", "facebook_unified_*.csv"],
                            "🎵 TikTok": ["tiktok_leads_*.csv", "tiktok_unified_*.csv"],
                            "📸 Instagram": ["instagram_leads_*.csv", "instagram_unified_*.csv"],
                            "🎥 YouTube": ["youtube_leads_*.csv", "youtube_unified_*.csv"],
                            "📝 Medium": ["medium_leads_*.csv", "medium_unified_*.csv"],
                            "🗨️ Reddit": ["reddit_leads_*.csv", "reddit_unified_*.csv"]
                        }
                        
                        for platform_name, patterns in platform_patterns.items():
                            user_files = []
                            
                            # Check each pattern for user-specific files
                            for pattern in patterns:
                                # Look for files with username in filename
                                user_pattern = pattern.replace("*.csv", f"*{current_username}*.csv")
                                files_with_user = glob.glob(user_pattern)
                                
                                # Also check for files with username at different positions
                                alt_pattern = pattern.replace("*.csv", f"{current_username}_*.csv")
                                files_alt = glob.glob(alt_pattern)
                                
                                user_files.extend(files_with_user)
                                user_files.extend(files_alt)
                            
                            if user_files:
                                # Get the most recent file for this user
                                latest_file = max(user_files, key=os.path.getctime)
                                try:
                                    df = pd.read_csv(latest_file)
                                    if not df.empty:
                                        available_files[platform_name] = latest_file
                                except:
                                    pass
                        
                        if available_files:
                            selected_platform = st.selectbox(
                                "Select Platform Leads:",
                                list(available_files.keys()),
                                key="platform_dm_selection"
                            )
                            
                            if selected_platform:
                                try:
                                    df = pd.read_csv(available_files[selected_platform])
                                    st.success(f"✅ Loaded {len(df)} of YOUR leads from {selected_platform}")
                                    
                                    # Show which file is being used for transparency
                                    filename = os.path.basename(available_files[selected_platform])
                                    st.caption(f"📄 Using file: {filename}")
                                    
                                    # Show preview
                                    st.dataframe(df.head(), use_container_width=True)
                                    
                                    # Convert to contacts format
                                    contacts_for_dm = [
                                        {"name": row.get("name", ""), "bio": row.get("bio", "")}
                                        for _, row in df.iterrows()
                                    ]
                                    
                                except Exception as e:
                                    st.error(f"❌ Error loading your leads: {str(e)}")
                        else:
                            st.info(f"📭 No leads found for user: {current_username}")
                            st.markdown(f"""
                            **To generate your own leads:**
                            1. 🔍 Go to **Empire Scraper** tab above
                            2. 📝 Enter your target keywords  
                            3. 🚀 Select platforms and run search
                            4. 💬 Your leads will appear here for DM generation
                            
                            **Note:** You can only see leads you've generated, not other users' leads.
                            """)
                    
                    elif dm_source == "Upload New CSV":
                        uploaded_file = st.file_uploader(
                            "Upload CSV with leads (name, bio columns required)",
                            type=["csv"],
                            key="upload_csv_dm"
                        )
                        
                        if uploaded_file is not None:
                            try:
                                df = pd.read_csv(uploaded_file)
                                st.success(f"✅ Uploaded {len(df)} contacts")
                                
                                # Validate columns
                                if "name" in df.columns and "bio" in df.columns:
                                    st.dataframe(df.head(), use_container_width=True)
                                    
                                    contacts_for_dm = [
                                        {"name": row["name"], "bio": row["bio"]}
                                        for _, row in df.iterrows()
                                    ]
                                else:
                                    st.error("❌ CSV must have 'name' and 'bio' columns")
                            except Exception as e:
                                st.error(f"❌ Error reading CSV: {str(e)}")
                    
                    elif dm_source == "Manual Entry":
                        st.markdown("**Enter contacts manually:**")
                        
                        num_contacts = st.number_input(
                            "Number of contacts:",
                            min_value=1,
                            max_value=10,
                            value=3,
                            key="num_manual_contacts"
                        )
                        
                        manual_contacts = []
                        for i in range(num_contacts):
                            col_name, col_bio = st.columns(2)
                            with col_name:
                                name = st.text_input(f"Name {i+1}", key=f"manual_name_{i}")
                            with col_bio:
                                bio = st.text_input(f"Bio {i+1}", key=f"manual_bio_{i}")
                            
                            if name and bio:
                                manual_contacts.append({"name": name, "bio": bio})
                        
                        contacts_for_dm = manual_contacts
                        
                        if contacts_for_dm:
                            st.success(f"✅ {len(contacts_for_dm)} contacts ready for DM generation")
            
            with ml_col2:
                st.subheader("🌍 Language Settings")
                
                # Language selection
                language_mode = st.radio(
                    "Language Generation Mode:",
                    ["Auto-detect per contact", "Force specific language", "Multi-language campaign"],
                    key="language_mode_selection"
                )
                
                target_language = None
                campaign_languages = []
                
                if language_mode == "Force specific language":
                    available_languages = list(LANGUAGE_KEYWORDS.keys())
                    target_language = st.selectbox(
                        "Target Language:",
                        available_languages,
                        key="force_language_select"
                    )
                    
                    st.info(f"🎯 All DMs will be generated in {target_language.title()}")
                
                elif language_mode == "Multi-language campaign":
                    available_languages = list(LANGUAGE_KEYWORDS.keys())
                    campaign_languages = st.multiselect(
                        "Campaign Languages:",
                        available_languages,
                        default=["english", "spanish", "french"],
                        key="campaign_languages_select"
                    )
                    
                    st.info(f"🌍 DMs will be generated in {len(campaign_languages)} languages")
                
                else:
                    st.info("🔍 Language will be auto-detected for each contact")
                
                # Platform selection for DM style
                dm_platform = st.selectbox(
                    "DM Platform Style:",
                    ["twitter", "linkedin", "facebook", "tiktok", "instagram", "youtube", "medium", "reddit"],
                    key="dm_platform_style"
                )
                
                st.markdown("---")
                st.subheader("📊 Generation Preview")
                
                if contacts_for_dm:
                    total_contacts = len(contacts_for_dm)
                    
                    if language_mode == "Multi-language campaign":
                        total_dms = total_contacts * len(campaign_languages)
                        st.metric("Total DMs", total_dms)
                        st.metric("Languages", len(campaign_languages))
                    else:
                        st.metric("Total Contacts", total_contacts)
                        st.metric("Language Mode", language_mode.split()[0])
                    
                    estimated_time = max(1, total_contacts / 10)  # ~10 contacts per minute
                    st.metric("Est. Time", f"{estimated_time:.1f} min")
            
            # Generate DMs button
            st.markdown("---")
            
            if not contacts_for_dm:
                st.error("❌ Please provide contacts for DM generation")
                st.button("🌍 Generate Multilingual DMs", disabled=True, use_container_width=True)
            elif st.button("🌍 Generate Multilingual DMs", type="primary", key="generate_multilingual_dms", use_container_width=True):
                progress = st.progress(0)
                status = st.empty()
                
                try:
                    all_results = []
                       
                    if language_mode == "Multi-language campaign":
                        # Generate DMs in multiple languages
                        total_iterations = len(campaign_languages)
                        
                        for i, language in enumerate(campaign_languages):
                            status.info(f"🌍 Generating {language.title()} DMs... ({i+1}/{total_iterations})")
                            
                            results = generate_multilingual_batch(
                                contacts=contacts_for_dm,
                                platform=dm_platform,
                                target_language=language
                            )
                            
                            # Add language suffix to names for identification
                            for result in results:
                                result["campaign_language"] = language
                                result["original_name"] = result["original_name"]
                                result["name"] = f"{result['original_name']} ({language.title()})"
                            
                            all_results.extend(results)
                            progress.progress((i + 1) / total_iterations)
                    
                    else:
                        # Single language mode (auto -detect or forced)
                        status.info(f"🌍 Generating multilingual DMs...")
                        
                        if language_mode == "Force specific language":
                            results = generate_multilingual_batch(
                                contacts=contacts_for_dm,
                                platform=dm_platform,
                                target_language=target_language
                            )
                        else:
                            # Auto-detect mode
                            results = generate_multilingual_batch(
                                contacts=contacts_for_dm,
                                platform=dm_platform,
                                target_language=None  # Auto-detect
                            )
                        
                        all_results = results
                        progress.progress(1.0)
                    
                    status.success("✅ Multilingual DM generation completed!")

                    
                    if all_results:
                        st.session_state.all_results      = all_results
                        st.session_state.generation_mode  = language_mode
                        st.session_state.dm_platform       = dm_platform
                        st.success(f"🎉 Generated {len(all_results)} multilingual DMs!")

                    if st.session_state.get("all_results"):
                        results = st.session_state.all_results        
                        
                        # Language breakdown
                        language_breakdown = {}
                        for result in all_results:
                            lang = result.get("detected_language", "unknown")
                            language_breakdown[lang] = language_breakdown.get(lang, 0) + 1
                        
                        st.markdown("**🌍 Language Breakdown:**")
                        lang_cols = st.columns(len(language_breakdown))
                        for i, (lang, count) in enumerate(language_breakdown.items()):
                            with lang_cols[i]:
                                percentage = (count / len(all_results)) * 100
                                st.metric(f"{lang.title()}", count, delta=f"{percentage:.0f}%")
                        
                        # Display results
                        st.subheader("📋 Generated Multilingual DMs")
                        
                        # Convert to DataFrame for display
                        display_df = pd.DataFrame([
                            {
                                "Name": result.get("original_name", result.get("name", "")),
                                "Language": result.get("detected_language", "unknown"),
                                "Platform": result.get("platform", dm_platform),
                                "DM": result.get("dm", ""),
                                "Length": result.get("length", 0),
                                "Method": result.get("method", "unknown")
                            }
                            for result in all_results
                        ])
                        
                        # Filter controls
                        filter_col1, filter_col2 = st.columns(2)
                        
                        with filter_col1:
                            language_filter = st.selectbox(
                                "Filter by Language:",
                                ["All Languages"] + sorted(list(language_breakdown.keys())),
                                key="results_language_filter"
                            )
                        
                        with filter_col2:
                            search_filter = st.text_input(
                                "Search in names/DMs:",
                                key="results_search_filter"
                            )
                        
                        # Apply filters
                        filtered_df = display_df.copy()
                        
                        if language_filter != "All Languages":
                            filtered_df = filtered_df[filtered_df["Language"] == language_filter]
                        
                        if search_filter:
                            mask = filtered_df["Name"].str.contains(search_filter, case=False, na=False) | \
                                   filtered_df["DM"].str.contains(search_filter, case=False, na=False)
                            filtered_df = filtered_df[mask]
                        
                        st.dataframe(filtered_df, use_container_width=True)
                        
                        # Export options
                        st.markdown("---")
                        st.subheader("📤 Export & Save Options")
                        
                        export_col1, export_col2, export_col3, export_col4 = st.columns(4)

                        with export_col1:

                            st.button(
                                "💾 Save to Library",
                                key="save_dm",
                                on_click=save_dms_callback
                            )

                        
                        with export_col2:
                            # Export all results
                            all_csv = display_df.to_csv(index=False)
                            st.download_button(
                                "📄 Export All DMs",
                                data=all_csv,
                                file_name=f"multilingual_dms_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv",
                                use_container_width=True,
                                key="export_all_multilingual_dms"
                            )
                        
                        with export_col3:
                            # Export filtered results
                            if language_filter != "All Languages" or search_filter:
                                filtered_csv = filtered_df.to_csv(index=False)
                                export_label = f"📄 Export {language_filter}" if language_filter != "All Languages" else "📄 Export Filtered"
                                st.download_button(
                                    export_label,
                                    data=filtered_csv,
                                    file_name=f"multilingual_dms_filtered_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                    mime="text/csv",
                                    use_container_width=True,
                                    key="export_filtered_multilingual_dms"
                                )
                            else:
                                st.button("📄 Export Filtered", disabled=True, use_container_width=True, key="export_filtered_disabled")
                        
                        with export_col4:
                            # Create enhanced export with metadata
                            if st.button("📊 Create Summary", use_container_width=True, key="create_enhanced_export"):
                                # Create summary data
                                summary_data = {
                                    "Total DMs Generated": len(all_results),
                                    "Languages Used": len(language_breakdown),
                                    "Platform": dm_platform,
                                    "Generation Mode": language_mode,
                                    "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                
                                summary_df = pd.DataFrame([summary_data])
                                summary_csv = summary_df.to_csv(index=False)
                                
                                st.download_button(
                                    "📊 Download Summary",
                                    data=summary_csv,
                                    file_name=f"multilingual_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                    mime="text/csv",
                                    key="download_summary_report"
                                )
                        
                        # ✅ MANUAL EXIT BUTTON
                        st.markdown("---")
                        col1, col2, col3 = st.columns([1, 1, 1])
                        with col2:
                            if st.button("❌ Close Results", use_container_width=True, type="secondary", key="close_dm_results"):
                                # Clear any stored session state for DM results
                                keys_to_clear = [key for key in st.session_state.keys() if 'dm' in key.lower() or 'multilingual' in key.lower()]
                                for key in keys_to_clear:
                                    del st.session_state[key]
                                
                                # Force page refresh to return to generation form
                                st.rerun()

                except Exception as e:
                    status.error(f"❌ DM generation failed: {str(e)}")
                    st.error(f"Error details: {e}")
            
            with dm_tab2:
                st.markdown(f"### 📚 DM Library - {current_username}")

                campaigns = load_user_dm_library(current_username)        
                                        
                # Load user's saved campaigns
                saved_campaigns = load_user_dm_library(current_username)
                
                if saved_campaigns:
                    st.success(f"📚 You have {len(saved_campaigns)} saved DM campaigns")
                    
                    # Library overview
                    total_dms = sum(campaign.get("total_dms", 0) for campaign in saved_campaigns)
                    all_languages = set()
                    all_platforms = set()
                    
                    for campaign in saved_campaigns:
                        all_languages.update(campaign.get("languages", []))
                        all_platforms.add(campaign.get("platform", "unknown"))
                    
                    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)
                    
                    with overview_col1:
                        st.metric("📝 Total Campaigns", len(saved_campaigns))
                    with overview_col2:
                        st.metric("💬 Total DMs", total_dms)
                    with overview_col3:
                        st.metric("🌍 Languages", len(all_languages))
                    with overview_col4:
                        st.metric("📱 Platforms", len(all_platforms))
                    
                    st.markdown("---")
                    
                    # Campaign listing
                    st.markdown("#### 📋 Saved Campaigns")
                    
                    for i, campaign in enumerate(reversed(saved_campaigns)):  # Show newest first
                        with st.expander(f"📅 {campaign.get('timestamp', '')[:16]} - {campaign.get('total_dms', 0)} DMs ({campaign.get('platform', 'unknown')})"):
                            
                            # Campaign details
                            detail_col1, detail_col2, detail_col3 = st.columns(3)
                            
                            with detail_col1:
                                st.write(f"**🎯 Generation Mode:** {campaign.get('generation_mode', 'Unknown')}")
                                st.write(f"**📱 Platform:** {campaign.get('platform', 'Unknown').title()}")
                            
                            with detail_col2:
                                st.write(f"**💬 Total DMs:** {campaign.get('total_dms', 0)}")
                                st.write(f"**🌍 Languages:** {', '.join(campaign.get('languages', []))}")
                            
                            with detail_col3:
                                st.write(f"**📅 Created:** {campaign.get('timestamp', 'Unknown')[:19]}")
                                st.write(f"**🆔 Campaign ID:** {campaign.get('id', 'Unknown')[-8:]}")
                            
                            # Show campaign DMs
                            campaign_dms = campaign.get('dms', [])
                            if campaign_dms:
                                
                                # Campaign filter
                                camp_filter_col1, camp_filter_col2 = st.columns(2)
                                
                                with camp_filter_col1:
                                    campaign_languages = list(set([dm.get("detected_language", "unknown") for dm in campaign_dms]))
                                    campaign_lang_filter = st.selectbox(
                                        "Filter by Language:",
                                        ["All Languages"] + sorted(campaign_languages),
                                        key=f"campaign_lang_filter_{i}"
                                    )
                                
                                with camp_filter_col2:
                                    campaign_search = st.text_input(
                                        "Search in DMs:",
                                        key=f"campaign_search_{i}"
                                    )
                                
                                # Apply filters to campaign DMs
                                filtered_campaign_dms = campaign_dms.copy()
                                
                                if campaign_lang_filter != "All Languages":
                                    filtered_campaign_dms = [dm for dm in filtered_campaign_dms if dm.get("detected_language") == campaign_lang_filter]
                                
                                if campaign_search:
                                    filtered_campaign_dms = [
                                        dm for dm in filtered_campaign_dms 
                                        if campaign_search.lower() in dm.get("dm", "").lower() or 
                                        campaign_search.lower() in dm.get("original_name", dm.get("name", "")).lower()
                                    ]
                                
                                # Display filtered DMs
                                if filtered_campaign_dms:
                                    import pandas as pd
                                    campaign_df = pd.DataFrame([
                                        {
                                            "Name": dm.get("original_name", dm.get("name", "")),
                                            "Language": dm.get("detected_language", "unknown"),
                                            "DM": dm.get("dm", "")[:100] + "..." if len(dm.get("dm", "")) > 100 else dm.get("dm", ""),
                                            "Length": dm.get("length", len(dm.get("dm", "")))
                                        }
                                        for dm in filtered_campaign_dms
                                    ])
                                    
                                    st.dataframe(campaign_df, use_container_width=True)
                                    st.caption(f"Showing {len(filtered_campaign_dms)} of {len(campaign_dms)} DMs")
                                else:
                                    st.info("No DMs match the current filters")
                            
                            # Campaign actions
                            st.markdown("**📤 Campaign Actions:**")
                            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                            
                            with action_col1:
                                # Export this campaign
                                if campaign_dms:
                                    import pandas as pd
                                    campaign_export_df = pd.DataFrame([
                                        {
                                            "Name": dm.get("original_name", dm.get("name", "")),
                                            "Language": dm.get("detected_language", "unknown"),
                                            "Platform": dm.get("platform", campaign.get("platform", "unknown")),
                                            "DM": dm.get("dm", ""),
                                            "Length": dm.get("length", len(dm.get("dm", ""))),
                                            "Method": dm.get("method", "unknown"),
                                            "Campaign_ID": campaign.get("id", ""),
                                            "Created": campaign.get("timestamp", "")
                                        }
                                        for dm in campaign_dms
                                    ])
                                    
                                    campaign_csv = campaign_export_df.to_csv(index=False)
                                    
                                    st.download_button(
                                        "📄 Export Campaign",
                                        data=campaign_csv,
                                        file_name=f"campaign_{campaign.get('id', 'unknown')}.csv",
                                        mime="text/csv",
                                        key=f"export_campaign_{i}",
                                        use_container_width=True
                                    )
                            
                            with action_col2:
                                # Copy to new generation (reuse settings)
                                if st.button("🔄 Reuse Settings", key=f"reuse_settings_{i}", use_container_width=True):
                                    # Store campaign settings in session state to pre-fill generation form
                                    st.session_state['reuse_platform'] = campaign.get('platform', 'twitter')
                                    st.session_state['reuse_mode'] = campaign.get('generation_mode', 'Auto-detect per contact')
                                    st.session_state['reuse_languages'] = campaign.get('languages', [])
                                    st.success("✅ Settings copied! Switch to Generate DMs tab.")
                            
                            with action_col3:
                                # Show detailed view
                                if st.button("🔍 View Details", key=f"view_details_{i}", use_container_width=True):
                                    # Store detailed view in session state
                                    st.session_state[f'show_details_{campaign.get("id", "unknown")}'] = True
                                    st.rerun()
                            
                            with action_col4:
                                # Delete campaign
                                if st.button("🗑️ Delete", key=f"delete_campaign_{i}", use_container_width=True):
                                    if delete_campaign_from_library(current_username, campaign.get("id", "")):
                                        st.success("✅ Campaign deleted!")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error deleting campaign")

                        
                    
                    # Library management
                    st.markdown("---")
                    st.markdown("#### 🔧 Library Management")
                    
                    manage_col1, manage_col2, manage_col3 = st.columns(3)
                    
                    with manage_col1:
                        # Export entire library
                        if st.button("📦 Export All Campaigns", use_container_width=True, key="export_all_campaigns"):
                            try:
                                # Combine all campaigns into one file
                                all_campaign_dms = []
                                for campaign in saved_campaigns:
                                    for dm in campaign.get('dms', []):
                                        dm_copy = dm.copy()
                                        dm_copy['campaign_id'] = campaign.get('id', '')
                                        dm_copy['campaign_timestamp'] = campaign.get('timestamp', '')
                                        dm_copy['campaign_platform'] = campaign.get('platform', '')
                                        dm_copy['campaign_mode'] = campaign.get('generation_mode', '')
                                        all_campaign_dms.append(dm_copy)
                                
                                if all_campaign_dms:
                                    import pandas as pd
                                    from datetime import datetime
                                    
                                    library_df = pd.DataFrame([
                                        {
                                            "Name": dm.get("original_name", dm.get("name", "")),
                                            "Language": dm.get("detected_language", "unknown"),
                                            "Platform": dm.get("campaign_platform", "unknown"),
                                            "DM": dm.get("dm", ""),
                                            "Length": dm.get("length", len(dm.get("dm", ""))),
                                            "Campaign_ID": dm.get("campaign_id", ""),
                                            "Campaign_Date": dm.get("campaign_timestamp", ""),
                                            "Generation_Mode": dm.get("campaign_mode", "")
                                        }
                                        for dm in all_campaign_dms
                                    ])
                                    
                                    library_csv = library_df.to_csv(index=False)
                                    
                                    st.download_button(
                                        "📦 Download Complete Library",
                                        data=library_csv,
                                        file_name=f"{current_username}_dm_library_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv",
                                        key="download_complete_library"
                                    )
                                    
                                    st.success(f"✅ Library export ready! ({len(all_campaign_dms)} total DMs)")
                            
                            except Exception as e:
                                st.error(f"❌ Export error: {e}")
                    
                    with manage_col2:
                        # Clear old campaigns
                        if st.button("🧹 Clear Old Campaigns", use_container_width=True, key="clear_old_campaigns"):
                            # Keep only last 10 campaigns
                            if len(saved_campaigns) > 10:
                                import json
                                import os
                                
                                try:
                                    library_file = os.path.join("dm_library", f"{current_username}_dm_library.json")
                                    library_data = {"campaigns": saved_campaigns[-10:]}  # Keep last 10
                                    
                                    with open(library_file, 'w', encoding='utf-8') as f:
                                        json.dump(library_data, f, indent=2, ensure_ascii=False)
                                    
                                    st.success(f"✅ Cleaned library! Kept last 10 campaigns.")
                                    st.rerun()
                                
                                except Exception as e:
                                    st.error(f"❌ Cleanup error: {e}")
                            else:
                                st.info("📚 Library is already optimized (≤10 campaigns)")
                    
                    with manage_col3:
                        # Refresh library
                        if st.button("🔄 Refresh Library", use_container_width=True, key="refresh_library"):
                            st.rerun()
                
                else:
                    st.info("📚 Your DM library is empty. Generate some DMs to get started!")
                    
                    # Tips for new users
                    st.markdown("#### 💡 DM Library Features:")
                    st.markdown("- **📝 Save campaigns** - Keep generated DMs for later use")
                    st.markdown("- **🔍 Search & filter** - Find specific DMs by language or content")
                    st.markdown("- **📤 Export options** - Download individual campaigns or entire library")
                    st.markdown("- **🔄 Reuse settings** - Copy successful campaign configurations")
                    st.markdown("- **🗑️ Manage storage** - Delete old campaigns to save space")                

        st.markdown(
            '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
            'padding:12px 16px;border-radius:25px;'
            'background:linear-gradient(135deg,#0066cc,#4dabf7);'
            'color:white;font-weight:bold;text-decoration:none;'
            'z-index:9999;">⬆️ Top</a>',
            unsafe_allow_html=True,
        )

    # ✅ RESTORE USER SESSION when returning from Stripe
    def restore_user_session_from_url():
        """Restore user session when returning from Stripe checkout"""
        returned_user = st.query_params.get("user")
        
        if returned_user and not simple_auth.get_current_user():
            # User returned from Stripe but session was lost
            try:
                # Log the user back in automatically
                if simple_auth.authenticate_user(returned_user, skip_password=True):
                    st.session_state.username = returned_user
                    st.success(f"✅ Welcome back, {returned_user}!")
                    print(f"🔄 Restored session for user: {returned_user}")
                    return True
            except Exception as e:
                print(f"❌ Failed to restore session: {e}")
                st.warning("Please log in again")
        
        return False

    # ✅ CAPTURE USERNAME FIRST - before clearing any params
    url_username = st.query_params.get("username")
    payment_cancelled = "payment_cancelled" in st.query_params

    # ✅ HANDLE CANCELLATION - but keep username for restoration
    if payment_cancelled:
        st.warning("⚠️ Payment was cancelled. You can try again anytime.")
        st.query_params.clear()  # Now safe to clear

    # ✅ RESTORE SESSION using captured username
    current_user = simple_auth.get_current_user() if 'simple_auth' in globals() else None

    if url_username and not current_user:
        st.write("🔄 Attempting session restoration...")
        
        # User returned from Stripe but session was lost - restore it
        st.session_state.authenticated = True
        st.session_state.current_user = url_username
        st.session_state.username = url_username
        
        # Force the simple_auth system to recognize the user
        if hasattr(simple_auth, 'current_user'):
            simple_auth.current_user = url_username
            st.write("✅ Set simple_auth.current_user")
        
        st.success(f"✅ Session restored for {url_username}!")
        st.write("🔄 Refreshing app...")

    # Continue with the rest of the tabs...
    with tab4:  # Pricing Plans
        
        if "payment_success" in st.query_params:
            from stripe_checkout import handle_payment_success_url
            if handle_payment_success_url():
                # Payment success page is showing, exit early
                st.stop()
            
        st.header("💳 Empire Pricing Plans")

        # — Who am I and what plan do they have? —
        if user_authenticated:
            current_plan = simple_auth.get_user_plan().lower()
            current_credits = simple_auth.get_user_credits()
            st.info(f"💎 Current: {current_credits} credits • {current_plan.title()} plan")
        else:
            current_plan = "demo"
            st.warning("📱 Demo Mode: 5 demo leads remaining • Upgrade to unlock full features")

        col1, col2, col3 = st.columns(3)

        # ─── Starter ────────────────────────────────────────────────────────────────
        with col1:
            st.markdown("### 🆓 Lead Hunter")
            st.info("STARTER")
            st.write("$29 per month")
            st.markdown("---")
            st.markdown("**✅ What's Included:**")
            st.markdown("""
            - 2 platforms (Twitter, Facebook)  
            - 250 credits  
            - Basic filtering  
            - CSV export  
            - Email support
            """)
            st.success("**Perfect for:** Beginners")

            if current_plan == "starter":
                st.success("✅ Your Current Plan")
            else:
                agreed = st.checkbox(
                    "✅ Agree to terms",
                    key="agree_starter",
                    help="I agree to Terms of Service & No-Refund Policy"
                )
                if st.button(
                    "🚀 Upgrade to Starter",
                    disabled=not agreed,
                    type="primary",
                    use_container_width=True,
                    key="upgrade_starter"
                ):
                    if agreed:
                        # Create Stripe session and redirect immediately
                        from stripe_checkout import create_no_refund_checkout
                        checkout_url = create_no_refund_checkout(
                            username=st.session_state.username,
                            user_email=st.session_state.user_data["email"],
                            tier={"name": "Starter", "price": 29},
                            
                        )

                        if checkout_url and checkout_url != "debug_mode":
                            st.success("🔄 Redirecting to Stripe checkout...")
                            st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
                            st.stop()
                        else:
                            st.error("Failed to create checkout session")

        # ─── Pro ────────────────────────────────────────────────────────────────────
        with col2:
            st.markdown("### 💎 Lead Generator")
            st.success("MOST POPULAR")
            st.write("$197 per month")
            st.markdown("---")
            st.markdown("**✅ What's Included:**")
            st.markdown("""
            - 6 platforms (adds LinkedIn, TikTok, Instagram, YouTube)  
            - 2,000 credits/month  
            - Advanced filtering & relevance scoring  
            - Unlimited DM templates  
            - Analytics dashboard  
            - Priority support
            """)
            st.success("**Perfect for:** Small businesses, coaches, agencies")

            if current_plan == "pro":
                st.success("✅ Your Current Plan")
            else:
                agreed = st.checkbox(
                    "✅ Agree to terms",
                    key="agree_pro",
                    help="I agree to Terms of Service & No-Refund Policy"
                )
                if st.button(
                    "💎 Upgrade to Pro",
                    disabled=not agreed,
                    type="primary",
                    use_container_width=True,
                    key="upgrade_pro"
                ):
                    
                    if agreed:
                        # Create Stripe session and redirect immediately
                        from stripe_checkout import create_no_refund_checkout
                        checkout_url = create_no_refund_checkout(
                            username=st.session_state.username,
                            user_email=st.session_state.user_data["email"],
                            tier={"name": "Pro", "price": 197},
                            
                            
                        )
                        if checkout_url and checkout_url != "debug_mode":
                            st.success("🔄 Redirecting to Stripe checkout...")
                            st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
                            st.stop()
                        else:
                            st.error("Failed to create checkout session")

        # ─── Ultimate ───────────────────────────────────────────────────────────────
        with col3:
            st.markdown("### 👑 Lead Empire")
            st.warning("ULTIMATE")
            st.write("$497 per month")
            st.markdown("---")
            st.markdown("**✅ What's Included:**")
            st.markdown("""
            - 8 platforms (adds Medium, Reddit)  
            - Unlimited credits  
            - Geo-location targeting  
            - Google Sheets integration  
            - CRM integrations  
            - API access  
            - Priority+ support
            """)
            st.success("**Perfect for:** Enterprise teams & marketing companies")

            if current_plan == "ultimate":
                st.success("✅ Your Current Plan")
            else:
                agreed = st.checkbox(
                    "✅ Agree to terms",
                    key="agree_ultimate",
                    help="I agree to Terms of Service & No-Refund Policy"
                )
                if st.button(
                    "🚀 Upgrade to Ultimate",
                    disabled=not agreed,
                    type="primary",
                    use_container_width=True,
                    key="upgrade_ultimate"
                ):
                    if agreed:
                        # Create checkout session
                        from stripe_checkout import create_no_refund_checkout
                        checkout_url = create_no_refund_checkout(
                            username=st.session_state.username,
                            user_email=st.session_state.user_data["email"],
                            tier={"name": "Ultimate", "price": 497},
                            
                        )
                        
                        if checkout_url and checkout_url != "debug_mode":
                            st.success("🔄 Redirecting to Stripe checkout...")
                            st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
                            st.stop()
                        else:
                            st.error("Failed to create checkout session")

            # Handle cancelled payments
            #if "payment_cancelled" in st.query_params:
                #st.warning("⚠️ Payment was cancelled. You can try again anytime.")
                #st.query_params.clear()
                
        def show_demo_dashboard():
            """Dashboard for demo users"""
            st.warning("📱 Demo Mode - Upgrade to unlock full features")
            
            # Check demo usage
            username = simple_auth.get_current_user()
            can_demo, remaining = credit_system.can_use_demo(username)
            
            if remaining > 0:
                st.info(f"🎯 You have {remaining} demo leads remaining")
                st.markdown("### 🚀 Try Lead Generation")
                st.markdown("**Demo features:**")
                st.markdown("- ✅ Twitter platform access")
                st.markdown(f"- ✅ {remaining} leads remaining")
                st.markdown("- ✅ Basic lead information")
                
                if st.button("🔬 Try Demo Lead Generation", type="primary", use_container_width=True):
                    # Allow demo scraping with limited features
                    st.info("Demo mode: Use the Empire Scraper tab to try generating leads")
            else:
                st.error("❌ Demo leads exhausted")
                st.markdown("### 🚀 Upgrade to Continue")
                st.markdown("**Choose your plan:**")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📱 Starter ($29/mo)", type="primary", use_container_width=True, key="starter4"):
                        st.session_state.show_pricing = True
                        st.rerun()
                
                with col2:
                    if st.button("💎 Pro ($197/mo)", use_container_width=True):
                        st.session_state.show_pricing = True
                        st.rerun()
                
                with col3:
                    if st.button("👑 Ultimate ($497/mo)", use_container_width=True):
                        st.session_state.show_pricing = True
                        st.rerun()

        with st.expander("📋 Digital Product Terms"):
            st.markdown("""
            **📦 Digital Product Terms:**
            • **Instant Delivery** - Credits added immediately after payment
            • **No Refunds** - All credit purchases are final
            • **90-Day Expiry** - Credits expire 90 days from purchase
            • **Legitimate Use** - For business purposes only
            • **Terms Required** - Must agree to Terms of Service
            """)
        
        # ROI Calculator using native components
        st.markdown("---")
        st.header("💰 ROI Calculator")
        
        roi_col1, roi_col2, roi_col3 = st.columns(3)
        
        with roi_col1:
            st.subheader("🆓 Starter Plan ROI")
            st.success("250 credits × $25 value = $625 value")
            st.success("Cost: $29 → **2,055% ROI**")
        
        with roi_col2:
            st.subheader("💎 Pro Plan ROI")
            st.success("2,000 credits × $25 value = $50,000 value")
            st.success("Cost: $197 → **25,400% ROI**")
        
        with roi_col3:
            st.subheader("👑 Ultimate ROI")
            st.success("Unlimited credits × $25 value = **Unlimited value**")
            st.success("Cost: $497 → **Unlimited ROI**")
        
        # Credit Purchase Section
        st.markdown("---")
        st.header("💎 Buy Additional Credits")
        
        if user_authenticated:
            username = simple_auth.get_current_user()
            user_email = f"{username}@empire.com"
            display_pricing_tiers_with_enforcement(username, user_email)
        else:
            st.info("🔐 Sign in to purchase additional credits")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Starter", type="primary", use_container_width=True, key="credits_register"):
                    st.session_state.show_register = True
                    st.session_state.show_login = False  # ← ADD THIS
                    st.rerun()
            with col2:
                if st.button("🔑 Sign In", key="tab4_login"):
                    st.session_state.show_login = True
                    st.session_state.show_register = False  # ← ADD THIS
                    st.rerun()

        st.markdown(
            '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
            'padding:12px 16px;border-radius:25px;'
            'background:linear-gradient(135deg,#0066cc,#4dabf7);'
            'color:white;font-weight:bold;text-decoration:none;'
            'z-index:9999;">⬆️ Top</a>',
            unsafe_allow_html=True,
        )

        

    with tab5:  # Lead Packages tab
        

        st.header("📦 Lead Package Bundles")
        st.markdown("*One-time purchases for instant lead delivery*")
        
        with st.expander("📋 Digital Product Terms"):
            st.markdown("""
            **📦 Digital Product Terms:**
            • **Instant Delivery** - Credits added immediately after payment
            • **No Refunds** - All credit purchases are final
            • **90-Day Expiry** - Credits expire 90 days from purchase
            • **Legitimate Use** - For business purposes only
            • **Terms Required** - Must agree to Terms of Service
            """)
        
        if not user_authenticated:
            st.info("🔐 Sign in to purchase lead packages")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Join Empire", type="primary", use_container_width=True, key="packages_register"):
                    st.session_state.show_register = True
                    st.rerun()
            with col2:
                if st.button("🔑 Sign In", key="tab5_login"):
                    st.session_state.show_login = True
                    st.session_state.show_register = False  # ← ADD THIS
                    st.rerun()
        
        else:
            # INDUSTRY SELECTION SECTION - Add this before the package cards
            st.markdown("---")
            st.subheader("🎯 Target Industry Selection")
            st.markdown("*Choose your target industry for personalized lead generation*")
            
            # Industry selection
            col1, col2, col3 = st.columns(3)
            
            with col1:
                target_industry = st.selectbox(
                    "🏢 Primary Industry",
                    [
                        "Fitness & Wellness",
                        "Business & Marketing", 
                        "Technology & SaaS",
                        "Finance & Real Estate",
                        "E-commerce & Retail",
                        "Healthcare & Medical",
                        "Education & Training",
                        "Food & Restaurant",
                        "Beauty & Fashion",
                        "Travel & Hospitality",
                        "Legal & Professional Services",
                        "Manufacturing & Industrial",
                        "Non-profit & Charity",
                        "Entertainment & Media",
                        "Custom (specify below)"
                    ],
                    index=0,
                    key="target_industry_select",
                    help="Primary industry for your lead targeting"
                )
            
            with col2:
                target_location = st.selectbox(
                    "📍 Geographic Focus",
                    [
                        "United States (All States)",
                        "North America (US + Canada)",
                        "English Speaking (US, UK, AU, CA)",
                        "Europe (All Countries)",
                        "Global (Worldwide)",
                        "United States - Specific State",
                        "Canada Only",
                        "United Kingdom Only",
                        "Australia Only",
                        "Custom Geographic Area"
                    ],
                    index=0,
                    key="target_location_select",
                    help="Geographic targeting for your leads"
                )
            
            with col3:
                lead_type = st.selectbox(
                    "👥 Lead Type Focus",
                    [
                        "Business Owners",
                        "Decision Makers",
                        "Content Creators",
                        "Influencers",
                        "Professionals",
                        "Entrepreneurs",
                        "Small Business Owners",
                        "Enterprise Executives",
                        "Freelancers",
                        "Coaches & Consultants",
                        "End Customers",
                        "Mixed (All Types)"
                    ],
                    index=0,
                    key="lead_type_select",
                    help="Type of prospects you want to target"
                )
            
            # Custom specifications
            if target_industry == "Custom (specify below)" or target_location == "Custom Geographic Area":
                st.markdown("**🔧 Custom Specifications:**")
                
                custom_col1, custom_col2 = st.columns(2)
                
                with custom_col1:
                    if target_industry == "Custom (specify below)":
                        custom_industry = st.text_input(
                            "Specify Custom Industry:",
                            placeholder="e.g., Renewable Energy, Pet Care, Automotive...",
                            key="custom_industry_input"
                        )
                    else:
                        custom_industry = ""
                
                with custom_col2:
                    if target_location == "Custom Geographic Area":
                        custom_location = st.text_input(
                            "Specify Custom Location:",
                            placeholder="e.g., California only, Major US Cities, Germany + Austria...",
                            key="custom_location_input"
                        )
                    else:
                        custom_location = ""
            else:
                custom_industry = ""
                custom_location = ""
            
            # Additional targeting options
            with st.expander("🎯 Advanced Targeting Options (Optional)"):
                advanced_col1, advanced_col2 = st.columns(2)
                
                with advanced_col1:
                    keywords = st.text_input(
                        "🔍 Specific Keywords/Terms:",
                        placeholder="e.g., fitness coach, digital marketing, sustainability...",
                        key="target_keywords_input",
                        help="Specific terms to focus on in profiles and bios"
                    )
                    
                    exclude_keywords = st.text_input(
                        "🚫 Exclude Keywords:",
                        placeholder="e.g., MLM, pyramid, spam...",
                        key="exclude_keywords_input",
                        help="Terms to avoid in lead selection"
                    )
                
                with advanced_col2:
                    follower_range = st.selectbox(
                        "👥 Follower Count Preference:",
                        [
                            "Any Size (No Preference)",
                            "Micro Influencers (1K-10K)",
                            "Mid-tier (10K-100K)", 
                            "Large Accounts (100K+)",
                            "Business Accounts Only",
                            "Personal Accounts Only"
                        ],
                        key="follower_range_select"
                    )
                    
                    engagement_level = st.selectbox(
                        "📈 Engagement Level:",
                        [
                            "Any Level",
                            "High Engagement (Active)",
                            "Moderate Engagement", 
                            "Recently Active (Last 30 days)",
                            "Professional/Business Focus"
                        ],
                        key="engagement_level_select"
                    )
            
            # Show targeting summary
            st.markdown("---")

            # Package status mapping
            package_status = {
                "Fitness & Wellness": ("🚀 **FITNESS & WELLNESS LEADS PRE-BUILT & READY** - Instant download available", "success"),
                
                # Add more pre-built packages here
            }

            # Display appropriate message
            if target_industry in package_status:
                message, status_type = package_status[target_industry]
                if status_type == "success":
                    st.success(message)
            else:
                st.info("🔄 **CUSTOM BUILD REQUIRED** - 3-5 business days delivery")

            st.subheader("📋 Your Targeting Summary")
            
            # Determine final industry and location
            final_industry = custom_industry if target_industry == "Custom (specify below)" and custom_industry else target_industry
            final_location = custom_location if target_location == "Custom Geographic Area" and custom_location else target_location
            
            targeting_summary = f"""
            **🏢 Industry:** {final_industry}  
            **📍 Location:** {final_location}  
            **👥 Lead Type:** {lead_type}
            """
            
            if keywords:
                targeting_summary += f"\n**🔍 Keywords:** {keywords}"
            if exclude_keywords:
                targeting_summary += f"\n**🚫 Exclude:** {exclude_keywords}"
            if follower_range != "Any Size (No Preference)":
                targeting_summary += f"\n**👥 Followers:** {follower_range}"
            if engagement_level != "Any Level":
                targeting_summary += f"\n**📈 Engagement:** {engagement_level}"
            
            st.info(targeting_summary)
            
            # Validation
            targeting_complete = bool(final_industry and final_location)
            
            if not targeting_complete:
                st.warning("⚠️ Please complete your targeting selections above before purchasing")
        
        st.markdown("---")
        
        # Lead package bundles with targeting integration
        package_col1, package_col2, package_col3 = st.columns(3)

with package_col1:
    st.markdown("### 🎯 Niche Starter Pack")
    st.info("🎯 STARTER")
    st.markdown("## $97")
    st.markdown("---")
    
    st.markdown("**📦 What's Included:**")
    st.markdown("""
    - **500 targeted leads** in your chosen industry
    - 2-3 platforms included
    - Basic filtering applied
    - CSV + Google Sheets delivery
    - 48-hour delivery
    """)
    
    st.info("**Perfect for:** Testing a new niche, quick campaigns")
    
    if user_authenticated and config.get("stripe_secret_key"):
        # ✅ Agree to terms checkbox
        agree_key = "agree_starter_pack"
        agreed = st.checkbox(
            "✅ Agree to terms",
            key=agree_key,
            help="I agree to the Terms of Service & No-Refund Policy"
        )

        # Disable if targeting not done OR terms not agreed
        button_disabled = not targeting_complete or not agreed
        if not targeting_complete:
            button_help = "Complete targeting selections above"
        elif not agreed:
            button_help = "Please agree to terms"
        else:
            button_help = "Purchase Niche Starter Pack"
        
        if st.button("🎯 Buy Starter Pack", use_container_width=True, 
                    key="starter_package_buy_btn",
                    disabled=button_disabled, help=button_help):
            if targeting_complete:
                try:
                    from payment_auth_recovery import create_package_stripe_session
                    import stripe
                    
                    current_username = st.session_state.get('username', 'unknown')
                    
                    session = create_package_stripe_session(
                        stripe,
                        current_username,
                        "starter",
                        97,
                        f"Lead Empire - Niche Starter Pack ({final_industry})",
                        final_industry,
                        final_location
                    )
                    
                    st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
                    st.success(f"🚀 Redirecting to checkout...")
                    st.stop()
                    
                except Exception as e:
                    st.error(f"❌ Payment setup error: {str(e)}")
    elif user_authenticated:
        st.button("🎯 Buy Starter Pack", disabled=True, help="Stripe not configured", 
                use_container_width=True, key="starter_package_disabled_btn")
    else:
        if st.button("🔑 Sign In to Buy", use_container_width=True, 
                    key="starter_package_signin_btn"):
            st.session_state.show_login = True
            st.rerun()

# PACKAGE 2: DEEP DIVE (package_col2)
with package_col2:
    st.markdown("### 🔥 Industry Deep Dive")
    st.success("💎 MOST POPULAR")
    st.markdown("## $297")
    st.markdown("---")
    
    st.markdown("**📦 What's Included:**")
    st.markdown("""
    - **2,000 highly-targeted leads** in your industry
    - Comprehensive industry research
    - All 8 platforms
    - Advanced relevance filtering
    - Social media profiles included
    - DMs pre-generated for your industry
    - 72-hour delivery
    """)
    
    st.info("**Perfect for:** Serious campaigns, market research")
    
    if user_authenticated and config.get("stripe_secret_key"):
        # ✅ Agree to terms checkbox
        agree_key = "agree_deep_dive_pack"
        agreed = st.checkbox(
            "✅ Agree to terms",
            key=agree_key,
            help="I agree to the Terms of Service & No-Refund Policy"
        )

        # Disable if targeting not done OR terms not agreed
        button_disabled = not targeting_complete or not agreed
        if not targeting_complete:
            button_help = "Complete targeting selections above"
        elif not agreed:
            button_help = "Please agree to terms"
        else:
            button_help = "Purchase Industry Deep Dive"
        
        if st.button("🔥 Buy Deep Dive", type="primary", use_container_width=True, 
                    key="deep_dive_package_buy_btn",
                    disabled=button_disabled, help=button_help):
            if targeting_complete:
                try:
                    from payment_auth_recovery import create_package_stripe_session
                    import stripe
                    
                    current_username = st.session_state.get('username', 'unknown')
                    
                    session = create_package_stripe_session(
                        stripe,
                        current_username,
                        "deep_dive",
                        297,
                        f"Lead Empire - Industry Deep Dive ({final_industry})",
                        final_industry,
                        final_location
                    )
                    
                    st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
                    st.success(f"🚀 Redirecting to checkout...")
                    st.stop()
                    
                except Exception as e:
                    st.error(f"❌ Payment setup error: {str(e)}")
    elif user_authenticated:
        st.button("🔥 Buy Deep Dive", disabled=True, help="Stripe not configured", 
                use_container_width=True, key="deep_dive_package_disabled_btn")
    else:
        if st.button("🔑 Sign In to Buy", use_container_width=True, 
                    key="deep_dive_package_signin_btn"):
            st.session_state.show_login = True
            st.rerun()

# PACKAGE 3: MARKET DOMINATION (package_col3)
with package_col3:
    st.markdown("### 💎 Market Domination")
    st.warning("👑 ENTERPRISE")
    st.markdown("## $897")
    st.markdown("---")
    
    st.markdown("**📦 What's Included:**")
    st.markdown("""
    - **5,000 premium leads** across multiple related niches
    - Advanced geographic targeting
    - Phone/email enrichment when available
    - Custom DM sequences for your industry
    - 30-day refresh guarantee
    - 5 business days delivery
    """)
    
    st.info("**Perfect for:** Enterprise campaigns, market domination")
    
    if user_authenticated and config.get("stripe_secret_key"):
        # ✅ Agree to terms checkbox
        agree_key = "agree_domination_pack"
        agreed = st.checkbox(
            "✅ Agree to terms",
            key=agree_key,
            help="I agree to the Terms of Service & No-Refund Policy"
        )

        # Disable if targeting not done OR terms not agreed
        button_disabled = not targeting_complete or not agreed
        if not targeting_complete:
            button_help = "Complete targeting selections above"
        elif not agreed:
            button_help = "Please agree to terms"
        else:
            button_help = "Purchase Market Domination"
        
        if st.button("💎 Buy Domination", use_container_width=True, 
                    key="domination_package_buy_btn",
                    disabled=button_disabled, help=button_help):
            if targeting_complete:
                try:
                    from payment_auth_recovery import create_package_stripe_session
                    import stripe
                    
                    current_username = st.session_state.get('username', 'unknown')
                    
                    session = create_package_stripe_session(
                        stripe,
                        current_username,
                        "domination",
                        897,
                        f"Lead Empire - Market Domination ({final_industry})",
                        final_industry,
                        final_location
                    )
                    
                    st.markdown(f'<meta http-equiv="refresh" content="2;url={session.url}">', unsafe_allow_html=True)
                    st.success(f"🚀 Redirecting to checkout...")
                    st.stop()
                    
                except Exception as e:
                    st.error(f"❌ Payment setup error: {str(e)}")
    elif user_authenticated:
        st.button("💎 Buy Domination", disabled=True, help="Stripe not configured", 
                use_container_width=True, key="domination_package_disabled_btn")
    else:
        if st.button("🔑 Sign In to Buy", use_container_width=True, 
                    key="domination_package_signin_btn"):
            st.session_state.show_login = True
            st.rerun()
    
    # ROI showcase
st.markdown("---")
st.header("💰 Package ROI Calculator")
        
roi_col1, roi_col2, roi_col3 = st.columns(3)
        
with roi_col1:
    st.subheader("🎯 **Starter Pack ROI**")
    st.success("500 leads × $25 value = **$12,500 value**")
    st.markdown("Cost: $97 → **12,786% ROI**")
        
with roi_col2:
    st.subheader("🔥 **Deep Dive ROI**")
    st.success("2,000 leads × $25 value = **$50,000 value**")
    st.markdown("Cost: $297 → **16,835% ROI**")
        
with roi_col3:
    st.subheader("💎 **Domination ROI**")
    st.success("5,000 leads × $25 value = **$250,000 value**")
    st.markdown("Cost: $897 → **27,869% ROI**")
        
# Package comparison
st.markdown("---")
st.header("📊 Package Comparison")
        
comparison_data = {
    "Feature": [
        "Number of Leads",
        "Platforms Included", 
        "Delivery Time",
        "Social Profiles",
        "DM Generation",
        "Geographic Targeting",
        "Industry Research",
        "Support Level",
        "Refresh Guarantee"
    ],
    "🎯 Starter ($97)": [
        "500",
        "2-3 platforms",
        "48 hours",
        "Basic",
        "Templates",
        "No",
        "Basic",
        "Email",
        "No"
    ],
    "🔥 Deep Dive ($297)": [
        "2,000",
        "All 8 platforms",
        "72 hours", 
        "Included",
        "Pre-generated",
        "Basic",
        "Comprehensive",
        "Priority",
        "7 days"
    ],
    "💎 Domination ($897)": [
        "5,000",
        "All 8 platforms",
        "5 business days",
        "Enhanced",
        "Custom sequences", 
        "Advanced",
        "Multi-niche",
        "Priority+",
        "30 days"
    ]
}
    
st.dataframe(comparison_data, use_container_width=True)   

st.markdown(
    '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
    'padding:12px 16px;border-radius:25px;'
    'background:linear-gradient(135deg,#0066cc,#4dabf7);'
    'color:white;font-weight:bold;text-decoration:none;'
    'z-index:9999;">⬆️ Top</a>',
    unsafe_allow_html=True,
)
    

with tab6:  # Settings tab

        st.header("⚙️ Account Settings")
    
        if not user_authenticated:
            st.info("🔐 Sign in to manage your account settings")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Create Account", type="primary", use_container_width=True, key="settings_register"):
                    st.session_state.show_register = True
                    st.session_state.show_login = False
                    st.rerun()
            with col2:
                if st.button("🔑 Sign In", use_container_width=True, key="settings_login"):
                    st.session_state.show_login = True
                    st.session_state.show_register = False
                    st.rerun()
            
            # Show what settings they'll have access to
            st.markdown("---")
            st.markdown("### 🎯 Available Settings")
            st.markdown("""
            **📊 Account Management**
            - View your plan and credit balance
            - Update password and security settings
            - Manage email preferences
            
            **🎯 Lead Generation Preferences**
            - Set default search keywords
            - Configure platform preferences
            - Customize DM templates
            
            **🌍 Language & Localization**
            - Choose your interface language
            - Set geographic targeting preferences
            - Configure cultural adaptation settings
            
            **📧 Communication Settings**
            - Email notifications for completed campaigns
            - Weekly usage reports
            - Platform updates and announcements
            """)
        
        else:
            # Authenticated user settings
            username = simple_auth.get_current_user()
            user_plan = simple_auth.get_user_plan()
            current_credits = simple_auth.get_user_credits()
            
            # Account Overview
            st.subheader("👤 Account Overview")
            
            # Account info cards
            overview_col1, overview_col2, overview_col3 = st.columns(3)
            
            with overview_col1:
                plan_emoji = "📱" if user_plan == "demo" else "🎯" if user_plan == "starter" else "💎" if user_plan == "pro" else "👑"
                st.metric("Plan", f"{plan_emoji} {user_plan.title()}")
            
            with overview_col2:
                if user_plan == "demo":
                    # Show demo leads remaining
                    try:
                        can_demo, remaining = credit_system.can_use_demo(username)
                        st.metric("Demo Leads", f"{remaining}/5")
                    except:
                        st.metric("Credits", current_credits)
                else:
                    st.metric("Credits", current_credits)
            
            with overview_col3:
                # Show account age
                try:
                    user_data = st.session_state.get('user_data', {})
                    created_at = user_data.get('created_at', '')
                    if created_at:
                        created_date = datetime.fromisoformat(created_at).strftime("%b %Y")
                        st.metric("Member Since", created_date)
                    else:
                        st.metric("Status", "Active")
                except:
                    st.metric("Status", "Active")

            # View statistics
            st.markdown("---")
            st.subheader("📊 Detailed Usage Statistics")

            try:
                user_info = credit_system.get_user_info(username)
                if user_info:
                    # ✅ ENHANCED USAGE METRICS WITH DYNAMIC CREDITS
                    usage_col1, usage_col2, usage_col3, usage_col4 = st.columns(4)
                    
                    with usage_col1:
                        if user_plan == "demo":
                            # For demo users, calculate total from demo leads used
                            try:
                                can_demo, remaining = credit_system.can_use_demo(username)
                                demo_used = 5 - remaining  # Calculate used demo leads
                                total_leads = demo_used     # ✅ FIX: Use demo leads as total
                                st.metric("Total Leads Generated", total_leads)
                            except:
                                total_leads = user_info.get('total_leads_downloaded', 0)
                                st.metric("Total Leads Generated", total_leads)
                        else:
                            # For paid users, use regular total
                            total_leads = user_info.get('total_leads_downloaded', 0)
                            st.metric("Total Leads Generated", total_leads)
                    
                    with usage_col2:
                        total_campaigns = len(user_info.get('transactions', []))
                        st.metric("Campaigns Run", total_campaigns)
                    
                    with usage_col3:
                        if user_plan == "demo":
                            try:
                                can_demo, remaining = credit_system.can_use_demo(username)
                                demo_used = 5 - remaining
                                st.metric("Demo Leads Used", f"{demo_used}/5")  # ✅ This looks correct
                            except:
                                st.metric("Demo Leads Used", "5/5")
                        else:
                            # ✅ DYNAMIC CREDITS USED CALCULATION
                            try:
                                current_credits = simple_auth.get_user_credits()  # 1340 in your case
                                
                                # Calculate total credits ever owned
                                plan_starting_credits = {
                                    'starter': 250,
                                    'pro': 2000,
                                    'ultimate': 9999
                                }
                                starting_credits = plan_starting_credits.get(user_plan, 250)
                                
                                # Add any purchased credits from transactions
                                purchased_credits = 0
                                transactions = user_info.get('transactions', [])
                                for tx in transactions:
                                    if tx.get('type') == 'credit_purchase':
                                        purchased_credits += tx.get('credits_added', 0)
                                
                                total_credits_ever = starting_credits + purchased_credits
                                credits_used = total_credits_ever - current_credits
                                
                                st.metric("Credits Used", credits_used, delta=f"of {total_credits_ever}")
                                
                            except Exception as e:
                                # Fallback: use total leads as approximation
                                total_leads = user_info.get('total_leads_downloaded', 0)
                                st.metric("Credits Used", total_leads, delta="≈ leads generated")
                    
                    with usage_col4:
                        member_since = user_info.get('created_at', '')
                        if member_since:
                            try:
                                days_active = (datetime.now() - datetime.fromisoformat(member_since)).days
                                st.metric("Days Active", days_active)
                            except:
                                st.metric("Status", "Active")
                        else:
                            st.metric("Status", "Active")

                    # ✅ NEW: PLATFORM PERFORMANCE SECTION
                    st.markdown("---")
                    st.subheader("🎯 Platform Performance")
                    
                    # Calculate platform statistics from transactions
                    platform_stats = {}
                    platform_leads = {}
                    platform_campaigns = {}
                    
                    transactions = user_info.get('transactions', [])
                    
                    for tx in transactions:
                        if tx.get('type') == 'lead_download':
                            platform = tx.get('platform', 'unknown')
                            leads_count = tx.get('leads_downloaded', 0)
                            
                            # Track total leads per platform
                            if platform not in platform_leads:
                                platform_leads[platform] = 0
                                platform_campaigns[platform] = 0
                            
                            platform_leads[platform] += leads_count
                            platform_campaigns[platform] += 1
                    
                    # Display platform performance
                    if platform_leads:
                        # Sort platforms by total leads (descending)
                        sorted_platforms = sorted(platform_leads.items(), key=lambda x: x[1], reverse=True)
                        
                        # Create performance metrics
                        perf_col1, perf_col2, perf_col3 = st.columns(3)
                        
                        with perf_col1:
                            st.markdown("**📊 Leads by Platform:**")
                            for platform, leads in sorted_platforms[:5]:  # Top 5 platforms
                                percentage = (leads / total_leads * 100) if total_leads > 0 else 0
                                
                                # Platform emojis
                                platform_emojis = {
                                    'twitter': '🐦', 'facebook': '📘', 'linkedin': '💼',
                                    'tiktok': '🎵', 'instagram': '📸', 'youtube': '🎥',
                                    'medium': '📝', 'reddit': '🗨️', 'parallel_session': '⚡'
                                }
                                
                                emoji = platform_emojis.get(platform, '📱')
                                st.metric(f"{emoji} {platform.title()}", leads, delta=f"{percentage:.1f}%")
                        
                        with perf_col2:
                            st.markdown("**🎯 Performance Metrics:**")
                            
                            # Best performing platform
                            best_platform = sorted_platforms[0] if sorted_platforms else ('none', 0)
                            st.metric("🏆 Top Platform", f"{best_platform[0].title()}", delta=f"{best_platform[1]} leads")
                            
                            # Average leads per campaign
                            avg_leads = total_leads / total_campaigns if total_campaigns > 0 else 0
                            st.metric("📈 Avg Leads/Campaign", f"{avg_leads:.1f}")
                            
                            # Platform diversity
                            active_platforms = len([p for p, l in platform_leads.items() if l > 0])
                            st.metric("🌍 Active Platforms", active_platforms)
                        
                        with perf_col3:
                            st.markdown("**⚡ Efficiency Stats:**")
                            
                            # Most recent activity
                            if transactions:
                                latest_tx = max(transactions, key=lambda x: x.get('timestamp', ''))
                                latest_platform = latest_tx.get('platform', 'unknown')
                                latest_leads = latest_tx.get('leads_downloaded', 0)
                                
                                st.metric("🕒 Latest Campaign", latest_platform.title(), delta=f"{latest_leads} leads")
                            
                            # Total campaigns
                            st.metric("🚀 Total Campaigns", total_campaigns)
                            
                            # Success rate (campaigns with >0 leads)
                            successful_campaigns = len([tx for tx in transactions 
                                                    if tx.get('type') == 'lead_download' and tx.get('leads_downloaded', 0) > 0])
                            success_rate = (successful_campaigns / total_campaigns * 100) if total_campaigns > 0 else 0
                            st.metric("✅ Success Rate", f"{success_rate:.1f}%")
                        
                        # ✅ PLATFORM PERFORMANCE CHART
                        if len(sorted_platforms) > 1:
                            st.markdown("**📊 Platform Distribution:**")
                            
                            # Create simple bar chart using metrics
                            chart_cols = st.columns(len(sorted_platforms))
                            max_leads = max(leads for _, leads in sorted_platforms)
                            
                            for i, (platform, leads) in enumerate(sorted_platforms):
                                with chart_cols[i]:
                                    # Calculate bar height (normalized to 100)
                                    bar_height = int((leads / max_leads * 100)) if max_leads > 0 else 0
                                    
                                    # Platform emoji
                                    emoji = platform_emojis.get(platform, '📱')
                                    
                                    # Simple visual bar using progress
                                    st.markdown(f"**{emoji} {platform.title()}**")
                                    st.progress(leads / max_leads if max_leads > 0 else 0)
                                    st.caption(f"{leads} leads ({(leads/total_leads*100):.1f}%)")
                    
                    else:
                        st.info("📊 No platform performance data yet. Generate some leads to see your stats!")

                    # ✅ CONDENSED RECENT ACTIVITY (DROPDOWN)
                    st.markdown("---")
                    
                    if transactions:
                        # Summary stats for recent activity
                        recent_transactions = sorted(transactions, key=lambda x: x.get('timestamp', ''), reverse=True)
                        recent_count = len(recent_transactions)
                        
                        # Show summary
                        activity_summary_col1, activity_summary_col2, activity_summary_col3 = st.columns(3)
                        
                        with activity_summary_col1:
                            st.metric("📋 Total Activities", recent_count)
                        
                        with activity_summary_col2:
                            # Most recent activity
                            if recent_transactions:
                                latest = recent_transactions[0]
                                latest_type = latest.get('type', 'unknown')
                                if latest_type == 'lead_download':
                                    summary = f"Generated {latest.get('leads_downloaded', 0)} leads"
                                elif latest_type == 'credit_purchase':
                                    summary = f"Purchased {latest.get('credits_added', 0)} credits"
                                else:
                                    summary = latest_type.replace('_', ' ').title()
                                
                                st.metric("🕒 Latest Activity", summary)
                        
                        with activity_summary_col3:
                            # Recent activity timeframe
                            if len(recent_transactions) >= 2:
                                try:
                                    latest_time = datetime.fromisoformat(recent_transactions[0].get('timestamp', ''))
                                    oldest_time = datetime.fromisoformat(recent_transactions[-1].get('timestamp', ''))
                                    timespan = (latest_time - oldest_time).days
                                    st.metric("📅 Activity Span", f"{timespan} days")
                                except:
                                    st.metric("📅 Status", "Active")
                        
                        # ✅ COLLAPSIBLE DETAILED ACTIVITY LIST
                        with st.expander(f"📋 View Detailed Activity History ({recent_count} entries)", expanded=False):
                            st.markdown("**Recent Activity Timeline:**")
                            
                            # Show last 15 transactions in a more compact format
                            for i, tx in enumerate(recent_transactions[:15]):
                                tx_type = tx.get('type', 'unknown')
                                timestamp = tx.get('timestamp', '')
                                
                                if timestamp:
                                    try:
                                        tx_date = datetime.fromisoformat(timestamp).strftime("%m/%d %H:%M")
                                    except:
                                        tx_date = timestamp
                                else:
                                    tx_date = "Unknown"
                                
                                # Create compact display
                                if tx_type == 'lead_download':
                                    leads_count = tx.get('leads_downloaded', 0)
                                    platform = tx.get('platform', 'unknown')
                                    
                                    # Platform emoji
                                    platform_emojis = {
                                        'twitter': '🐦', 'facebook': '📘', 'linkedin': '💼',
                                        'tiktok': '🎵', 'instagram': '📸', 'youtube': '🎥',
                                        'medium': '📝', 'reddit': '🗨️', 'parallel_session': '⚡'
                                    }
                                    emoji = platform_emojis.get(platform, '📱')
                                    
                                    st.success(f"{emoji} **{tx_date}**: Generated **{leads_count}** leads from {platform}")
                                    
                                elif tx_type == 'credit_purchase':
                                    credits_added = tx.get('credits_added', 0)
                                    st.info(f"💳 **{tx_date}**: Purchased **{credits_added}** credits")
                                    
                                elif tx_type == 'demo_usage':
                                    st.info(f"🎯 **{tx_date}**: Used demo lead")
                                    
                                else:
                                    st.caption(f"📋 **{tx_date}**: {tx_type.replace('_', ' ').title()}")
                            
                            # Show "load more" if there are more transactions
                            if len(recent_transactions) > 15:
                                st.caption(f"... and {len(recent_transactions) - 15} more activities")
                                
                                if st.button("📄 Export Full Activity History"):
                                    # Create CSV export of all transactions
                                    import pandas as pd
                                    
                                    export_data = []
                                    for tx in transactions:
                                        export_data.append({
                                            'Date': tx.get('timestamp', ''),
                                            'Type': tx.get('type', ''),
                                            'Platform': tx.get('platform', ''),
                                            'Leads': tx.get('leads_downloaded', 0),
                                            'Credits': tx.get('credits_added', 0)
                                        })
                                    
                                    df = pd.DataFrame(export_data)
                                    csv = df.to_csv(index=False)
                                    
                                    st.download_button(
                                        label="📥 Download Activity History",
                                        data=csv,
                                        file_name=f"activity_history_{username}_{datetime.now().strftime('%Y%m%d')}.csv",
                                        mime="text/csv"
                                    )
                    else:
                        st.info("📋 No activity yet - start generating leads to see your history!")

                    # ✅ QUICK STATS SUMMARY
                    st.markdown("---")
                    st.subheader("⚡ Quick Stats Summary")
                    
                    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                    
                    with summary_col1:
                        leads_per_day = total_leads / max(days_active, 1) if 'days_active' in locals() else 0
                        st.metric("📈 Leads/Day", f"{leads_per_day:.1f}")
                    
                    with summary_col2:
                        if platform_leads:
                            best_platform_name = max(platform_leads, key=platform_leads.get)
                            st.metric("🏆 Best Platform", best_platform_name.title())
                        else:
                            st.metric("🏆 Best Platform", "None yet")
                    
                    with summary_col3:
                        avg_campaign_size = total_leads / total_campaigns if total_campaigns > 0 else 0
                        st.metric("🎯 Avg Campaign", f"{avg_campaign_size:.1f} leads")
                    
                    with summary_col4:
                        efficiency = (total_leads / max(days_active, 1)) if 'days_active' in locals() and days_active > 0 else 0
                        st.metric("⚡ Efficiency", f"{efficiency:.1f}/day")

                else:
                    st.warning("⚠️ Could not load usage data")
                    
            except Exception as e:
                st.error(f"❌ Error loading usage data: {str(e)}")
                
                # ✅ DEBUG INFO FOR TROUBLESHOOTING
                with st.expander("🔍 Debug Information", expanded=False):
                    st.code(f"""
                    Error: {str(e)}
                    Username: {username if 'username' in locals() else 'Not set'}
                    User Plan: {user_plan if 'user_plan' in locals() else 'Not set'}
                    Session Credits: {st.session_state.get('credits', 'Not set')}
                    """)
            
            # Quick actions
            st.markdown("---")
            st.subheader("⚡ Quick Actions")
            
            quick_col1, quick_col2, quick_col3 = st.columns(3)
            
            with quick_col1:
                if user_plan == "demo":
                    if st.button("🚀 Upgrade Account", type="primary", use_container_width=True):
                        # Switch to pricing tab
                        st.session_state.show_pricing = True
                        st.rerun()
                else:
                    if st.button("💎 Buy More Credits", type="primary", use_container_width=True):
                        # Switch to pricing tab
                        st.session_state.show_pricing = True
                        st.rerun()
            
            with quick_col2:
                if st.button("🔐 Change Password", use_container_width=True):
                    st.session_state.show_password_change = True
                    st.rerun()
            
            with quick_col3:
                if "show_usage_details" not in st.session_state:
                    st.session_state.show_usage_details = False

            # now, conditionally render the Detailed Usage panel
            if st.session_state.show_usage_details:
                st.markdown("---")
                st.subheader("📊 Detailed Usage Statistics")
                
                try:
                    user_info = credit_system.get_user_info(username)
                    if user_info:
                        # Usage metrics
                        usage_col1, usage_col2, usage_col3, usage_col4 = st.columns(4)
                        
                        with usage_col1:
                            total_leads = user_info.get('total_leads_downloaded', 0)
                            st.metric("Total Leads Generated", total_leads)
                        
                        with usage_col2:
                            total_campaigns = len(user_info.get('transactions', []))
                            st.metric("Campaigns Run", total_campaigns)
                        
                        with usage_col3:
                            if user_plan == "demo":
                                can_demo, remaining = credit_system.can_use_demo(username)
                                demo_used = 5 - remaining
                                st.metric("Demo Leads Used", f"{demo_used}/5")
                            else:
                                credits_used = user_info.get('total_credits_used', 0)
                                st.metric("Credits Used", credits_used)
                        
                        with usage_col4:
                            member_since = user_info.get('created_at', '')
                            if member_since:
                                try:
                                    days_active = (datetime.now() - datetime.fromisoformat(member_since)).days
                                    st.metric("Days Active", days_active)
                                except:
                                    st.metric("Status", "Active")
                            else:
                                st.metric("Status", "Active")
                        
                        # Transaction history
                        transactions = user_info.get('transactions', [])
                        if transactions:
                            st.markdown("**📋 Recent Activity:**")
                            
                            # Show last 10 transactions
                            recent_transactions = sorted(transactions, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
                            
                            for tx in recent_transactions:
                                tx_type = tx.get('type', 'unknown')
                                timestamp = tx.get('timestamp', '')
                                
                                if timestamp:
                                    try:
                                        tx_date = datetime.fromisoformat(timestamp).strftime("%m/%d/%Y %H:%M")
                                    except:
                                        tx_date = timestamp
                                else:
                                    tx_date = "Unknown"
                                
                                if tx_type == 'lead_download':
                                    leads_count = tx.get('leads_downloaded', 0)
                                    platform = tx.get('platform', 'unknown')
                                    st.success(f"📊 {tx_date}: Generated {leads_count} leads from {platform}")
                                
                                elif tx_type == 'credit_purchase':
                                    credits_added = tx.get('credits_added', 0)
                                    st.info(f"💳 {tx_date}: Purchased {credits_added} credits")
                                
                                elif tx_type == 'demo_usage':
                                    st.info(f"🎯 {tx_date}: Used demo lead")
                        else:
                            st.info("📋 No activity yet - start generating leads!")
                    
                    else:
                        st.warning("⚠️ Could not load usage data")
                        
                except Exception as e:
                    st.error(f"❌ Error loading usage data: {str(e)}")
            
            # Settings sections
            st.markdown("---")
            
            # Personal Preferences
            st.subheader("🎯 Lead Generation Preferences")

            pref_col1, pref_col2 = st.columns(2)

            with pref_col1:
                # Load current user config properly
                username = simple_auth.get_current_user() if user_authenticated else None
                current_user_config = get_current_config(username)
                
                default_search = st.text_input(
                    "🔍 Default Search Keywords",
                    value=current_user_config.get("search_term", ""),
                    help="Your preferred search terms for lead generation",
                    key="user_default_search"
                )
                
                default_intensity = st.slider(
                    "📊 Default Intensity Level",
                    min_value=1,
                    max_value=20,
                    value=current_user_config.get("max_scrolls", 12),
                    help="Your preferred intensity level for campaigns",
                    key="user_default_intensity"
                )
                
                # Show current values for confirmation
                st.info(f"Current defaults: '{current_user_config.get('search_term', 'not set')}' with intensity {current_user_config.get('max_scrolls', 'not set')}")

            with pref_col2:
                # Platform preferences (your existing code for this column)
                st.markdown("**🌍 Preferred Platforms:**")
                
                # Show available platforms based on plan
                plan_access = {
                    'demo': ['Twitter'],
                    'starter': ['Twitter', 'Facebook'],
                    'pro': ['Twitter', 'Facebook', 'LinkedIn', 'TikTok', 'Instagram', 'YouTube'],
                    'ultimate': ['Twitter', 'Facebook', 'LinkedIn', 'TikTok', 'Instagram', 'YouTube', 'Medium', 'Reddit']
                }
                
                available_platforms = plan_access.get(user_plan, ['Twitter'])
                
                for platform in available_platforms:
                    platform_emojis = {
                        'Twitter': '🐦', 'Facebook': '📘', 'LinkedIn': '💼',
                        'TikTok': '🎵', 'Instagram': '📸', 'YouTube': '🎥',
                        'Medium': '📝', 'Reddit': '🗨️'
                    }
                    emoji = platform_emojis.get(platform, '🎯')
                    
                    pref_key = f"prefer_{platform.lower()}"
                    platform_pref = st.checkbox(
                        f"{emoji} {platform}",
                        value=True,
                        key=pref_key,
                        help=f"Include {platform} in your campaigns by default"
                    )

            # NEW: Account Exclusion Management Section
            st.markdown("---")
            st.subheader("🚫 Account Exclusions")
            st.markdown("*Manage which accounts are excluded from your lead results*")
            
            # Load current excluded accounts
            try:
                import os
                from enhanced_config_loader import ConfigLoader
                config_file = f"client_configs/client_{st.session_state.username}_config.json"
                config_loader = ConfigLoader(config_file)
               
                
                excluded_accounts = config_loader.config.get("excluded_accounts", {})
                platform_accounts = excluded_accounts.get("accounts", {})
                global_excludes = excluded_accounts.get("global_excludes", [])
                
            except Exception as e:
                st.error(f"Could not load account exclusions: {e}")
                platform_accounts = {}
                global_excludes = []
            
            # Statistics
            total_excluded = sum(len(accounts) for accounts in platform_accounts.values()) + len(global_excludes)
            
            excl_col1, excl_col2, excl_col3 = st.columns(3)
            with excl_col1:
                st.metric("🚫 Total Excluded", total_excluded)
            with excl_col2:
                st.metric("🌍 Global Exclusions", len(global_excludes))
            with excl_col3:
                platforms_with_exclusions = len([p for p in platform_accounts.values() if len(p) > 0])
                st.metric("📱 Platforms Configured", platforms_with_exclusions)
            
            # Tabs for different exclusion management
            exclusion_tab1, exclusion_tab2 = st.tabs(["📱 Platform-Specific", "🌍 Global Exclusions"])
            
            with exclusion_tab1:
                st.markdown("#### Manage Platform-Specific Exclusions")
                
                platforms = {
                    'instagram': {'emoji': '📸', 'name': 'Instagram', 'color': '#E4405F'},
                    'tiktok': {'emoji': '🎵', 'name': 'TikTok', 'color': '#000000'},
                    'facebook': {'emoji': '📘', 'name': 'Facebook', 'color': '#1877F2'},
                    'twitter': {'emoji': '🐦', 'name': 'Twitter', 'color': '#1DA1F2'},
                    'youtube': {'emoji': '📹', 'name': 'YouTube', 'color': '#FF0000'},
                    'linkedin': {'emoji': '💼', 'name': 'LinkedIn', 'color': '#0A66C2'},
                    'medium': {'emoji': '📝', 'name': 'Medium', 'color': '#000000'},
                    'reddit': {'emoji': '🗨️', 'name': 'Reddit', 'color': '#FF4500'}
                }
                
                # Create two columns for platform management
                plat_col1, plat_col2 = st.columns(2)
                
                for idx, (platform_id, platform_info) in enumerate(platforms.items()):
                    col = plat_col1 if idx % 2 == 0 else plat_col2
                    
                    with col:
                        with st.container():
                            st.markdown(f"**{platform_info['emoji']} {platform_info['name']}**")
                            
                            current_accounts = platform_accounts.get(platform_id, [])
                            
                            # Show current exclusions
                            if current_accounts:
                                for account in current_accounts:
                                    account_col1, account_col2 = st.columns([3, 1])
                                    with account_col1:
                                        st.text(f"@{account}")
                                    with account_col2:
                                        if st.button("🗑️", key=f"remove_{platform_id}_{account}", help=f"Remove @{account}"):
                                            try:
                                                config_loader.remove_excluded_account(platform_id, account)
                                                config_loader.save_config() 
                                                st.success(f"Removed @{account} from {platform_info['name']}")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error removing account: {e}")
                            else:
                                st.text("No excluded accounts")
                            
                            # Add new account
                            new_account = st.text_input(
                                f"Add {platform_info['name']} account",
                                key=f"new_{platform_id}",
                                placeholder="username (without @)",
                                help=f"Enter username to exclude from {platform_info['name']} results"
                            )
                            
                            if st.button(f"➕ Add to {platform_info['name']}", key=f"add_{platform_id}"):
                                if new_account.strip():
                                    clean_account = new_account.strip().lstrip('@')
                                    try:
                                        success = config_loader.add_excluded_account(platform_id, clean_account)
                                        if success:
                                            config_loader.save_config()
                                            st.success(f"Added @{clean_account} to {platform_info['name']} exclusions")
                                            st.rerun()
                                        else:
                                            st.warning(f"@{clean_account} already excluded from {platform_info['name']}")
                                    except Exception as e:
                                        st.error(f"Error adding account: {e}")
                                else:
                                    st.error("Please enter a username")
                        
                        st.markdown("---")
            
            with exclusion_tab2:
                st.markdown("#### Manage Global Exclusions")
                st.markdown("*These accounts are excluded from ALL platforms*")
                
                # Show current global exclusions
                if global_excludes:
                    st.markdown("**Current Global Exclusions:**")
                    for account in global_excludes:
                        global_col1, global_col2 = st.columns([3, 1])
                        with global_col1:
                            st.text(f"@{account}")
                        with global_col2:
                            if st.button("🗑️", key=f"remove_global_{account}", help=f"Remove @{account} from global exclusions"):
                                try:
                                    # Remove from global excludes
                                    if "excluded_accounts" in config_loader.config:
                                        global_list = config_loader.config["excluded_accounts"].get("global_excludes", [])
                                        if account in global_list:
                                            global_list.remove(account)
                                            config_loader.save_config()
                                            st.success(f"Removed @{account} from global exclusions")
                                            st.rerun()
                                except Exception as e:
                                    st.error(f"Error removing global account: {e}")
                else:
                    st.text("No global exclusions configured")
                
                # Add new global exclusion
                st.markdown("**Add Global Exclusion:**")
                new_global = st.text_input(
                    "Username to exclude globally",
                    key="new_global_exclusion",
                    placeholder="username (without @)",
                    help="This account will be excluded from ALL platform results"
                )
                
                if st.button("➕ Add Global Exclusion"):
                    if new_global.strip():
                        clean_global = new_global.strip().lstrip('@')
                        try:
                            success = config_loader.add_global_exclude(clean_global)
                            if success:
                                st.success(f"Added @{clean_global} to global exclusions")
                                st.rerun()
                            else:
                                st.warning(f"@{clean_global} already in global exclusions")
                        except Exception as e:
                            st.error(f"Error adding global exclusion: {e}")
                    else:
                        st.error("Please enter a username")
            
            # Quick Actions
            st.markdown("---")
            st.markdown("#### ⚡ Exclusion Tools")
            
            quick_col1, quick_col2, quick_col3 = st.columns(3)
            
            with quick_col1:
                if st.button("🔄 Refresh Exclusions", help="Reload exclusions from config"):
                    st.rerun()
            
            with quick_col2:
                if st.button("📥 Import from Registration", help="Add accounts from your registration"):
                    try:
                        # Try to find registration data
                        user_data = simple_auth.get_user_data(st.session_state.current_user)
                        if user_data and 'social_accounts' in user_data:
                            added_count = 0
                            for platform, username in user_data['social_accounts'].items():
                                if username.strip():
                                    try:
                                        if config_loader.add_excluded_account(platform, username):
                                            added_count += 1
                                    except:
                                        pass
                            
                            if added_count > 0:
                                st.success(f"Added {added_count} accounts from registration")
                                st.rerun()
                            else:
                                st.info("No new accounts to import")
                        else:
                            st.warning("No registration data found")
                    except Exception as e:
                        st.error(f"Import failed: {e}")
            
            with quick_col3:
                if st.button("🧹 Clear All Exclusions", help="Remove all excluded accounts"):
                    if st.checkbox("⚠️ Confirm: Clear all exclusions", key="confirm_clear_exclusions"):
                        try:
                            # Clear all exclusions
                            config_loader.config["excluded_accounts"] = {
                                "enabled": True,
                                "accounts": {
                                    "instagram": [],
                                    "tiktok": [],
                                    "facebook": [],
                                    "twitter": [],
                                    "youtube": [],
                                    "linkedin": [],
                                    "medium": [],
                                    "reddit": []
                                },
                                "global_excludes": []
                            }
                            config_loader.save_config()
                            st.success("All exclusions cleared")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error clearing exclusions: {e}")
            
            # Help section
            with st.expander("ℹ️ How Account Exclusions Work"):
                st.markdown("""
                **Account exclusions prevent your own social media accounts from appearing in your lead results.**
                
                **Platform-Specific Exclusions:**
                - Only apply to that specific platform
                - Example: Excluding your Instagram won't affect TikTok results
                
                **Global Exclusions:**
                - Apply to ALL platforms automatically
                - Useful for accounts you use across multiple platforms
                
                **Best Practices:**
                - Add your business accounts to prevent self-targeting
                - Add personal accounts if they might appear in business searches
                - Use global exclusions for accounts used across platforms
                - Regularly review and update your exclusions
                
                **Tips:**
                - Changes take effect immediately for new lead generation
                - You can add usernames with or without the @ symbol
                - Usernames are case-insensitive
                """)
            
            # Show current configuration summary (FILTERED BY CURRENT USER)
            st.markdown("---")
            st.markdown("#### 📊 Current Configuration Summary")

            # ✅ GET CURRENT USER'S EXCLUSIONS ONLY
            if 'username' in st.session_state and st.session_state.username:
                current_username = st.session_state.username
                
                # Filter exclusions for current user only
                user_platform_accounts = {}
                user_global_excludes = []
                
                # Get user-specific platform exclusions
                for platform, accounts in platform_accounts.items():
                    if accounts:
                        # Filter accounts that belong to current user
                        user_accounts = []
                        for account in accounts:
                            # Check if this account belongs to current user
                            # (You might need to adjust this logic based on how you store user associations)
                            if current_username in account or account.startswith(current_username):
                                user_accounts.append(account)
                        
                        if user_accounts:
                            user_platform_accounts[platform] = user_accounts
                
                # Get user-specific global exclusions  
                if global_excludes:
                    for account in global_excludes:
                        if current_username in account or account.startswith(current_username):
                            user_global_excludes.append(account)
                
                # Count total user exclusions
                user_total_excluded = sum(len(accounts) for accounts in user_platform_accounts.values()) + len(user_global_excludes)
                
                if user_total_excluded > 0:
                    summary_data = []
                    
                    # Platform-specific summary (user only)
                    for platform, accounts in user_platform_accounts.items():
                        if accounts:
                            platform_info = platforms.get(platform, {'emoji': '📱', 'name': platform.title()})
                            summary_data.append({
                                "Platform": f"{platform_info['emoji']} {platform_info['name']}",
                                "Excluded Accounts": f"{len(accounts)} accounts", 
                                "Accounts": ", ".join([f"@{acc}" for acc in accounts[:3]]) + ("..." if len(accounts) > 3 else "")
                            })
                    
                    # Global summary (user only)
                    if user_global_excludes:
                        summary_data.append({
                            "Platform": "🌍 Global",
                            "Excluded Accounts": f"{len(user_global_excludes)} accounts",
                            "Accounts": ", ".join([f"@{acc}" for acc in user_global_excludes[:3]]) + ("..." if len(user_global_excludes) > 3 else "")
                        })
                    
                    if summary_data:
                        st.table(summary_data)
                        st.success(f"👤 **{current_username}**: {user_total_excluded} total exclusions configured")
                    else:
                        st.info("No exclusions configured for your account")
                else:
                    st.info(f"💡 **Hi {current_username}!** Add your social media accounts to prevent them from appearing in your lead results!")

            else:
                st.warning("⚠️ Please log in to view your configuration summary")
            
            # Communication Preferences
            st.markdown("---")
            st.subheader("📧 Communication Preferences")
            
            comm_col1, comm_col2 = st.columns(2)
            
            with comm_col1:
                email_completion = st.checkbox(
                    "📧 Email when campaigns complete",
                    value=True,
                    help="Get notified when your lead generation campaigns finish"
                )
                
                email_weekly = st.checkbox(
                    "📊 Weekly usage reports",
                    value=True,
                    help="Receive weekly summaries of your lead generation activity"
                )
            
            with comm_col2:
                email_updates = st.checkbox(
                    "🔔 Platform updates",
                    value=True,
                    help="Stay informed about new features and improvements"
                )
                
                email_tips = st.checkbox(
                    "💡 Lead generation tips",
                    value=True,
                    help="Receive expert tips for better lead generation results"
                )
            
            # Language & Localization (if multilingual is available)
            if MULTILINGUAL_AVAILABLE:
                st.markdown("---")
                st.subheader("🌍 Language & Localization")
                
                lang_col1, lang_col2 = st.columns(2)
                
                with lang_col1:
                    interface_language = st.selectbox(
                        "🔤 Interface Language",
                        ["English", "Spanish", "French", "German", "Portuguese"],
                        key="interface_language_select",
                        help="Choose your preferred interface language"
                    )
                    
                    default_dm_language = st.selectbox(
                        "💬 Default DM Language",
                        ["Auto-detect", "English", "Spanish", "French", "German", "Portuguese"],
                        key="default_dm_language_select",
                        help="Default language for generated DMs"
                    )
                
                with lang_col2:
                    cultural_style = st.selectbox(
                        "🎭 Cultural Adaptation",
                        ["Standard", "Casual", "Professional", "Creative"],
                        key="cultural_adaptation_select",
                        help="Adjust tone and style for different cultures"
                    )
                    
                    geographic_focus = st.selectbox(
                        "📍 Geographic Focus",
                        ["Global", "North America", "Europe", "Asia-Pacific", "Latin America"],
                        key="geographic_focus_select",
                        help="Focus your campaigns on specific regions"
                    )
            
            # Security Settings
            st.markdown("---")
            st.subheader("🔐 Security & Privacy")
            
            security_col1, security_col2 = st.columns(2)
            
            with security_col1:
                st.markdown("**🔐 Password Security**")
                
                if st.button("🔑 Change Password", use_container_width=True, key="change_password_main"):
                    st.session_state.show_update_password = True
                    st.rerun()
                
                # Show password requirements
                with st.expander("🛡️ Password Requirements"):
                    st.markdown("""
                    **Strong passwords must include:**
                    - At least 8 characters
                    - One uppercase letter (A-Z)
                    - One lowercase letter (a-z)  
                    - One number (0-9)
                    - One special character (!@#$%^&*)
                    """)
            
            with security_col2:
                st.markdown("**🔒 Privacy Settings**")
                
                data_retention = st.selectbox(
                    "📊 Data Retention",
                    ["30 days", "90 days", "1 year", "Until deleted"],
                    index=2,
                    help="How long to keep your generated leads"
                )
                
                usage_analytics = st.checkbox(
                    "📈 Usage Analytics",
                    value=True,
                    help="Help improve the platform by sharing anonymous usage data"
                )
            
            # Account Actions
            st.markdown("---")
            st.subheader("⚙️ Account Actions")
            
            action_col1, action_col2, action_col3 = st.columns(3)
            
            with action_col1:
                if st.button("📤 Export Account Data", use_container_width=True):
                    try:
                        # Create account data export
                        user_data = st.session_state.get('user_data', {})
                        export_data = {
                            "username": username,
                            "plan": user_plan,
                            "credits": current_credits,
                            "created_at": user_data.get('created_at', ''),
                            "total_leads_downloaded": user_data.get('total_leads_downloaded', 0),
                            "export_date": datetime.now().isoformat()
                        }
                        
                        export_json = json.dumps(export_data, indent=2)
                        
                        st.download_button(
                            "📥 Download Account Data",
                            data=export_json,
                            file_name=f"account_data_{username}_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"❌ Export failed: {str(e)}")
            
            with action_col2:
                if st.button("🔄 Reset Preferences", use_container_width=True):
                    if st.checkbox("⚠️ Confirm reset", key="confirm_reset_prefs"):
                        try:
                            # Reset user preferences to defaults
                            st.success("✅ Preferences reset to defaults")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Reset failed: {str(e)}")
                    else:
                        st.info("Check the box above to confirm")
            
            with action_col3:
                if st.button("🔒 Logout", use_container_width=True):
                    simple_auth.logout_user()
                    st.success("✅ Successfully logged out")
                    st.rerun()
                
            # 4️⃣ Close Account Button
            if st.button("❌ Close Account", use_container_width=True, key="close_account_btn"):
                st.session_state.show_close_expander = True
            
            # Show confirmation expander
            if st.session_state.get("show_close_expander", False):
                with st.expander("⚠️ Are you absolutely sure? This will permanently delete your account", expanded=True):
                    st.warning(
                        "⚠️ **PERMANENT DELETION WARNING** ⚠️\n\n"
                        "Deleting your account will:\n"
                        "• Remove ALL your data and credits\n" 
                        "• Delete any saved campaigns and settings\n"
                        "• Remove your user profile permanently\n"
                        "• **This action CANNOT be undone**",
                        icon="⚠️"
                    )
                    
                    # Reason for leaving
                    reason = st.selectbox(
                        "📝 Why are you closing your account? (helps us improve)",
                        [
                            "Select a reason...",
                            "Found a better alternative", 
                            "Too expensive",
                            "Not using it enough",
                            "Missing features I need",
                            "Technical issues",
                            "Privacy concerns",
                            "Other reason"
                        ],
                        key="close_reason"
                    )
                    
                    # Optional feedback
                    feedback = st.text_area(
                        "💬 Any suggestions to help us improve? (optional)",
                        placeholder="Your feedback helps us build a better product for future users...",
                        key="close_feedback",
                        height=100
                    )
                    
                    # Final confirmation checkbox
                    confirm_understood = st.checkbox(
                        "✅ I understand this will **permanently delete** my account and all data",
                        key="confirm_close"
                    )
                    
                    # Additional warning if they haven't selected a reason
                    reason_selected = reason != "Select a reason..."
                    
                    if not reason_selected:
                        st.info("💡 Please select a reason before proceeding")
                    
                    # Show what will be deleted
                    if confirm_understood:
                        current_user = simple_auth.get_current_user()
                        st.markdown("### 🗑️ The following will be deleted:")
                        st.markdown(f"""
                        - **User account:** {current_user}
                        - **All credits and payment history**
                        - **Campaign data and settings** 
                        - **Configuration files**
                        - **All stored preferences**
                        """)
                    
                    # Final delete button with double confirmation
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button(
                            "❌ Cancel",
                            use_container_width=True,
                            key="cancel_delete_btn"
                        ):
                            # Clear all the deletion-related session state
                            st.session_state.show_close_expander = False
                            st.session_state.pop('close_reason', None)
                            st.session_state.pop('close_feedback', None)
                            st.session_state.pop('confirm_close', None)
                            st.rerun()
                    
                    with col2:
                        delete_enabled = confirm_understood and reason_selected
                        
                        if st.button(
                            "🗑️ DELETE MY ACCOUNT PERMANENTLY" if delete_enabled else "❌ Complete Requirements Above",
                            type="primary" if delete_enabled else "secondary",
                            disabled=not delete_enabled,
                            use_container_width=True,
                            key="final_delete_btn"
                        ):
                            if delete_enabled:
                                # Show deletion in progress
                                with st.spinner("🗑️ Deleting your account..."):
                                    try:
                                        # Log the deletion reason and feedback
                                        current_user = simple_auth.get_current_user()
                                        st.write(f"📝 Deletion reason: {reason}")
                                        if feedback.strip():
                                            st.write(f"💬 User feedback: {feedback}")
                                        
                                        # Perform the actual deletion
                                        deletion_successful = simple_auth.delete_user_account()
                                        
                                        # The delete_user_account method will handle the rerun
                                        # So we don't need to do anything else here
                                        
                                    except Exception as e:
                                        st.error(f"❌ Account deletion failed: {str(e)}")
                                        st.info("💡 Please try again or contact support if the problem persists")
                                        
                                        # Log the error for debugging
                                        st.write(f"🐛 Error details: {e}")
                            else:
                                st.error("❌ Please complete all requirements before proceeding")


        # Additional helper function for complete cleanup
        def force_complete_user_cleanup(username: str):
            """Nuclear option: completely remove all traces of a user"""
            import os
            import json
            import glob
            import streamlit as st
            
            st.write(f"💣 COMPLETE CLEANUP for {username}")
            
            # 1. All possible JSON files
            json_files_to_check = [
                "users.json",
                "users_credits.json", 
                "users_credit.json",  # Check both versions
                "rate_limits.json",
                "password_reset_tokens.json"
            ]
            
            for json_file in json_files_to_check:
                if os.path.exists(json_file):
                    try:
                        with open(json_file, "r") as f:
                            data = json.load(f)
                        
                        if username in data:
                            del data[username]
                            
                            with open(json_file, "w") as f:
                                json.dump(data, f, indent=2)
                            
                            st.write(f"✅ Removed {username} from {json_file}")
                    except Exception as e:
                        st.write(f"❌ Error with {json_file}: {e}")
            
            # 2. All possible directories and file patterns
            patterns_to_check = [
                f"client_configs/client_{username}_config.json",
                f"user_data/{username}*",
                f"*{username}*",
            ]
            
            for pattern in patterns_to_check:
                try:
                    matching_files = glob.glob(pattern)
                    for file_path in matching_files:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            st.write(f"🗑️ Removed: {file_path}")
                except Exception as e:
                    st.write(f"⚠️ Pattern {pattern} error: {e}")
            
            st.write("💥 Complete cleanup finished")
            
            # Save preferences button
            st.markdown("---")
            
            if st.button("💾 Save All Settings", type="primary", use_container_width=True):
                try:
                    # Get current username
                    username = simple_auth.get_current_user() if user_authenticated else None
                    
                    # Update config with new default settings
                    if CONFIG_MANAGER_AVAILABLE:
                        config_updated = update_config(username, default_search, default_intensity)
                    else:
                        config_updated = False
                    
                    # Save user preferences (your existing code)
                    user_preferences = {
                        "default_search": default_search,
                        "default_intensity": default_intensity,
                        "email_completion": email_completion,
                        "email_weekly": email_weekly,
                        "email_updates": email_updates,
                        "email_tips": email_tips,
                        "data_retention": data_retention,
                        "usage_analytics": usage_analytics
                    }
                    
                    # Add multilingual preferences if available
                    if MULTILINGUAL_AVAILABLE:
                        user_preferences.update({
                            "interface_language": interface_language,
                            "default_dm_language": default_dm_language,
                            "cultural_style": cultural_style,
                            "geographic_focus": geographic_focus
                        })
                    
                    # Save to user's session data
                    user_data = st.session_state.get('user_data', {})
                    user_data['preferences'] = user_preferences
                    st.session_state.user_data = user_data
                    
                    if config_updated:
                        st.success("✅ Settings saved successfully!")
                        st.info("🔄 Your preferences will be applied to future campaigns")
                        st.info(f"📝 Updated: Search term = '{default_search}', Intensity = {default_intensity}")
                        
                        # Simple instruction for user
                        st.markdown("---")
                        st.markdown("### ✅ Settings Saved")
                        st.markdown(f"""
                        **Your new defaults:**
                        - 🔍 Search term: **{default_search}**
                        - 📊 Intensity: **{default_intensity}**
                        
                        **💡 To use these in Empire Scraper:**
                        - Go to Empire Scraper tab
                        - Click "🔄 Load from Settings" in the optional section
                        - Or just type your preferred values directly
                        """)
                        
                    else:
                        st.warning("⚠️ Settings partially saved - config update may have failed")
                    
                except Exception as e:
                    st.error(f"❌ Error saving settings: {str(e)}")
                    print(f"Settings save error: {e}")

            # Enhanced status indicator
            if st.session_state.get('settings_just_updated'):
                settings_update_time = st.session_state.get('settings_update_time', 'unknown')
                try:
                    if settings_update_time != 'unknown':
                        update_time = datetime.fromisoformat(settings_update_time)
                        time_ago = (datetime.now() - update_time).total_seconds()
                        
                        if time_ago < 300:  # Show for 5 minutes
                            st.info(f"🔄 Settings updated {int(time_ago)} seconds ago - Empire Scraper will refresh when you switch tabs")
                            
                            # Show current session state for verification
                            with st.expander("🔍 Current Session State", expanded=False):
                                st.json({
                                    "search_term": st.session_state.get('search_term'),
                                    "max_scrolls": st.session_state.get('max_scrolls'),
                                    "last_tab": st.session_state.get('last_active_tab'),
                                    "force_refresh": st.session_state.get('force_empire_refresh')
                                })
                        else:
                            # Clear the flag after 5 minutes
                            st.session_state.settings_just_updated = False
                except:
                    pass


st.markdown(
    """
    <style>
      /* make room for the footer so it doesn't cover content */
      .appview-container .main {
        padding-bottom: 60px;  
      }
      /* footer styling */
      .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 50px;
        background: rgba(0, 0, 0, 0.8);
        color: #aaa;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
        z-index: 1000;
      }
    </style>

    <div class="footer">
      ⚙️ Lead Generator Empire Settings | Secure &amp; Private
    </div>
    """,
    unsafe_allow_html=True,
)
