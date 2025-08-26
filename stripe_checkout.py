

# stripe_checkout.py - Updated for better tab organization
import time
import os
import stripe
import streamlit as st
from typing import Tuple, List, Dict
#from simple_credit_system import credit_system
from postgres_credit_system import credit_system
from datetime import datetime

APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "https://leadgeneratorempire.com") 
)

def create_package_download(username: str, package_type: str, industry: str, location: str) -> bool:
    """Create downloadable package file for user"""
    try:
        import os
        import shutil
        from datetime import datetime
        
        # Map package types to your existing CSV files
        package_files = {
            "starter": "leads/fitness_wellness_500.csv",
            "deep_dive": "leads/fitness_wellness_2000.csv", 
            "domination": "leads/fitness_wellness_5000.csv"
        }
        
        # Get source file
        source_file = package_files.get(package_type)
        if not source_file or not os.path.exists(source_file):
            print(f"Source file not found: {source_file}")
            return False
        
        # Create user downloads directory
        downloads_dir = f"downloads/{username}"
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{package_type}_{industry}_{location}_{timestamp}.csv"
        destination = os.path.join(downloads_dir, filename)
        
        # Copy the file
        shutil.copy2(source_file, destination)
        
        # Add to downloads tracking system
        add_to_downloads_database(username, filename, package_type, industry, location)
        
        print(f"Package created: {destination}")
        return True
        
    except Exception as e:
        print(f"Package creation error: {e}")
        return False

def add_to_downloads_database(username: str, filename: str, package_type: str, industry: str, location: str):
    """Add package to downloads tracking system"""
    try:
        # This should integrate with however your "My Downloads" tab works
        # You might need to create/update a downloads.json file or database table
        
        download_entry = {
            "username": username,
            "filename": filename,
            "package_type": package_type,
            "industry": industry,
            "location": location,
            "created_at": datetime.now().isoformat(),
            "downloaded_count": 0
        }
        
        # Save to your downloads system
        # (You'll need to implement this based on how My Downloads reads data)
        
    except Exception as e:
        print(f"Downloads database error: {e}")
        
def _restore_session_state(username: str):
    """Helper to restore session state after package purchase"""
    try:
        from postgres_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if user_info:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = user_info
            st.session_state.credits = user_info.get("credits", 0)
            st.session_state.user_plan = user_info.get("plan", "demo")
            st.session_state.show_login = False
            st.session_state.show_register = False
            print(f"Session state set: plan={st.session_state.user_plan}, credits={st.session_state.credits}")
    except Exception as e:
        print(f"Session restore error: {e}")

