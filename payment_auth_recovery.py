
# payment_auth_recovery.py
"""
Payment Authentication Recovery Module
Handles authentication restoration after Stripe payment returns
"""
import streamlit as st
from discord_notification_system import send_discord_notification, send_linkedin_results_discord, send_linkedin_confirmation_discord
import os
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart 
import json
import stripe
import requests
import time
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
import threading


STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "https://leadgeneratorempire.com") 
)

NOTIFY_MODE = os.getenv("NOTIFY_MODE", "webhook")  # 'webhook' | 'email' | 'none'
NOTIFY_IN_UI  = os.getenv("NOTIFY_IN_UI", "0") == "1" # only send from UI when explicitly enabled

def restore_payment_authentication() -> bool:
    """
    CRITICAL: Handle authentication restoration after Stripe payment
    Returns True if this is a payment return, False otherwise
    """
    query_params = st.query_params
    
    # Check if this is a payment return
    payment_indicators = ["success", "payment_success", "cancelled", "plan", "package", "amount", "tier", "credits"]
    is_payment_return = any(param in query_params for param in payment_indicators)
    
    if not is_payment_return:
        return False
    
    # Get username from URL
    username_from_url = query_params.get("username", "")
    
    print(f"🔄 Payment return detected - User: {username_from_url}")
    
    # If user is already authenticated, we're good
    if st.session_state.get('authenticated', False):
        print("✅ User already authenticated")
        # even if authed, finalize the purchase (idempotent)
        _process_payment_success(query_params, username_from_url or st.session_state.get("username", ""))
        return True

    
    # Attempt to restore authentication
    if username_from_url and username_from_url != "unknown":
        print(f"🔧 Attempting to restore auth for: {username_from_url}")
        
        # Try multiple restoration methods
        if _restore_from_credit_system(username_from_url):
            _process_payment_success(query_params, username_from_url)
            return True
        
        if _restore_from_users_json(username_from_url):
            _process_payment_success(query_params, username_from_url)
            return True
        
        if _create_emergency_session(username_from_url, query_params):
            _process_payment_success(query_params, username_from_url)
            return True
    
    print("❌ Payment authentication restoration failed")
    return True  # Still a payment return, just failed to restore

def _restore_from_credit_system(username: str) -> bool:
    """Try to restore from credit system"""
    try:
        from postgres_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if user_info:
            print(f"✅ Found user in credit system: {user_info}")
            _set_session_state(username, user_info)
            return True
    except Exception as e:
        print(f"❌ Credit system restore error: {e}")
    
    return False

def _restore_from_users_json(username: str) -> bool:
    """Try to restore from users.json"""
    try:
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)
            
            if username in users:
                user_data = users[username]
                print(f"✅ Found user in users.json: {user_data}")
                _set_session_state(username, user_data)
                return True
    except Exception as e:
        print(f"❌ users.json restore error: {e}")
    
    return False

def _create_emergency_session(username: str, query_params: Dict) -> bool:
    """Create emergency session as last resort"""
    try:
        print(f"🚨 Creating emergency session for {username}")
        
        plan = query_params.get("plan", "starter")
        credits = int(query_params.get("credits", 250))
        
        emergency_user_data = {
            "username": username,
            "plan": plan,
            "credits": credits,
            "email": f"{username}@payment-recovery.com",
            "created_at": datetime.now().isoformat(),
            "emergency_recovery": True,
            "total_leads_downloaded": 0
        }
        
        _set_session_state(username, emergency_user_data)
        print(f"✅ Emergency session created for {username}")
        return True
        
    except Exception as e:
        print(f"❌ Emergency session creation failed: {e}")
        return False

def _set_session_state(username: str, user_data: Dict) -> None:
    """Set session state for authenticated user"""
    # FORCE restore session state
    st.session_state.authenticated = True
    st.session_state.username = username
    st.session_state.user_data = user_data
    st.session_state.credits = user_data.get('credits', 0)
    st.session_state.login_time = datetime.now().isoformat()
    
    # Also restore simple_auth state (import here to avoid circular imports)
    try:
        # We'll need to access simple_auth from the main module
        # This will be handled in the main app
        pass
    except:
        pass

