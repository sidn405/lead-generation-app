
# payment_auth_recovery.py
"""
Payment Authentication Recovery Module
Handles authentication restoration after Stripe payment returns
"""
import streamlit as st
from emailer import send_admin_package_notification, EMAIL_ADDRESS
import os 
import json
import time
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "https://leadgeneratorempire.com") 
)

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

def _process_payment_success(query_params: Dict, username: str) -> None:
    """Process payment success actions"""
    try:
        if "success" in query_params and "plan" in query_params:
            plan = query_params.get("plan", "")
            if plan:
                print(f"📋 Processing plan upgrade to: {plan}")
                # Update plan in system
                try:
                    from postgres_credit_system import credit_system
                    credit_system.update_user_plan(username, plan)
                    
                    # Update session state
                    if 'user_data' in st.session_state:
                        st.session_state.user_data['plan'] = plan
                    
                    print(f"✅ Updated plan to: {plan}")
                except Exception as e:
                    print(f"⚠️ Plan update warning: {e}")
    except Exception as e:
        print(f"⚠️ Payment success processing error: {e}")

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


            if stamp and not st.session_state.get(notice_flag):
                admin_email = os.getenv("ADMIN_EMAIL", EMAIL_ADDRESS)
                sent = send_admin_package_notification(
                    admin_email=admin_email,
                    username=username,
                    user_email=user_email,
                    package_type=package,
                    amount=amount_val,
                    industry=industry,
                    location=location,
                    session_id=session_id,
                    timestamp=stamp
                )
                st.session_state[notice_flag] = True
                if sent:
                    st.info("📨 Admin has been notified. We’re preparing your package now.")
            
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

def update_simple_auth_state(simple_auth_instance) -> None:
    """Update simple_auth state after session restoration"""
    if st.session_state.get('authenticated', False):
        username = st.session_state.get('username')
        user_data = st.session_state.get('user_data')
        
        if username and user_data:
            simple_auth_instance.current_user = username
            simple_auth_instance.user_data = user_data
            print(f"✅ Updated simple_auth state for {username}")

def create_package_stripe_session(stripe, username: str, package_type: str, amount: float, description: str, industry: str, location: str):
    """Create Stripe session for package purchases (one-time payments)"""
    import time
    from urllib.parse import quote_plus
    # Get user email safely
    try:
        user_data = st.session_state.get('user_data', {})
        user_email = user_data.get('email', f"{username}@empire.com")
    except:
        user_email = f"{username}@empire.com"
        
    base = APP_BASE_URL.rstrip("/")
    # Create package-specific success URL
    success_url = f"https://leadgeneratorempire.com/?success=true&package={package_type}&username={username}&amount={amount}&industry={industry.replace(' ', '+')}&location={location.replace(' ', '+')}&timestamp={int(time.time())}"
    cancel_url = (
        f"{base}/?success=0"
        f"&cancel=1"
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
                    "description": f"Industry: {industry} | Location: {location}"
                },
                "unit_amount": int(amount * 100),  # Convert to cents
            },
            "quantity": 1,
        }],
        mode="payment",  # One-time payment for packages
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={
            "purchase_type": "package",
            "username": username,
            "package_type": package_type,
            "target_industry": industry,
            "target_location": location,
            "amount": str(amount)
        }
    )
    
    return session

