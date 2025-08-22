"""
Exclusion Management & Testing Script
Use this to test and manage excluded accounts across all platforms
"""

from config_loader import ConfigLoader, should_exclude_account

def test_exclusions():
    """Test the exclusion functionality"""
    print("🧪 Testing Exclusion Functionality")
    print("=" * 50)
    
    config_loader = ConfigLoader()
    
    # Test accounts
    test_cases = [
        ("twitter", "@testuser1"),
        ("facebook", "testuser2"),
        ("instagram", "@testuser3"),
        ("linkedin", "Test User Four"),
        ("youtube", "@testchannel1"),
        ("tiktok", "@testuser4"),
        ("medium", "Test User Five"),
        ("reddit", "@testchannel2"),
    ]
    
    for platform, username in test_cases:
        is_excluded = should_exclude_account(username, platform, config_loader)
        status = "🚫 EXCLUDED" if is_excluded else "✅ ALLOWED"
        print(f"{platform.upper():10} | {username:15} | {status}")

def show_all_exclusions():
    """Show all excluded accounts for all platforms"""
    print("\n📋 Current Exclusion Lists")
    print("=" * 50)
    
    config_loader = ConfigLoader()
    platforms = ['twitter', 'facebook', 'instagram', 'linkedin', 'youtube', 'tiktok', 'reddit', 'medium']
    
    total_exclusions = 0
    
    for platform in platforms:
        excluded = config_loader.get_excluded_accounts(platform)
        total_exclusions += len(excluded)
        
        print(f"\n🚀 {platform.upper()}:")
        if excluded:
            for i, account in enumerate(excluded, 1):
                print(f"  {i:2}. {account}")
        else:
            print("  No excluded accounts")
    
    print(f"\n📊 Total excluded accounts across all platforms: {total_exclusions}")

def add_exclusion(platform, username):
    """Add an account to exclusion list"""
    config_loader = ConfigLoader()
    success = config_loader.add_excluded_account(platform, username)
    
    if success:
        print(f"✅ Added '{username}' to {platform} exclusions")
    else:
        print(f"⚠️ '{username}' already excluded from {platform}")
    
    return success

def remove_exclusion(platform, username):
    """Remove an account from exclusion list"""
    config_loader = ConfigLoader()
    success = config_loader.remove_excluded_account(platform, username)
    
    if success:
        print(f"✅ Removed '{username}' from {platform} exclusions")
    else:
        print(f"⚠️ '{username}' not found in {platform} exclusions")
    
    return success

def bulk_add_exclusions(platform, usernames):
    """Add multiple accounts to exclusion list"""
    print(f"📋 Bulk adding {len(usernames)} accounts to {platform} exclusions...")
    
    config_loader = ConfigLoader()
    added_count = 0
    
    for username in usernames:
        success = config_loader.add_excluded_account(platform, username.strip())
        if success:
            added_count += 1
            print(f"  ✅ Added: {username}")
        else:
            print(f"  ⚠️ Already exists: {username}")
    
    print(f"📊 Successfully added {added_count} new exclusions to {platform}")

def interactive_menu():
    """Interactive menu for managing exclusions"""
    config_loader = ConfigLoader()
    
    while True:
        print("\n" + "="*50)
        print("🚀 EXCLUSION MANAGER")
        print("="*50)
        print("1. 📋 Show all exclusions")
        print("2. 🧪 Test exclusion functionality")
        print("3. ➕ Add single exclusion")
        print("4. ➖ Remove single exclusion")
        print("5. 📦 Bulk add exclusions")
        print("6. 🔍 Check if account is excluded")
        print("0. ❌ Exit")
        
        choice = input("\nEnter choice (0-6): ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice == "1":
            show_all_exclusions()
        elif choice == "2":
            test_exclusions()
        elif choice == "3":
            platform = input("Platform (twitter/facebook/instagram/etc): ").strip().lower()
            username = input("Username to exclude: ").strip()
            add_exclusion(platform, username)
        elif choice == "4":
            platform = input("Platform (twitter/facebook/instagram/etc): ").strip().lower()
            username = input("Username to remove: ").strip()
            remove_exclusion(platform, username)
        elif choice == "5":
            platform = input("Platform (twitter/facebook/instagram/etc): ").strip().lower()
            print("Enter usernames (one per line, blank line to finish):")
            usernames = []
            while True:
                username = input().strip()
                if not username:
                    break
                usernames.append(username)
            
            if usernames:
                bulk_add_exclusions(platform, usernames)
            else:
                print("⚠️ No usernames entered")
        elif choice == "6":
            platform = input("Platform (twitter/facebook/instagram/etc): ").strip().lower()
            username = input("Username to check: ").strip()
            is_excluded = should_exclude_account(username, platform, config_loader)
            status = "🚫 EXCLUDED" if is_excluded else "✅ ALLOWED"
            print(f"Result: {username} on {platform} is {status}")
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    print("🚀 Lead Generator Empire - Exclusion Manager")
    print("📋 Manage excluded accounts across all platforms")
    
    # Quick test on startup
    test_exclusions()
    
    # Start interactive menu
    interactive_menu()