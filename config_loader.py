#!/usr/bin/env python3
"""
Unified Config Loader for Lead Generator Empire
Manages all platform configurations from a single config.json file
"""

import json
import os
from typing import Dict, Any, Optional
from enhanced_config_loader import patch_stripe_credentials

class ConfigLoader:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self._config = None
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load the unified configuration file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            # 🔧 PRESERVE STRIPE CONFIG: Always ensure Stripe config exists
            self._ensure_stripe_config()
            
            return self._config
        except FileNotFoundError:
            print(f"⚠️ {self.config_file} not found, creating default config")
            self._config = self._create_default_config()
            self.save_config()
            return self._config
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {self.config_file}: {e}")
            return {}
        except Exception as e:
            print(f"❌ Error loading {self.config_file}: {e}")
            return {}
    
    def _ensure_stripe_config(self):
        """Ensure Stripe configuration exists and is properly structured"""
        if not self._config:
            return
        
        # Check if Stripe config is missing or incomplete
        if 'stripe' not in self._config:
            print("🔧 Adding missing Stripe configuration...")
            self._config['stripe'] = self._get_default_stripe_config()
            self.save_config()
        else:
            # Ensure all required Stripe fields exist
            stripe_config = self._config['stripe']
            default_stripe = self._get_default_stripe_config()
            
            updated = False
            for key, value in default_stripe.items():
                if key not in stripe_config:
                    stripe_config[key] = value
                    updated = True
            
            if updated:
                print("🔧 Updated Stripe configuration with missing fields...")
                self.save_config()
    
    def _get_default_stripe_config(self) -> Dict[str, Any]:
        """Get default Stripe configuration"""
        return {
            "enabled": True,
            "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
            "publishable_key": os.getenv("PUBLISHABLE_KEY", ""),
            "webhook_secret": "whsec_your_webhook_secret_here",
            "currency": "usd",
            "success_url": "https://leadgeneratorempire.com/success",
            "cancel_url": "https://leadgeneratorempire.com/cancel",
            "test_mode": True
        }
    
    def get_stripe_config(self) -> Dict[str, Any]:
        """Get Stripe configuration"""
        if not self._config:
            self.load_config()
        
        return self._config.get('stripe', self._get_default_stripe_config())
    
    def update_stripe_config(self, stripe_config: Dict[str, Any]) -> bool:
        """Update Stripe configuration"""
        try:
            if not self._config:
                self.load_config()
            
            self._config['stripe'] = stripe_config
            self.save_config()
            return True
        except Exception as e:
            print(f"❌ Error updating Stripe config: {e}")
            return False
    
    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """Get configuration for a specific platform - supports both config formats"""
        if not self._config:
            self.load_config()
        
        # Check if this is the client config format (has global_settings)
        if 'global_settings' in self._config:
            # Handle client config format
            global_settings = self._config.get('global_settings', {})
            user_settings = self._config.get('user_settings', {})
            
            # Create platform config by combining global_settings with platform defaults
            platform_config = {
                # Copy all fields from global_settings
                **global_settings,
                
                # Add platform name
                'platform': platform.lower(),
                
                # Add user-specific fields
                'username': user_settings.get('username', 'user'),
            }
            
            # Add platform-specific defaults if needed
            platform_defaults = self._get_platform_defaults(platform)
            
            # Merge defaults (global_settings takes priority)
            for key, value in platform_defaults.items():
                if key not in platform_config:
                    platform_config[key] = value
            
            return platform_config
        
        else:
            # Handle original config format (has 'global' and 'platforms')
            global_config = self._config.get('global', {})
            platform_config = self._config.get('platforms', {}).get(platform.lower(), {})
            
            # Merge global and platform settings (platform settings override global)
            merged_config = {**global_config, **platform_config}
            merged_config['platform'] = platform.lower()
            
            return merged_config

    def _handle_client_config_format(self, platform: str) -> Dict[str, Any]:
        """Handle the newer client config format"""
        
        # Get global settings
        global_settings = self._config.get('global_settings', {})
        user_settings = self._config.get('user_settings', {})
        
        # Create platform config with defaults
        platform_config = {
            # Core settings from global_settings
            'search_term': global_settings.get('search_term', 'fitness coach'),
            'max_scrolls': global_settings.get('max_scrolls', 10),
            'delay_between_scrolls': global_settings.get('delay_between_scrolls', 3),
            'extraction_timeout': global_settings.get('extraction_timeout', 45),
            
            # Platform-specific output file
            'lead_output_file': self._get_client_output_file(platform, user_settings.get('username', 'user')),
            'backup_output_file': self._get_client_backup_file(platform, user_settings.get('username', 'user')),
            
            # Platform defaults
            'enable_screenshots': False,
            'location_csv': 'locations.csv',
            'platform': platform.lower()
        }
        
        # Add platform-specific defaults
        platform_defaults = self._get_platform_defaults(platform)
        platform_config.update(platform_defaults)
        
        return platform_config

    def _handle_original_config_format(self, platform: str) -> Dict[str, Any]:
        """Handle the original config format"""
        
        # Get global settings
        global_config = self._config.get('global', {})
        
        # Get platform-specific settings
        platform_config = self._config.get('platforms', {}).get(platform.lower(), {})
        
        # Merge global and platform settings (platform settings override global)
        merged_config = {**global_config, **platform_config}
        
        # Add platform name for reference
        merged_config['platform'] = platform.lower()
        
        return merged_config

    def _get_client_output_file(self, platform: str, username: str) -> str:
        """Get client-specific output file name"""
        return f"leads/{username}_{platform}_leads.csv"

    def _get_client_backup_file(self, platform: str, username: str) -> str:
        """Get client-specific backup file name"""
        return f"leads/{username}_{platform}_leads_backup.csv"

    def _get_platform_defaults(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific default settings"""
        
        defaults = {
            'twitter': {
                'delay_between_scrolls': 2,
                'extraction_timeout': 60,
                'enable_screenshots': False,
                'target_leads_10k': 2000
            },
            'facebook': {
                'max_pages': 150,
                'delay_min': 3,
                'delay_max': 5,
                'enable_screenshots': False,
                'target_leads_10k': 2000
            },
            'instagram': {
                'debug_screenshots': True,
                'search_filters': {
                    'accounts_only': True,
                    'business_accounts': True,
                    'min_followers': 100
                },
                'enable_screenshots': False,
                'target_leads_10k': 1500
            },
            'youtube': {
                'search_filters': {
                    'channels_only': True,
                    'min_subscribers': 10,
                    'upload_frequency': 'active'
                },
                'enable_screenshots': False,
                'target_leads_10k': 1000
            }
        }
        
        return defaults.get(platform.lower(), {})
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration settings"""
        if not self._config:
            self.load_config()
        return self._config.get('global', {})
    
    def get_dm_templates(self) -> list:
        """Get DM template rules"""
        if not self._config:
            self.load_config()
        return self._config.get('dm_template_rules', [])
    
    def get_excluded_accounts(self, platform: str) -> list:
        """Get list of excluded accounts - supports both config formats"""
        if not self._config:
            self.load_config()
        
        # Check if this is the client config format
        if 'excluded_accounts' in self._config and 'accounts' in self._config['excluded_accounts']:
            # Handle client config format
            excluded_config = self._config.get('excluded_accounts', {})
            
            if not excluded_config.get('enabled', True):
                return []
            
            # Get platform-specific exclusions
            platform_exclusions = excluded_config.get('accounts', {}).get(platform.lower(), [])
            
            # Get global exclusions
            global_exclusions = excluded_config.get('global_excludes', [])
            
            # Combine both lists and remove duplicates
            all_exclusions = list(set(platform_exclusions + global_exclusions))
            
            return all_exclusions
        else:
            # Handle original config format
            platform_config = self._config.get('platforms', {}).get(platform.lower(), {})
            platform_exclusions = platform_config.get('excluded_accounts', [])
            
            global_exclusions = self._config.get('global', {}).get('excluded_accounts', [])
            
            all_exclusions = list(set(platform_exclusions + global_exclusions))
            
            return all_exclusions

    def add_excluded_account(self, platform: str, username: str) -> bool:
        """Add an account to the exclusion list - supports both config formats"""
        try:
            if not self._config:
                self.load_config()
            
            # Check if this is the newer client config format
            if 'excluded_accounts' in self._config and 'accounts' in self._config['excluded_accounts']:
                # Handle newer client config format
                if 'excluded_accounts' not in self._config:
                    self._config['excluded_accounts'] = {
                        'enabled': True,
                        'accounts': {},
                        'global_excludes': []
                    }
                
                if 'accounts' not in self._config['excluded_accounts']:
                    self._config['excluded_accounts']['accounts'] = {}
                
                if platform.lower() not in self._config['excluded_accounts']['accounts']:
                    self._config['excluded_accounts']['accounts'][platform.lower()] = []
                
                excluded_list = self._config['excluded_accounts']['accounts'][platform.lower()]
                if username not in excluded_list:
                    excluded_list.append(username)
                    self.save_config()
                    return True
                
                return False
            else:
                # Handle original config format
                if 'platforms' not in self._config:
                    self._config['platforms'] = {}
                
                if platform.lower() not in self._config['platforms']:
                    self._config['platforms'][platform.lower()] = {}
                
                if 'excluded_accounts' not in self._config['platforms'][platform.lower()]:
                    self._config['platforms'][platform.lower()]['excluded_accounts'] = []
                
                excluded_list = self._config['platforms'][platform.lower()]['excluded_accounts']
                if username not in excluded_list:
                    excluded_list.append(username)
                    self.save_config()
                    return True
                
                return False
                
        except Exception as e:
            print(f"❌ Error adding excluded account: {e}")
            return False
    
    def remove_excluded_account(self, platform: str, username: str) -> bool:
        """Remove an account from the exclusion list"""
        try:
            if not self._config:
                self.load_config()
            
            platform_config = self._config.get('platforms', {}).get(platform.lower(), {})
            excluded_list = platform_config.get('excluded_accounts', [])
            
            if username in excluded_list:
                excluded_list.remove(username)
                self.save_config()
                return True
            
            return False  # Not in list
        except Exception as e:
            print(f"❌ Error removing excluded account: {e}")
            return False
    
    def get_usage_limits(self, plan: str = 'free') -> Dict[str, Any]:
        """Get usage limits for a specific plan"""
        if not self._config:
            self.load_config()
        return self._config.get('usage_limits', {}).get(plan.lower(), {})
    
    def get_multilingual_config(self) -> Dict[str, Any]:
        """Get multilingual configuration"""
        if not self._config:
            self.load_config()
        return self._config.get('multilingual', {})
    
    def update_global_setting(self, key: str, value: Any) -> bool:
        """Update a global setting and save to file"""
        try:
            if not self._config:
                self.load_config()
            
            if 'global' not in self._config:
                self._config['global'] = {}
            
            self._config['global'][key] = value
            self.save_config()
            return True
        except Exception as e:
            print(f"❌ Error updating global setting {key}: {e}")
            return False
    
    def update_platform_setting(self, platform: str, key: str, value: Any) -> bool:
        """Update a platform-specific setting and save to file"""
        try:
            if not self._config:
                self.load_config()
            
            if 'platforms' not in self._config:
                self._config['platforms'] = {}
            
            if platform.lower() not in self._config['platforms']:
                self._config['platforms'][platform.lower()] = {}
            
            self._config['platforms'][platform.lower()][key] = value
            self.save_config()
            return True
        except Exception as e:
            print(f"❌ Error updating {platform} setting {key}: {e}")
            return False
    
    def save_config(self) -> bool:
        """Save the current configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create a default configuration with complete Stripe setup"""
        return {
            # 🔧 STRIPE CONFIGURATION - ALWAYS INCLUDED
            "stripe": {
                "enabled": True,
                "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
                "publishable_key": "pk_test_your_publishable_key_here",
                "webhook_secret": "whsec_your_webhook_secret_here",
                "currency": "usd",
                "success_url": "https://leadgeneratorempire.com/success",
                "cancel_url": "https://leadgeneratorempire.com/cancel",
                "test_mode": True
            },
            
            
            # 🔧 PAYMENT SETTINGS
            "payment_settings": {
                "allow_test_payments": True,
                "require_email_verification": True,
                "send_receipt_emails": True,
                "auto_deliver_leads": True
            },
            
            # Legacy field for backwards compatibility
            "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY", ""),
            
            "global": {
                "search_term": "fitness coach",
                "max_scrolls": 12,
                "enable_multilingual": False,
                "default_dm": "Hi there! I love your content and would be excited to connect. Let's chat!",
                "fallback_dm": "Hey! Just came across your profile and really impressed by your work. Would love to connect!",
                "excluded_accounts": []
            },
            "platforms": {
                "twitter": {
                    "lead_output_file": "twitter_leads.csv",
                    "backup_output_file": "twitter_leads_backup.csv",
                    "location_csv": "locations.csv",
                    "max_scrolls": 12,
                    "excluded_accounts": []
                },
                "facebook": {
                    "lead_output_file": "facebook_leads.csv",
                    "backup_output_file": "facebook_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                },
                "tiktok": {
                    "lead_output_file": "tiktok_leads.csv",
                    "backup_output_file": "tiktok_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                },
                "youtube": {
                    "lead_output_file": "youtube_leads.csv",
                    "backup_output_file": "youtube_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                },
                "medium": {
                    "lead_output_file": "medium_leads.csv",
                    "backup_output_file": "medium_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                },
                "instagram": {
                    "lead_output_file": "instagram_leads.csv",
                    "backup_output_file": "instagram_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                },
                "reddit": {
                    "lead_output_file": "reddit_leads.csv",
                    "backup_output_file": "reddit_leads_backup.csv", 
                    "location_csv": "locations.csv",
                    "max_scrolls": 10,
                    "excluded_accounts": []
                }
            },
            "dm_template_rules": [],
            "multilingual": {
                "enabled": False
            
            }
        }
    
    def get_search_term(self) -> str:
        """Get the current search term (convenience method)"""
        return self.get_global_config().get('search_term', 'fitness coach')
    
    def update_search_term(self, search_term: str) -> bool:
        """Update the search term (convenience method)"""
        return self.update_global_setting('search_term', search_term)
    
    def get_max_scrolls(self, platform: str = None) -> int:
        """Get max scrolls for a platform (or global default)"""
        if platform:
            platform_config = self.get_platform_config(platform)
            return platform_config.get('max_scrolls', 12)
        else:
            return self.get_global_config().get('max_scrolls', 12)
    
    def print_config_summary(self):
        """Print a summary of the current configuration"""
        if not self._config:
            self.load_config()
        
        print("📋 Configuration Summary:")
        print("=" * 50)
        
        # Stripe configuration
        stripe_config = self.get_stripe_config()
        print(f"💳 Stripe Configuration:")
        print(f"  ✅ Enabled: {stripe_config.get('enabled', False)}")
        print(f"  🔑 Secret Key: {stripe_config.get('secret_key', 'Not set')[:20]}...")
        print(f"  🧪 Test Mode: {stripe_config.get('test_mode', False)}")
        
        # Global settings
        global_config = self.get_global_config()
        print(f"\n🌍 Global Settings:")
        print(f"  🔍 Search Term: {global_config.get('search_term', 'Not set')}")
        print(f"  📜 Max Scrolls: {global_config.get('max_scrolls', 'Not set')}")
        print(f"  🌍 Multilingual: {global_config.get('enable_multilingual', False)}")
        
        # Platform settings
        platforms = self._config.get('platforms', {})
        if platforms:
            print(f"\n🚀 Platform Settings:")
            for platform, config in platforms.items():
                print(f"  {platform.title()}:")
                print(f"    📜 Max Scrolls: {config.get('max_scrolls', 'Global default')}")
                print(f"    📁 Output File: {config.get('lead_output_file', 'Not set')}")

def get_config_with_env():
    """Load config.json and merge with environment variables for credentials"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        config = patch_stripe_credentials(config)
    except:
        config = {}
    
    # Override sensitive credentials with environment variables
    if "stripe" in config:
        config["stripe"]["secret_key"] = os.environ.get("STRIPE_SECRET_KEY", "")
        config["stripe"]["publishable_key"] = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
        config["stripe"]["webhook_secret"] = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    # Legacy support for direct stripe_secret_key access
    config["stripe_secret_key"] = os.environ.get("STRIPE_SECRET_KEY", "")
    
    return config

def should_exclude_account(username: str, platform: str, config_loader_instance: ConfigLoader) -> bool:
    """Check if an account should be excluded from scraping"""
    try:
        # Remove @ symbol if present
        clean_username = username.lstrip('@').lower()
        
        # Get excluded accounts for this platform
        excluded_accounts = config_loader_instance.get_excluded_accounts(platform)
        
        # Check if username is in exclusion list (case insensitive)
        excluded_accounts_lower = [acc.lstrip('@').lower() for acc in excluded_accounts]
        
        return clean_username in excluded_accounts_lower
    except Exception as e:
        print(f"⚠️ Error checking exclusion for {username}: {e}")
        return False  # Don't exclude if there's an error


# Global instance for easy importing
config_loader = ConfigLoader()

# Convenience functions for easy usage
def get_platform_config(platform: str) -> Dict[str, Any]:
    """Get configuration for a specific platform"""
    return config_loader.get_platform_config(platform)

def get_search_term() -> str:
    """Get the current search term"""
    return config_loader.get_search_term()

def get_max_scrolls(platform: str = None) -> int:
    """Get max scrolls for a platform"""
    return config_loader.get_max_scrolls(platform)

def update_search_term(search_term: str) -> bool:
    """Update the search term"""
    return config_loader.update_search_term(search_term)

# Example usage function
def main():
    """Example usage of the config loader"""
    print("🚀 Lead Generator Empire - Config Loader Test")
    
    # Print current config
    config_loader.print_config_summary()
    
    # Test getting platform configs
    print(f"\n🧪 Testing Platform Configs:")
    for platform in ['twitter', 'facebook', 'instagram', 'linkedin']:
        config = get_platform_config(platform)
        print(f"{platform.title()}: {config.get('search_term')} | {config.get('max_scrolls')} scrolls")

if __name__ == "__main__":
    main()