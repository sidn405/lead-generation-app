import streamlit as st
from typing import Tuple, List, Dict, Optional
from datetime import datetime, timedelta
import sys
import smtplib
import time
import subprocess
import pandas as pd
import glob
import os
import hashlib
import sqlite3
import secrets
import time
import re
import json
#from simple_credit_system import credit_system
from postgres_credit_system import credit_system
from cryptography.fernet import Fernet
from email.message import EmailMessage
from emailer import EMAIL_ADDRESS, EMAIL_PASSWORD

def load_legal_document(filename):
    """Load legal document from markdown file"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return f"❌ Document '{filename}' not found. Please contact support."
    except Exception as e:
        return f"❌ Error loading document: {str(e)}"

def show_terms_of_service():
    """Display Terms of Service in registration flow"""
    st.markdown("# 📜 Terms of Service")
    
    # Back button at top
    if st.button("🔙 Back to Registration", key="back_from_terms"):
        st.session_state.show_terms = False
        st.rerun()
    
    st.markdown("---")
    
    # Load and display the terms
    terms_content = load_legal_document('terms_of_service.md')
    st.markdown(terms_content)
    
    st.markdown("---")
    
    # Accept terms directly from this view
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Accept Terms", type="primary", use_container_width=True, key="accept_terms"):
            st.session_state.reg_terms = False
            st.session_state.show_terms = False
            st.success("✅ Terms accepted!")
            time.sleep(1)
            st.rerun()
    
    with col2:
        if st.button("🔙 Back to Registration", use_container_width=True, key="back_from_terms_bottom"):
            st.session_state.show_terms = False
            st.rerun()

def show_privacy_policy():
    """Display Privacy Policy in registration flow"""
    st.markdown("# 🔒 Privacy Policy")
    
    # Back button at top
    if st.button("🔙 Back to Registration", key="back_from_privacy"):
        st.session_state.show_privacy = False
        st.rerun()
    
    st.markdown("---")
    
    # Load and display the privacy policy
    privacy_content = load_legal_document('privacy_policy.md')
    st.markdown(privacy_content)
    
    st.markdown("---")
    
    # Accept privacy directly from this view
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Accept Privacy Policy", type="primary", use_container_width=True, key="accept_privacy"):
            st.session_state.reg_privacy = False
            st.session_state.show_privacy = False
            st.success("✅ Privacy Policy accepted!")
            time.sleep(1)
            st.rerun()
    
    with col2:
        if st.button("🔙 Back to Registration", use_container_width=True, key="back_from_privacy_bottom"):
            st.session_state.show_privacy = False
            st.rerun()

def delete_user_data(username):
    """Delete all user data from JSON files and config"""
    import os, json, streamlit as st
    
    st.write(f"🗑️ Attempting to delete all data for user: {username}")
    deletion_success = False
    
    # 1. Delete client config file
    config_dir = "client_configs"
    config_file = os.path.join(config_dir, f"client_{username}_config.json")
    
    st.write(f"📁 Checking config file: {config_file}")
    if os.path.exists(config_file):
        try:
            os.remove(config_file)
            st.write("✅ Removed user config file")
            deletion_success = True
        except Exception as e:
            st.write(f"❌ Error removing config file: {e}")
    else:
        st.write("ℹ️ No config file found")

    # 2. Delete from JSON files - FIXED FILENAMES AND LOGIC
    json_files = [
        "users_credits.json",  # Fixed: was "users_credit.json" 
        "users.json"
    ]
    
    for filename in json_files:
        st.write(f"📄 Processing {filename}...")
        
        if not os.path.exists(filename):
            st.write(f"ℹ️ File {filename} not found, skipping")
            continue
            
        try:
            # Read the file
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if user exists
            if username in data:
                st.write(f"👤 Found {username} in {filename}")
                
                # Remove user
                del data[username]
                
                # Write back to file (safer method)
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                st.write(f"✅ Removed {username} from {filename}")
                deletion_success = True
            else:
                st.write(f"ℹ️ User {username} not found in {filename}")
                
        except json.JSONDecodeError as e:
            st.write(f"❌ JSON error in {filename}: {e}")
        except Exception as e:
            st.write(f"❌ Error processing {filename}: {e}")
    
    # 3. Also check for any other user-specific files
    try:
        # Check for any other files that might contain user data
        user_specific_patterns = [
            f"*{username}*",
            f"user_{username}_*",
        ]
        
        files_removed = 0
        for pattern in user_specific_patterns:
            import glob
            matching_files = glob.glob(pattern)
            for file_path in matching_files:
                if os.path.isfile(file_path) and username in file_path:
                    try:
                        os.remove(file_path)
                        st.write(f"🗑️ Removed additional file: {file_path}")
                        files_removed += 1
                    except Exception as e:
                        st.write(f"⚠️ Could not remove {file_path}: {e}")
        
        if files_removed > 0:
            st.write(f"✅ Removed {files_removed} additional user files")
            deletion_success = True
            
    except Exception as e:
        st.write(f"⚠️ Error during additional file cleanup: {e}")
    
    st.write(f"📊 Deletion summary: {'Success' if deletion_success else 'No data found'}")
    return deletion_success

class SimpleCreditAuth:
    """Simple credit-based authentication"""
    
    def __init__(self):
        self.current_user = None
        self.user_data = None
    
    def register_user(self, username: str, email: str, password: str) -> Tuple[bool, str]:
        """Register new user with starter credits"""
        return credit_system.create_user(username, email, password)
    
    def login_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Login user"""
        success, message, user_data = credit_system.login_user(username, password)
        
        if success:
            self.current_user = username
            self.user_data = user_data
            
            # Set Streamlit session state
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.user_data = user_data
            st.session_state.credits = user_data.get('credits', 0)
        
        return success, message
    
    def logout_user(self):
        """Logout user"""
        self.current_user = None
        self.user_data = None
        
        # Clear session state
        for key in ['authenticated', 'username', 'user_data', 'credits', 'show_login', 'show_register']:
            if key in st.session_state:
                del st.session_state[key]
    
    # Update your authentication functions to use PostgreSQL
    def authenticate_user_postgres(identifier, password):
        """Authenticate using PostgreSQL"""
        if not credit_system:
            return False, "Database not available", {}
        
        success, message, user_data = credit_system.login_user(identifier, password)
        
        if success:
            # Set session state
            st.session_state.username = user_data['username']
            st.session_state.user_authenticated = True
            st.session_state.user_data = user_data
            st.session_state.user_plan = user_data['plan']
            st.session_state.user_credits = user_data['credits']
        
        return success, message, user_data
    
    def get_current_user(self) -> str:
        """Get current username"""
        return st.session_state.get('username')
    
    def get_user_credits(self) -> int:
        """Get user's current credits or demo leads remaining"""
        username = self.get_current_user()
        if username:
            try:
                from simple_credit_system import credit_system
                user_info = credit_system.get_user_info(username)
                
                if user_info:
                    # For demo users, return demo leads remaining
                    if user_info.get('plan') == 'demo':
                        can_demo, remaining = credit_system.can_use_demo(username)
                        return remaining
                    
                    # For paid users, return regular credits
                    credits = user_info.get('credits', 0)
                    st.session_state.credits = credits  # Update session state
                    return credits
            except:
                pass
            
            # Fallback to session state
            return st.session_state.get('credits', 0)
        return 0
    
    def get_user_plan(self) -> str:
        """Get user's plan"""
        user_data = st.session_state.get('user_data', {})
        return user_data.get('plan', 'starter')
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        return st.session_state.get('authenticated', False)
    
    def delete_user_account(self) -> bool:
        """FIXED: Remove all user data and handle the cleanup properly"""
        import streamlit as st
        
        username = self.get_current_user()
        if not username:
            st.error("❌ No user currently logged in.")
            return False

        st.write(f"🗑️ Starting account deletion for: {username}")
        
        # Step 1: Delete all user data files
        try:
            deletion_successful = delete_user_data(username)
            st.write(f"📋 File deletion result: {deletion_successful}")
        except Exception as e:
            st.error(f"❌ Error during file deletion: {e}")
            return False

        # Step 2: Try to reload/sync the credit system
        try:
            # Import here to avoid circular imports
            from simple_credit_system import credit_system
            
            # Force reload the credit system
            if hasattr(credit_system, 'reload_user_data'):
                credit_system.reload_user_data()
                st.write("✅ Credit system reloaded successfully")
            else:
                st.write("⚠️ Credit system reload method not available")
                
        except ImportError:
            st.write("⚠️ Credit system not available for reload")
        except Exception as e:
            st.write(f"⚠️ Credit system reload warning: {e}")

        # Step 3: Clear ALL session state thoroughly
        st.write("🧹 Clearing session state...")
        
        # List of ALL possible session keys to clear
        keys_to_clear = [
            # Auth keys
            'authenticated', 'username', 'user_data', 'credits',
            # Login/register keys  
            'show_login', 'show_register',
            'login_username', 'login_password',
            'reg_username', 'reg_email', 'reg_password', 'reg_confirm_password', 'reg_terms',
            'reg_company_name', 'reg_instagram', 'reg_tiktok', 'reg_facebook',
            'reg_twitter', 'reg_youtube', 'reg_linkedin', 'reg_medium', 'reg_reddit',
            'reg_privacy', 'show_terms', 'show_privacy',
            # Account closure keys
            'show_close_expander', 'confirm_close', 'close_reason', 'close_feedback',
            # Password reset keys
            'show_forgot_password', 'show_password_reset', 'show_update_password',
            'demo_reset_token', 'demo_reset_username', 'demo_reset_email',
            # Any other user-specific keys
            'current_page', 'search_results', 'selected_platforms',
        ]
        
        cleared_count = 0
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
                cleared_count += 1
        
        # Also clear any keys that contain the username
        additional_cleared = 0
        for key in list(st.session_state.keys()):
            if username.lower() in key.lower():
                del st.session_state[key]
                additional_cleared += 1
        
        st.write(f"🧹 Cleared {cleared_count} standard keys + {additional_cleared} user-specific keys")
        
        # Step 4: Reset auth object state
        self.current_user = None
        self.user_data = None
        
        # Step 5: Force redirect to login
        st.session_state.show_login = True
        
        # Step 6: Show success and rerun
        if deletion_successful:
            st.success("✅ Account successfully deleted. All your data has been removed.")
        else:
            st.warning("⚠️ Account deletion completed, but no user data was found to remove.")
        
        st.info("🔄 Redirecting to login page...")
        
        # Force a complete rerun
        st.rerun()
        
        return True
    