# Update your show_payment_success_message function to handle packages:

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
        industry = query_params.get("industry", "").replace('+', ' ')
        location = query_params.get("location", "").replace('+', ' ')
        
        if plan:
            # Plan upgrade success
            #st.balloons()
            st.success(f"🎉 Plan upgrade successful! Welcome to {plan.title()} plan!")
            
            # Show plan benefits
            if plan == "pro":
                st.info("""
                **🚀 Pro Plan Activated:**
                - ✅ 6 platforms unlocked (Twitter, Facebook, LinkedIn, TikTok, Instagram, YouTube)
                - ✅ 2,000 credits per session
                - ✅ Advanced filtering & relevance scoring
                - ✅ Priority support
                """)
            elif plan == "ultimate":
                st.info("""
                **👑 Ultimate Plan Activated:**
                - ✅ All 8 platforms unlocked (adds Medium, Reddit)
                - ✅ Unlimited credits per session
                - ✅ Enterprise features
                - ✅ Priority+ support
                """)
            elif plan == "starter":
                st.info("""
                **🎯 Starter Plan Activated:**
                - ✅ 2 platforms unlocked (Twitter, Facebook)
                - ✅ 250 credits per session
                - ✅ Basic filtering and CSV export
                - ✅ Email support
                """)
            
            if st.button("🚀 Continue to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            
            return True
            
        elif package:
            # Package purchase success
            #st.balloons()
            
            package_names = {
                "starter": "Niche Starter Pack",
                "deep_dive": "Industry Deep Dive",
                "domination": "Market Domination"
            }
            
            package_name = package_names.get(package, package.title())
            
            st.success(f"📦 {package_name} purchase successful!")
            
            # Show package details
            if package == "starter":
                st.info(f"""
                **🎯 Your Niche Starter Pack:**
                - ✅ 500 targeted leads in {industry}
                - ✅ Geographic focus: {location}
                - ✅ 2-3 platforms included
                - ✅ CSV + Google Sheets delivery
                - ✅ 48-hour delivery timeline
                """)
            elif package == "deep_dive":
                st.info(f"""
                **🔥 Your Industry Deep Dive:**
                - ✅ 2,000 highly-targeted leads in {industry}
                - ✅ Geographic focus: {location}
                - ✅ All 8 platforms included
                - ✅ Advanced relevance filtering
                - ✅ Pre-generated DMs for your industry
                - ✅ 24-hour delivery timeline
                """)
            elif package == "domination":
                st.info(f"""
                **💎 Your Market Domination Package:**
                - ✅ 5,000 premium leads in {industry}
                - ✅ Geographic focus: {location}
                - ✅ Advanced geographic targeting
                - ✅ Phone/email enrichment when available
                - ✅ Custom DM sequences
                - ✅ 12-hour priority delivery
                - ✅ Dedicated account manager assigned
                """)
            
            st.markdown("---")
            st.markdown("### 📧 What Happens Next?")
            st.markdown("""
            1. **📧 Confirmation Email**: You'll receive a detailed order confirmation
            2. **🔬 Research Phase**: Our team begins targeting and research
            3. **📊 Lead Generation**: We generate your targeted leads
            4. **📤 Delivery**: Results delivered via email as promised
            5. **💬 Support**: Dedicated support throughout the process
            """)
            
            if st.button("🏠 Back to Dashboard", type="primary"):
                st.query_params.clear()
                st.rerun()
            
            return True
    
    elif "cancelled" in query_params:
        # Payment cancelled
        st.warning("⚠️ Payment was cancelled. You can try again anytime!")
        
        # Show what they missed
        st.info("""
        **💡 Don't miss out on:**
        - High-quality targeted leads
        - Fast delivery times
        - Expert research and filtering
        - Dedicated customer support
        """)
        
        if st.button("🔙 Back to Packages"):
            st.query_params.clear()
            st.rerun()
        
        return True
    
    return False

# Update the _process_payment_success function to handle packages:

def _process_payment_success(query_params: Dict, username: str) -> None:
    """Process payment success actions for both plans and packages"""
    try:
        if "success" in query_params:
            if "plan" in query_params:
                # Handle plan upgrade
                plan = query_params.get("plan", "")
                if plan:
                    print(f"📋 Processing plan upgrade to: {plan}")
                    try:
                        from postgres_credit_system import credit_system
                        credit_system.update_user_plan(username, plan)
                        
                        # Update session state
                        if 'user_data' in st.session_state:
                            st.session_state.user_data['plan'] = plan
                        
                        print(f"✅ Updated plan to: {plan}")
                    except Exception as e:
                        print(f"⚠️ Plan update warning: {e}")
            
            elif "package" in query_params:
                # Handle package purchase
                package = query_params.get("package", "")
                amount = query_params.get("amount", "0")
                industry = query_params.get("industry", "").replace('+', ' ')
                location = query_params.get("location", "").replace('+', ' ')
                
                print(f"📦 Processing package purchase: {package} for ${amount}")
                
                try:
                    from postgres_credit_system import credit_system
                    
                    # Log the package purchase
                    package_transaction = {
                        "type": "package_purchase",
                        "package_type": package,
                        "amount": float(amount),
                        "industry": industry,
                        "location": location,
                        "timestamp": datetime.now().isoformat(),
                        "status": "purchased"
                    }
                    
                    # Add transaction to user record
                    user_info = credit_system.get_user_info(username)
                    if user_info:
                        if "transactions" not in user_info:
                            user_info["transactions"] = []
                        user_info["transactions"].append(package_transaction)
                        
                        # Update total packages purchased
                        user_info["total_packages_purchased"] = user_info.get("total_packages_purchased", 0) + 1
                        
                        credit_system.save_data()
                        print(f"✅ Logged package purchase for {username}")
                    
                except Exception as e:
                    print(f"⚠️ Package logging warning: {e}")
    
    except Exception as e:
        print(f"⚠️ Payment success processing error: {e}")

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