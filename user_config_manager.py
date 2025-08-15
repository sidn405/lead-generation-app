"""
User Configuration Manager Module
Handles user-specific and global configuration management for Lead Generator Empire
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from json_utils import load_json_safe

# Resolve a persistent config dir (Railway or local)
def _resolve_client_config_dir() -> str:
    # Preferred: env override (set this in Railway → Variables)
    base = os.getenv("CLIENT_CONFIG_DIR")
    if base:
        os.makedirs(base, exist_ok=True)
        return base

    # Secondary: running on Railway? default to the mounted path
    if os.getenv("RAILWAY_ENVIRONMENT"):
        base = "/app/client_configs"
        os.makedirs(base, exist_ok=True)
        return base

    # Local dev fallback
    base = "client_configs"
    os.makedirs(base, exist_ok=True)
    return base

def _sanitize_username(u: str) -> str:
    return "".join(c for c in (u or "") if c.isalnum() or c in (".","-","_")).lower()

class UserConfigManager:
    """Manages user-specific configurations and syncs with global config"""
    
    def __init__(self, main_config_file: str = "config.json"):
        self.main_config_file = main_config_file
        self.client_configs_dir = os.getenv("CLIENT_CONFIG_DIR", "client_configs")
        
    
    def ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(self.client_configs_dir, exist_ok=True)
    
    def get_client_config_path(self, username: str) -> str:
        """Get path to client-specific config file"""
        safe = _sanitize_username(username)
        path = os.path.join(self.client_configs_dir, f"client_{safe}_config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path
    
    def get_users_db_path(self) -> str:
        return os.path.join(self.client_configs_dir, "users.json")

    def get_leads_dir(self) -> str:
        p = os.path.join(self.client_configs_dir, "leads_output")
        os.makedirs(p, exist_ok=True)
        return p

    
    def load_main_config(self) -> Dict[str, Any]:
        """Load main configuration file"""
        try:
            if os.path.exists(self.main_config_file):
                with open(self.main_config_file, "r") as f:
                    return load_json_safe(f)
        except Exception as e:
            print(f"Error loading main config: {e}")
        
        return self._get_default_config()
    
    def load_user_config(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Load user-specific configuration or fall back to main config"""
        if not username:
            return self._extract_search_config(self.load_main_config())
        
        try:
            client_config_path = self.get_client_config_path(username)
            
            if os.path.exists(client_config_path):
                with open(client_config_path, "r") as f:
                    client_config = load_json_safe(f)
                
                # Extract global settings
                global_settings = client_config.get("global_settings", {})
                return {
                    "search_term": global_settings.get("search_term", "crypto trader"),
                    "max_scrolls": global_settings.get("max_scrolls", 12)
                }
            else:
                # Create client config from main config
                return self.create_client_config(username)
                
        except Exception as e:
            print(f"Error loading user config for {username}: {e}")
            return self._extract_search_config(self.load_main_config())
    
    def create_client_config(self, username: str) -> Dict[str, Any]:
        """Create client-specific config from main config"""
        try:
            # Load main config for defaults
            main_config = self.load_main_config()
            search_config = self._extract_search_config(main_config)
            
            # Create client config structure
            client_config = {
                "stripe_secret_key": main_config.get("stripe_secret_key", ""),
                "global_settings": {
                    "search_term": search_config["search_term"],
                    "max_scrolls": search_config["max_scrolls"],
                    "delay_between_scrolls": 3,
                    "extraction_timeout": 45,
                    "lead_output_file": "leads.csv"
                },
                "excluded_accounts": {
                    "enabled": True,
                    "accounts": {
                        "instagram": [], "tiktok": [], "facebook": [], "twitter": [],
                        "youtube": [], "linkedin": [], "medium": [], "reddit": []
                    },
                    "global_excludes": []
                },
                "user_settings": {
                    "created_date": datetime.now().isoformat()
                }
            }
            
            # Save client config
            client_config_path = self.get_client_config_path(username)
            with open(client_config_path, "w") as f:
                json.dump(client_config, f, indent=2)
            
            print(f"✅ Created client config for {username}")
            return search_config
            
        except Exception as e:
            print(f"❌ Error creating client config for {username}: {e}")
            return self._extract_search_config(self.load_main_config())
    
    def update_user_config(self, username: Optional[str], search_term: str, max_scrolls: int) -> bool:
        """Update user-specific configuration and sync with main config"""
        success = True
        
        if username:
            # Update client config
            try:
                client_config_path = self.get_client_config_path(username)
                
                # Load existing client config or create new one
                if os.path.exists(client_config_path):
                    with open(client_config_path, "r") as f:
                        client_config = load_json_safe(f)
                else:
                    # Create new client config
                    self.create_client_config(username)
                    with open(client_config_path, "r") as f:
                        client_config = load_json_safe(f)
                
                # Update global settings
                if "global_settings" not in client_config:
                    client_config["global_settings"] = {}
                
                client_config["global_settings"]["search_term"] = search_term
                client_config["global_settings"]["max_scrolls"] = max_scrolls
                client_config["global_settings"]["last_updated"] = datetime.now().isoformat()
                
                # Save updated client config
                with open(client_config_path, "w") as f:
                    json.dump(client_config, f, indent=2)
                
                print(f"✅ Updated client config for {username}: search_term='{search_term}', max_scrolls={max_scrolls}")
                
            except Exception as e:
                print(f"❌ Error updating client config for {username}: {e}")
                success = False
        
        # Always update main config for backward compatibility
        if not self._update_main_config(search_term, max_scrolls):
            success = False
        
        return success
    
    def get_debug_info(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Get debug information about current configuration state"""
        debug_info = {
            "username": username or "not_authenticated",
            "main_config": {},
            "client_config": {},
            "files_exist": {}
        }
        
        # Check main config
        debug_info["files_exist"]["main_config"] = os.path.exists(self.main_config_file)
        if debug_info["files_exist"]["main_config"]:
            try:
                main_config = self.load_main_config()
                debug_info["main_config"] = {
                    "root_search_term": main_config.get("search_term", "NOT_SET"),
                    "root_max_scrolls": main_config.get("max_scrolls", "NOT_SET"),
                    "global_search_term": main_config.get("global", {}).get("search_term", "NOT_SET"),
                    "global_max_scrolls": main_config.get("global", {}).get("max_scrolls", "NOT_SET"),
                    "has_global_section": "global" in main_config,
                    "has_platforms_section": "platforms" in main_config
                }
            except Exception as e:
                debug_info["main_config"]["error"] = str(e)
        
        # Check client config
        if username:
            client_config_path = self.get_client_config_path(username)
            debug_info["files_exist"]["client_config"] = os.path.exists(client_config_path)
            
            if debug_info["files_exist"]["client_config"]:
                try:
                    with open(client_config_path, "r") as f:
                        client_config = load_json_safe(f)
                    global_settings = client_config.get("global_settings", {})
                    debug_info["client_config"] = {
                        "search_term": global_settings.get("search_term", "NOT_SET"),
                        "max_scrolls": global_settings.get("max_scrolls", "NOT_SET"),
                        "last_updated": global_settings.get("last_updated", "NOT_SET")
                    }
                except Exception as e:
                    debug_info["client_config"]["error"] = str(e)
        
        return debug_info
    
    def test_config_update(self, username: Optional[str] = None) -> Tuple[bool, str]:
        """Test configuration update functionality"""
        test_search = "test_search_term"
        test_scrolls = 15
        
        try:
            # Save original values
            original_config = self.load_user_config(username)
            original_search = original_config.get("search_term", "crypto trader")
            original_scrolls = original_config.get("max_scrolls", 12)
            
            # Test update
            success = self.update_user_config(username, test_search, test_scrolls)
            
            if success:
                # Verify the update worked
                updated_config = self.load_user_config(username)
                if (updated_config.get("search_term") == test_search and 
                    updated_config.get("max_scrolls") == test_scrolls):
                    
                    # Restore original values
                    self.update_user_config(username, original_search, original_scrolls)
                    
                    return True, f"Test successful: {test_search}, {test_scrolls} (restored to: {original_search}, {original_scrolls})"
                else:
                    return False, f"Update succeeded but verification failed. Expected: {test_search}, {test_scrolls}. Got: {updated_config.get('search_term')}, {updated_config.get('max_scrolls')}"
            else:
                return False, "Update function returned False"
                
        except Exception as e:
            return False, f"Test failed with error: {str(e)}"
    
    def _extract_search_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract search-related configuration from config dict - handles nested structure"""
        # Priority: root level -> global section -> defaults
        search_term = (
            config.get("search_term") or 
            config.get("global", {}).get("search_term") or 
            "crypto trader"
        )
        
        max_scrolls = (
            config.get("max_scrolls") or 
            config.get("global", {}).get("max_scrolls") or 
            12
        )
        
        return {
            "search_term": search_term,
            "max_scrolls": int(max_scrolls)
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            "search_term": "crypto trader",
            "max_scrolls": 12
        }
    
    def _update_main_config(self, search_term: str, max_scrolls: int) -> bool:
        """Update main config.json file - handles both root level and nested global section"""
        try:
            # Load existing config
            main_config = self.load_main_config()
            
            # Update root level settings
            main_config["search_term"] = search_term
            main_config["max_scrolls"] = max_scrolls
            main_config["last_updated"] = datetime.now().isoformat()
            
            # ALSO update the nested "global" section if it exists
            if "global" in main_config:
                main_config["global"]["search_term"] = search_term
                main_config["global"]["max_scrolls"] = max_scrolls
            
            # Update platform-specific max_scrolls if they exist
            if "platforms" in main_config:
                for platform_name, platform_config in main_config["platforms"].items():
                    if isinstance(platform_config, dict) and "max_scrolls" in platform_config:
                        platform_config["max_scrolls"] = max_scrolls
            
            # Save main config
            with open(self.main_config_file, "w") as f:
                json.dump(main_config, f, indent=4)
            
            print(f"✅ Updated main config (root + global + platforms): search_term='{search_term}', max_scrolls={max_scrolls}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating main config: {e}")
            return False


# Create a global instance for easy importing
config_manager = UserConfigManager()

# Convenience functions for easy use
def get_current_config(username: Optional[str] = None) -> Dict[str, Any]:
    """Get current configuration for user"""
    return config_manager.load_user_config(username)

def update_config(username: Optional[str], search_term: str, max_scrolls: int) -> bool:
    """Update configuration for user"""
    return config_manager.update_user_config(username, search_term, max_scrolls)

def get_config_debug_info(username: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration debug information"""
    return config_manager.get_debug_info(username)

def test_config_system(username: Optional[str] = None) -> Tuple[bool, str]:
    """Test the configuration system"""
    return config_manager.test_config_update(username)