# one global instance
simple_auth = SimpleCreditAuth()
    
# Email validation patterns
# Load both user files for comprehensive checking
def load_all_existing_users():
    """Load existing users from both users.json AND users_credits.json"""
    all_users = {}
    all_emails = set()
    
    # Load users.json
    try:
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users_json = json.load(f)
                for username, user_data in users_json.items():
                    all_users[username.lower()] = {
                        'source': 'users.json',
                        'email': user_data.get('email', ''),
                        'plan': user_data.get('plan', 'free')
                    }
                    if user_data.get('email'):
                        all_emails.add(user_data['email'].lower())
    except Exception as e:
        print(f"Error loading users.json: {e}")
    
    # Load users_credits.json
    try:
        if os.path.exists("users_credits.json"):
            with open("users_credits.json", "r") as f:
                users_credits = json.load(f)
                for username, user_data in users_credits.items():
                    all_users[username.lower()] = {
                        'source': 'users_credits.json',
                        'email': user_data.get('email', ''),
                        'plan': user_data.get('plan', 'demo')
                    }
                    if user_data.get('email'):
                        all_emails.add(user_data['email'].lower())
    except Exception as e:
        print(f"Error loading users_credits.json: {e}")
    
    print(f"📊 Loaded {len(all_users)} total users from both files")
    print(f"📧 Found {len(all_emails)} total emails")
    
    return all_users, all_emails

# Email validation
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
DISPOSABLE_DOMAINS = {
    '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.org',
    'throwaway.email', 'spam4.me', 'maildrop.cc', 'temp-mail.org', 'yopmail.com'
}

def validate_username_realtime(username: str) -> Tuple[bool, str, str]:
    """FIXED: Real-time username validation checking BOTH JSON files"""
    if not username:
        return False, "Enter a username", "placeholder"
    
    if len(username) < 3:
        return False, "Username too short (minimum 3 characters)", "error"
    
    if len(username) > 20:
        return False, "Username too long (maximum 20 characters)", "error"
    
    if not username.isalnum():
        return False, "Username must contain only letters and numbers", "error"
    
    # FIXED: Check availability against BOTH user files
    all_users, _ = load_all_existing_users()
    username_lower = username.lower()
    
    if username_lower in all_users:
        user_info = all_users[username_lower]
        source_file = user_info['source']
        return False, f"Username already taken", "error"
    
    return True, "Username available", "success"

def validate_email_realtime(email: str) -> Tuple[bool, str, str]:
    """FIXED: Real-time email validation checking BOTH JSON files"""
    if not email:
        return False, "Enter your email address", "placeholder"
    
    if not EMAIL_PATTERN.match(email):
        return False, "Please use a valid email format", "error"
    
    domain = email.split('@')[1].lower() if '@' in email else ""
    if domain in DISPOSABLE_DOMAINS:
        return False, "Please use a permanent email address", "error"
    
    # FIXED: Check if email already exists in BOTH files
    _, all_emails = load_all_existing_users()
    
    if email.lower() in all_emails:
        return False, "Email already registered", "error"
    
    return True, "Valid email", "success"

def validate_password_realtime(password: str) -> Tuple[bool, str, str, Dict]:
    """Real-time password validation with detailed requirements"""
    requirements = {
        'length': False,
        'uppercase': False,
        'lowercase': False,
        'number': False,
        'special': False
    }
    
    if not password:
        return False, "Password must contain at least 8 characters, one special character(!@#$%^&*), one uppercase(A-Z) and lowercase(a-z) letter, one number(0-9)", "placeholder", requirements
    
    # Check each requirement
    requirements['length'] = len(password) >= 8
    requirements['uppercase'] = bool(re.search(r'[A-Z]', password))
    requirements['lowercase'] = bool(re.search(r'[a-z]', password))
    requirements['number'] = bool(re.search(r'\d', password))
    requirements['special'] = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>/?]', password))
    
    # Create feedback message
    missing = []
    if not requirements['length']:
        missing.append("8+ characters")
    if not requirements['uppercase']:
        missing.append("uppercase letter")
    if not requirements['lowercase']:
        missing.append("lowercase letter")
    if not requirements['number']:
        missing.append("number")
    if not requirements['special']:
        missing.append("special character")
    
    if missing:
        message = f"Password must contain: {', '.join(missing)}"
        return False, message, "error", requirements
    
    return True, "Strong password", "success", requirements

def validate_password_match(password: str, confirm_password: str) -> Tuple[bool, str, str]:
    """Real-time password confirmation validation"""
    if not confirm_password:
        return False, "Confirm your password", "placeholder"
    
    if password != confirm_password:
        return False, "Passwords do not match", "error"
    
    return True, "Passwords match", "success"

def create_input_with_validation(label: str, value: str, input_type: str = "text", 
                                validation_result: Tuple = None, key: str = None):
    """Create input field with inline validation and checkmark"""
    
    # Determine validation state
    if validation_result:
        is_valid, message, state = validation_result[:3]
    else:
        is_valid, message, state = False, "", "placeholder"
    
    # Create columns for input and checkmark
    col1, col2 = st.columns([10, 1])
    
    with col1:
        # Input field with placeholder text based on validation
        if input_type == "password":
            input_value = st.text_input(
                label,
                value=value,
                type="password",
                placeholder=message if state in ["placeholder", "error"] else "",
                help=message if state == "success" else None,
                key=key
            )
        else:
            input_value = st.text_input(
                label,
                value=value,
                placeholder=message if state in ["placeholder", "error"] else "",
                help=message if state == "success" else None,
                key=key
            )
    
    with col2:
        # Checkmark or error indicator
        if state == "success":
            st.markdown('<div style="color: green; font-size: 24px; text-align: center;">✓</div>', 
                       unsafe_allow_html=True)
        elif state == "error" and value:  # Only show error if user has typed something
            st.markdown('<div style="color: red; font-size: 24px; text-align: center;">✗</div>', 
                       unsafe_allow_html=True)
        else:
            st.markdown('<div style="height: 24px;"></div>', unsafe_allow_html=True)
    
    # Show error message below input if there's an error
    if state == "error" and value:
        st.error(message)
    elif state == "success":
        st.success(message)
    
    return input_value

def create_password_requirements_checklist(requirements: Dict):
    """Create visual requirements checklist for password"""
    if not any(requirements.values()):
        return
    
    st.markdown("**Password Requirements:**")
    
    req_items = [
        ("length", "At least 8 characters"),
        ("uppercase", "One uppercase letter (A-Z)"),
        ("lowercase", "One lowercase letter (a-z)"),
        ("number", "One number (0-9)"),
        ("special", "One special character (!@#$%^&*)")
    ]
    
    cols = st.columns(len(req_items))
    for i, (req_key, req_text) in enumerate(req_items):
        with cols[i]:
            if requirements[req_key]:
                st.markdown(f'<div style="color: green;">✓ {req_text}</div>', 
                          unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color: #888;">○ {req_text}</div>', 
                          unsafe_allow_html=True)