# ---- Handle ?payment_success=1 redirects deterministically ----
def handle_payment_success_url():
    """Finalize purchase from query params, update Postgres, refresh session/UI."""
    if not st.query_params.get("payment_success"):
        return False

    # Pull params
    qp = st.query_params

    def _v(key, default=None):
        v = qp.get(key, default)
        # st.query_params can return list-like; normalize to scalar
        if isinstance(v, (list, tuple)):
            return v[0] if v else default
        return v

    username         = (_v("username", "") or "").strip()
    payment_type     = (_v("type", "") or "").strip()
    tier_name        = (_v("tier", "") or "").strip()
    credits          = int(_v("credits", 0) or 0)
    amount           = int(float(_v("amount", 0) or 0))
    monthly_credits  = int(_v("monthly_credits", 0) or 0)

    # ✅ the checkout session id that we appended in success_url as {CHECKOUT_SESSION_ID}
    session_id = (
        _v("session_id")
        or _v("checkout_session_id")
        or _v("cs")
        or None
    )

    print(f"[stripe return] user={username} type={payment_type} tier={tier_name} "
        f"credits={credits} monthly_credits={monthly_credits} session_id={session_id}")
    
    is_credit_success = bool(qp.get("payment_success"))
    is_package_success = bool(qp.get("success") and qp.get("package"))
    
    if not (is_credit_success or is_package_success):
        return False

    # Handle package purchases
    if is_package_success:
        username = qp.get("username")
        package_key = qp.get("package")
        
        if username and package_key:
            # Map package keys to display names
            package_names = {
                "starter": "Niche Starter Pack",
                "deep_dive": "Industry Deep Dive", 
                "domination": "Market Domination"
            }
            
            package_name = package_names.get(package_key, package_key)
            
            # Add to package database
            from package_system import add_package_to_database
            add_package_to_database(username, package_name)
            
            # Restore session state
            _restore_session_state(username)
            
            # Show success message
            st.balloons()
            st.success(f"Package '{package_name}' added to your downloads!")
            
            # Clear params and redirect
            st.query_params.clear()
            st.rerun()
            return True
        
    payment_type = qp.get("type", "subscription")
    tier_name = (qp.get("tier") or "").replace("_", " ").strip().lower()
    monthly_credits = int(qp.get("monthly_credits", "0") or 0)
    credits = int(qp.get("credits", "0") or 0)
    username = qp.get("username") or st.session_state.get("username")
    payment_intent = qp.get("session_id") or qp.get("payment_intent") or "unknown"
    amount = float(qp.get("amount", "0") or 0)
    
    # NEW: Check for package purchases
    package_type = qp.get("package")
    industry = qp.get("industry", "").replace('+', ' ')
    location = qp.get("location", "").replace('+', ' ')

    # --- Idempotency guard: prevent double credit adds on reruns ---
    pid = payment_intent  # from qp.get("session_id") or "payment_intent"
    if pid and pid != "unknown":
        flag = f"_paid_{pid}"
        if st.session_state.get(flag):
            # Already processed in this browser session, just clean URL and rerun
            st.query_params.clear()
            st.rerun()
            return True
        st.session_state[flag] = True

    if not username:
        st.error("You're not signed in. Please log in and try again.")
        return True
    
    subscription_id = None
    customer_id = None
    current_period_end = None

    if session_id:
        try:
            sess = stripe.checkout.Session.retrieve(
                session_id,
                expand=["subscription", "customer"]
            )
            if getattr(sess, "subscription", None):
                subscription_id = (
                    sess.subscription.id
                    if hasattr(sess.subscription, "id") else str(sess.subscription)
                )
                if hasattr(sess.subscription, "current_period_end"):
                    current_period_end = int(sess.subscription.current_period_end or 0)

            if getattr(sess, "customer", None):
                customer_id = (
                    sess.customer.id
                    if hasattr(sess.customer, "id") else str(sess.customer)
                )
        except Exception as e:
            print(f"[stripe ids] capture failed: {e}")

    from postgres_credit_system import credit_system
    from datetime import datetime
    
    # Process payment
    is_subscription = (payment_type == "subscription") or (monthly_credits > 0)
    
    # --- expand checkout session to capture billing IDs (subscription/customer) ---
    try:
        if session_id:
            sess = stripe.checkout.Session.retrieve(
                session_id,
                expand=["subscription", "customer"]
            )
            subscription_id = None
            customer_id = None
            current_period_end = None

            if getattr(sess, "subscription", None):
                subscription_id = (
                    sess.subscription.id
                    if hasattr(sess.subscription, "id") else str(sess.subscription)
                )
                if hasattr(sess.subscription, "current_period_end"):
                    current_period_end = int(sess.subscription.current_period_end or 0)

            if getattr(sess, "customer", None):
                customer_id = sess.customer.id if hasattr(sess.customer, "id") else str(sess.customer)

            if subscription_id or customer_id:
                from postgres_credit_system import credit_system
                credit_system.set_stripe_billing(
                    username=username,
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    current_period_end_epoch=current_period_end or 0,
                )
    except Exception as e:
        print(f"[stripe ids] capture failed: {e}")
    # ----------------------------------------------------------------------------- 

    # Normalize inputs up front
    plan_key = (tier_name or "").strip().lower().replace(" ", "_")
    credit_amount = (monthly_credits if is_subscription else credits) or 0
    is_package = bool(package_type)

    # capture pre state so we can verify changes even if functions return None
    prev = credit_system.get_user_info(username) or {}
    prev_credits = int(prev.get("credits", 0))
    prev_status  = (prev.get("subscription_status") or "").lower()

    ok = False
    err_msg = None

    if is_package:
        # Package flow
        try:
            print(f"Processing package purchase: {package_type} for {username}")
            ok = bool(create_package_download(username, package_type, industry, location))
            if ok:
                st.success("Package created and added to your downloads!")
            else:
                err_msg = "Failed to create package download"
        except Exception as e:
            err_msg = f"Package creation failed: {e}"
            print(err_msg)

    elif is_subscription:
        # Subscription flow: call and then VERIFY persisted effects
        try:
            _ret = credit_system.activate_subscription(
                username=username,
                plan=plan_key or "pro",
                monthly_credits=credit_amount or 2000,
                stripe_session_id=payment_intent,  # this is really the checkout session id
            )
        except Exception as e:
            _ret = False
            err_msg = f"activate_subscription error: {e}"
            print(err_msg)

        # Re-fetch and validate regardless of return value
        fresh = credit_system.get_user_info(username) or {}
        new_credits = int(fresh.get("credits", prev_credits))
        status = (fresh.get("subscription_status") or "").lower()
        plan_in_store = (fresh.get("plan") or "").lower()

        ok = (_ret is True) or (
            status == "active" and
            (plan_key == "" or plan_in_store == plan_key) and
            new_credits >= prev_credits  # monthly top-up might be equal if already added
        )

    else:
        # One-time credits flow: call then VERIFY credits increased
        try:
            _ret = credit_system.add_credits(
                username=username,
                credits=credit_amount,
                plan="credit_purchase",
                stripe_session_id=payment_intent,
            )
        except Exception as e:
            _ret = False
            err_msg = f"add_credits error: {e}"
            print(err_msg)

        fresh = credit_system.get_user_info(username) or {}
        new_credits = int(fresh.get("credits", prev_credits))
        ok = (_ret is True) or (new_credits >= prev_credits + max(int(credit_amount), 0))

    # ---- CRITICAL: only restore + rerun on success ----
    if ok:
        try:
            fresh = credit_system.get_user_info(username) or {}
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = fresh
            st.session_state.credits = fresh.get("credits", 0)
            st.session_state.user_plan = fresh.get("plan", "demo")
            st.session_state.show_login = False
            st.session_state.show_register = False
            print(f"SESSION RESTORED: {username} with {st.session_state.credits} credits")

            if is_package:
                st.success("Payment successful! Your package is ready in Downloads.")
            elif is_subscription:
                st.success(f"Subscription active! Monthly credits: {credit_amount}")
            else:
                st.success(f"Payment successful! {credit_amount} credits added.")
        except Exception as e:
            print(f"Session restore error: {e}")

        # Admin logging (best-effort)
        try:
            from frontend_app import log_payment_to_admin_system
            log_payment_to_admin_system({
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "tier": tier_name,
                "credits": credit_amount,
                "amount": amount,
                "payment_intent": payment_intent,
                "type": payment_type,
            })
        except Exception as e:
            print(f"Admin logging failed (non-critical): {e}")

        # Clear QS and rerun only on success
        try: st.query_params.clear()
        except Exception: pass
        st.rerun()
        return True
    else:
        # Don’t rerun; show a meaningful error so you can see the issue
        if not err_msg:
            err_msg = "We couldn’t verify the account update. Please refresh or contact support."
        st.error(err_msg)
        return False


