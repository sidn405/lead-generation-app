# simple_credit_system.py - Clean monetization system
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import hashlib

class CreditSystem:
    """Simple credit-based lead system with anti-abuse protection"""
    
    def __init__(self):
        self.users_file = "users_credits.json"
        self.transactions_file = "transactions.json"
        self.load_data()
    
    def load_data(self):
        """Load user credits and transaction data"""
        # Load users with credits
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}
        
        # Load transaction history
        if os.path.exists(self.transactions_file):
            with open(self.transactions_file, 'r') as f:
                self.transactions = json.load(f)
        else:
            self.transactions = []
    
    def save_data(self):
        """Save all data to files"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=4)
        
        with open(self.transactions_file, 'w') as f:
            json.dump(self.transactions, f, indent=4)
    
    def hash_password(self, password: str) -> str:
        """Simple password hashing"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, email: str, password: str) -> Tuple[bool, str]:
        """Create new user with demo mode"""
        if username in self.users:
            return False, "Username already exists"
        
        self.users[username] = {
            "email": email,
            "password_hash": self.hash_password(password),
            "credits": 0,  # Regular credits = 0 for demo
            "plan": "demo",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "total_leads_downloaded": 0,
            "transactions": [],
            "agreed_to_terms": False,
            "demo_leads_used": 0,    # Track demo usage
            "demo_limit": 5         # Allow 5 demo leads
        }
        
        self.save_data()
        return True, "Demo account created with 5 free demo leads"
    
    def get_demo_status(self, username: str) -> Tuple[bool, int, int]:
        """Get demo status: (is_demo, used, remaining)"""
        if username not in self.users:
            return False, 0, 0
        
        user = self.users[username]
        if user.get("plan") != "demo":
            return False, 0, 0
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        remaining = max(0, limit - used)
        
        return True, used, remaining

    def can_use_demo(self, username: str) -> Tuple[bool, int]:
        """Check if user can still use demo leads"""
        is_demo, used, remaining = self.get_demo_status(username)
        return is_demo and remaining > 0, remaining

    def consume_demo_lead(self, username: str) -> bool:
        """Consume one demo lead"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        if user.get("plan") != "demo":
            return False
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        
        if used >= limit:
            return False
        
        user["demo_leads_used"] = used + 1
        self.save_data()
        return True
    
    def login_user(self, username: str, password: str) -> Tuple[bool, str, Dict]:
        """Authenticate user"""
        if username not in self.users:
            return False, "User not found", {}
        
        user = self.users[username]
        if user["password_hash"] != self.hash_password(password):
            return False, "Invalid password", {}
        
        # Update last login
        user["last_login"] = datetime.now().isoformat()
        self.save_data()
        
        return True, "Login successful", user
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        return self.users.get(username)
    
    def is_demo_user(self, username: str) -> bool:
        """Check if user is in demo mode"""
        user = self.users.get(username, {})
        return user.get("plan", "demo") == "demo"

    def can_use_demo(self, username: str) -> Tuple[bool, int]:
        """Check if user can still use demo leads"""
        user = self.users.get(username, {})
        if not self.is_demo_user(username):
            return False, 0
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        remaining = max(0, limit - used)
        
        return remaining > 0, remaining

    def consume_demo_lead(self, username: str) -> bool:
        """Consume one demo lead"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        if not self.is_demo_user(username):
            return False
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        
        if used >= limit:
            return False
        
        user["demo_leads_used"] = used + 1
        self.save_data()
        return True
    
    def check_credits(self, username: str, required_credits: int) -> Tuple[bool, str, int]:
        """Check if user has enough credits"""
        if username not in self.users:
            return False, "User not found", 0
        
        user = self.users[username]
        current_credits = user.get("credits", 0)
        
        if current_credits >= required_credits:
            return True, f"{current_credits} credits available", current_credits
        else:
            return False, f"Insufficient credits: {current_credits}/{required_credits}", current_credits
    
    def consume_credits(self, username: str, credits_used: int, leads_downloaded: int, platform: str) -> bool:
        """Consume credits and log the transaction"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        if user.get("credits", 0) < credits_used:
            return False
        
        # Deduct credits
        user["credits"] -= credits_used
        user["total_leads_downloaded"] += leads_downloaded
        
        # Log transaction
        transaction = {
            "username": username,
            "type": "lead_download",
            "credits_used": credits_used,
            "leads_downloaded": leads_downloaded,
            "platform": platform,
            "timestamp": datetime.now().isoformat(),
            "credits_remaining": user["credits"]
        }
        
        user["transactions"].append(transaction)
        self.transactions.append(transaction)
        
        self.save_data()
        return True
    
    def add_credits(self, username: str, credits: int, plan: str, stripe_session_id: str = None) -> bool:
        """Add credits to user account (from purchase) with proper plan handling"""
        if username not in self.users:
            print(f"❌ User {username} not found for credit addition")
            return False

        user = self.users[username]

        # Add credits
        old_credits = user.get("credits", 0)
        user["credits"] += credits

        # 🔧 IMPROVED plan handling
        if plan and plan.lower() not in ["unknown", "", "credit_purchase"]:
            # This is a plan upgrade (pro/ultimate), update the plan
            old_plan = user.get("plan", "demo")
            user["plan"] = plan.lower()
            print(f"🔧 Plan upgraded: {username} {old_plan} → {plan}")
        elif plan == "credit_purchase":
            # This is just a credit purchase, don't change the plan
            print(f"💳 Credits added: {username} +{credits} (plan unchanged: {user.get('plan', 'starter')})")
        else:
            # Fallback: infer plan from total credits only if current plan is demo
            current_plan = user.get("plan", "demo")
            if current_plan == "demo":
                total_credits = user["credits"]
                if total_credits >= 10000:
                    user["plan"] = "ultimate"
                elif total_credits >= 2000:
                    user["plan"] = "pro"
                elif total_credits >= 500:
                    user["plan"] = "starter"
                print(f"🔧 Plan inferred from credits: {username} → {user['plan']}")

        print(f"💎 Credits: {old_credits} → {user['credits']}")

        # Log purchase transaction
        transaction = {
            "username": username,
            "type": "credit_purchase" if plan == "credit_purchase" else "plan_upgrade",
            "credits_added": credits,
            "plan": user["plan"],
            "stripe_session_id": stripe_session_id or "unknown",
            "timestamp": datetime.now().isoformat(),
            "credits_after": user["credits"]
        }

        user.setdefault("transactions", []).append(transaction)
        self.transactions.append(transaction)

        self.save_data()
        return True
    
    def activate_subscription(self, username: str, plan: str, monthly_credits: int, stripe_session_id: str) -> bool:
        """Activate a monthly subscription plan"""
        if username not in self.users:
            print(f"❌ User {username} not found for subscription activation")
            return False

        user = self.users[username]

        # Set subscription plan (don't add to existing credits - subscriptions replace)
        old_plan = user.get("plan", "demo")
        old_credits = user.get("credits", 0)
        
        user["plan"] = plan.lower()
        user["credits"] = monthly_credits  # Set to monthly amount (replace, don't add)
        user["subscription_active"] = True
        user["subscription_started"] = datetime.now().isoformat()
        user["monthly_credits"] = monthly_credits
        
        print(f"✅ Subscription activated: {username}")
        print(f"   Plan: {old_plan} → {plan}")
        print(f"   Credits: {old_credits} → {monthly_credits}/month")

        # Log subscription activation
        transaction = {
            "username": username,
            "type": "subscription_activation",
            "plan": plan,
            "old_plan": old_plan,
            "monthly_credits": monthly_credits,
            "stripe_session_id": stripe_session_id or "unknown",
            "timestamp": datetime.now().isoformat(),
            "credits_set": monthly_credits
        }

        user.setdefault("transactions", []).append(transaction)
        self.transactions.append(transaction)

        self.save_data()
        return True
    
    def get_user_stats(self, username: str) -> Dict:
        """Get user statistics"""
        user = self.users.get(username, {})
        
        if not user:
            return {}
        
        # Calculate stats
        total_purchased = sum(t.get("credits_added", 0) for t in user.get("transactions", []) if t.get("type") in ["credit_purchase", "plan_upgrade", "subscription_activation"])
        total_used = sum(t.get("credits_used", 0) for t in user.get("transactions", []) if t.get("type") == "lead_download")
        
        # ✅ FIX: Make credits_used equal to total_leads_downloaded  
        credits_used = user.get("total_leads_downloaded", 0)  # 1 lead = 1 credit used
        
        return {
            "current_credits": user.get("credits", 0),
            "total_purchased": total_purchased,
            "credits_used": credits_used,  # ✅ This will now equal total leads generated
            "total_leads_downloaded": user.get("total_leads_downloaded", 0),
            "plan": user.get("plan", "demo"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "agreed_to_terms": user.get("agreed_to_terms", False),
            "subscription_active": user.get("subscription_active", False),
            "monthly_credits": user.get("monthly_credits", 0)
        }

    def get_pricing_tiers(self) -> List[Dict]:
        """Get available pricing tiers"""
        return [
            {
                "name": "Lead Starter",
                "credits": 500,
                "price": 97,
                "description": "Perfect for small campaigns",
                "features": ["500 leads", "All platforms", "Basic DMs", "CSV export"]
            },
            {
                "name": "Lead Pro", 
                "credits": 2000,
                "price": 297,
                "description": "Most popular for agencies",
                "features": ["2,000 leads", "All platforms", "Advanced DMs", "Priority support", "Geo-targeting"]
            },
            {
                "name": "Lead Empire",
                "credits": 5000, 
                "price": 897,
                "description": "Enterprise campaigns",
                "features": ["5,000 leads", "All platforms", "Custom DMs", "Dedicated support", "Advanced filtering"]
            }
        ]
    
    def mask_leads_for_trial(self, leads: List[Dict], username: str) -> List[Dict]:
        """Mask lead information for trial users"""
        user = self.users.get(username, {})
        
        # Demo users get basic masking
        if user.get("plan") == "demo":
            masked_leads = []
            for lead in leads:
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
                
                # Mask phone if present
                if "phone" in masked_lead and masked_lead["phone"]:
                    phone = masked_lead["phone"]
                    masked_lead["phone"] = f"***-***-{phone[-4:]}" if len(phone) >= 4 else "***"
                
                # Add demo watermark
                masked_lead["demo_mode"] = True
                masked_lead["upgrade_message"] = "Upgrade to see full contact details"
                
                masked_leads.append(masked_lead)
            
            return masked_leads
        
        # Starter users get some masking
        elif user.get("plan") == "starter":
            masked_leads = []
            for lead in leads:
                masked_lead = lead.copy()
                
                # Light masking for starter - only mask phone
                if "phone" in masked_lead and masked_lead["phone"]:
                    phone = masked_lead["phone"]
                    masked_lead["phone"] = f"***-***-{phone[-4:]}" if len(phone) >= 4 else "***"
                
                masked_leads.append(masked_lead)
            
            return masked_leads
        
        # Pro and Ultimate users get no masking
        return leads
    
    def generate_invoice_data(self, username: str, transaction_id: str) -> Dict:
        """Generate invoice data for PDF export"""
        user = self.users.get(username, {})
        
        # Find the transaction
        transaction = None
        for t in self.transactions:
            if t.get("stripe_session_id") == transaction_id:
                transaction = t
                break
        
        if not transaction:
            return {}
        
        return {
            "invoice_number": f"LGE-{transaction_id[-8:].upper()}",
            "date": transaction["timestamp"],
            "customer": {
                "username": username,
                "email": user.get("email", "")
            },
            "items": [{
                "description": f"{transaction['plan'].title()} Credits",
                "credits": transaction["credits_added"],
                "amount": self._get_price_for_plan(transaction["plan"])
            }],
            "total": self._get_price_for_plan(transaction["plan"]),
            "payment_method": "Credit Card (Stripe)",
            "terms": "No refunds. Credits expire after 90 days."
        }
    
    def _get_price_for_plan(self, plan: str) -> float:
        """Get price for plan name"""
        pricing = {
            "lead starter": 97,
            "lead pro": 297, 
            "lead empire": 897
        }
        return pricing.get(plan.lower(), 0)
    
    def get_user_stats(self, username: str) -> Dict:
        """Get user statistics"""
        user = self.users.get(username, {})
        
        if not user:
            return {}
        
        # Calculate stats
        total_purchased = sum(t.get("credits_added", 0) for t in user.get("transactions", []) if t.get("type") == "credit_purchase")
        total_used = sum(t.get("credits_used", 0) for t in user.get("transactions", []) if t.get("type") == "lead_download")
        
        return {
            "current_credits": user.get("credits", 250),
            "total_purchased": total_purchased,
            "total_used": total_used,
            "total_leads_downloaded": user.get("total_leads_downloaded", 0),
            "plan": user.get("plan", "starter"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "agreed_to_terms": user.get("agreed_to_terms", False)
        }
    
    def agree_to_terms(self, username: str) -> bool:
        """Record that user agreed to terms"""
        if username not in self.users:
            return False
        
        self.users[username]["agreed_to_terms"] = True
        self.users[username]["terms_agreed_at"] = datetime.now().isoformat()
        self.save_data()
        return True
    
    def update_user_plan(self, username: str, new_plan: str) -> bool:
        """Update user's plan and add appropriate credits"""
        if username not in self.users:
            print(f"❌ User {username} not found for plan update")
            return False
        
        old_plan = self.users[username].get("plan", "demo")
        self.users[username]["plan"] = new_plan
        self.users[username]["plan_updated_at"] = datetime.now().isoformat()
        
        # Add plan-specific credits for plan upgrades
        plan_credits = {
            'starter': 250,
            'pro': 2000,        # Pro gets 2000 credits
            'ultimate': 9999
        }
        
        credits_to_add = plan_credits.get(new_plan, 0)
        if credits_to_add > 0:
            old_credits = self.users[username].get("credits", 0)
            # Set to the plan amount (don't add to existing)
            self.users[username]["credits"] = credits_to_add
            print(f"💎 Set {new_plan} plan credits to {credits_to_add}")
        
        # Log plan change transaction
        transaction = {
            "username": username,
            "type": "plan_upgrade",
            "old_plan": old_plan,
            "new_plan": new_plan,
            "credits_set": credits_to_add,
            "timestamp": datetime.now().isoformat()
        }
        
        self.users[username].setdefault("transactions", []).append(transaction)
        self.transactions.append(transaction)
        
        self.save_data()
        print(f"✅ Plan updated: {username} {old_plan} → {new_plan}")
        return True
    
    def fix_user_credits(self, username: str) -> bool:
        """Fix user credits to match their plan"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        current_plan = user.get("plan", "demo")
        
        # Set correct credits based on plan
        correct_credits = {
            'demo': 5,
            'starter': 250,
            'pro': 2000,
            'ultimate': 9999
        }
        
        if current_plan in correct_credits:
            old_credits = user.get("credits", 0)
            new_credits = correct_credits[current_plan]
            
            user["credits"] = new_credits
            
            # Log the fix
            transaction = {
                "username": username,
                "type": "credit_fix",
                "plan": current_plan,
                "old_credits": old_credits,
                "new_credits": new_credits,
                "timestamp": datetime.now().isoformat(),
                "reason": "Credit correction to match plan"
            }
            
            user.setdefault("transactions", []).append(transaction)
            self.transactions.append(transaction)
            
            self.save_data()
            print(f"✅ Fixed credits for {username}: {current_plan} plan → {new_credits} credits")
            return True
        
        return False
    
    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update user password in credit system"""
        if username not in self.users:
            print(f"❌ User {username} not found in credit system")
            return False
        
        # Update password hash using credit system's own method
        old_hash = self.users[username].get("password_hash", "")
        new_hash = self.hash_password(new_password)
        
        self.users[username]["password_hash"] = new_hash
        self.users[username]["password_updated_at"] = datetime.now().isoformat()
        
        # Save to file
        self.save_data()
        
        print(f"✅ Credit system password updated for {username}")
        print(f"🔧 Old hash: {old_hash[:20]}...")
        print(f"🔧 New hash: {new_hash[:20]}...")
        return True

    def reload_user_data(self):
        """Force reload user data from files"""
        print("🔄 Reloading credit system data...")
        old_user_count = len(self.users)
        
        self.load_data()
        
        new_user_count = len(self.users)
        print(f"✅ Credit system data reloaded: {new_user_count} users (was {old_user_count})")
        
        # Debug: Show what users we have
        for username in list(self.users.keys())[:5]:  # Show first 5 users
            user = self.users[username]
            print(f"👤 {username}: {user.get('email', 'no email')} | {user.get('plan', 'no plan')}")

    def debug_user_password(self, username: str, password: str) -> Dict:
        """Debug password checking in credit system"""
        if username not in self.users:
            available_users = list(self.users.keys())
            return {
                "error": "User not found in credit system",
                "available_users": available_users[:10],  # Show first 10
                "total_users": len(available_users)
            }
        
        user = self.users[username]
        stored_hash = user.get("password_hash", "")
        test_hash = self.hash_password(password)
        
        return {
            "username": username,
            "email": user.get("email", ""),
            "stored_hash": stored_hash[:20] + "..." if stored_hash else "NO HASH",
            "test_hash": test_hash[:20] + "...", 
            "hashes_match": stored_hash == test_hash,
            "plan": user.get("plan", "unknown"),
            "credits": user.get("credits", 0),
            "last_login": user.get("last_login", "never"),
            "password_updated_at": user.get("password_updated_at", "never")
        }

    def login_user(self, identifier: str, password: str) -> Tuple[bool, str, Dict]:
        """Authenticate user by username OR email"""
        # First try direct username lookup
        if identifier in self.users:
            user = self.users[identifier]
            if user["password_hash"] == self.hash_password(password):
                # Update last login
                user["last_login"] = datetime.now().isoformat()
                self.save_data()
                return True, f"Login successful for {identifier}", user
            else:
                return False, "Invalid password", {}
        
        # Then try email lookup
        for username, user_data in self.users.items():
            if user_data.get("email", "").lower() == identifier.lower():
                if user_data["password_hash"] == self.hash_password(password):
                    # Update last login
                    user_data["last_login"] = datetime.now().isoformat()
                    self.save_data()
                    return True, f"Login successful for {username} (via email)", user_data
                else:
                    return False, "Invalid password", {}
        
        return False, f"User not found: {identifier}", {}

    def force_user_sync(self, username: str, email: str, password: str, plan: str = "demo", credits: int = 5) -> bool:
        """Force create/update user with specific data (for fixing sync issues)"""
        password_hash = self.hash_password(password)
        
        # Get existing data if available
        existing_user = self.users.get(username, {})
        
        user_data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "plan": plan,
            "credits": credits,
            "created_at": existing_user.get("created_at", datetime.now().isoformat()),
            "last_login": datetime.now().isoformat(),
            "password_updated_at": datetime.now().isoformat(),
            "total_leads_downloaded": existing_user.get("total_leads_downloaded", 0),
            "transactions": existing_user.get("transactions", []),
            "demo_leads_used": existing_user.get("demo_leads_used", 0),
            "demo_limit": existing_user.get("demo_limit", 5),
            "force_synced": True,
            "sync_timestamp": datetime.now().isoformat()
        }
        
        self.users[username] = user_data
        self.save_data()
        
        print(f"🔧 Force synced user: {username}")
        print(f"📧 Email: {email}")
        print(f"🏷️ Plan: {plan}")
        print(f"💎 Credits: {credits}")
        return True

    def get_user_by_email(self, email: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Find user by email address"""
        for username, user_data in self.users.items():
            if user_data.get("email", "").lower() == email.lower():
                return username, user_data
        return None, None

    def verify_system_integrity(self) -> Dict:
        """Verify the integrity of the credit system"""
        issues = []
        stats = {
            "total_users": len(self.users),
            "users_with_emails": 0,
            "users_with_passwords": 0,
            "demo_users": 0,
            "paid_users": 0,
            "issues": []
        }
        
        for username, user_data in self.users.items():
            # Check email
            if user_data.get("email"):
                stats["users_with_emails"] += 1
            else:
                issues.append(f"❌ {username}: No email")
            
            # Check password hash
            if user_data.get("password_hash"):
                stats["users_with_passwords"] += 1
            else:
                issues.append(f"❌ {username}: No password hash")
            
            # Check plan
            plan = user_data.get("plan", "unknown")
            if plan == "demo":
                stats["demo_users"] += 1
            else:
                stats["paid_users"] += 1
        
        stats["issues"] = issues
        return stats

    # 🔧 UPDATE YOUR CreditSystem.__init__ method to include these:
    def __init__(self):
        self.users_file = "users_credits.json"
        self.transactions_file = "transactions.json" 
        self.load_data()
        
        # Add debug logging
        print(f"🔧 Credit system initialized: {len(self.users)} users loaded")
    
    def get_admin_stats(self) -> Dict:
        """Get admin statistics"""
        total_users = len(self.users)
        starter_users = len([u for u in self.users.values() if u.get("plan") == "starter"])
        paid_users = total_users - starter_users
        
        total_revenue = sum(self._get_price_for_plan(t.get("plan", "")) for t in self.transactions if t.get("type") == "credit_purchase")
        total_leads_served = sum(t.get("leads_downloaded", 0) for t in self.transactions if t.get("type") == "lead_download")
        
        return {
            "total_users": total_users,
            "starter_users": starter_users,
            "paid_users": paid_users,
            "total_revenue": total_revenue,
            "total_leads_served": total_leads_served,
            "total_transactions": len(self.transactions)
        }

# Global instance
credit_system = CreditSystem()

# Convenience functions for scrapers
def check_user_credits(username: str, estimated_leads: int) -> Tuple[bool, str]:
    """Check if user has enough credits for estimated leads"""
    return credit_system.check_credits(username, estimated_leads)

def consume_user_credits(username: str, leads_downloaded: int, platform: str) -> bool:
    """Consume credits after successful scraping"""
    return credit_system.consume_credits(username, leads_downloaded, leads_downloaded, platform)

def apply_lead_masking(leads: List[Dict], username: str) -> List[Dict]:
    """Apply lead masking for trial users"""
    return credit_system.mask_leads_for_trial(leads, username)