def show_realtime_registration():
    """FIXED: Registration form with both JSON files checking"""

    # 🔧 Handle legal document display FIRST
    if st.session_state.get('show_terms', False):
        show_terms_of_service()
        return  # Stop here and show terms
    
    if st.session_state.get('show_privacy', False):
        show_privacy_policy()
        return  # Stop here and show privacy

    st.markdown("### 🚀 Create Your Empire Account")
    
    # Initialize session state for real-time updates
    if 'reg_username' not in st.session_state:
        st.session_state.reg_username = ""
    if 'reg_email' not in st.session_state:
        st.session_state.reg_email = ""
    if 'reg_password' not in st.session_state:
        st.session_state.reg_password = ""
    if 'reg_confirm_password' not in st.session_state:
        st.session_state.reg_confirm_password = ""
    if 'reg_terms' not in st.session_state:
        st.session_state.reg_terms = False

    # NEW: Social media account states
    if 'reg_company_name' not in st.session_state:
        st.session_state.reg_company_name = ""
    if 'reg_instagram' not in st.session_state:
        st.session_state.reg_instagram = ""
    if 'reg_tiktok' not in st.session_state:
        st.session_state.reg_tiktok = ""
    if 'reg_facebook' not in st.session_state:
        st.session_state.reg_facebook = ""
    if 'reg_twitter' not in st.session_state:
        st.session_state.reg_twitter = ""
    if 'reg_youtube' not in st.session_state:
        st.session_state.reg_youtube = ""
    if 'reg_linkedin' not in st.session_state:
        st.session_state.reg_linkedin = ""
    if 'reg_medium' not in st.session_state:
        st.session_state.reg_medium = ""
    if 'reg_reddit' not in st.session_state:
        st.session_state.reg_reddit = ""
    
    
    # Create form container with tabs
    tab1, tab2 = st.tabs(["🔐 Account Info", "📱 Social Accounts"])
    
    with tab1:
        # FIXED: Real-time validation using the updated functions
        username_valid, username_msg, username_state = validate_username_realtime(st.session_state.reg_username)
        email_valid, email_msg, email_state = validate_email_realtime(st.session_state.reg_email)
        password_valid, password_msg, password_state, password_reqs = validate_password_realtime(st.session_state.reg_password)
        confirm_valid, confirm_msg, confirm_state = validate_password_match(st.session_state.reg_password, st.session_state.reg_confirm_password)
        
        # Username input with FIXED validation
        new_username = create_input_with_validation(
            "👤 Username",
            st.session_state.reg_username,
            validation_result=(username_valid, username_msg, username_state),
            key="username_input"
        )
        if new_username != st.session_state.reg_username:
            st.session_state.reg_username = new_username
            st.rerun()
        
        # Email input with FIXED validation
        new_email = create_input_with_validation(
            "📧 Email Address",
            st.session_state.reg_email,
            validation_result=(email_valid, email_msg, email_state),
            key="email_input"
        )
        if new_email != st.session_state.reg_email:
            st.session_state.reg_email = new_email
            st.rerun()
        
        # Password input with real-time validation
        new_password = create_input_with_validation(
            "🔒 Password",
            st.session_state.reg_password,
            input_type="password",
            validation_result=(password_valid, password_msg, password_state),
            key="password_input"
        )
        if new_password != st.session_state.reg_password:
            st.session_state.reg_password = new_password
            st.rerun()
        
        # Show password requirements checklist
        if st.session_state.reg_password:
            create_password_requirements_checklist(password_reqs)
        
        # Confirm password input with real-time validation
        new_confirm = create_input_with_validation(
            "🔒 Confirm Password",
            st.session_state.reg_confirm_password,
            input_type="password",
            validation_result=(confirm_valid, confirm_msg, confirm_state),
            key="confirm_input"
        )
        if new_confirm != st.session_state.reg_confirm_password:
            st.session_state.reg_confirm_password = new_confirm
            st.rerun()
    
    with tab2:
        st.markdown("### 🏢 Business Information")
        st.markdown("*Help us customize your lead generation experience*")
        
        # Company name
        new_company = st.text_input(
            "🏢 Company/Business Name",
            value=st.session_state.reg_company_name,
            placeholder="e.g., Sarah's Fitness Coaching",
            help="Your business name for personalization",
            key="company_input"
        )
        if new_company != st.session_state.reg_company_name:
            st.session_state.reg_company_name = new_company
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 🚫 Exclude Your Own Accounts")
        st.markdown("*Add your social media accounts to prevent them from appearing in your leads*")
        
        # Create two columns for social accounts
        social_col1, social_col2 = st.columns(2)
        
        def clean_username(username):
            """Clean username by removing @ and whitespace"""
            return username.strip().lstrip('@') if username else ""
        
        with social_col1:
            # Instagram
            new_instagram = st.text_input(
                "📸 Instagram Username",
                value=st.session_state.reg_instagram,
                placeholder="yourhandle (without @)",
                help="Your Instagram username to exclude from leads",
                key="instagram_input"
            )
            if new_instagram != st.session_state.reg_instagram:
                st.session_state.reg_instagram = clean_username(new_instagram)
                st.rerun()
            
            # TikTok
            new_tiktok = st.text_input(
                "🎵 TikTok Username",
                value=st.session_state.reg_tiktok,
                placeholder="yourhandle (without @)",
                help="Your TikTok username to exclude from leads",
                key="tiktok_input"
            )
            if new_tiktok != st.session_state.reg_tiktok:
                st.session_state.reg_tiktok = clean_username(new_tiktok)
                st.rerun()
            
            # Facebook
            new_facebook = st.text_input(
                "📘 Facebook Username/Profile",
                value=st.session_state.reg_facebook,
                placeholder="your.profile.name",
                help="Your Facebook profile name to exclude from leads",
                key="facebook_input"
            )
            if new_facebook != st.session_state.reg_facebook:
                st.session_state.reg_facebook = clean_username(new_facebook)
                st.rerun()

            # Medium
            new_medium = st.text_input(
                "📝 Medium Username/Profile",
                value=st.session_state.reg_medium,
                placeholder="your.profile.name",
                help="Your Medium profile name to exclude from leads",
                key="medium_input"
            )
            if new_medium != st.session_state.reg_medium:
                st.session_state.reg_medium = clean_username(new_medium)
                st.rerun()
        
        with social_col2:
            # Twitter
            new_twitter = st.text_input(
                "🐦 Twitter Username",
                value=st.session_state.reg_twitter,
                placeholder="yourhandle (without @)",
                help="Your Twitter username to exclude from leads",
                key="twitter_input"
            )
            if new_twitter != st.session_state.reg_twitter:
                st.session_state.reg_twitter = clean_username(new_twitter)
                st.rerun()
            
            # YouTube
            new_youtube = st.text_input(
                "📹 YouTube Channel",
                value=st.session_state.reg_youtube,
                placeholder="YourChannelName",
                help="Your YouTube channel name to exclude from leads",
                key="youtube_input"
            )
            if new_youtube != st.session_state.reg_youtube:
                st.session_state.reg_youtube = clean_username(new_youtube)
                st.rerun()
            
            # LinkedIn
            new_linkedin = st.text_input(
                "💼 LinkedIn Profile",
                value=st.session_state.reg_linkedin,
                placeholder="your-linkedin-name",
                help="Your LinkedIn profile name to exclude from leads",
                key="linkedin_input"
            )
            if new_linkedin != st.session_state.reg_linkedin:
                st.session_state.reg_linkedin = clean_username(new_linkedin)
                st.rerun()

            # Reddit
            new_reddit = st.text_input(
                "🗨️ Reddit Username/Profile",
                value=st.session_state.reg_reddit,
                placeholder="your.profile.name",
                help="Your Reddit profile name to exclude from leads",
                key="reddit_input"
            )
            if new_reddit != st.session_state.reg_reddit:
                st.session_state.reg_reddit = clean_username(new_reddit)
                st.rerun()
        
        # Show preview of excluded accounts
        excluded_accounts = []
        for platform, username in [
            ("Instagram", st.session_state.reg_instagram),
            ("TikTok", st.session_state.reg_tiktok),
            ("Facebook", st.session_state.reg_facebook),
            ("Twitter", st.session_state.reg_twitter),
            ("YouTube", st.session_state.reg_youtube),
            ("LinkedIn", st.session_state.reg_linkedin),
            ("Medium", st.session_state.reg_medium),
            ("Reddit", st.session_state.reg_reddit)
        ]:
            if username.strip():
                excluded_accounts.append(f"{platform}: @{username}")
        
        if excluded_accounts:
            st.info(f"🚫 **Accounts to exclude:** {', '.join(excluded_accounts)}")
        else:
            st.warning("💡 **Tip:** Adding your accounts prevents them from appearing in your lead results!")
    
    # Terms checkbox with legal document links (outside tabs)
    st.markdown("---")
    st.markdown("### 📋 Legal Agreement")

    # Initialize privacy state if needed
    if 'reg_privacy' not in st.session_state:
        st.session_state.reg_privacy = False

    # Add buttons to read legal documents
    legal_col1, legal_col2 = st.columns(2)

    with legal_col1:
        if st.button("📜 Read Terms of Service", key="reg_read_terms", use_container_width=True):
            st.session_state.show_terms = True
            st.rerun()

    with legal_col2:
        if st.button("🔒 Read Privacy Policy", key="reg_read_privacy", use_container_width=True):
            st.session_state.show_privacy = True
            st.rerun()

    # Show status of each agreement
    agreement_col1, agreement_col2 = st.columns(2)

    with agreement_col1:
        terms_agreed = st.checkbox(
            "✅ I agree to the Terms of Service",
            value=st.session_state.reg_terms,
            key="terms_checkbox"
        )
        if terms_agreed != st.session_state.reg_terms:
            st.session_state.reg_terms = terms_agreed
            st.rerun()

    with agreement_col2:
        privacy_agreed = st.checkbox(
            "✅ I agree to the Privacy Policy",
            value=st.session_state.reg_privacy,
            key="privacy_checkbox"
        )
        if privacy_agreed != st.session_state.reg_privacy:
            st.session_state.reg_privacy = privacy_agreed
            st.rerun()

    # Overall agreement status
    both_agreed = terms_agreed and privacy_agreed

    # Show requirement if not agreed
    if not both_agreed:
        missing = []
        if not terms_agreed:
            missing.append("Terms of Service")
        if not privacy_agreed:
            missing.append("Privacy Policy")
        
        st.warning(f"⚠️ Please read and agree to: {', '.join(missing)}")
    else:
        st.success("✅ All legal agreements accepted")
    
    # Live registration status
    st.markdown("### 📋 Registration Status")
    
    status_items = [
        ("Username", username_valid, f"✓ Available: {st.session_state.reg_username}" if username_valid else f"✗ {username_msg}"),
        ("Email", email_valid, f"✓ Valid: {st.session_state.reg_email}" if email_valid else f"✗ {email_msg}"),
        ("Password", password_valid, "✓ Strong password" if password_valid else f"✗ {password_msg}"),
        ("Confirmation", confirm_valid, "✓ Passwords match" if confirm_valid else f"✗ {confirm_msg}"),
        ("Legal Agreement", both_agreed, "✓ Terms and Privacy accepted" if both_agreed else "✗ Must accept all agreements")
]
    
    for item_name, is_valid, message in status_items:
        if is_valid:
            st.success(message)
        else:
            st.error(message)
    
    # Submit button
    all_valid = username_valid and email_valid and password_valid and confirm_valid and terms_agreed
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(
            "🚀 Create Empire Account" if all_valid else "Complete Requirements Above",
            type="primary" if all_valid else "secondary",
            disabled=not all_valid,
            use_container_width=True
        ):
            if all_valid:
                try:
                    # Prepare registration data with social accounts
                    registration_data = {
                        "username": st.session_state.reg_username,
                        "email": st.session_state.reg_email,
                        "password": st.session_state.reg_password,
                        "company_name": st.session_state.reg_company_name,
                        "social_accounts": {
                            "instagram": st.session_state.reg_instagram,
                            "tiktok": st.session_state.reg_tiktok,
                            "facebook": st.session_state.reg_facebook,
                            "twitter": st.session_state.reg_twitter,
                            "youtube": st.session_state.reg_youtube,
                            "linkedin": st.session_state.reg_linkedin,
                            "medium": st.session_state.reg_medium,
                            "reddit": st.session_state.reg_reddit
                            
                        }
                    }
                    
                    # Call registration function
                    success, message = simple_auth.register_user(
                        st.session_state.reg_username,
                        st.session_state.reg_email,
                        st.session_state.reg_password
                    )
                    
                    if success:
                        # Setup client config with excluded accounts  
                        try:
                            # Import your existing config loader
                            from enhanced_config_loader import ConfigLoader
                            import uuid
                            import os
                            
                            # Create client configs directory if it doesn't exist
                            config_dir = "client_configs"
                            os.makedirs(config_dir, exist_ok=True)
                            
                            # Create user-specific config file
                            client_id = str(uuid.uuid4())[:8]
                            config_file = f"{config_dir}/client_{st.session_state.reg_username}_config.json"
                            
                            print(f"🔧 Creating config file: {config_file}")
                            
                            # Initialize config loader with user-specific file
                            config_loader = ConfigLoader(config_file)
                            
                            # Setup basic user settings
                            config_loader.config["user_settings"] = {
                                "user_id": client_id,
                                "username": st.session_state.reg_username,
                                "company_name": st.session_state.reg_company_name,
                                "monthly_lead_target": 10000,
                                "created_date": datetime.now().isoformat()
                            }
                            
                            # Setup excluded accounts from registration
                            social_accounts = registration_data.get("social_accounts", {})
                            excluded_count = 0
                            
                            for platform, username_to_exclude in social_accounts.items():
                                if username_to_exclude and username_to_exclude.strip():
                                    clean_username = username_to_exclude.strip().lstrip('@')
                                    print(f"🚫 Adding {platform} exclusion: {clean_username}")
                                    
                                    # Use your existing add_excluded_account method
                                    success_added = config_loader.add_excluded_account(platform, clean_username)
                                    if success_added:
                                        excluded_count += 1
                                        print(f"✅ Added {platform}: {clean_username}")
                                    else:
                                        print(f"⚠️ Failed to add {platform}: {clean_username}")
                            
                            # Save the configuration
                            config_saved = config_loader.save_config()
                            
                            if config_saved:
                                if excluded_count > 0:
                                    st.success(f"✅ Account created with {excluded_count} social account exclusions!")
                                    st.info(f"🚫 Your accounts will be excluded from lead results: {excluded_count} accounts added")
                                else:
                                    st.success("✅ Account created successfully!")
                                    st.info("💡 No social accounts to exclude - you can add them later in Settings")
                            else:
                                st.warning("⚠️ Account created but exclusions may not be saved properly")
                                
                            print(f"✅ Config setup completed for {st.session_state.reg_username}")
                            
                        except ImportError as e:
                            st.warning(f"⚠️ Account created but exclusions not available: enhanced_config_loader not found")
                            print(f"❌ Import error: {e}")
                            
                        except FileNotFoundError as e:
                            st.warning(f"⚠️ Account created but config directory not accessible")
                            print(f"❌ File error: {e}")
                            
                        except Exception as e:
                            st.warning(f"⚠️ Account created but exclusion setup failed: {str(e)}")
                            print(f"❌ Config setup error: {e}")
                            print(f"❌ Full traceback:")
                            import traceback
                            traceback.print_exc()
                        
                        # Continue with success message regardless
                        st.success(f"✅ {message}")
                        
                        # Auto-login
                        login_success, login_message = simple_auth.login_user(
                            st.session_state.reg_username,
                            st.session_state.reg_password
                        )
                        
                        if login_success:
                            # Clear registration state
                            reg_keys = ['reg_username', 'reg_email', 'reg_password', 'reg_confirm_password', 'reg_terms',
                                       'reg_company_name', 'reg_instagram', 'reg_tiktok', 'reg_facebook',
                                       'reg_twitter', 'reg_youtube', 'reg_linkedin']
                            for key in reg_keys:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            # Clear auth modals
                            st.session_state.show_login = False
                            st.session_state.show_register = False
                            
                            st.success("🎉 Welcome to Lead Generator Empire!")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error(f"❌ {message}")
                
                except Exception as e:
                    st.error(f"❌ Registration error: {str(e)}")
    
    with col2:
        if st.button("🔑 Sign In Instead", use_container_width=True):
            # Clear registration state
            reg_keys = ['reg_username', 'reg_email', 'reg_password', 'reg_confirm_password', 'reg_terms',
                       'reg_company_name', 'reg_instagram', 'reg_tiktok', 'reg_facebook',
                       'reg_twitter', 'reg_youtube', 'reg_linkedin']
            for key in reg_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.show_register = False
            st.session_state.show_login = True
            st.rerun()