def ensure_user_session(username: str):
    """Ensure user session is properly maintained"""
    if not st.session_state.get('authenticated', False):
        # Try to restore session from database
        from postgres_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if user_info:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = user_info
            st.session_state.credits = user_info.get("credits", 0)
            st.session_state.user_plan = user_info.get("plan", "demo")
            
            print(f"🔧 Session restored for {username}")
            return True
    
    return st.session_state.get('authenticated', False)

def create_no_refund_checkout(username: str, user_email: str, tier: dict) -> str:
    """Create Stripe checkout with proper username handling"""
    
    try:
        # Validate username before creating checkout
        if not username or username == "unknown":
            print(f"❌ Invalid username for checkout: '{username}'")
            return None
        
        print(f"🔄 Creating Stripe checkout for user: {username}")
        
        # Handle different possible tier structures
        plan_name = tier.get('name') or tier.get('plan_name') or tier.get('title') or 'Unknown Plan'
        
        # Try different possible keys for credits
        credits = (tier.get('credits') or 
                  tier.get('monthly_credits') or 
                  tier.get('limit') or 
                  tier.get('lead_limit') or 
                  0)
        
        # Try different possible keys for price  
        price = (tier.get('price') or 
                tier.get('monthly_price') or 
                tier.get('cost') or 
                0)
        
        print(f"   Tier: {plan_name}")
        print(f"   Credits: {credits}")
        print(f"   Price: ${price}")
        
        # If no credits specified, assume it's a subscription plan and set default credits based on plan
        if credits == 0:
            # Default monthly credits based on plan name
            plan_credits = {
                'lead hunter': 250,
                'starter': 250,
                'lead generator': 2000,
                'pro': 2000,
                'most popular': 2000,
                'lead empire': 10000,
                'ultimate': 10000,
                'enterprise': 10000
            }
            
            plan_lower = plan_name.lower()
            credits = plan_credits.get(plan_lower, 1000)  # Default to 1000 if not found
            print(f"   ✅ Subscription plan detected - assigned {credits} monthly credits")
        
        if not price or price <= 0:
            print("❌ Invalid price found in tier data")
            return None
            
        # For subscription plans, create success URL with subscription flag
        is_subscription = credits > 0 and tier.get('credits') is None  # No explicit credits = subscription
        
        # Build URLs from APP_BASE_URL (declared at top of file)
        base = APP_BASE_URL.rstrip("/")
        if is_subscription:
            success_url = (
                f"{base}/?payment_success=1"
                f"&type=subscription"
                f"&tier={plan_name.lower().replace(' ', '_')}"
                f"&monthly_credits={credits}"
                f"&username={username}"
                f"&amount={price}"
                f"&session_id={{CHECKOUT_SESSION_ID}}"
            )
        else:
            success_url = (
                f"{base}/?payment_success=1"
                f"&type=credits"
                f"&tier={plan_name.lower().replace(' ', '_')}"
                f"&credits={credits}"
                f"&username={username}"
                f"&amount={price}"
                f"&session_id={{CHECKOUT_SESSION_ID}}"
            )
        print(f"🔗 Success URL: {success_url}")

        
        if is_subscription:
            # Create subscription checkout
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Lead Generator Empire - {plan_name}",
                            "description": f"{credits} credits/month • Monthly subscription • NO REFUNDS",
                        },
                        "unit_amount": int(price * 100),
                        "recurring": {
                            "interval": "month"
                        }
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                
                # SUCCESS URL with username validation
                success_url=success_url,
                cancel_url=f"{base}/?payment_cancelled=1&username={username}",
                
                # Customer info
                customer_email=user_email,
                
                # Metadata with username for backup
                metadata={
                    "username": username,
                    "tier_name": plan_name,
                    "monthly_credits": str(credits),
                    "no_refund_policy": "agreed",
                    "product_type": "subscription"
                }
            )
        else:
            # Create one-time payment checkout (for credit packages)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Lead Generator Empire - {plan_name}",
                            "description": f"{credits} credits • One-time purchase • NO REFUNDS",
                        },
                        "unit_amount": int(price * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                
                # SUCCESS URL with username validation
                success_url=success_url,
                cancel_url=f"{base}/?payment_cancelled=1&username={username}",

                
                # Customer info
                customer_email=user_email,
                
                # Metadata with username for backup
                metadata={
                    "username": username,
                    "tier_name": plan_name,
                    "credits": str(credits),
                    "no_refund_policy": "agreed",
                    "product_type": "digital_credits"
                },
                
                # Payment intent metadata (backup username storage)
                payment_intent_data={
                    "metadata": {
                        "username": username,
                        "credits": str(credits),
                        "tier_name": plan_name
                    }
                }
            )
        
        print(f"✅ Stripe session created: {session.id}")
        return session.url
        
    except Exception as e:
        print(f"❌ Stripe checkout error: {str(e)}")
        print(f"❌ Tier data: {tier}")  # Debug: show the tier structure
        st.error(f"❌ Payment setup error: {str(e)}")
        return None

