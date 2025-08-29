# FIX FOR: unsupported operand type(s) for /: 'str' and 'str'
# This error occurs in CSV reading code, likely in calculate_empire_from_csvs or similar

from pathlib import Path
import pandas as pd
import csv
import glob
import os

# COMMON ERROR PATTERNS AND FIXES
# ============================================================================

def problematic_csv_reading():
    """
    THESE CAUSE THE ERROR - Don't do this!
    """
    # ❌ ERROR: Using / between two strings
    csv_dir = "client_configs"  # String
    filename = "twitter_leads_jane_2025-08-28.csv"  # String
    
    # ❌ This fails: unsupported operand type(s) for /: 'str' and 'str'
    # file_path = csv_dir / filename  # DON'T DO THIS
    
    # ❌ Also fails in pandas.read_csv()
    # df = pd.read_csv(csv_dir / filename)  # DON'T DO THIS

def correct_csv_reading():
    """
    THESE ARE THE CORRECT APPROACHES
    """
    csv_dir = "client_configs"  # String
    filename = "twitter_leads_jane_2025-08-28.csv"  # String
    
    # ✅ METHOD 1: Convert to Path object first
    csv_path = Path(csv_dir)
    file_path = csv_path / filename  # Now this works
    df = pd.read_csv(file_path)
    
    # ✅ METHOD 2: Use string concatenation
    file_path = csv_dir + "/" + filename
    df = pd.read_csv(file_path)
    
    # ✅ METHOD 3: Use f-string formatting
    file_path = f"{csv_dir}/{filename}"
    df = pd.read_csv(file_path)
    
    # ✅ METHOD 4: Use os.path.join (old school but works)
    file_path = os.path.join(csv_dir, filename)
    df = pd.read_csv(file_path)

# SPECIFIC FIX FOR EMPIRE CALCULATION
# ============================================================================

def fixed_calculate_empire_from_csvs(username: str):
    """
    Fixed version of empire calculation with proper path handling
    """
    from pathlib import Path
    import pandas as pd
    import glob
    
    # Get CSV directory
    csv_dir = os.getenv("CSV_DIR", "/app/client_configs")
    csv_path = Path(csv_dir)  # Convert to Path object
    
    stats = {}
    platforms = ['twitter', 'linkedin', 'facebook', 'tiktok', 'instagram', 'youtube', 'medium', 'reddit']
    
    for platform in platforms:
        try:
            # ✅ FIXED: Use proper path operations
            pattern = f"{platform}_leads_*{username}_*.csv"
            
            # Method 1: Using glob with string paths
            search_pattern = f"{csv_dir}/{pattern}"
            matching_files = glob.glob(search_pattern)
            
            # Method 2: Using pathlib (preferred)
            # matching_files = list(csv_path.glob(pattern))
            # matching_files = [str(f) for f in matching_files]  # Convert back to strings for pandas
            
            if matching_files:
                total_leads = 0
                for file_path in matching_files:
                    try:
                        # ✅ FIXED: file_path is already a proper string path
                        df = pd.read_csv(file_path)
                        total_leads += len(df)
                        print(f"✅ Read {len(df)} leads from {file_path}")
                    except Exception as e:
                        print(f"❌ {platform.title()} error: {e}")
                        continue
                
                stats[platform] = total_leads
                print(f"📊 {platform.title()}: {total_leads} total leads")
            else:
                stats[platform] = 0
                print(f"❌ {platform.title()}: No user-specific files found")
                
        except Exception as e:
            print(f"❌ {platform.title()} error: {e}")
            stats[platform] = 0
    
    return stats

# QUICK DIAGNOSTIC FUNCTIONS
# ============================================================================