def show_enhanced_login_with_forgot_password():
    """Enhanced login form with forgot password link"""
    st.markdown("### 🔑 Sign In to Your Empire")
    
    # Initialize session state
    if 'login_username' not in st.session_state:
        st.session_state.login_username = ""
    if 'login_password' not in st.session_state:
        st.session_state.login_password = ""
    
    with st.container():
        # Username/Email input
        new_username = st.text_input(
            "👤 Username or Email",
            value=st.session_state.login_username,
            placeholder="Enter username or email",
            key="login_username_input"
        )
        if new_username != st.session_state.login_username:
            st.session_state.login_username = new_username
            st.rerun()
        
        # Password input
        new_password = st.text_input(
            "🔒 Password",
            value=st.session_state.login_password,
            type="password",
            placeholder="Enter password",
            key="login_password_input"
        )
        if new_password != st.session_state.login_password:
            st.session_state.login_password = new_password
            st.rerun()
        
        # Forgot password link
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔐 Forgot Password?", key="forgot_password_link"):
                st.session_state.show_forgot_password = True
                st.session_state.show_login = False
                st.rerun()
        
        # Login button
        can_login = bool(st.session_state.login_username and st.session_state.login_password)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                "🔑 Sign In" if can_login else "Enter Credentials",
                type="primary" if can_login else "secondary",
                disabled=not can_login,
                use_container_width=True
            ):
                if can_login:
                    try:
                        success, message = simple_auth.login_user(
                            st.session_state.login_username,
                            st.session_state.login_password
                        )
                        
                        if success:
                            st.success(f"✅ {message}")
                            
                            # Clear login state
                            for key in ['login_username', 'login_password']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            # Clear auth modals
                            st.session_state.show_login = False
                            st.session_state.show_register = False
                            
                            credits = simple_auth.get_user_credits()
                            plan = simple_auth.get_user_plan()
                            st.success(f"💎 Welcome back! You have {credits} credits ({plan} plan)")
                            
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                            st.info("💡 Forgot your password? Use the 'Forgot Password?' link above")
                    
                    except Exception as e:
                        st.error(f"❌ Login error: {str(e)}")
        
        with col2:
            if st.button("🚀 Create Account", use_container_width=True):
                # Clear login state
                for key in ['login_username', 'login_password']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.session_state.show_login = False
                st.session_state.show_register = True
                st.rerun()