def show_compact_credit_terms():
    """Show compact credit terms for add-on section"""
    with st.expander("📋 Important Credit Terms"):
        st.markdown("""
        **📦 Digital Product Terms:**
        • **Instant Delivery** - Credits added immediately after payment
        • **No Refunds** - All credit purchases are final
        • **90-Day Expiry** - Credits expire 90 days from purchase
        • **Legitimate Use** - For business purposes only
        • **Terms Required** - Must agree to Terms of Service
        """)

def display_compact_credit_addon(username: str, user_email: str):
    """Display compact credit add-on section (not full packages)"""
    
    st.markdown("#### 💳 Credit Top-Up Packages")
    st.markdown("*Quick credit boosts for your current plan*")
    
    # Show compact terms
    show_compact_credit_terms()
    
    # Get current user stats
    user_stats = credit_system.get_user_stats(username)
    current_credits = user_stats.get('current_credits', 250) if user_stats else 0
    current_plan = user_stats.get('plan', 'starter') if user_stats else 'starter'
    
    # Show current status
    st.info(f"💎 **Current:** {current_credits} credits • {current_plan.title()} plan")
    
    # Define COMPACT credit tiers (smaller packages)
    compact_tiers = [
        {
            "name": "Quick Boost",
            "credits": 100,
            "price": 47,
            "description": "Small campaign boost",
            "best_for": "Quick campaigns"
        },
        {
            "name": "Power Pack", 
            "credits": 500,
            "price": 197,
            "description": "Most popular add-on",
            "best_for": "Extended campaigns",
            "popular": True
        },
        {
            "name": "Mega Boost",
            "credits": 1000,
            "price": 347,
            "description": "Large scale operations", 
            "best_for": "Enterprise campaigns"
        }
    ]
    
    # Display in horizontal layout
    cols = st.columns(len(compact_tiers))
    
    for i, tier in enumerate(compact_tiers):
        with cols[i]:
            # Popular badge
            if tier.get('popular'):
                st.success("⭐ POPULAR")
            
            st.markdown(f"**{tier['name']}**")
            st.markdown(f"## ${tier['price']}")
            st.markdown(f"**+{tier['credits']} Credits**")
            st.caption(tier['best_for'])
            
            # Show value
            cost_per_credit = tier['price'] / tier['credits']
            st.markdown(f"💰 ${cost_per_credit:.2f}/credit")
            
            # Compact terms agreement
            agree_key = f"agree_compact_{tier['name'].lower().replace(' ', '_')}"
            agreed_to_terms = st.checkbox(
                "✅ Agree to terms",
                key=agree_key,
                help="I agree to Terms of Service & No-Refund Policy"
            )
            
            # Purchase button
            button_type = "primary" if tier.get('popular') else "secondary"
            
            if agreed_to_terms:
                if st.button(
                    f"Buy +{tier['credits']}", 
                    type=button_type,
                    use_container_width=True,
                    key=f"buy_compact_{tier['name'].lower().replace(' ', '_')}"
                ):
                    # Record terms agreement
                    credit_system.agree_to_terms(username)
                    
                    # Create checkout session
                    checkout_url = create_no_refund_checkout(username, user_email, tier)
                    
                    if checkout_url:
                        st.success(f"🔄 Redirecting to checkout for {tier['credits']} credits...")
                        st.markdown(f'<meta http-equiv="refresh" content="2;url={checkout_url}">', unsafe_allow_html=True)
                        st.stop()
            else:
                st.button(
                    f"Buy +{tier['credits']}", 
                    disabled=True,
                    use_container_width=True,
                    help="Agree to terms first",
                    key=f"buy_compact_disabled_{tier['name'].lower().replace(' ', '_')}"
                )

