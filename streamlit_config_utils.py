
# streamlit_config_utils.py
import streamlit as st
from datetime import datetime
import os
import json
from enhanced_config_loader import ConfigLoader

def ensure_client_config_exists(username):
    """Ensure client config exists for user"""
    config_file = f"client_configs/client_{username}_config.json"
    
    if not os.path.exists(config_file):
        # Create config directory
        os.makedirs("client_configs", exist_ok=True)
        
        # Create default config for user
        config_loader = ConfigLoader(config_file)
        return config_loader
    
    return ConfigLoader(config_file)

def get_user_excluded_accounts(username):
    """Get excluded accounts for a specific user"""
    try:
        config_loader = ensure_client_config_exists(username)
        return config_loader.config.get("excluded_accounts", {})
    except Exception as e:
        print(f"Error getting excluded accounts: {e}")
        return {}

def save_user_social_accounts(username, social_accounts):
    """Save user's social accounts to their config"""
    try:
        config_loader = ensure_client_config_exists(username)
        
        # Add each social account as exclusion
        for platform, account in social_accounts.items():
            if account and account.strip():
                clean_account = account.strip().lstrip('@')
                config_loader.add_excluded_account(platform, clean_account)
        
        return True
    except Exception as e:
        print(f"Error saving social accounts: {e}")
        return False

def create_registration_config(username, email, social_accounts):
    """Create config during user registration"""
    try:
        config_loader = ensure_client_config_exists(username)
        
        # Update user settings
        config_loader.config["user_settings"] = {
            "username": username,
            "email": email,
            "created_date": datetime.now().isoformat(),
            "registration_complete": True
        }
        
        # Add social accounts as exclusions
        for platform, account in social_accounts.items():
            if account and account.strip():
                clean_account = account.strip().lstrip('@')
                config_loader.add_excluded_account(platform, clean_account)
        
        config_loader.save_config()
        return True
        
    except Exception as e:
        print(f"Error creating registration config: {e}")
        return False

def show_exclusion_preview(username):
    """Show preview of current exclusions"""
    try:
        config_loader = ensure_client_config_exists(username)
        excluded_accounts = config_loader.config.get("excluded_accounts", {})
        
        platform_accounts = excluded_accounts.get("accounts", {})
        global_excludes = excluded_accounts.get("global_excludes", [])
        
        # Count total exclusions
        total_excluded = sum(len(accounts) for accounts in platform_accounts.values()) + len(global_excludes)
        
        return {
            "total": total_excluded,
            "platform_accounts": platform_accounts,
            "global_excludes": global_excludes
        }
    except Exception as e:
        print(f"Error showing exclusion preview: {e}")
        return {"total": 0, "platform_accounts": {}, "global_excludes": []}

def render_social_account_input(platform_name, current_value="", key_suffix=""):
    """Render social account input field"""
    return st.text_input(
        f"{platform_name} Username",
        value=current_value,
        placeholder="yourhandle (without @)",
        help=f"Your {platform_name} username to exclude from leads",
        key=f"{platform_name.lower()}_input_{key_suffix}"
    )