# Password reset tokens (in production, this would be in a database)
PASSWORD_RESET_TOKENS = {}

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_reset_token() -> str:
    """Generate a secure reset token"""
    return secrets.token_urlsafe(32)

def load_user_from_both_files(identifier: str) -> Tuple[Optional[Dict], str, str]:
    """
    Find user by username or email in both JSON files
    Returns: (user_data, username, source_file)
    """
    identifier_lower = identifier.lower()
    
    # Check users.json
    try:
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)
                
                # Check by username
                for username, user_data in users.items():
                    if username.lower() == identifier_lower:
                        return user_data, username, "users.json"
                
                # Check by email
                for username, user_data in users.items():
                    if user_data.get('email', '').lower() == identifier_lower:
                        return user_data, username, "users.json"
    except Exception as e:
        print(f"Error reading users.json: {e}")
    
    # Check users_credits.json
    try:
        if os.path.exists("users_credits.json"):
            with open("users_credits.json", "r") as f:
                users = json.load(f)
                
                # Check by username
                for username, user_data in users.items():
                    if username.lower() == identifier_lower:
                        return user_data, username, "users_credits.json"
                
                # Check by email
                for username, user_data in users.items():
                    if user_data.get('email', '').lower() == identifier_lower:
                        return user_data, username, "users_credits.json"
    except Exception as e:
        print(f"Error reading users_credits.json: {e}")
    
    return None, "", ""

def update_user_password(username: str, new_password: str, source_file: str) -> bool:
    """Update user password in the appropriate JSON file AND sync credit system"""
    try:
        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        # Load the appropriate file
        with open(source_file, "r") as f:
            users = json.load(f)
        
        # Update password and last login
        if username in users:
            users[username]["password_hash"] = new_password_hash
            users[username]["last_login"] = datetime.now().isoformat()
            users[username]["password_updated_at"] = datetime.now().isoformat()
            
            # Save back to file
            with open(source_file, "w") as f:
                json.dump(users, f, indent=4)
            
            print(f"✅ Password updated for {username} in {source_file}")
            
            # 🔧 CRITICAL FIX: Also update credit system
            try:
                # Force credit system reload first
                credit_system.reload_user_data()
                print("✅ Credit system reloaded after password update")
                
                # Update password in credit system directly
                if hasattr(credit_system, 'update_user_password'):
                    credit_system.update_user_password(username, new_password)
                    print("✅ Credit system password updated via method")
                else:
                    # Manual update if method doesn't exist
                    if username in credit_system.users:
                        credit_system.users[username]["password_hash"] = new_password_hash
                        credit_system.users[username]["password_updated_at"] = datetime.now().isoformat()
                        credit_system.save_data()
                        print("✅ Credit system password updated manually")
                
            except Exception as e:
                print(f"⚠️ Credit system sync failed (non-critical): {e}")
                # Don't fail the whole operation if credit system sync fails
            
            return True
        else:
            print(f"❌ User {username} not found in {source_file}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating password: {e}")
        return False

def verify_current_password(username: str, current_password: str, source_file: str) -> bool:
    """Verify user's current password"""
    try:
        with open(source_file, "r") as f:
            users = json.load(f)
        
        if username in users:
            stored_hash = users[username].get("password_hash", "")
            current_hash = hash_password(current_password)
            return stored_hash == current_hash
        
        return False
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False

def create_reset_token(username: str, email: str) -> str:
    """Create a password reset token"""
    token = generate_reset_token()
    
    # Store token with expiration (24 hours)
    PASSWORD_RESET_TOKENS[token] = {
        "username": username,
        "email": email,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=24),
        "used": False
    }
    
    return token

def validate_reset_token(token: str) -> Tuple[bool, str, str]:
    """Validate a password reset token"""
    if token not in PASSWORD_RESET_TOKENS:
        return False, "", ""
    
    token_data = PASSWORD_RESET_TOKENS[token]
    
    # Check if token is expired
    if datetime.now() > token_data["expires_at"]:
        return False, "", ""
    
    # Check if token was already used
    if token_data["used"]:
        return False, "", ""
    
    return True, token_data["username"], token_data["email"]

def mark_token_as_used(token: str):
    """Mark a reset token as used"""
    if token in PASSWORD_RESET_TOKENS:
        PASSWORD_RESET_TOKENS[token]["used"] = True

def show_forgot_password_form():
    """Display forgot password form"""
    st.markdown("### 🔐 Forgot Password")
    st.markdown("Enter your username or email to reset your password")
    
    with st.form("forgot_password_form"):
        identifier = st.text_input(
            "👤 Username or Email",
            placeholder="Enter your username or email address",
            help="We'll send you a password reset link"
        )
        
        if st.form_submit_button("🔐 Reset Password", type="primary", use_container_width=True):
            if not identifier:
                st.error("❌ Please enter your username or email")
                return
            
            # Find user in both files
            user_data, username, source_file = load_user_from_both_files(identifier)
            
            if not user_data:
                st.error("❌ No account found with that username or email")
                st.info("💡 Double-check your spelling or create a new account")
                return
            
            email = user_data.get('email', '')
            if not email:
                st.error("❌ No email address associated with this account")
                return
            
            # Generate reset token
            reset_token = create_reset_token(username, email)
            
            # In production, you would send an email here
            # For demo purposes, we'll show the reset link
            st.success("✅ Password reset requested!")
            st.info(f"📧 Reset instructions would be sent to: {email}")
            
            # Show reset token for demo (in production, this would be in the email)
            st.markdown("---")
            st.warning("🔧 **Demo Mode:** Use this reset code:")
            st.code(reset_token)
            st.info("💡 Copy this code and use it in the password reset form below")
            
            # Store token in session state for easy access
            st.session_state.demo_reset_token = reset_token
            st.session_state.demo_reset_username = username
            st.session_state.demo_reset_email = email
        
        if st.form_submit_button("🔙 Back to Login", use_container_width=True):
            st.session_state.show_forgot_password = False
            st.session_state.show_login = True
            st.rerun()

