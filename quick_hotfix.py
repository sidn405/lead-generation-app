# quick_hotfix.py - Add this to fix the missing method immediately
from datetime import datetime
import json

def add_missing_methods_to_credit_system():
    """Add missing methods to existing credit system"""
    
    try:
        from simple_credit_system import credit_system
        
        # Add get_system_health method if missing
        if not hasattr(credit_system, 'get_system_health'):
            def get_system_health(self):
                """Get system health status for monitoring"""
                try:
                    health = {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat(),
                        "users_count": len(self.users),
                        "transactions_count": len(self.transactions),
                        "files_exist": {
                            "users": self.users_file.exists(),
                            "transactions": self.transactions_file.exists()
                        },
                        "data_directory": str(self.users_file.parent),
                        "issues": []
                    }
                    
                    # Check for potential issues
                    if not self.users_file.exists():
                        health["issues"].append("Users file missing")
                    if not self.transactions_file.exists():
                        health["issues"].append("Transactions file missing")
                    
                    # Check file sizes (detect corruption)
                    try:
                        if self.users_file.exists() and self.users_file.stat().st_size == 0:
                            health["issues"].append("Users file is empty")
                        if self.transactions_file.exists() and self.transactions_file.stat().st_size == 0:
                            health["issues"].append("Transactions file is empty")
                    except Exception:
                        health["issues"].append("Cannot check file sizes")
                    
                    # Check data integrity
                    if not isinstance(self.users, dict):
                        health["issues"].append("Users data is not a dictionary")
                    if not isinstance(self.transactions, list):
                        health["issues"].append("Transactions data is not a list")
                    
                    if health["issues"]:
                        health["status"] = "degraded"
                    
                    return health
                    
                except Exception as e:
                    return {
                        "status": "error",
                        "timestamp": datetime.now().isoformat(),
                        "error": str(e),
                        "users_count": 0,
                        "transactions_count": 0,
                        "files_exist": {"users": False, "transactions": False},
                        "data_directory": "unknown",
                        "issues": [f"Health check failed: {str(e)}"]
                    }
            
            # Monkey patch the method
            credit_system.__class__.get_system_health = get_system_health
            print("✅ Added missing get_system_health method")
        
        # Add force_data_persistence method if missing
        if not hasattr(credit_system, 'force_data_persistence'):
            def force_data_persistence(self):
                """Force data to persist - simplified version"""
                try:
                    self.save_data()
                    print("✅ Data persistence forced")
                    return True
                except Exception as e:
                    print(f"❌ Data persistence failed: {e}")
                    return False
            
            credit_system.__class__.force_data_persistence = force_data_persistence
            print("✅ Added missing force_data_persistence method")
        
        # Add recover_from_persistent_storage method if missing
        if not hasattr(credit_system, 'recover_from_persistent_storage'):
            def recover_from_persistent_storage(self):
                """Simple recovery attempt - looks for backup files"""
                try:
                    # Try to find backup files
                    from pathlib import Path
                    backup_dir = Path('.') / 'backup'
                    
                    if backup_dir.exists():
                        backup_users = backup_dir / 'users_credits_backup.json'
                        if backup_users.exists():
                            with open(backup_users, 'r', encoding='utf-8') as f:
                                self.users = json.load(f)
                            print("✅ Recovered users from backup")
                            return True
                    
                    print("ℹ️ No backup data found")
                    return False
                except Exception as e:
                    print(f"❌ Recovery failed: {e}")
                    return False
            
            credit_system.__class__.recover_from_persistent_storage = recover_from_persistent_storage
            print("✅ Added missing recover_from_persistent_storage method")
        
        return True
        
    except Exception as e:
        print(f"❌ Hotfix failed: {e}")
        return False

# Call this in your Streamlit app to fix the missing methods
if __name__ == "__main__":
    add_missing_methods_to_credit_system()