def display_pricing_tiers_with_enforcement(username: str, user_email: str):
    """UPDATED: Display compact credit addon instead of full packages"""
    
    # Use the new compact display instead of the old full package display
    display_compact_credit_addon(username, user_email)

def show_full_credit_packages_standalone(username: str, user_email: str):
    """Full credit packages display (for standalone credit page if needed)"""
    
    # Show full no-refund warning
    st.error("🚨 **NO REFUND POLICY**")
    st.markdown("""
    **⚠️ IMPORTANT - READ BEFORE PURCHASING:**
    
    - **Digital Product**: Credits are delivered instantly upon payment
    - **No Refunds**: All sales are final - no refunds or chargebacks accepted  
    - **Immediate Access**: You get full access to download leads immediately
    - **Credits Expire**: Credits expire after 90 days from purchase date
    - **Terms Required**: You must agree to our Terms of Service to proceed
    - **Legitimate Use Only**: Credits are for legitimate business use only
    """)
    
    st.markdown("---")
    st.header("💳 Choose Your Credit Package")
    
    # Full credit tiers (original large packages)
    full_tiers = [
        {
            "name": "Lead Starter",
            "credits": 500,
            "price": 97,
            "description": "Perfect for small campaigns",
            "features": [
                "500 premium credits",
                "All 8 platforms access",
                "Basic filtering",
                "CSV export",
                "90-day expiry"
            ]
        },
        {
            "name": "Lead Pro",
            "credits": 2000, 
            "price": 297,
            "description": "Most popular for agencies",
            "features": [
                "2,000 premium credits",
                "All 8 platforms access", 
                "Advanced filtering",
                "Priority support",
                "Analytics dashboard",
                "90-day expiry"
            ]
        },
        {
            "name": "Lead Empire",
            "credits": 10000,
            "price": 897,
            "description": "Enterprise campaigns",
            "features": [
                "10,000 premium credits",
                "All 8 platforms access",
                "Enterprise filtering", 
                "Dedicated support",
                "Custom integrations",
                "Extended 180-day expiry"
            ]
        }
    ]
    
    cols = st.columns(len(full_tiers))
    
    for i, tier in enumerate(full_tiers):
        with cols[i]:
            # Tier card
            st.markdown(f"### {tier['name']}")
            if tier['name'] == "Lead Pro":
                st.success("💎 MOST POPULAR")
            elif tier['name'] == "Lead Empire":
                st.warning("👑 ENTERPRISE")
                
            st.markdown(f"## ${tier['price']}")
            st.markdown(f"**{tier['credits']} Credits**")
            st.caption(tier['description'])
            
            st.markdown("**✅ Features:**")
            for feature in tier['features']:
                st.markdown(f"• {feature}")
            
            # Value proposition
            cost_per_lead = tier['price'] / tier['credits']
            st.success(f"💰 ${cost_per_lead:.2f} per lead")
            
            # Terms agreement checkbox
            agree_key = f"agree_full_{tier['name'].lower().replace(' ', '_')}"
            agreed_to_terms = st.checkbox(
                f"✅ I agree to Terms of Service & No-Refund Policy",
                key=agree_key,
                help="Required: You must agree to terms before purchasing"
            )
            
            # Purchase button
            if agreed_to_terms:
                if st.button(
                    f"🚀 Buy {tier['name']}", 
                    type="primary" if tier['name'] == "Lead Pro" else "secondary",
                    use_container_width=True,
                    key=f"buy_full_{tier['name'].lower().replace(' ', '_')}"
                ):
                    # Record terms agreement
                    credit_system.agree_to_terms(username)
                    
                    # Create checkout session
                    checkout_url = create_no_refund_checkout(username, user_email, tier)
                    
                    if checkout_url:
                        st.markdown(f"""
                        <meta http-equiv="refresh" content="2;url={checkout_url}">
                        <div style="text-align: center; padding: 2rem; background: #d4edda; border-radius: 10px;">
                            <h3>🔄 Redirecting to secure checkout...</h3>
                            <p>⚠️ Remember: NO REFUNDS on digital credits</p>
                        </div>
                        """, unsafe_allow_html=True)
                        st.stop()
            else:
                st.button(
                    f"🚀 Buy {tier['name']}", 
                    disabled=True,
                    use_container_width=True,
                    help="Please agree to terms first",
                    key=f"buy_full_disabled_{tier['name'].lower().replace(' ', '_')}"
                )