def show_password_reset_form():
    """Display password reset form with token"""
    st.markdown("### 🔑 Reset Your Password")
    st.markdown("Enter your reset code and new password")
    
    with st.form("password_reset_form"):
        reset_token = st.text_input(
            "🎫 Reset Code",
            placeholder="Enter the reset code from your email",
            help="Check your email for the password reset code"
        )
        
        # Auto-fill token if we have it from demo
        if 'demo_reset_token' in st.session_state and not reset_token:
            reset_token = st.text_input(
                "🎫 Reset Code",
                value=st.session_state.demo_reset_token,
                help="Demo code auto-filled"
            )
        
        new_password = st.text_input(
            "🔒 New Password",
            type="password",
            placeholder="Enter your new password",
            help="Choose a strong password"
        )
        
        confirm_password = st.text_input(
            "🔒 Confirm New Password",
            type="password",
            placeholder="Confirm your new password"
        )
        
        # Show password requirements
        if new_password:
            password_valid, password_msg, password_state, password_reqs = validate_password_realtime(new_password)
            
            if password_valid:
                st.success("✅ Strong password")
            else:
                st.error(password_msg)
            
            # Show requirements checklist
            create_password_requirements_checklist(password_reqs)
        
        # Password confirmation check
        if new_password and confirm_password:
            if new_password == confirm_password:
                st.success("✅ Passwords match")
                passwords_match = True
            else:
                st.error("❌ Passwords don't match")
                passwords_match = False
        else:
            passwords_match = False
        
        # Submit button
        can_reset = bool(reset_token and new_password and confirm_password and passwords_match)
        
        if st.form_submit_button(
            "🔑 Reset Password" if can_reset else "Complete All Fields",
            type="primary" if can_reset else "secondary",
            disabled=not can_reset,
            use_container_width=True
        ):
            if not can_reset:
                st.error("❌ Please complete all fields correctly")
                return
            
            # Validate reset token
            token_valid, token_username, token_email = validate_reset_token(reset_token)
            
            if not token_valid:
                st.error("❌ Invalid or expired reset code")
                st.info("💡 Request a new password reset if your code expired")
                return
            
            # Validate new password
            password_valid, password_msg, password_state, password_reqs = validate_password_realtime(new_password)
            if not password_valid:
                st.error(f"❌ {password_msg}")
                return
            
            # Find user and update password
            user_data, username, source_file = load_user_from_both_files(token_username)
            
            if not user_data:
                st.error("❌ User account not found")
                return
            
            # Update password
            if update_user_password(username, new_password, source_file):
                # Mark token as used
                mark_token_as_used(reset_token)
                
                # Clear demo session state
                for key in ['demo_reset_token', 'demo_reset_username', 'demo_reset_email']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.success("✅ Password reset successfully!")
                st.info("🔑 You can now sign in with your new password")
                
                # Auto-redirect to login
                time.sleep(2)
                st.session_state.show_password_reset = False
                st.session_state.show_login = True
                st.rerun()
            else:
                st.error("❌ Failed to update password. Please try again.")
        
        if st.form_submit_button("🔙 Back to Login", use_container_width=True):
            st.session_state.show_password_reset = False
            st.session_state.show_login = True
            st.rerun()

def show_update_password_form():
    """UPDATED: Update password form for logged-in users with credit system sync"""
    if not st.session_state.get('authenticated', False):
        st.error("❌ You must be logged in to change your password")
        return
    
    username = st.session_state.get('username')
    if not username:
        st.error("❌ User session not found")
        return
    
    st.markdown("### 🔐 Update Password")
    st.markdown("Change your account password")
    
    # Find user in both files to determine source
    user_data, found_username, source_file = load_user_from_both_files(username)
    
    if not user_data:
        st.error("❌ User account not found")
        return
    
    with st.form("update_password_form_v2"):
        current_password = st.text_input(
            "🔒 Current Password",
            type="password",
            placeholder="Enter your current password",
            help="We need to verify your current password"
        )
        
        new_password = st.text_input(
            "🔒 New Password",
            type="password",
            placeholder="Enter your new password",
            help="Choose a strong password"
        )
        
        confirm_password = st.text_input(
            "🔒 Confirm New Password",
            type="password",
            placeholder="Confirm your new password"
        )
        
        # Validate current password
        if current_password:
            current_valid = verify_current_password(username, current_password, source_file)
            if current_valid:
                st.success("✅ Current password verified")
            else:
                st.error("❌ Current password is incorrect")
        else:
            current_valid = False
        
        # Validate new password
        if new_password:
            password_valid, password_msg, password_state, password_reqs = validate_password_realtime(new_password)
            
            if password_valid:
                st.success("✅ Strong new password")
            else:
                st.error(password_msg)
            
            # Show requirements checklist
            create_password_requirements_checklist(password_reqs)
        else:
            password_valid = False
        
        # Password confirmation check
        if new_password and confirm_password:
            if new_password == confirm_password:
                st.success("✅ Passwords match")
                passwords_match = True
            else:
                st.error("❌ Passwords don't match")
                passwords_match = False
        else:
            passwords_match = False
        
        # Check if new password is different from current
        if current_password and new_password and current_password == new_password:
            st.warning("⚠️ New password must be different from current password")
            password_different = False
        else:
            password_different = True
        
        # Submit button
        can_update = (current_valid and password_valid and passwords_match and password_different)
        
        if st.form_submit_button(
            "🔐 Update Password" if can_update else "Complete All Requirements",
            type="primary" if can_update else "secondary",
            disabled=not can_update,
            use_container_width=True
        ):
            if not can_update:
                st.error("❌ Please complete all requirements correctly")
                return
            
            # 🔧 USE THE ENHANCED UPDATE FUNCTION
            if update_user_password(username, new_password, source_file):
                st.success("✅ Password updated successfully!")
                st.info("🔑 Your password has been changed")
                
                # 🔧 TEST THE NEW PASSWORD IMMEDIATELY
                st.markdown("**🧪 Testing Your New Password:**")
                try:
                    test_success, test_message = simple_auth.login_user(username, new_password)
                    if test_success:
                        st.success(f"✅ Password change verified: {test_message}")
                        st.info("🎉 Your new password is working correctly!")
                    else:
                        st.warning(f"⚠️ Verification: {test_message}")
                        st.info("💡 Password was updated, but please test logging in again")
                except Exception as e:
                    st.info("💡 Password updated successfully")
                
                # Log the update
                try:
                    # Add transaction record if using credits system
                    if source_file == "users_credits.json":
                        with open(source_file, "r") as f:
                            users = json.load(f)
                        
                        if username in users:
                            if "transactions" not in users[username]:
                                users[username]["transactions"] = []
                            
                            users[username]["transactions"].append({
                                "type": "password_update",
                                "timestamp": datetime.now().isoformat(),
                                "source": "user_initiated"
                            })
                            
                            with open(source_file, "w") as f:
                                json.dump(users, f, indent=4)
                except Exception as e:
                    print(f"Warning: Could not log password update: {e}")
                
                time.sleep(2)
                st.rerun()

def show_password_management_menu():
    """Show password management options in settings"""
    st.markdown("### 🔐 Password Management")
    
    if st.session_state.get('authenticated', False):
        # Logged-in user options
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔐 Change Password", use_container_width=True):
                st.session_state.show_update_password = True
                st.rerun()
        
        with col2:
            if st.button("🔑 Password Security Tips", use_container_width=True):
                st.session_state.show_password_tips = True
                st.rerun()
        
        # Show update password form if requested
        if st.session_state.get('show_update_password', False):
            st.markdown("---")
            show_update_password_form()
            
            if st.button("❌ Cancel", key="cancel_update_password"):
                st.session_state.show_update_password = False
                st.rerun()
        
        # Show password tips if requested
        if st.session_state.get('show_password_tips', False):
            show_password_security_tips()
            
            if st.button("❌ Close Tips", key="close_password_tips"):
                st.session_state.show_password_tips = False
                st.rerun()
    
    else:
        # Non-logged-in user options
        st.info("🔐 Sign in to access password management features")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔐 Forgot Password", use_container_width=True):
                st.session_state.show_forgot_password = True
                st.rerun()
        
        with col2:
            if st.button("🔑 Reset Password", use_container_width=True):
                st.session_state.show_password_reset = True
                st.rerun()

def show_password_security_tips():
    """Display password security tips"""
    st.markdown("---")
    st.markdown("### 🛡️ Password Security Tips")
    
    tips = [
        "🔐 **Use a unique password** for each account",
        "📝 **Use a password manager** to generate and store strong passwords",
        "🔄 **Change passwords regularly** especially if you suspect compromise", 
        "🚫 **Never share your password** with anyone",
        "📧 **Be wary of phishing emails** asking for your password",
        "🔒 **Enable two-factor authentication** when available",
        "💻 **Don't save passwords** on shared or public computers",
        "👀 **Check for breaches** using services like HaveIBeenPwned"
    ]
    
    for tip in tips:
        st.markdown(f"- {tip}")
    
    st.markdown("---")
    st.markdown("### 🎯 Strong Password Examples:")
    
    st.code("MySecure2024Password!")
    st.code("Coffee&Sunshine123#")
    st.code("Blue$Sky789Mountain")
    
    st.info("💡 **Pro Tip:** Use a memorable phrase with numbers and symbols")

