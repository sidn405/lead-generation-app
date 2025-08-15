# enhanced_config_loader.py
import json
import os
from datetime import datetime
from user_auth import load_json_safe

class ConfigLoader:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return load_json_safe(f)
        except FileNotFoundError:
            return self.create_default_config()
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            return self.create_default_config()
    
    def create_default_config(self):
        default_config = {
            "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
            "global_settings": {
                "search_term": "fitness coach",
                "max_scrolls": 10,
                "delay_between_scrolls": 3,
                "extraction_timeout": 45,
                "lead_output_file": "leads.csv"
            },
            "excluded_accounts": {
                "enabled": True,
                "accounts": {
                    "instagram": [],
                    "tiktok": [],
                    "facebook": [],
                    "twitter": [],
                    "youtube": [],
                    "linkedin": [],
                    "medium": [],
                    "reddit": []
                },
                "global_excludes": []
            },
            "user_settings": {
                "created_date": datetime.now().isoformat()
            }
        }
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config=None):
        if config is None:
            config = self.config
        try:
            os.makedirs(os.path.dirname(self.config_file) if os.path.dirname(self.config_file) else ".", exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_excluded_accounts(self, platform=None):
        excluded_config = self.config.get("excluded_accounts", {})
        if not excluded_config.get("enabled", True):
            return []
        
        excluded_accounts = []
        global_excludes = excluded_config.get("global_excludes", [])
        excluded_accounts.extend(global_excludes)
        
        if platform:
            platform_excludes = excluded_config.get("accounts", {}).get(platform.lower(), [])
            excluded_accounts.extend(platform_excludes)
        
        return list(set(excluded_accounts))
    
    def add_excluded_account(self, platform, username):
        if "excluded_accounts" not in self.config:
            self.config["excluded_accounts"] = {"enabled": True, "accounts": {}, "global_excludes": []}
        
        if "accounts" not in self.config["excluded_accounts"]:
            self.config["excluded_accounts"]["accounts"] = {}
        
        platform_lower = platform.lower()
        if platform_lower not in self.config["excluded_accounts"]["accounts"]:
            self.config["excluded_accounts"]["accounts"][platform_lower] = []
        
        if username not in self.config["excluded_accounts"]["accounts"][platform_lower]:
            self.config["excluded_accounts"]["accounts"][platform_lower].append(username)
            self.save_config()
            return True
        return False
    
    def remove_excluded_account(self, platform, username):
        try:
            platform_lower = platform.lower()
            accounts = self.config["excluded_accounts"]["accounts"][platform_lower]
            if username in accounts:
                accounts.remove(username)
                self.save_config()
                return True
        except (KeyError, ValueError):
            pass
        return False
    
    def add_global_exclude(self, username):
        if "excluded_accounts" not in self.config:
            self.config["excluded_accounts"] = {"enabled": True, "accounts": {}, "global_excludes": []}
        
        if "global_excludes" not in self.config["excluded_accounts"]:
            self.config["excluded_accounts"]["global_excludes"] = []
        
        if username not in self.config["excluded_accounts"]["global_excludes"]:
            self.config["excluded_accounts"]["global_excludes"].append(username)
            self.save_config()
            return True
        return False

def patch_stripe_credentials(config):
    """Add environment variables to config after loading"""
    config["stripe_secret_key"] = os.environ.get("STRIPE_SECRET_KEY", "")
    if "stripe" in config:
        config["stripe"]["secret_key"] = os.environ.get("STRIPE_SECRET_KEY", "")
        config["stripe"]["publishable_key"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    return config

def should_exclude_account(username, handle, platform, config_loader):
    excluded_accounts = config_loader.get_excluded_accounts(platform)
    if not excluded_accounts:
        return False
    
    username_lower = username.lower().strip()
    handle_lower = handle.lower().strip().lstrip('@')
    
    for excluded in excluded_accounts:
        excluded_lower = excluded.lower().strip().lstrip('@')
        if (username_lower == excluded_lower or handle_lower == excluded_lower):
            print(f"  Excluding {platform} account: {handle}")
            return True
    return False