def handle_payment_success(username: str, tier_name: str, credits: int = None, monthly_credits: int = None, payment_type: str = "credits"):
    """Handle successful payment for both subscriptions and credit purchases"""
    
    # Clear any redirect states since we're back from Stripe
    st.session_state.redirect_to_stripe_credits = False
    st.session_state.stripe_checkout_url = None
    st.session_state.purchasing_tier = None
    st.session_state.redirect_to_stripe_full = False
    st.session_state.stripe_checkout_url_full = None
    st.session_state.purchasing_tier_full = None
    
    #st.balloons()
    st.success(f"🎉 Payment Successful!")
    
    # Import here to avoid circular imports
    from postgres_credit_system import credit_system
    
    # Determine if this is a subscription or credit purchase
    is_subscription = payment_type == "subscription" or monthly_credits is not None
    credit_amount = monthly_credits if is_subscription else credits
    
    if is_subscription:
        st.success(f"✅ Subscription activated: {tier_name}")
        st.info(f"📅 You'll receive {credit_amount} credits each month")
        
        # For subscriptions, activate the subscription plan
        success = credit_system.activate_subscription(
            username=username,
            plan=tier_name,
            monthly_credits=credit_amount,
            stripe_session_id=st.query_params.get("payment_intent", "unknown")
        )
        
        if success:
            st.markdown(f"""
            ### 🚀 Welcome to {tier_name.title()}!
            
            **Your Subscription:**
            - ✅ {credit_amount} credits per month
            - ✅ Access to all 8 platforms
            - ✅ Advanced filtering & DMs
            - ✅ Full contact information (no masking)
            - 🔄 **Auto-renewal**: Credits refresh monthly
            
            **Next Steps:**
            1. Go to the **Empire Scraper** tab
            2. Set your target keywords
            3. Select platforms  
            4. Launch your lead generation!
            
            **💡 Pro Tip:** You get {credit_amount} new credits every month automatically.
            """)
        else:
            st.error("❌ Error activating subscription. Please contact support with your payment confirmation.")
            
    else:
        # Handle one-time credit purchase
        success = credit_system.add_credits(
            username=username,
            credits=credit_amount, 
            plan="credit_purchase",  # Don't change plan for credit purchases
            stripe_session_id=st.query_params.get("payment_intent", "unknown")
        )
        
        if success:
            st.success(f"✅ {credit_amount} credits added to your account!")
            
            # Show what they can do now
            st.markdown(f"""
            ### 🚀 You're Ready to Generate Leads!
            
            **Your Account:**
            - ✅ {credit_amount} credits added
            - ✅ Access to all 8 platforms
            - ✅ Advanced filtering & DMs
            - ✅ Full contact information (no masking)
            
            **Next Steps:**
            1. Go to the **Empire Scraper** tab
            2. Set your target keywords
            3. Select platforms  
            4. Launch your lead generation!
            
            **💡 Pro Tip:** Each lead costs 1 credit, so you can generate {credit_amount} leads with this purchase.
            """)
        else:
            st.error("❌ Error adding credits. Please contact support with your payment confirmation.")
    
    # Continue button
    if st.button("🏠 Start Generating Leads", type="primary", use_container_width=True):
        st.query_params.clear()
        st.rerun()