# Updated _process_payment_success function:
def _process_payment_success(query_params: Dict, username: str) -> None:
    """Process payment success with Discord notifications only"""
    
    # Prevent duplicate processing
    stamp = query_params.get("timestamp") or query_params.get("session_id")
    if stamp:
        flag = f"_pkg_proc_{stamp}"
        if st.session_state.get(flag):
            print(f"Already processed payment {stamp}, skipping")
            return
        st.session_state[flag] = True

    try:
        if "success" in query_params:
            # Handle plan upgrades (unchanged)
            if "plan" in query_params:
                plan = query_params.get("plan", "")
                if plan:
                    print(f"Processing plan upgrade to: {plan}")
                    try:
                        from postgres_credit_system import credit_system
                        credit_system.update_user_plan(username, plan)
                        if 'user_data' in st.session_state:
                            st.session_state.user_data['plan'] = plan
                        print(f"Updated plan to: {plan}")
                    except Exception as e:
                        print(f"Plan update warning: {e}")
            
            # Handle package purchases 
            elif "package" in query_params:
                package = query_params.get("package", "")
                amount = query_params.get("amount", "0")
                industry = query_params.get("industry", "").replace('+', ' ')
                location = query_params.get("location", "").replace('+', ' ')
                session_id = query_params.get("session_id", "")
                
                # Check if this is a custom build
                requires_build = str(query_params.get("requires_build", "0")).lower() in ("1", "true", "yes")
                
                print(f"Processing package purchase: {package} for ${amount} (custom={requires_build})")
                
                # Always log the transaction first
                try:
                    from postgres_credit_system import credit_system
                    package_transaction = {
                        "type": "package_purchase",
                        "package_type": package,
                        "amount": float(amount),
                        "industry": industry,
                        "location": location,
                        "timestamp": datetime.now().isoformat(),
                        "status": "purchased",
                        "requires_build": requires_build,
                        "session_id": session_id
                    }
                    
                    user_info = credit_system.get_user_info(username)
                    if user_info:
                        if "transactions" not in user_info:
                            user_info["transactions"] = []
                        user_info["transactions"].append(package_transaction)
                        user_info["total_packages_purchased"] = user_info.get("total_packages_purchased", 0) + 1
                        credit_system.save_data()
                        print(f"Logged package purchase for {username}")
                except Exception as e:
                    print(f"Package logging warning: {e}")
                
                # Branch handling based on package type
                if requires_build:
                    # CUSTOM PACKAGE - Send Discord notification
                    print("Custom package - sending Discord notification")
                    
                    # Get user email for notification
                    user_data = st.session_state.get("user_data") or {}
                    user_email = user_data.get("email", f"{username}@leadgeneratorempire.com")
                    
                    def discord_worker():
                        try:
                            result = send_via_webhook(
                                username=username,
                                user_email=user_email,
                                package_type=package,
                                amount=float(amount),
                                industry=industry,
                                location=location,
                                session_id=session_id,
                                timestamp=stamp or str(int(time.time()))
                            )
                            print(f"Discord notification result: {result}")
                            
                        except Exception as e:
                            print(f"Discord notification failed: {e}")
                            # Fallback to file logging
                            with open("custom_orders.log", "a") as f:
                                f.write(f"{datetime.now()}: {username}, {package}, ${amount}, {industry}, {location}\n")
                    
                    # Start Discord notification in background
                    discord_thread = threading.Thread(target=discord_worker, daemon=True)
                    discord_thread.start()
                    print("Discord notification queued")
                    
                    # Store for UI display - DON'T add to downloads
                    st.session_state["package_industry"] = industry
                    st.session_state["package_location"] = location 
                    st.session_state["custom_order_pending"] = True
                    
                else:
                    # PREBUILT PACKAGE - Add to downloads immediately
                    print(f"Prebuilt package - adding to downloads")
                    
                    try:
                        from package_system import add_package_to_database
                        name_map = {
                            "starter": "Niche Starter Pack",
                            "deep_dive": "Industry Deep Dive",
                            "domination": "Market Domination",
                        }
                        display_name = name_map.get(package, package.replace("_", " ").title())
                        add_package_to_database(username, display_name)
                        
                        # Cache for UI display
                        st.session_state["package_industry"] = industry
                        st.session_state["package_location"] = location
                        st.session_state["prebuilt_package_ready"] = True
                        
                        print(f"Added {display_name} to downloads for {username}")
                    except Exception as e:
                        print(f"Package DB add warning: {e}")

    except Exception as e:
        print(f"Payment success processing error: {e}")
        