def diagnose_path_errors():
    """
    Run this to find where your path errors are occurring
    """
    import traceback
    
    print("🔍 Diagnosing path operation errors...")
    
    # Test basic path operations
    try:
        csv_dir = "client_configs"
        filename = "test.csv"
        
        # This should fail
        result = csv_dir / filename
    except TypeError as e:
        print(f"✅ Confirmed error: {e}")
        print("This is the exact error you're seeing")
    
    # Test correct approaches
    try:
        csv_path = Path("client_configs")
        filename = "test.csv"
        result = csv_path / filename
        print(f"✅ Path method works: {result}")
    except Exception as e:
        print(f"❌ Path method failed: {e}")

def fix_existing_csv_reading_function():
    """
    Generic fix that can be applied to any function with path errors
    """
    
    # IF YOUR CODE LOOKS LIKE THIS:
    # def some_function():
    #     csv_dir = "client_configs"  # or os.getenv("CSV_DIR", "...")
    #     filename = "some_file.csv"
    #     df = pd.read_csv(csv_dir / filename)  # ❌ ERROR HERE
    
    # CHANGE IT TO THIS:
    def fixed_function():
        csv_dir = os.getenv("CSV_DIR", "/app/client_configs")
        csv_path = Path(csv_dir)  # Convert to Path object
        filename = "some_file.csv"
        
        # Now this works
        file_path = csv_path / filename
        df = pd.read_csv(file_path)
        return df

# SEARCH AND REPLACE PATTERNS
# ============================================================================

def common_fixes():
    """
    Common search and replace patterns to fix path errors
    """
    fixes = {
        "FIND": [
            'csv_dir / filename',
            'directory / file', 
            'path / name',
            'base_path / file_name',
        ],
        "REPLACE_WITH": [
            'Path(csv_dir) / filename',
            'Path(directory) / file',
            'Path(path) / name', 
            'Path(base_path) / file_name',
        ],
        "OR_USE_STRING_CONCATENATION": [
            'f"{csv_dir}/{filename}"',
            'f"{directory}/{file}"',
            'f"{path}/{name}"',
            'f"{base_path}/{file_name}"',
        ]
    }
    
    return fixes

# SPECIFIC FIX FOR YOUR LOGS
# ============================================================================

def fix_twitter_facebook_reading():
    """
    Based on your error logs, fix the specific CSV reading for Twitter and Facebook
    """
    username = "jane"
    csv_dir = "/app/client_configs"
    csv_path = Path(csv_dir)
    
    # Fix Twitter reading
    twitter_pattern = f"twitter_leads_*{username}_*.csv"
    twitter_files = list(csv_path.glob(twitter_pattern))
    
    if twitter_files:
        for file_path in twitter_files:
            try:
                # ✅ CORRECT: file_path is already a Path object
                df = pd.read_csv(file_path)
                print(f"✅ Twitter: Read {len(df)} leads from {file_path.name}")
            except Exception as e:
                print(f"❌ Twitter error: {e}")
    
    # Fix Facebook reading
    facebook_pattern = f"facebook_leads_*{username}_*.csv"
    facebook_files = list(csv_path.glob(facebook_pattern))
    
    if facebook_files:
        for file_path in facebook_files:
            try:
                # ✅ CORRECT: file_path is already a Path object
                df = pd.read_csv(file_path)
                print(f"✅ Facebook: Read {len(df)} leads from {file_path.name}")
            except Exception as e:
                print(f"❌ Facebook error: {e}")

if __name__ == "__main__":
    print("🔧 CSV Path Error Diagnosis and Fixes")
    print("=====================================")
    
    diagnose_path_errors()
    
    print("\n📋 To fix your specific error:")
    print("1. Find your calculate_empire_from_csvs function")
    print("2. Look for lines with: string_variable / another_string")
    print("3. Replace with: Path(string_variable) / another_string")
    print("4. Or use f-strings: f'{string_variable}/{another_string}'")
    
    # Test the fixed empire calculation
    print("\n🧪 Testing fixed empire calculation...")
    stats = fixed_calculate_empire_from_csvs("jane")
    print(f"Final stats: {stats}")