class IntegratedPasswordReset:
    """Password reset system using your existing email infrastructure"""
    
    def __init__(self):
        self.db_file = "password_reset_tokens.db"
        self.rate_limit_file = "rate_limits.json"
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        self._init_database()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key"""
        key_file = "token_encryption.key"
        
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            print("✅ Generated new encryption key for tokens")
            return key
    
    def _init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reset_tokens (
                    token_hash TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    ip_address TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    identifier TEXT PRIMARY KEY,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TIMESTAMP,
                    blocked_until TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Password reset database initialized")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
    
    def _hash_token(self, token: str) -> str:
        """Create secure hash of token"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _check_rate_limit(self, email: str) -> Tuple[bool, str]:
        """Check if email is rate limited"""
        try:
            # Load rate limits from JSON file
            rate_limits = {}
            if os.path.exists(self.rate_limit_file):
                with open(self.rate_limit_file, "r") as f:
                    rate_limits = json.load(f)
            
            now = datetime.now()
            email_lower = email.lower()
            
            if email_lower in rate_limits:
                data = rate_limits[email_lower]
                last_attempt = datetime.fromisoformat(data.get('last_attempt', now.isoformat()))
                attempts = data.get('attempts', 0)
                blocked_until = data.get('blocked_until')
                
                # Check if still blocked
                if blocked_until:
                    blocked_until_dt = datetime.fromisoformat(blocked_until)
                    if blocked_until_dt > now:
                        remaining = int((blocked_until_dt - now).total_seconds() / 60)
                        return False, f"Rate limited. Try again in {remaining} minutes."
                
                # Reset attempts if more than 1 hour passed
                if (now - last_attempt).total_seconds() > 3600:
                    attempts = 0
                
                # Check attempts limit (5 per hour)
                if attempts >= 5:
                    blocked_until = now + timedelta(hours=1)
                    rate_limits[email_lower] = {
                        'attempts': attempts + 1,
                        'last_attempt': now.isoformat(),
                        'blocked_until': blocked_until.isoformat()
                    }
                    
                    with open(self.rate_limit_file, "w") as f:
                        json.dump(rate_limits, f, indent=2)
                    
                    return False, "Too many attempts. Blocked for 1 hour."
            
            return True, "OK"
            
        except Exception as e:
            print(f"Rate limit check error: {e}")
            return True, "OK"  # Allow on error
    
    def _update_rate_limit(self, email: str):
        """Update rate limit counter"""
        try:
            # Load existing rate limits
            rate_limits = {}
            if os.path.exists(self.rate_limit_file):
                with open(self.rate_limit_file, "r") as f:
                    rate_limits = json.load(f)
            
            email_lower = email.lower()
            now = datetime.now()
            
            if email_lower in rate_limits:
                rate_limits[email_lower]['attempts'] = rate_limits[email_lower].get('attempts', 0) + 1
                rate_limits[email_lower]['last_attempt'] = now.isoformat()
            else:
                rate_limits[email_lower] = {
                    'attempts': 1,
                    'last_attempt': now.isoformat()
                }
            
            with open(self.rate_limit_file, "w") as f:
                json.dump(rate_limits, f, indent=2)
                
        except Exception as e:
            print(f"Rate limit update error: {e}")
    
    def create_reset_token(self, username: str, email: str) -> Tuple[bool, str, str]:
        """Create password reset token"""
        try:
            # Check rate limit
            rate_ok, rate_msg = self._check_rate_limit(email)
            if not rate_ok:
                return False, rate_msg, ""
            
            # Generate secure token (shorter for easier typing)
            token = secrets.token_hex(8).upper()  # 16 characters, easy to type
            token_hash = self._hash_token(token)
            
            # Store in database
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            now = datetime.now()
            expires_at = now + timedelta(hours=1)  # 1 hour expiry
            
            cursor.execute('''
                INSERT INTO reset_tokens 
                (token_hash, username, email, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                token_hash, username, email, 
                now.isoformat(), expires_at.isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            # Update rate limit
            self._update_rate_limit(email)
            
            print(f"✅ Reset token created for {username} ({email})")
            return True, "Reset token created successfully", token
            
        except Exception as e:
            print(f"❌ Token creation failed: {e}")
            return False, "Failed to create reset token", ""
    
    def validate_token(self, token: str) -> Tuple[bool, str, str]:
        """Validate password reset token"""
        try:
            token_hash = self._hash_token(token)
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, email, expires_at, used 
                FROM reset_tokens 
                WHERE token_hash = ?
            ''', (token_hash,))
            
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return False, "", ""
            
            username, email, expires_at, used = result
            expires_at = datetime.fromisoformat(expires_at)
            
            # Check if expired
            if datetime.now() > expires_at:
                conn.close()
                return False, "", ""
            
            # Check if already used
            if used:
                conn.close()
                return False, "", ""
            
            conn.close()
            return True, username, email
            
        except Exception as e:
            print(f"❌ Token validation failed: {e}")
            return False, "", ""
    
    def mark_token_used(self, token: str) -> bool:
        """Mark token as used"""
        try:
            token_hash = self._hash_token(token)
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE reset_tokens SET used = TRUE WHERE token_hash = ?',
                (token_hash,)
            )
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
            
        except Exception as e:
            print(f"❌ Failed to mark token as used: {e}")
            return False

def send_password_reset_email(user_email: str, username: str, reset_token: str) -> bool:
    """Send password reset email using your existing email system"""
    try:
        msg = EmailMessage()
        msg["Subject"] = f"🔐 Password Reset - Lead Generator Empire"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = user_email
        
        # Create email body in your style
        email_body = f"""
Hi {username}!

We received a request to reset your Lead Generator Empire password.

🔑 **Your Reset Code:** {reset_token}

⏰ **Important:**
• This code expires in 1 hour
• Can only be used once
• Never share this code with anyone

🔧 **To Reset Your Password:**
1. Go back to the Lead Generator Empire login page
2. Click "Reset Password" 
3. Enter this code: {reset_token}
4. Create your new password

If you didn't request this password reset, please ignore this email or contact support.

Best regards,
Lead Generator Empire Team
🚀 Conquering 8 platforms with 21.3 leads/minute!

---
Need help? Reply to this email or contact support.
        """.strip()
        
        msg.set_content(email_body)
        
        # Send using your existing SMTP setup
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        
        print(f"✅ Password reset email sent to {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Password reset email failed: {e}")
        return False

# Initialize the system
password_reset_system = IntegratedPasswordReset()