# Optional: Add a function to check email queue status
def get_email_queue_status():
    """Check how many email threads are currently running"""
    import threading
    email_threads = [t for t in threading.enumerate() if t.name.startswith("EmailWorker")]
    return len(email_threads)

def show_payment_success_message() -> bool:
    """
    Show payment success message if user just completed payment
    Returns True if message was shown (should stop execution), False otherwise
    """
    query_params = st.query_params
    
    if "success" in query_params:
        plan = query_params.get("plan", "")
        amount = query_params.get("amount", "")
        package = query_params.get("package", "")
        
        if plan:
            #st.balloons()
            st.success(f"🎉 Plan upgrade successful! Welcome to {plan.title()} plan!")
            
            if st.button("🚀 Continue to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            
            return True
            
        elif package:
            #st.balloons()
            st.success(f"📦 Package purchase successful! Your {package} package will be delivered soon!")
            
            # ---- Admin notification (idempotent by timestamp) ----
        if NOTIFY_MODE == "email" and NOTIFY_IN_UI:    
            username = st.session_state.get("username") or st.query_params.get("username", "")
            user_email = (st.session_state.get("user_data") or {}).get("email", "")
            amount_val = float(amount or 0)
            session_id = st.query_params.get("session_id") or st.query_params.get("payment_intent")
            stamp = st.query_params.get("timestamp")  # added by your package success_url
            notice_flag = f"_pkg_notice_{stamp or ''}"
            
            # Resolve industry/location with robust fallbacks
            industry = (
                st.query_params.get("industry")
                or st.session_state.get("package_industry")
                or ""
            )
            location = (
                st.query_params.get("location")
                or st.session_state.get("package_location")
                or ""
            )
            
            if st.button("🏠 Back to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            
            return True
    
    elif "cancelled" in query_params:
        st.warning("⚠️ Payment was cancelled. You can try again anytime!")
        
        if st.button("🔙 Back to Dashboard"):
            st.query_params.clear()
            st.rerun()
        
        return True
    
    return False

def _normalize_plan_from_user_data(user_data: dict) -> str:
    """Return one of {'demo','starter','pro','ultimate'} from DB row."""
    ud = user_data or {}
    sp = (ud.get("subscribed_plan") or "").lower()
    ss = (ud.get("subscription_status") or "").lower()
    bp = (ud.get("plan") or "").lower()

    if sp == "demo" or bp == "demo":
        return "demo"
    if ss == "active" and sp in {"starter", "pro", "ultimate"}:
        return sp
    if bp in {"starter", "pro", "ultimate"}:
        return bp
    return "demo"

def update_simple_auth_state(simple_auth_instance) -> None:
    """Update simple_auth state after session restoration WITHOUT clobbering plan."""
    if not st.session_state.get('authenticated', False):
        return

    username  = st.session_state.get('username')
    user_data = st.session_state.get('user_data') or {}
    if not username:
        return

    # Sync simple_auth
    simple_auth_instance.current_user = username
    simple_auth_instance.user_data     = user_data

    # Keep credits in sync
    st.session_state['credits'] = user_data.get('credits', st.session_state.get('credits', 0))

    # Only set plan if it's missing/invalid; NEVER default to 'starter'
    current_plan = st.session_state.get('plan')
    if current_plan not in {'demo','starter','pro','ultimate'}:
        st.session_state['plan'] = _normalize_plan_from_user_data(user_data)

    print(f"✅ Updated simple_auth state for {username} (plan={st.session_state.get('plan')})")
    print("[PLAN_GUARD] after update_simple_auth_state =>", st.session_state.get("plan"))


def create_package_stripe_session(stripe, username: str, package_type: str, amount: float, description: str, industry: str, location: str, requires_build: bool = False):
    """Create Stripe session for package purchases with custom/prebuilt distinction"""
    import time
    from urllib.parse import quote_plus
    
    # Get user email safely
    try:
        user_data = st.session_state.get('user_data', {})
        user_email = user_data.get('email', f"{username}@empire.com")
    except:
        user_email = f"{username}@empire.com"
        
    base = APP_BASE_URL.rstrip("/")
    
    # Create package-specific success URL with requires_build flag
    success_url = (
        f"{base}/?success=1"
        f"&package_success=1"
        f"&package={package_type}"
        f"&username={username}"
        f"&amount={amount}"
        f"&industry={quote_plus(industry or '')}"
        f"&location={quote_plus(location or '')}"
        f"&requires_build={'1' if requires_build else '0'}"  # NEW: Add this flag
        f"&timestamp={int(time.time())}"
        f"&session_id={{CHECKOUT_SESSION_ID}}"  # This gets replaced by Stripe
    )

    cancel_url = (
        f"{base}/?success=0"
        f"&package_cancelled=1"
        f"&package={package_type}"
        f"&username={username}"
        f"&industry={quote_plus(industry or '')}"
        f"&location={quote_plus(location or '')}"
    )
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": description,
                    "description": f"Industry: {industry} | Location: {location} | {'Custom Build' if requires_build else 'Ready to Download'}"
                },
                "unit_amount": int(amount * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={
            "purchase_type": "package",
            "username": username,
            "package_type": package_type,
            "target_industry": industry,
            "target_location": location,
            "amount": str(amount),
            "requires_build": "1" if requires_build else "0",  # NEW: Store in metadata
            "order_type": "custom" if requires_build else "prebuilt"  # NEW: Human readable type
        }
    )
    
    return session

# Update your show_payment_success_message function to handle packages:

def show_payment_success_message() -> bool:
    """Show payment success message with custom/prebuilt distinction"""
    query_params = st.query_params
    
    if "success" in query_params:
        plan = query_params.get("plan", "")
        amount = query_params.get("amount", "")
        package = query_params.get("package", "")
        industry = query_params.get("industry", "").replace('+', ' ')
        location = query_params.get("location", "").replace('+', ' ')
        requires_build = str(query_params.get("requires_build", "0")).lower() in ("1", "true", "yes")
        
        if plan:
            # Plan upgrade success (unchanged)
            st.success(f"🎉 Plan upgrade successful! Welcome to {plan.title()} plan!")
            
            if st.button("🚀 Continue to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            return True
            
        elif package:
            # Package purchase success - different messages for custom vs prebuilt
            package_names = {
                "starter": "Niche Starter Pack",
                "deep_dive": "Industry Deep Dive",
                "domination": "Market Domination"
            }
            
            package_name = package_names.get(package, package.title())
            
            if requires_build:
                # CUSTOM PACKAGE SUCCESS
                st.success(f"🔨 Custom {package_name} order received!")
                
                st.info(f"""
                **🎯 Your Custom Order Details:**
                - 📦 Package: {package_name}
                - 🏢 Industry: {industry or 'As discussed'}
                - 📍 Location: {location or 'As discussed'}
                - 💰 Investment: ${amount}
                
                **📧 What happens next:**
                1. **Confirmation sent** - Check your email for order confirmation
                2. **Admin notified** - Our team has been alerted about your custom order
                3. **Build process starts** - We'll begin researching and building your custom lead list
                4. **Delivery timeline** - Expect your custom leads within 24-48 hours
                5. **Email delivery** - Your custom leads will be sent to your registered email
                
                **Need to modify your order?** Contact support immediately.
                """)
                
                st.warning("⏳ This is a custom build order. Your leads will be delivered via email within 2-5 business days.")
                
            else:
                # PREBUILT PACKAGE SUCCESS
                st.success(f"📦 {package_name} purchase successful!")
                
                if package == "starter":
                    st.info(f"""
                    **🎯 Your Niche Starter Pack is ready:**
                    - ✅ 500 targeted leads in {industry}
                    - ✅ Geographic focus: {location}
                    - ✅ 2-3 platforms included
                    - ✅ **Available now in Downloads tab**
                    - ✅ CSV + Google Sheets format
                    """)
                elif package == "deep_dive":
                    st.info(f"""
                    **🔥 Your Industry Deep Dive is ready:**
                    - ✅ 2,000 highly-targeted leads in {industry}
                    - ✅ Geographic focus: {location}
                    - ✅ All 8 platforms included
                    - ✅ **Available now in Downloads tab**
                    - ✅ Advanced relevance filtering applied
                    """)
                elif package == "domination":
                    st.info(f"""
                    **💎 Your Market Domination Package is ready:**
                    - ✅ 5,000 premium leads in {industry}
                    - ✅ Geographic focus: {location}
                    - ✅ **Available now in Downloads tab**
                    - ✅ Phone/email enrichment included
                    - ✅ Advanced geographic targeting applied
                    """)
                
                st.markdown("### 📂 Access Your Leads")
                st.markdown("**👈 Click 'My Downloads' in the sidebar to download your lead files**")
            
            if st.button("🏠 Back to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            
            return True
    
    elif "cancelled" in query_params:
        st.warning("⚠️ Payment was cancelled. You can try again anytime!")
        
        if st.button("🔙 Back to Packages"):
            st.query_params.clear()
            st.rerun()
        
        return True
    
    return False  

def create_improved_stripe_session(stripe, username: str, plan_type: str, amount: float, description: str):
    """Create improved Stripe checkout session with better return handling"""
    
    # Get user email safely
    try:
        user_data = st.session_state.get('user_data', {})
        user_email = user_data.get('email', f"{username}@empire.com")
    except:
        user_email = f"{username}@empire.com"
        
    base = APP_BASE_URL.rstrip("/")
    # Create more robust success URL
    success_url = f"https://leadgeneratorempire.com/?success=true&plan={plan_type}&username={username}&amount={amount}&timestamp={int(time.time())}"
    cancel_url = (
        f"{base}/?cancel=1"
        f"&type=credits"
        f"&tier={plan_type.lower().replace(' ', '_')}"
        f"&username={username}"
    )
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": description
                },
                "unit_amount": int(amount * 97),
                "recurring": {"interval": "month"} if plan_type in ["starter", "pro", "ultimate"] else None
            },
            "quantity": 1,
        }],
        mode="subscription" if plan_type in ["starter", "pro", "ultimate"] else "payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={
            "username": username,
            "plan_type": plan_type,
            "amount": str(amount)
        }
    )
    
    return session

