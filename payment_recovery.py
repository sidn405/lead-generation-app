# REPLACE the payment recovery function in payment_recovery.py

import streamlit as st
import datetime
import json
import os
from json_utils import load_json_safe

def try_save_user_to_database(username, user_data):
    try:
        users = {}
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = load_json_safe(f)

        users[username] = user_data

        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"⚠️ Database save failed (non-critical): {str(e)}")

def automatic_payment_recovery(user_db):
    """Enhanced payment recovery - handles all paid plans including Starter"""
    
    # PREVENT MULTIPLE TRIGGERS - Check if already processed
    if st.session_state.get('payment_recovery_processed', False):
        return
    
    params = st.query_params
    
    # Check if this is any kind of payment success
    is_payment_success = (
        params.get("success") == "true" or 
        params.get("payment_success") == "true"
    )
    
    if not is_payment_success:
        return

    # MARK AS PROCESSED to prevent repeated triggers
    st.session_state['payment_recovery_processed'] = True
    
    plan = params.get("plan")
    package = params.get("package") 
    username = params.get("username")
    credits = params.get("credits")

    print(f"🔄 Payment recovery triggered:")
    print(f"   Plan: {plan}")
    print(f"   Package: {package}")
    print(f"   Username: {username}")
    print(f"   Credits: {credits}")

    # PLAN UPGRADE RECOVERY (Starter/Pro/Ultimate subscriptions)
    if plan and username and username != "unknown":
        print(f"🔄 Processing plan upgrade: {plan} for {username}")
        
        try:
            from simple_credit_system import credit_system
            
            user_info = credit_system.get_user_info(username)
            if user_info:
                # Update plan in credit system
                success = credit_system.update_user_plan(username, plan)
                
                if success:
                    # Add credits based on plan
                    plan_credits = {
                        'starter': 250,    # Starter gets 250 credits
                        'pro': 2000,       # Pro gets 2000 credits  
                        'ultimate': 9999   # Ultimate gets "unlimited"
                    }
                    
                    credits_to_add = plan_credits.get(plan, 0)
                    if credits_to_add > 0:
                        credit_system.add_credits(username, credits_to_add, plan)
                    
                    # Restore session
                    updated_user_info = credit_system.get_user_info(username)
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_data = updated_user_info
                    st.session_state.credits = updated_user_info.get('credits', 0)
                    
                    print(f"✅ Plan upgraded to {plan} for {username}")
                    
                    # Show success message based on plan
                    if plan == 'starter':
                        st.success("🎉 Welcome to Starter Plan!")
                        st.markdown("""
                        **📱 Starter Plan Benefits:**
                        - ✅ 2 platforms (Twitter, Facebook)
                        - ✅ 250 credits per month
                        - ✅ Basic filtering & CSV export
                        - ✅ Email support
                        """)
                    elif plan == 'pro':
                        st.success("🎉 Welcome to Pro Plan!")
                        st.markdown("""
                        **💎 Pro Plan Benefits:**
                        - ✅ 6 platforms (adds LinkedIn, TikTok, Instagram, YouTube)
                        - ✅ 2,000 credits per month
                        - ✅ Advanced filtering & analytics
                        - ✅ Priority support
                        """)
                    elif plan == 'ultimate':
                        st.success("🎉 Welcome to Ultimate Plan!")
                        st.markdown("""
                        **👑 Ultimate Plan Benefits:**
                        - ✅ All 8 platforms (adds Medium, Reddit)
                        - ✅ Unlimited credits
                        - ✅ Enterprise features & API access
                        - ✅ Dedicated account manager
                        """)
                    
                    st.balloons()
                    
                    # Clear the URL parameters and redirect
                    if st.button("🚀 Explore New Features", type="primary"):
                        st.query_params.clear()
                        st.session_state['payment_recovery_processed'] = False
                        st.rerun()
                    st.stop()
                    
        except ImportError:
            print("⚠️ Credit system not available, using fallback")
        
        # Fallback to users.json
        if username in user_db:
            user_data = user_db[username]
            user_data["plan"] = plan
            
            # Add appropriate credits
            plan_credits = {
                'starter': 250,
                'pro': 2000,
                'ultimate': 9999
            }
            user_data["credits"] = user_data.get("credits", 0) + plan_credits.get(plan, 0)
            
            try_save_user_to_database(username, user_data)
            
            # Restore session
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = user_data
            st.session_state.credits = user_data.get("credits", 0)
            
            st.success(f"🎉 Plan upgraded to {plan.title()}!")
            st.balloons()
            
            if st.button("🚀 Continue", type="primary"):
                st.query_params.clear()
                st.session_state['payment_recovery_processed'] = False
                st.rerun()
            st.stop()

    # CREDIT PURCHASE RECOVERY  
    elif credits and username and username != "unknown":
        print(f"🔄 Processing credit purchase: {credits} credits for {username}")
        
        try:
            from simple_credit_system import credit_system
            
            # Add credits to user account
            credits_int = int(credits)
            success = credit_system.add_credits(
                username=username,
                credits=credits_int,
                plan="credit_purchase",  # Don't change plan for credit purchases
                stripe_session_id=params.get("session_id", "recovery")
            )
            
            if success:
                # Restore session
                user_info = credit_system.get_user_info(username)
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_data = user_info
                    st.session_state.credits = user_info.get('credits', 0)
                    
                    st.success(f"🎉 {credits} credits added successfully!")
                    st.balloons()
                    
                    if st.button("🚀 Start Generating Leads", type="primary"):
                        st.query_params.clear()
                        st.session_state['payment_recovery_processed'] = False
                        st.rerun()
                    st.stop()
                    
        except Exception as e:
            print(f"❌ Credit recovery error: {e}")

    # PACKAGE PURCHASE RECOVERY 
    elif package and username and username != "unknown":
        print(f"🔄 Processing package purchase: {package} for {username}")
        
        try:
            from simple_credit_system import credit_system
            user_info = credit_system.get_user_info(username)
            
            if user_info:
                # Restore session
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.user_data = user_info
                st.session_state.credits = user_info.get("credits", 0)
                
                # Show package success
                package_names = {
                    "starter": "Niche Starter Pack (500 leads)",
                    "deep_dive": "Industry Deep Dive (2,000 leads)", 
                    "domination": "Market Domination (5,000 leads)"
                }
                
                package_name = package_names.get(package, "Lead Package")
                amount = params.get("amount", "0")
                industry = params.get("industry", "").replace('+', ' ')
                location = params.get("location", "").replace('+', ' ')
                
                st.balloons()
                st.success(f"🎉 {package_name} Purchase Successful!")
                
                st.markdown(f"""
                <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border-radius: 15px;">
                    <h2>📦 {package_name} Purchased!</h2>
                    <p><strong>${amount} payment processed successfully</strong></p>
                    <p>👤 <strong>Account:</strong> {username}</p>
                    <p>🎯 <strong>Targeting:</strong> {industry} in {location}</p>
                    <p>📧 <strong>Delivery:</strong> Package details sent to your email</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🏠 Continue to Dashboard", type="primary"):
                    st.query_params.clear()
                    st.session_state['payment_recovery_processed'] = False
                    st.rerun()
                st.stop()
                
        except Exception as e:
            print(f"❌ Package recovery error: {e}")
        
        # Fallback to user_db
        if username in user_db:
            user_data = user_db[username]
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = user_data
            st.session_state.credits = user_data.get("credits", 0)
            
            st.success(f"✅ Lead Package Purchase Successful for {username}!")
            
            if st.button("🏠 Continue to Dashboard", type="primary"):
                st.query_params.clear()
                st.session_state['payment_recovery_processed'] = False
                st.rerun()
            st.stop()

    print("⚠️ Payment recovery completed but no matching conditions found")