def integrated_show_forgot_password_form():
    """Forgot password form using your email system"""
    st.markdown("### 🔐 Reset Your Password")
    st.markdown("Enter your email address to receive a password reset code")
    
    with st.form("integrated_forgot_password_form"):
        identifier = st.text_input(
            "📧 Email Address", 
            placeholder="Enter your email address",
            help="We'll send a reset code to your email"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.form_submit_button("📧 Send Reset Code", type="primary", use_container_width=True):
                if not identifier:
                    st.error("❌ Please enter your email address")
                    return
                
                if '@' not in identifier:
                    st.error("❌ Please enter a valid email address")
                    return
                
                # Find user in your system
                user_data, username, source_file = load_user_from_both_files(identifier)
                
                if not user_data:
                    # For security, don't reveal if email exists
                    st.success("✅ If an account with this email exists, a reset code has been sent")
                    st.info("📧 Check your email for the reset code")
                    return
                
                email = user_data.get('email', '')
                if not email:
                    st.success("✅ If an account with this email exists, a reset code has been sent")
                    return
                
                # Create reset token
                success, message, token = password_reset_system.create_reset_token(username, email)
                
                if not success:
                    st.error(f"❌ {message}")
                    return
                
                # Send email using your system
                email_success = send_password_reset_email(email, username, token)
                
                if email_success:
                    st.success("✅ Password reset code sent to your email!")
                    st.info("📧 Check your email for the reset code")
                    
                    # Switch to reset form
                    st.session_state.show_forgot_password = False
                    st.session_state.show_password_reset = True
                    st.rerun()
                else:
                    st.error("❌ Failed to send email. Please try again.")
        
        with col2:
            if st.form_submit_button("🔙 Back to Login", use_container_width=True):
                st.session_state.show_forgot_password = False
                st.session_state.show_login = True
                st.rerun()

def integrated_show_password_reset_form():
    """UPDATED: Password reset form with automatic credit system sync"""
    st.markdown("### 🔑 Reset Your Password")
    st.markdown("Enter the reset code from your email and your new password")
    
    # Use direct inputs (not st.form) since that works
    reset_token = st.text_input(
        "🎫 Reset Code",
        placeholder="Enter the code from your email",
        help="Check your email for the reset code",
        key="reset_token_input_v2"
    )
    
    new_password = st.text_input(
        "🔒 New Password",
        type="password",
        placeholder="Enter your new password",
        help="Choose a strong password",
        key="new_password_input_v2"
    )
    
    confirm_password = st.text_input(
        "🔒 Confirm New Password", 
        type="password",
        placeholder="Confirm your new password",
        key="confirm_password_input_v2"
    )
    
    # Password validation
    password_valid = False
    passwords_match = False
    
    if new_password:
        password_valid, password_msg, password_state, password_reqs = validate_password_realtime(new_password)
        
        if password_valid:
            st.success("✅ Strong password")
        else:
            st.error(password_msg)
        
        # Show password requirements checklist
        st.markdown("**Password Requirements:**")
        
        # Requirements display
        req_items = [
            ("Length (8+)", len(new_password) >= 8),
            ("Uppercase", any(c.isupper() for c in new_password)),
            ("Lowercase", any(c.islower() for c in new_password)),
            ("Number", any(c.isdigit() for c in new_password)),
            ("Special char", any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in new_password))
        ]
        
        req_cols = st.columns(len(req_items))
        for i, (req_name, req_met) in enumerate(req_items):
            with req_cols[i]:
                if req_met:
                    st.markdown(f'<div style="color: green;">✅ {req_name}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="color: #888;">○ {req_name}</div>', unsafe_allow_html=True)
    
    # Password confirmation
    if new_password and confirm_password:
        passwords_match = new_password == confirm_password
        if passwords_match:
            st.success("✅ Passwords match")
        else:
            st.error("❌ Passwords don't match")
    
    # Button logic
    reset_token_valid = bool(reset_token and len(reset_token.strip()) > 0)
    can_reset = reset_token_valid and password_valid and passwords_match
    
    # Buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if can_reset:
            if st.button("🔑 Reset Password", type="primary", use_container_width=True, key="reset_password_btn_v2"):
                # Validate token
                try:
                    token_valid, token_username, token_email = password_reset_system.validate_token(reset_token.upper().strip())
                    
                    if not token_valid:
                        st.error("❌ Invalid or expired reset code")
                        st.info("💡 Request a new reset code if this one expired")
                        return
                    
                    # Update password with ENHANCED sync
                    user_data, username, source_file = load_user_from_both_files(token_username)
                    
                    if not user_data:
                        st.error("❌ Account not found")
                        return
                    
                    # 🔧 USE THE ENHANCED UPDATE FUNCTION
                    if update_user_password(username, new_password, source_file):
                        # Mark token as used
                        password_reset_system.mark_token_used(reset_token.upper().strip())
                        
                        # 🔧 ADDITIONAL SYNC: Update both JSON files to be safe
                        try:
                            new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                            
                            # Update users.json
                            if os.path.exists("users.json"):
                                with open("users.json", "r") as f:
                                    users_json = json.load(f)
                                if username in users_json:
                                    users_json[username]["password_hash"] = new_password_hash
                                    users_json[username]["password_updated_at"] = datetime.now().isoformat()
                                    with open("users.json", "w") as f:
                                        json.dump(users_json, f, indent=4)
                            
                            # Update users_credits.json
                            if os.path.exists("users_credits.json"):
                                with open("users_credits.json", "r") as f:
                                    users_credits = json.load(f)
                                if username in users_credits:
                                    users_credits[username]["password_hash"] = new_password_hash
                                    users_credits[username]["password_updated_at"] = datetime.now().isoformat()
                                    with open("users_credits.json", "w") as f:
                                        json.dump(users_credits, f, indent=4)
                            
                            print("✅ Password updated in both JSON files")
                            
                        except Exception as e:
                            print(f"⚠️ Additional sync warning: {e}")
                        
                        st.success("✅ Password reset successfully!")
                        st.balloons()
                        st.info("🔑 You can now sign in with your new password")
                        
                        # 🔧 TEST LOGIN IMMEDIATELY
                        st.markdown("**🧪 Testing Your New Password:**")
                        try:
                            test_success, test_message = simple_auth.login_user(username, new_password)
                            if test_success:
                                st.success(f"✅ Login test successful: {test_message}")
                                st.info("🎉 Your new password is working correctly!")
                            else:
                                st.warning(f"⚠️ Login test: {test_message}")
                                st.info("💡 Try logging in manually - the password was updated successfully")
                        except Exception as e:
                            st.info("💡 Password updated successfully - try logging in manually")
                        
                        # Clear the input fields
                        if 'reset_token_input_v2' in st.session_state:
                            del st.session_state['reset_token_input_v2']
                        if 'new_password_input_v2' in st.session_state:
                            del st.session_state['new_password_input_v2']
                        if 'confirm_password_input_v2' in st.session_state:
                            del st.session_state['confirm_password_input_v2']
                        
                        # Redirect to login
                        time.sleep(2)
                        st.session_state.show_password_reset = False
                        st.session_state.show_login = True
                        st.rerun()
                    else:
                        st.error("❌ Failed to update password. Please try again.")
                        
                except Exception as e:
                    st.error(f"❌ Reset error: {e}")
        else:
            st.button("❌ Complete All Requirements", disabled=True, use_container_width=True, key="disabled_reset_btn_v2")
            
            # Show what's missing
            missing = []
            if not reset_token_valid:
                missing.append("Reset code")
            if not password_valid:
                missing.append("Valid password")
            if not passwords_match:
                missing.append("Password confirmation")
            
            if missing:
                st.caption(f"Missing: {', '.join(missing)}")
    
    with col2:
        if st.button("🔙 Back to Login", use_container_width=True, key="back_to_login_btn_v2"):
            st.session_state.show_password_reset = False
            st.session_state.show_login = True
            st.rerun()


def test_integrated_email_system():
    """Test function for your email system"""
    st.subheader("🧪 Test Password Reset Email")
    
    test_email = st.text_input("Test email address:")
    test_username = st.text_input("Test username:", value="TestUser")
    
    if st.button("📧 Send Test Reset Email"):
        if test_email and test_username:
            # Create test token
            success, message, token = password_reset_system.create_reset_token(test_username, test_email)
            
            if success:
                # Send test email
                email_success = send_password_reset_email(test_email, test_username, token)
                
                if email_success:
                    st.success("✅ Test email sent successfully!")
                    st.info(f"📧 Reset code: {token}")
                else:
                    st.error("❌ Email sending failed")
            else:
                st.error(f"❌ Token creation failed: {message}")
        else:
            st.error("❌ Please enter both email and username")

# Cleanup function (run periodically)
def cleanup_expired_tokens():
    """Clean up expired tokens"""
    try:
        conn = sqlite3.connect(password_reset_system.db_file)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        # Delete expired tokens
        cursor.execute(
            'DELETE FROM reset_tokens WHERE expires_at < ? OR used = TRUE',
            (now.isoformat(),)
        )
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            print(f"✅ Cleaned up {deleted} expired tokens")
            
    except Exception as e:
        print(f"❌ Token cleanup failed: {e}")

# Handle authentication modals - SIMPLE VERSION
def show_auth_section_if_needed():
    """Only show auth section when requested and user not authenticated"""
    
    if not simple_auth.is_authenticated():
        # Check for password management modals
        if st.session_state.get('show_forgot_password', False):
            integrated_show_forgot_password_form()
            st.stop()
        
        if st.session_state.get('show_password_reset', False):
            integrated_show_password_reset_form()
            st.stop()
        
        # Existing login/register logic
        show_login = st.session_state.get('show_login', False)
        show_register = st.session_state.get('show_register', False)
        
        if show_login or show_register:
            auth_container = st.container()
            
            with auth_container:
                # Add close button at top
                col1, col2, col3 = st.columns([1, 2, 1])
                with col3:
                    if st.button("❌ Close", key="close_auth_forms"):
                        st.session_state.show_login = False
                        st.session_state.show_register = False
                        st.rerun()
                
                st.markdown("---")
                
                if show_login:
                    show_enhanced_login_with_forgot_password()  # ← Updated
                elif show_register:
                    show_realtime_registration()  # ← Updated
                
                st.markdown("---")
                st.stop()