def send_via_webhook(username, user_email, package_type, amount, industry, location, session_id, timestamp):
    """Send custom order notification via webhook"""
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not webhook_url:
        print("No WEBHOOK_URL configured")
        return False
    
    # Discord-formatted message
    embed = {
        "title": "New Custom Lead Package Order",
        "color": 15158332,  # Red color
        "fields": [
            {"name": "Customer", "value": f"{username}\n{user_email}", "inline": True},
            {"name": "Package", "value": package_type.replace("_", " ").title(), "inline": True},
            {"name": "Amount", "value": f"${amount}", "inline": True},
            {"name": "Industry", "value": industry or "Not specified", "inline": True},
            {"name": "Location", "value": location or "Not specified", "inline": True},
            {"name": "Session ID", "value": session_id or "N/A", "inline": False}
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 204  # Discord returns 204 on success
    except Exception as e:
        print(f"Discord webhook error: {e}")
        return False
            
    except requests.exceptions.Timeout:
        print("Webhook request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("Webhook connection failed")
        return False
    except Exception as e:
        print(f"Webhook error: {e}")
        return False

def send_notification_with_fallback(username, user_email, package_type, amount, industry, location, session_id, timestamp):
    """Try webhook first, fall back to file logging"""
    
    # Try webhook notification
    webhook_sent = send_via_webhook(username, user_email, package_type, amount, industry, location, session_id, timestamp)
    
    if webhook_sent:
        return True
    
    # Fallback: Log to file for manual processing
    try:
        order_data = {
            "timestamp": datetime.now().isoformat(),
            "username": username,
            "user_email": user_email,
            "package_type": package_type,
            "amount": amount,
            "industry": industry,
            "location": location,
            "session_id": session_id,
            "status": "webhook_failed"
        }
        
        # Write to JSON lines file for easy parsing
        with open("failed_notifications.jsonl", "a") as f:
            f.write(json.dumps(order_data) + "\n")
        
        print(f"Order logged to file for manual processing: {username}")
        return True
        
    except Exception as e:
        print(f"File logging also failed: {e}")
        return False


# Webhook service options and setup:

def setup_webhook_services():
    """
    Webhook service options you can use:
    
    1. **Zapier Webhooks** (easiest):
       - Create Zapier account
       - Make a "Catch Hook" trigger
       - Add Gmail/Slack/etc action
       - Use the webhook URL Zapier gives you
    
    2. **Make.com (Integromat)**:
       - Create webhook trigger
       - Add email/notification actions
       - Use their webhook URL
    
    3. **Discord Webhook** (for notifications):
       - Create Discord server
       - Add webhook in channel settings
       - Use Discord webhook URL
    
    4. **Slack Incoming Webhooks**:
       - Set up Slack app
       - Add incoming webhook
       - Use Slack webhook URL
    
    5. **Custom webhook server** (advanced):
       - Deploy simple webhook receiver
       - Forward notifications via email/SMS
    """
    pass

def test_webhook():
    """Test your webhook setup"""
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not webhook_url:
        print("WEBHOOK_URL not configured")
        return False
    
    test_payload = {
        "type": "test",
        "message": "Webhook test from Lead Generator Empire",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(webhook_url, json=test_payload, timeout=10)
        print(f"Test webhook response: {response.status_code}")
        return 200 <= response.status_code < 300
    except Exception as e:
        print(f"Test webhook failed: {e}")
        return False

# Add this to test your webhook setup
def debug_webhook_setup():
    """Add this to your debug interface"""
    if st.button("Test Webhook", key="test_webhook_btn"):
        webhook_url = os.getenv("WEBHOOK_URL")
        
        if not webhook_url:
            st.error("WEBHOOK_URL not set in Railway environment")
        else:
            st.info(f"Testing webhook: {webhook_url[:50]}...")
            
            success = test_webhook()
            
            if success:
                st.success("Webhook test successful!")
            else:
                st.error("Webhook test failed - check Railway logs")

def debug_authentication_state(simple_auth_instance, credit_system) -> None:
    """Debug authentication state - for troubleshooting"""
    
    if st.button("🔍 Debug Authentication State"):
        st.subheader("🔧 Authentication Debug Info")
        
        # Session state
        st.markdown("**📊 Streamlit Session State:**")
        auth_keys = ['authenticated', 'username', 'user_data', 'credits', 'login_time']
        for key in auth_keys:
            value = st.session_state.get(key, "NOT SET")
            st.text(f"{key}: {value}")
        
        # Simple auth state
        st.markdown("**🔐 Simple Auth State:**")
        st.text(f"current_user: {simple_auth_instance.current_user}")
        st.text(f"user_data: {simple_auth_instance.user_data}")
        st.text(f"is_authenticated(): {simple_auth_instance.is_authenticated()}")
        
        # URL parameters
        st.markdown("**🔗 URL Parameters:**")
        query_params = st.query_params
        if query_params:
            for key, value in query_params.items():
                st.text(f"{key}: {value}")
        else:
            st.text("No URL parameters")
        
        # Credit system check
        st.markdown("**💎 Credit System Check:**")
        try:
            username = st.session_state.get('username', 'none')
            if username and username != 'none':
                user_info = credit_system.get_user_info(username)
                st.text(f"Credit system has user: {bool(user_info)}")
                if user_info:
                    st.json(user_info)
            else:
                st.text("No username to check")
        except Exception as e:
            st.text(f"Credit system error: {e}")
        
        # Quick fix button
        st.markdown("**🔧 Force Re-authentication:**")
        username = st.text_input("Enter username:", key="debug_username")
        if username and st.button("🚀 Force Login", key="debug_force_login"):
            try:
                user_info = credit_system.get_user_info(username)
                if user_info:
                    _set_session_state(username, user_info)
                    update_simple_auth_state(simple_auth_instance)
                    st.success("✅ Force login successful!")
                    st.rerun()
                else:
                    st.error("❌ User not found")
            except Exception as e:
                st.error(f"❌ Force login failed: {e}")
                
def scroll_to_top():
    """Force scroll to top of page using JavaScript"""
    scroll_script = """
    <script>
        // Scroll to top immediately
        window.scrollTo(0, 0);
        
        // Also scroll after a small delay in case of timing issues
        setTimeout(function() {
            window.scrollTo(0, 0);
        }, 100);
        
        // Force focus to top of page
        document.body.scrollTop = 0;
        document.documentElement.scrollTop = 0;
    </script>
    """
    st.markdown(scroll_script, unsafe_allow_html=True)
                
