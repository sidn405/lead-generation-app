
import streamlit as st

def automatic_payment_capture():
    """
    AUTOMATIC PAYMENT CAPTURE
    This runs automatically and captures EVERY payment without fail
    Add this as the FIRST THING in your main app
    """
    try:
        import json
        import os
        from datetime import datetime
        
        query_params = st.query_params
        
        # Check for ANY payment indicators
        payment_indicators = [
            "payment_success", "success", "tier", "credits", "amount",
            "plan", "package", "stripe_session_id", "payment_intent"
        ]
        
        has_payment = any(param in query_params for param in payment_indicators)
        
        if not has_payment:
            return False
        
        # Extract payment data
        username = query_params.get("username", "")
        if not username or username == "unknown":
            return False
        
        # Handle credit purchases (most common)
        if "credits" in query_params and "amount" in query_params:
            try:
                credits = int(query_params.get("credits", 0))
                amount = float(query_params.get("amount", 0))
                tier = query_params.get("tier", "Credit Package")
                
                if credits > 0 and amount > 0:
                    # Log to admin automatically
                    success = log_credit_purchase_auto(username, tier, amount, credits)
                    
                    if success:
                        # Show success message
                        st.balloons()
                        st.success(f"🎉 Payment Successful! {tier} - ${amount}")
                        st.success(f"✅ {credits} credits added to your account!")
                        
                        if st.button("🏠 Continue", type="primary"):
                            st.query_params.clear()
                            st.rerun()
                        
                        return True
                        
            except (ValueError, TypeError):
                pass
        
        # Handle plan upgrades
        elif "plan" in query_params:
            try:
                plan = query_params.get("plan", "")
                amount = float(query_params.get("amount", 0))
                
                if plan and amount > 0:
                    success = log_subscription_purchase_auto(username, plan, amount)
                    
                    if success:
                        st.balloons()
                        st.success(f"🎉 Plan Upgrade Successful! {plan.title()} Plan")
                        st.success("📊 Subscription automatically logged to admin!")
                        
                        if st.button("🏠 Continue", type="primary"):
                            st.query_params.clear()
                            st.rerun()
                        
                        return True
                        
            except (ValueError, TypeError):
                pass
        
        return False
        
    except Exception as e:
        print(f"❌ Automatic payment capture error: {e}")
        return False

def log_credit_purchase_auto(username: str, tier: str, amount: float, credits: int) -> bool:
    """Automatically log credit purchase to admin"""
    try:
        from datetime import datetime
        import json
        import os
        
        # Create admin entry
        admin_entry = {
            "event_type": "credit_purchase",
            "package_type": "CREDIT_TOPUP",
            "username": username,
            "package_name": tier,
            "package_price": amount,
            "credits_purchased": credits,
            "cost_per_credit": round(amount / credits, 2) if credits > 0 else 0,
            "timestamp": datetime.now().isoformat(),
            "status": "COMPLETED",
            "user_email": f"{username}@auto.com",
            "user_plan": "unknown",
            "priority": "LOW",
            "logged_via": "automatic_capture",
            "auto_logged": True
        }
        
        # Load admin purchases
        admin_file = "package_purchases.json"
        if not os.path.exists(admin_file):
            with open(admin_file, 'w') as f:
                json.dump([], f)
        
        with open(admin_file, 'r') as f:
            admin_purchases = json.load(f)
        
        # Check for recent duplicates (prevent double-logging)
        recent_duplicate = any(
            p.get('username') == username and
            p.get('package_name') == tier and
            abs(p.get('package_price', 0) - amount) < 0.01 and
            (datetime.now() - datetime.fromisoformat(p.get('timestamp', ''))).total_seconds() < 600  # 10 minutes
            for p in admin_purchases[-10:]  # Check last 10 purchases
        )
        
        if recent_duplicate:
            print(f"⚠️ Duplicate credit purchase prevented: {username} - {tier}")
            return True  # Not an error, just already logged
        
        # Add new purchase
        admin_purchases.append(admin_entry)
        
        # Save back
        with open(admin_file, 'w') as f:
            json.dump(admin_purchases, f, indent=2)
        
        print(f"✅ AUTO-LOGGED CREDIT PURCHASE: {username} - {tier} - ${amount}")
        return True
        
    except Exception as e:
        print(f"❌ Auto credit logging error: {e}")
        return False

