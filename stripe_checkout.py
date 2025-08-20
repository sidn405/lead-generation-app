# stripe_checkout.py - Updated for better tab organization
import time
import os
import stripe
import streamlit as st
from typing import Tuple, List, Dict
#from simple_credit_system import credit_system
from postgres_credit_system import credit_system

APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "https://leadgeneratorempire.com") 
    or os.getenv("APP_BASE_URL") 
    or "http://localhost:8501"
)

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
        
        if is_subscription:
            success_url = f"https://leadgeneratorempire.com/?payment_success=true&tier={plan_name.lower().replace(' ', '_')}&monthly_credits={credits}&username={username}&amount={price}&type=subscription"
        else:
            success_url = f"https://leadgeneratorempire.com/?payment_success=true&tier={plan_name.lower().replace(' ', '_')}&credits={credits}&username={username}&amount={price}&type=credits"
        
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
                cancel_url=f"http://localhost:8501?username={username}&payment_cancelled=true",
                
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
                cancel_url=f"http://localhost:8501?username={username}&payment_cancelled=true",
                
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
    
    st.balloons()
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