def show_user_credit_status(username: str):
    """Show user's current credit status"""
    user_stats = credit_system.get_user_stats(username)
    
    if not user_stats:
        return
    
    current_credits = user_stats.get('current_credits', 0)
    plan = user_stats.get('plan', 'trial')
    total_downloaded = user_stats.get('total_leads_downloaded', 0)
    
    # Credit status display
    if current_credits > 100:
        st.success(f"💎 **{current_credits} credits** available ({plan} plan)")
    elif current_credits > 25:
        st.info(f"⚡ **{current_credits} credits** available ({plan} plan)")
    elif current_credits > 0:
        st.warning(f"⚠️ **{current_credits} credits** remaining ({plan} plan)")
    else:
        st.error(f"❌ **No credits** remaining ({plan} plan)")
        st.markdown("**🛒 [Purchase more credits](#) to continue generating leads**")
    
    # Usage stats
    if total_downloaded > 0:
        st.caption(f"📊 Total leads generated: {total_downloaded}")

def enforce_credit_limits_on_scraper(username: str, estimated_leads: int) -> Tuple[bool, str]:
    """Enforce credit limits before scraping"""
    can_proceed, message, current_credits = credit_system.check_credits(username, estimated_leads)
    
    if not can_proceed:
        return False, f"❌ Insufficient credits: {message}. [Purchase more credits](#) to continue."
    
    return True, f"✅ Ready to generate {estimated_leads} leads (you have {current_credits} credits)"

