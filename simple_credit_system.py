# simple_credit_system.py - Production-ready credit system with robust error handling
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import hashlib
from pathlib import Path
import traceback
import tempfile

class CreditSystem:
    """Production-ready credit-based lead system with comprehensive error handling"""
    
    def __init__(self):
        """Initialize credit system with production-safe file handling"""
        print("🚀 Initializing CreditSystem...")
        
        # Debug environment info
        self._debug_environment()
        
        # Set up file paths based on environment
        self._setup_file_paths()
        
        # Load data with error handling
        self.load_data()
        
        print(f"✅ Credit system initialized: {len(self.users)} users, {len(self.transactions)} transactions")
    
    def _debug_environment(self):
        """Debug environment information for troubleshooting"""
        print("🔍 Environment Debug Info:")
        print(f"   Python version: {sys.version.split()[0]}")
        print(f"   Working directory: {os.getcwd()}")
        print(f"   User home: {Path.home()}")
        print(f"   Temp directory: {tempfile.gettempdir()}")
        print(f"   Environment: {os.getenv('ENVIRONMENT', 'development')}")
        
        # Check write permissions
        test_dirs = [Path('.'), Path.home(), Path(tempfile.gettempdir())]
        for test_dir in test_dirs:
            try:
                test_file = test_dir / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                print(f"   ✅ {test_dir} is writable")
                break
            except Exception as e:
                print(f"   ❌ {test_dir} not writable: {e}")
    
    def _setup_file_paths(self):
        """Set up file paths based on environment with fallbacks"""
        # Determine the best directory for data files
        data_dir = self._get_data_directory()
        
        self.users_file = data_dir / "users_credits.json"
        self.transactions_file = data_dir / "transactions.json"
        
        print(f"📁 Data directory: {data_dir}")
        print(f"👤 Users file: {self.users_file}")
        print(f"💳 Transactions file: {self.transactions_file}")
        
        # Ensure directory exists
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Data directory ready: {data_dir}")
        except Exception as e:
            print(f"❌ Could not create data directory: {e}")
            # Fallback to temp directory
            self.users_file = Path(tempfile.gettempdir()) / "users_credits.json"
            self.transactions_file = Path(tempfile.gettempdir()) / "transactions.json"
            print(f"🔄 Using temp directory fallback")
    
    def _get_data_directory(self) -> Path:
        """Get the best directory for data files with multiple fallbacks"""
        # Try multiple locations in order of preference
        candidates = [
            Path('.'),  # Current directory (development)
            Path.home() / '.leadgen',  # User home subdirectory
            Path(tempfile.gettempdir()) / 'leadgen',  # Temp directory
            Path('/tmp/leadgen') if os.name != 'nt' else Path(tempfile.gettempdir()) / 'leadgen'  # Unix /tmp
        ]
        
        for candidate in candidates:
            try:
                # Test if we can write to this directory
                candidate.mkdir(parents=True, exist_ok=True)
                test_file = candidate / "test_write.tmp"
                test_file.write_text("test")
                test_file.unlink()
                print(f"✅ Using data directory: {candidate}")
                return candidate
            except Exception as e:
                print(f"❌ Cannot use {candidate}: {e}")
                continue
        
        # Final fallback - temp directory without subdirectory
        print("🔄 Using temp directory as final fallback")
        return Path(tempfile.gettempdir())
    
    def load_data(self):
        """Load user credits and transaction data with comprehensive error handling"""
        print("📖 Loading data files...")
        
        # Initialize defaults
        self.users = {}
        self.transactions = []
        
        # Load users file
        self._load_users_file()
        
        # Load transactions file
        self._load_transactions_file()
        
        print(f"📊 Data loaded: {len(self.users)} users, {len(self.transactions)} transactions")
    
    def _load_users_file(self):
        """Load users file with error handling and backup recovery"""
        try:
            if self.users_file.exists():
                content = self.users_file.read_text(encoding='utf-8').strip()
                if content:
                    self.users = json.loads(content)
                    print(f"👤 Loaded {len(self.users)} users from {self.users_file}")
                else:
                    print("📝 Users file is empty, starting with empty user database")
                    self.users = {}
            else:
                print("📝 Users file doesn't exist, creating new user database")
                self.users = {}
                
        except json.JSONDecodeError as e:
            print(f"❌ Corrupted users file: {e}")
            self._backup_corrupted_file(self.users_file)
            self.users = {}
            
        except Exception as e:
            print(f"❌ Error loading users file: {e}")
            print(f"🔍 Full error: {traceback.format_exc()}")
            self.users = {}
    
    def _load_transactions_file(self):
        """Load transactions file with error handling and backup recovery"""
        try:
            if self.transactions_file.exists():
                content = self.transactions_file.read_text(encoding='utf-8').strip()
                if content:
                    self.transactions = json.loads(content)
                    print(f"💳 Loaded {len(self.transactions)} transactions from {self.transactions_file}")
                else:
                    print("📝 Transactions file is empty, starting with empty transaction history")
                    self.transactions = []
            else:
                print("📝 Transactions file doesn't exist, creating new transaction history")
                self.transactions = []
                
        except json.JSONDecodeError as e:
            print(f"❌ Corrupted transactions file: {e}")
            self._backup_corrupted_file(self.transactions_file)
            self.transactions = []
            
        except Exception as e:
            print(f"❌ Error loading transactions file: {e}")
            print(f"🔍 Full error: {traceback.format_exc()}")
            self.transactions = []
    
    def _backup_corrupted_file(self, file_path: Path):
        """Backup corrupted file for potential recovery"""
        try:
            backup_path = file_path.with_suffix(f'.corrupted.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            file_path.rename(backup_path)
            print(f"💾 Backed up corrupted file to: {backup_path}")
        except Exception as e:
            print(f"❌ Could not backup corrupted file: {e}")
    
    def save_data(self):
        """Save all data to files with comprehensive error handling and recovery"""
        print("💾 Saving data files...")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Pre-save validation
                self._validate_data_before_save()
                
                # Save users file atomically
                self._save_file_atomically(self.users_file, self.users)
                
                # Save transactions file atomically
                self._save_file_atomically(self.transactions_file, self.transactions)
                
                print("✅ Data saved successfully")
                return True
                
            except Exception as e:
                retry_count += 1
                print(f"❌ Save attempt {retry_count} failed: {e}")
                
                if retry_count < max_retries:
                    print(f"🔄 Retrying save operation... ({retry_count}/{max_retries})")
                    # Wait a bit before retrying
                    import time
                    time.sleep(1)
                else:
                    print(f"💥 All save attempts failed. Data may be lost!")
                    # Try emergency backup
                    self._emergency_data_backup()
                    return False
    
    def _validate_data_before_save(self):
        """Validate data structure before saving"""
        # Validate users data
        if not isinstance(self.users, dict):
            raise ValueError("Users data must be a dictionary")
        
        # Validate transactions data
        if not isinstance(self.transactions, list):
            raise ValueError("Transactions data must be a list")
        
        # Check for any problematic data
        for username, user_data in self.users.items():
            if not isinstance(user_data, dict):
                raise ValueError(f"User data for {username} must be a dictionary")
            
            # Ensure required fields exist
            required_fields = ['email', 'password_hash', 'plan', 'credits']
            for field in required_fields:
                if field not in user_data:
                    print(f"⚠️ Missing field {field} for user {username}, adding default")
                    if field == 'email':
                        user_data[field] = ''
                    elif field == 'password_hash':
                        user_data[field] = ''
                    elif field == 'plan':
                        user_data[field] = 'demo'
                    elif field == 'credits':
                        user_data[field] = 0
    
    def _emergency_data_backup(self):
        """Create emergency backup when normal save fails"""
        try:
            import tempfile
            backup_dir = Path(tempfile.gettempdir()) / 'leadgen_emergency_backup'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup users
            emergency_users_file = backup_dir / f"emergency_users_{timestamp}.json"
            with emergency_users_file.open('w', encoding='utf-8') as f:
                json.dump(self.users, f, indent=4, default=str)
            
            # Backup transactions
            emergency_trans_file = backup_dir / f"emergency_transactions_{timestamp}.json"
            with emergency_trans_file.open('w', encoding='utf-8') as f:
                json.dump(self.transactions, f, indent=4, default=str)
            
            print(f"🆘 Emergency backup saved to {backup_dir}")
            print(f"   Users: {emergency_users_file}")
            print(f"   Transactions: {emergency_trans_file}")
            
        except Exception as e:
            print(f"💥 Emergency backup also failed: {e}")
            # Last resort - print data to console
            print("🆘 LAST RESORT - Data dump to console:")
            print("USERS:", json.dumps(self.users, indent=2, default=str)[:1000], "...")
            print("TRANSACTIONS:", json.dumps(self.transactions, indent=2, default=str)[:1000], "...")
    
    def _save_file_atomically(self, file_path: Path, data: dict | list):
        """Save file atomically with enhanced encoding safety"""
        # Write to temporary file first
        temp_file = file_path.with_suffix('.tmp')
        
        try:
            # Ensure data is JSON-serializable and clean
            cleaned_data = self._clean_data_for_json(data)
            
            # Write data to temp file with strict UTF-8 encoding
            with temp_file.open('w', encoding='utf-8', newline='') as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False, separators=(',', ': '))
                f.flush()  # Force write to disk
                os.fsync(f.fileno())  # Force OS to write to storage
            
            # Verify the file was written correctly by reading it back
            with temp_file.open('r', encoding='utf-8') as f:
                verification = json.load(f)
            
            # Atomic rename (on most filesystems)
            temp_file.replace(file_path)
            print(f"💾 Saved {len(data) if isinstance(data, (dict, list)) else 'data'} items to {file_path}")
            
            # Additional verification - read the final file
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    final_verification = json.load(f)
                print(f"✅ Final verification successful for {file_path}")
            except Exception as verify_error:
                print(f"⚠️ Final verification failed for {file_path}: {verify_error}")
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()
            print(f"❌ Failed to save {file_path}: {e}")
            raise e
    
    def _clean_data_for_json(self, data):
        """Clean data to ensure JSON serialization safety"""
        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                # Ensure keys are strings and clean
                clean_key = str(key).encode('utf-8', errors='ignore').decode('utf-8')
                cleaned[clean_key] = self._clean_data_for_json(value)
            return cleaned
        elif isinstance(data, list):
            return [self._clean_data_for_json(item) for item in data]
        elif isinstance(data, str):
            # Clean string data - remove null bytes and ensure valid UTF-8
            return data.encode('utf-8', errors='ignore').decode('utf-8').replace('\x00', '')
        else:
            return data
    
    def hash_password(self, password: str) -> str:
        """Simple password hashing with salt"""
        # Add a simple salt to make rainbow table attacks harder
        salt = "leadgen_salt_2024"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def create_user(self, username: str, email: str, password: str) -> Tuple[bool, str]:
        """Create new user with demo mode and validation"""
        try:
            # Validate inputs
            if not username or not email or not password:
                return False, "Username, email, and password are required"
            
            if username in self.users:
                return False, "Username already exists"
            
            # Check if email already exists
            for existing_username, user_data in self.users.items():
                if user_data.get("email", "").lower() == email.lower():
                    return False, f"Email already registered to user: {existing_username}"
            
            # Create user
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
            print(f"👤 Created demo user: {username} ({email})")
            return True, "Demo account created with 5 free demo leads"
            
        except Exception as e:
            print(f"❌ Error creating user {username}: {e}")
            return False, f"Error creating user: {str(e)}"
    
    def login_user(self, identifier: str, password: str) -> Tuple[bool, str, Dict]:
        """Authenticate user by username OR email with enhanced error handling"""
        try:
            if not identifier or not password:
                return False, "Username/email and password are required", {}
            
            # First try direct username lookup
            if identifier in self.users:
                user = self.users[identifier]
                if user["password_hash"] == self.hash_password(password):
                    # Update last login
                    user["last_login"] = datetime.now().isoformat()
                    self.save_data()
                    print(f"✅ User logged in: {identifier}")
                    return True, f"Login successful for {identifier}", user
                else:
                    print(f"❌ Invalid password for user: {identifier}")
                    return False, "Invalid password", {}
            
            # Then try email lookup
            for username, user_data in self.users.items():
                if user_data.get("email", "").lower() == identifier.lower():
                    if user_data["password_hash"] == self.hash_password(password):
                        # Update last login
                        user_data["last_login"] = datetime.now().isoformat()
                        self.save_data()
                        print(f"✅ User logged in via email: {username} ({identifier})")
                        return True, f"Login successful for {username} (via email)", user_data
                    else:
                        print(f"❌ Invalid password for email: {identifier}")
                        return False, "Invalid password", {}
            
            print(f"❌ User not found: {identifier}")
            return False, f"User not found: {identifier}", {}
            
        except Exception as e:
            print(f"❌ Error during login for {identifier}: {e}")
            return False, f"Login error: {str(e)}", {}
    
    def get_demo_status(self, username: str) -> Tuple[bool, int, int]:
        """Get demo status: (is_demo, used, remaining)"""
        try:
            if username not in self.users:
                return False, 0, 0
            
            user = self.users[username]
            if user.get("plan") != "demo":
                return False, 0, 0
            
            used = user.get("demo_leads_used", 0)
            limit = user.get("demo_limit", 5)
            remaining = max(0, limit - used)
            
            return True, used, remaining
            
        except Exception as e:
            print(f"❌ Error getting demo status for {username}: {e}")
            return False, 0, 0

    def can_use_demo(self, username: str) -> Tuple[bool, int]:
        """Check if user can still use demo leads"""
        try:
            is_demo, used, remaining = self.get_demo_status(username)
            return is_demo and remaining > 0, remaining
        except Exception as e:
            print(f"❌ Error checking demo usage for {username}: {e}")
            return False, 0

    def consume_demo_lead(self, username: str) -> bool:
        """Consume one demo lead with error handling"""
        try:
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
            print(f"🎯 Demo lead consumed: {username} ({used + 1}/{limit})")
            return True
            
        except Exception as e:
            print(f"❌ Error consuming demo lead for {username}: {e}")
            return False
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information with error handling"""
        try:
            return self.users.get(username)
        except Exception as e:
            print(f"❌ Error getting user info for {username}: {e}")
            return None
    
    def is_demo_user(self, username: str) -> bool:
        """Check if user is in demo mode"""
        try:
            user = self.users.get(username, {})
            return user.get("plan", "demo") == "demo"
        except Exception as e:
            print(f"❌ Error checking if {username} is demo user: {e}")
            return True  # Default to demo for safety
    
    def check_credits(self, username: str, required_credits: int) -> Tuple[bool, str, int]:
        """Check if user has enough credits"""
        try:
            if username not in self.users:
                return False, "User not found", 0
            
            user = self.users[username]
            current_credits = user.get("credits", 0)
            
            if current_credits >= required_credits:
                return True, f"{current_credits} credits available", current_credits
            else:
                return False, f"Insufficient credits: {current_credits}/{required_credits}", current_credits
                
        except Exception as e:
            print(f"❌ Error checking credits for {username}: {e}")
            return False, f"Error checking credits: {str(e)}", 0
    
    def consume_credits(self, username: str, credits_used: int, leads_downloaded: int, platform: str) -> bool:
        """Consume credits and log the transaction with error handling"""
        try:
            if username not in self.users:
                print(f"❌ User {username} not found for credit consumption")
                return False
            
            user = self.users[username]
            
            if user.get("credits", 0) < credits_used:
                print(f"❌ Insufficient credits for {username}: {user.get('credits', 0)}/{credits_used}")
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
            print(f"💳 Credits consumed: {username} used {credits_used} credits for {leads_downloaded} {platform} leads")
            return True
            
        except Exception as e:
            print(f"❌ Error consuming credits for {username}: {e}")
            return False
    
    def add_credits(self, username: str, credits: int, plan: str, stripe_session_id: str = None) -> bool:
        """Add credits to user account with enhanced error handling"""
        try:
            if username not in self.users:
                print(f"❌ User {username} not found for credit addition")
                return False

            user = self.users[username]

            # Add credits
            old_credits = user.get("credits", 0)
            user["credits"] += credits

            # Plan handling
            if plan and plan.lower() not in ["unknown", "", "credit_purchase"]:
                # This is a plan upgrade
                old_plan = user.get("plan", "demo")
                user["plan"] = plan.lower()
                print(f"📧 Plan upgraded: {username} {old_plan} → {plan}")
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
                    print(f"📧 Plan inferred from credits: {username} → {user['plan']}")

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
            
        except Exception as e:
            print(f"❌ Error adding credits for {username}: {e}")
            return False
    
    def get_user_stats(self, username: str) -> Dict:
        """Get user statistics with error handling"""
        try:
            user = self.users.get(username, {})
            
            if not user:
                return {}
            
            # Calculate stats safely
            total_purchased = sum(
                t.get("credits_added", 0) 
                for t in user.get("transactions", []) 
                if t.get("type") in ["credit_purchase", "plan_upgrade", "subscription_activation"]
            )
            
            credits_used = user.get("total_leads_downloaded", 0)  # 1 lead = 1 credit used
            
            return {
                "current_credits": user.get("credits", 0),
                "total_purchased": total_purchased,
                "credits_used": credits_used,
                "total_leads_downloaded": user.get("total_leads_downloaded", 0),
                "plan": user.get("plan", "demo"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "agreed_to_terms": user.get("agreed_to_terms", False),
                "subscription_active": user.get("subscription_active", False),
                "monthly_credits": user.get("monthly_credits", 0)
            }
            
        except Exception as e:
            print(f"❌ Error getting user stats for {username}: {e}")
            return {}
    
    def force_data_persistence(self):
        """Force data to persist even in problematic environments"""
        print("🔒 Forcing data persistence...")
        
        # Try multiple persistence strategies
        strategies = [
            self._persist_to_main_files,
            self._persist_to_backup_location,
            self._persist_to_temp_directory,
            self._persist_to_environment_variable
        ]
        
        success_count = 0
        for strategy in strategies:
            try:
                if strategy():
                    success_count += 1
                    print(f"✅ Persistence strategy succeeded: {strategy.__name__}")
                else:
                    print(f"❌ Persistence strategy failed: {strategy.__name__}")
            except Exception as e:
                print(f"💥 Persistence strategy error {strategy.__name__}: {e}")
        
        if success_count > 0:
            print(f"✅ Data persisted using {success_count} strategies")
            return True
        else:
            print("💥 All persistence strategies failed!")
            return False
    
    def _persist_to_main_files(self):
        """Persist to main data files"""
        return self.save_data()
    
    def _persist_to_backup_location(self):
        """Persist to backup location"""
        try:
            backup_dir = self.users_file.parent / 'backup'
            backup_dir.mkdir(exist_ok=True)
            
            backup_users = backup_dir / 'users_credits_backup.json'
            backup_trans = backup_dir / 'transactions_backup.json'
            
            self._save_file_atomically(backup_users, self.users)
            self._save_file_atomically(backup_trans, self.transactions)
            return True
        except:
            return False
    
    def _persist_to_temp_directory(self):
        """Persist to temp directory"""
        try:
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / 'leadgen_persistent'
            temp_dir.mkdir(exist_ok=True)
            
            temp_users = temp_dir / 'users_credits.json'
            temp_trans = temp_dir / 'transactions.json'
            
            self._save_file_atomically(temp_users, self.users)
            self._save_file_atomically(temp_trans, self.transactions)
            return True
        except:
            return False
    
    def _persist_to_environment_variable(self):
        """Persist critical data to environment variable as last resort"""
        try:
            # Only store essential user data
            essential_data = {}
            for username, user_data in self.users.items():
                essential_data[username] = {
                    'email': user_data.get('email', ''),
                    'plan': user_data.get('plan', 'demo'),
                    'credits': user_data.get('credits', 0),
                    'demo_leads_used': user_data.get('demo_leads_used', 0)
                }
            
            # Store as compressed JSON string
            import json
            essential_json = json.dumps(essential_data, separators=(',', ':'))
            
            # Store in session state as fallback
            if 'streamlit' in sys.modules:
                import streamlit as st
                st.session_state['leadgen_persistent_data'] = essential_json
                return True
            
            return False
        except:
            return False
    
    def recover_from_persistent_storage(self):
        """Recover data from persistent storage locations"""
        print("🔄 Attempting data recovery from persistent storage...")
        
        recovery_sources = [
            self._recover_from_backup_location,
            self._recover_from_temp_directory,
            self._recover_from_environment_variable
        ]
        
        for recovery_source in recovery_sources:
            try:
                recovered_data = recovery_source()
                if recovered_data:
                    self.users = recovered_data.get('users', {})
                    self.transactions = recovered_data.get('transactions', [])
                    print(f"✅ Data recovered from {recovery_source.__name__}")
                    return True
            except Exception as e:
                print(f"❌ Recovery failed from {recovery_source.__name__}: {e}")
        
        print("❌ No recoverable data found")
        return False
    
    def _recover_from_backup_location(self):
        """Recover from backup location"""
        backup_dir = self.users_file.parent / 'backup'
        backup_users = backup_dir / 'users_credits_backup.json'
        backup_trans = backup_dir / 'transactions_backup.json'
        
        if backup_users.exists() and backup_trans.exists():
            users = json.loads(backup_users.read_text(encoding='utf-8'))
            transactions = json.loads(backup_trans.read_text(encoding='utf-8'))
            return {'users': users, 'transactions': transactions}
        return None
    
    def _recover_from_temp_directory(self):
        """Recover from temp directory"""
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / 'leadgen_persistent'
        temp_users = temp_dir / 'users_credits.json'
        temp_trans = temp_dir / 'transactions.json'
        
        if temp_users.exists() and temp_trans.exists():
            users = json.loads(temp_users.read_text(encoding='utf-8'))
            transactions = json.loads(temp_trans.read_text(encoding='utf-8'))
            return {'users': users, 'transactions': transactions}
        return None
    
    def _recover_from_environment_variable(self):
        """Recover from environment variable"""
        try:
            if 'streamlit' in sys.modules:
                import streamlit as st
                if 'leadgen_persistent_data' in st.session_state:
                    essential_json = st.session_state['leadgen_persistent_data']
                    users = json.loads(essential_json)
                    return {'users': users, 'transactions': []}
            return None
        except:
            return None
    
    # Keep all other existing methods with similar error handling improvements...
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

# Initialize global instance with error handling
try:
    credit_system = CreditSystem()
    print("🎉 Global credit system instance created successfully")
except Exception as e:
    print(f"❌ Failed to create global credit system instance: {e}")
    print(f"🔍 Full error: {traceback.format_exc()}")
    # Create a minimal fallback
    credit_system = None

# Convenience functions for scrapers with error handling
def check_user_credits(username: str, estimated_leads: int) -> Tuple[bool, str]:
    """Check if user has enough credits for estimated leads"""
    try:
        if credit_system is None:
            return False, "Credit system not available"
        return credit_system.check_credits(username, estimated_leads)[:2]  # Return only bool and message
    except Exception as e:
        print(f"❌ Error checking user credits: {e}")
        return False, f"Error checking credits: {str(e)}"

def consume_user_credits(username: str, leads_downloaded: int, platform: str) -> bool:
    """Consume credits after successful scraping"""
    try:
        if credit_system is None:
            return False
        return credit_system.consume_credits(username, leads_downloaded, leads_downloaded, platform)
    except Exception as e:
        print(f"❌ Error consuming user credits: {e}")
        return False