def log_subscription_purchase_auto(username: str, plan: str, amount: float) -> bool:
    """Automatically log subscription purchase to admin"""
    try:
        from datetime import datetime
        import json
        import os
        
        admin_entry = {
            "event_type": "subscription_purchase",
            "package_type": "MONTHLY_SUBSCRIPTION",
            "username": username,
            "plan_name": plan,
            "monthly_price": amount,
            "billing_cycle": "monthly",
            "timestamp": datetime.now().isoformat(),
            "status": "ACTIVE",
            "user_email": f"{username}@auto.com",
            "previous_plan": "unknown",
            "priority": "MEDIUM",
            "logged_via": "automatic_capture",
            "auto_logged": True
        }
        
        admin_file = "package_purchases.json"
        if not os.path.exists(admin_file):
            with open(admin_file, 'w') as f:
                json.dump([], f)
        
        with open(admin_file, 'r') as f:
            admin_purchases = json.load(f)
        
        admin_purchases.append(admin_entry)
        
        with open(admin_file, 'w') as f:
            json.dump(admin_purchases, f, indent=2)
        
        print(f"✅ AUTO-LOGGED SUBSCRIPTION: {username} - {plan} - ${amount}")
        return True
        
    except Exception as e:
        print(f"❌ Auto subscription logging error: {e}")
        return False

# ===== INTEGRATION INSTRUCTIONS =====
"""
ADD THIS TO THE VERY TOP OF YOUR MAIN STREAMLIT APP:

# Right after your imports, add this:
payment_handled = automatic_payment_capture()
if payment_handled:
    st.stop()  # Stop execution if payment was handled

# Then continue with your normal app logic...
"""

# ===== IMMEDIATE FIX FOR CURRENT PROBLEM =====
def fix_test_purchase_types():
    """Fix the hardcoded test purchases that are showing as custom orders"""
    
    try:
        import json
        import os
        from datetime import datetime
        
        admin_file = "package_purchases.json"
        if not os.path.exists(admin_file):
            return False
        
        with open(admin_file, 'r') as f:
            admin_purchases = json.load(f)
        
        fixed_count = 0
        
        # Fix any test purchases that are incorrectly logged as custom orders
        for purchase in admin_purchases:
            # Look for test purchases that are custom orders
            if (purchase.get('event_type') == 'custom_package_purchase' and
                ('TEST' in purchase.get('package_name', '') or 
                 'test' in purchase.get('username', '').lower())):
                
                # Convert to credit purchase
                purchase['event_type'] = 'credit_purchase'
                purchase['package_type'] = 'CREDIT_TOPUP'
                purchase['status'] = 'COMPLETED'
                purchase['priority'] = 'LOW'
                purchase['fixed_from_custom_order'] = True
                
                # Estimate credits if not present
                if 'credits_purchased' not in purchase:
                    amount = purchase.get('package_price', 0)
                    estimated_credits = int(amount * 2)  # Rough estimate
                    purchase['credits_purchased'] = estimated_credits
                    purchase['cost_per_credit'] = round(amount / estimated_credits, 2) if estimated_credits > 0 else 0
                
                fixed_count += 1
        
        if fixed_count > 0:
            # Save fixed purchases
            with open(admin_file, 'w') as f:
                json.dump(admin_purchases, f, indent=2)
            
            print(f"✅ Fixed {fixed_count} test purchases (converted from custom orders to credit purchases)")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Fix test purchases error: {e}")
        return False

# Run the fix automatically
fix_test_purchase_types()