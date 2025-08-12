"""
csv_user_debug.py - FIXED VERSION - Complete User CSV Debug and Filter Module

Fixed the username scope issue in __init__ method.
"""

import glob
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

class CSVUserDebugger:
    """Complete CSV debugging and filtering system for user-specific data"""
    
    def __init__(self):
        """Initialize the debugger with base platform patterns"""
        # ✅ FIXED: Use base patterns without username, add username dynamically
        self.base_platform_patterns = {
            "🐦 Twitter": "twitter_unified_leads_*_*.csv",
            "💼 LinkedIn": "linkedin_leads_*_*.csv",
            "📘 Facebook": "facebook_unified_leads_*_*.csv",
            "🎵 TikTok": "tiktok_unified_leads_*_*.csv",
            "📸 Instagram": "instagram_unified_leads_*_*.csv",
            "🎥 YouTube": "youtube_unified_leads_*_*.csv",
            "📝 Medium": "medium_unified_leads_*_*.csv",
            "🗨️ Reddit": "reddit_unified_leads_*_*.csv",
        }
        
        self.user_columns = ['username', 'generated_by', 'user_id', 'scraper_user', 'created_by']
        self.time_columns = ['generated_at', 'timestamp', 'created_at', 'scraped_at']
    
    def get_user_platform_patterns(self, username: str) -> Dict[str, str]:
        """Get platform patterns with username inserted"""
        if not username:
            return self.base_platform_patterns
        
        user_patterns = {}
        for platform, base_pattern in self.base_platform_patterns.items():
            # Create user-specific pattern
            if "unified_leads_*_*" in base_pattern:
                user_pattern = base_pattern.replace("unified_leads_*_*", f"unified_leads_{username}_*")
            elif "leads_*_*" in base_pattern:
                user_pattern = base_pattern.replace("leads_*_*", f"leads_{username}_*")
            else:
                # Fallback: insert username before timestamp
                user_pattern = base_pattern.replace("_*.csv", f"_{username}_*.csv")
            
            user_patterns[platform] = user_pattern
        
        return user_patterns
    
    def analyze_all_csv_files(self, username: str) -> List[Dict[str, Any]]:
        """
        Analyze all CSV files in directory for user data
        
        Returns:
            List of file analysis dictionaries
        """
        all_csv_files = glob.glob("*.csv")
        file_analysis = []
        
        print(f"🔍 Analyzing {len(all_csv_files)} CSV files for user: {username}")
        
        for csv_file in all_csv_files:
            analysis = self._analyze_single_file(csv_file, username)
            file_analysis.append(analysis)
        
        return file_analysis
    
    def _analyze_single_file(self, csv_file: str, username: str) -> Dict[str, Any]:
        """Analyze a single CSV file for user data"""
        try:
            # File metadata
            stat = os.stat(csv_file)
            mod_time = stat.st_mtime
            age_hours = (datetime.now().timestamp() - mod_time) / 3600
            size_kb = round(stat.st_size / 1024, 1)
            
            # Read file content
            df = pd.read_csv(csv_file)
            
            # Check for user identification columns
            found_user_cols = [col for col in self.user_columns if col in df.columns]
            
            # Check if current user is in the data
            user_in_file = False
            user_values_found = []
            
            for col in found_user_cols:
                unique_vals = df[col].astype(str).unique()
                user_values_found.extend(unique_vals)
                if username in unique_vals:
                    user_in_file = True
                    break
            
            # ✅ FIXED: Check filename for username too
            username_in_filename = username.lower() in csv_file.lower()
            
            # Platform detection
            platform = self._detect_platform_from_filename(csv_file)
            
            # Time analysis
            time_info = self._analyze_timestamps(df)
            
            return {
                "file": csv_file,
                "platform": platform,
                "size_kb": size_kb,
                "modified": datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S"),
                "age_hours": round(age_hours, 1),
                "rows": len(df),
                "columns": list(df.columns),
                "user_columns": found_user_cols,
                "has_user_data": user_in_file,
                "username_in_filename": username_in_filename,
                "user_values": list(set(user_values_found))[:5],  # Show first 5 unique values
                "time_info": time_info,
                "is_recent": age_hours <= 2,
                "is_very_recent": age_hours <= 0.5,
                "belongs_to_user": self._file_belongs_to_user(csv_file, username, df)
            }
            
        except Exception as e:
            return {
                "file": csv_file,
                "platform": "Error",
                "size_kb": 0,
                "modified": "Error",
                "age_hours": 999,
                "rows": 0,
                "columns": [],
                "user_columns": [],
                "has_user_data": False,
                "username_in_filename": False,
                "user_values": [],
                "time_info": {},
                "is_recent": False,
                "is_very_recent": False,
                "belongs_to_user": False,
                "error": str(e)
            }
    
    def _detect_platform_from_filename(self, filename: str) -> str:
        """Detect platform from filename"""
        filename_lower = filename.lower()
        
        platform_keywords = {
            'twitter': '🐦 Twitter', 'tweet': '🐦 Twitter',
            'facebook': '📘 Facebook', 'fb': '📘 Facebook',
            'linkedin': '💼 LinkedIn', 'li': '💼 LinkedIn',
            'tiktok': '🎵 TikTok', 'tt': '🎵 TikTok',
            'instagram': '📸 Instagram', 'ig': '📸 Instagram', 'insta': '📸 Instagram',
            'youtube': '🎥 YouTube', 'yt': '🎥 YouTube',
            'medium': '📝 Medium',
            'reddit': '🗨️ Reddit'
        }
        
        for keyword, platform in platform_keywords.items():
            if keyword in filename_lower:
                return platform
        
        return "❓ Unknown"
    
    def _analyze_timestamps(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze timestamp columns in DataFrame"""
        time_info = {}
        
        for time_col in self.time_columns:
            if time_col in df.columns:
                try:
                    df_time = pd.to_datetime(df[time_col])
                    time_info[time_col] = {
                        'earliest': df_time.min().isoformat(),
                        'latest': df_time.max().isoformat(),
                        'count': df_time.notna().sum()
                    }
                except:
                    time_info[time_col] = {'error': 'Could not parse timestamps'}
        
        return time_info
    
    def _file_belongs_to_user(self, filepath: str, username: str, df: Optional[pd.DataFrame] = None) -> bool:
        """Determine if file belongs to specific user"""
        try:
            if df is None:
                df = pd.read_csv(filepath, nrows=20)
            
            # ✅ METHOD 1: Check filename for username
            if username.lower() in os.path.basename(filepath).lower():
                print(f"✅ File belongs to {username} via filename: {filepath}")
                return True
            
            # ✅ METHOD 2: Check user columns
            for col in self.user_columns:
                if col in df.columns:
                    if username in df[col].astype(str).values:
                        print(f"✅ File belongs to {username} via {col} column: {filepath}")
                        return True
            
            # ✅ METHOD 3: Check if very recent (assuming it's theirs)
            mod_time = os.path.getmtime(filepath)
            age_minutes = (datetime.now().timestamp() - mod_time) / 60
            if age_minutes <= 30:
                print(f"✅ File belongs to {username} via recent timestamp: {filepath}")
                return True
            
            # ✅ METHOD 4: Check for demo markers if applicable
            demo_columns = ['demo_mode', 'demo_status', 'sample_type']
            for col in demo_columns:
                if col in df.columns:
                    if age_minutes <= 120:  # 2 hours for demo files
                        print(f"✅ File belongs to {username} via demo marker: {filepath}")
                        return True
            
            print(f"❌ File does not belong to {username}: {filepath}")
            return False
            
        except Exception as e:
            print(f"❌ Error checking file ownership: {e}")
            return False
    
    def get_user_csv_file(self, pattern: str, username: str) -> Optional[str]:
        """
        Get CSV file for specific user with smart detection
        
        Args:
            pattern: File pattern (e.g., "twitter_leads_*.csv")
            username: Current user
            
        Returns:
            Path to user's CSV file or None
        """
        if not username:
            print("❌ No username provided")
            return None
        
        try:
            #print(f"🔍 Looking for user files with pattern: {pattern} for user: {username}")
            
            # ✅ STRATEGY 1: User-specific filename patterns
            user_patterns = [
                pattern.replace("*.csv", f"*{username}*.csv"),
                pattern.replace("*.csv", f"{username}_*.csv"),
                pattern.replace("_*.csv", f"_{username}_*.csv"),
                pattern.replace("leads_*.csv", f"leads_{username}_*.csv"),
                f"{username}_{pattern}"
            ]
            
            for user_pattern in user_patterns:
                files = sorted(glob.glob(user_pattern), key=os.path.getmtime, reverse=True)
                if files:
                    print(f"✅ Found user-specific file with pattern {user_pattern}: {files[0]}")
                    return files[0]
                else:
                    print(f"❌ No files found for pattern: {user_pattern}")
            
            # ✅ STRATEGY 2: Check all pattern files for user content
            print(f"🔍 Checking all files matching {pattern} for user content...")
            all_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
            
            for filepath in all_files:
                if self._file_belongs_to_user(filepath, username):
                    print(f"✅ Found user file via content analysis: {filepath}")
                    return filepath
            
            # ✅ STRATEGY 3: Most recent file as fallback
            if all_files:
                most_recent = all_files[0]
                mod_time = os.path.getmtime(most_recent)
                age_hours = (datetime.now().timestamp() - mod_time) / 3600
                
                if age_hours <= 2:  # Last 2 hours
                    print(f"⚠️ Using recent file as fallback (assuming it's yours): {most_recent}")
                    return most_recent
            
            #print(f"❌ No suitable files found for pattern: {pattern}")
            return None
            
        except Exception as e:
            #print(f"❌ Error in get_user_csv_file: {e}")
            return None
    
    def filter_dataframe_for_user(self, df: pd.DataFrame, username: str) -> pd.DataFrame:
        """
        Filter DataFrame to show only user's data
        
        Args:
            df: Original DataFrame
            username: Current user
            
        Returns:
            Filtered DataFrame
        """
        if df.empty or not username:
            return df
        
        original_count = len(df)
        print(f"🔍 Filtering DataFrame with {original_count} rows for user: {username}")
        
        # ✅ STRATEGY 1: User column filtering
        for col in self.user_columns:
            if col in df.columns:
                user_mask = df[col].astype(str).str.lower() == username.lower()
                filtered_df = df[user_mask]
                if not filtered_df.empty:
                    print(f"✅ Filtered by {col}: {original_count} → {len(filtered_df)} rows")
                    return filtered_df
        
        # ✅ STRATEGY 2: Time-based filtering (recent data)
        for time_col in self.time_columns:
            if time_col in df.columns:
                try:
                    df_copy = df.copy()
                    df_copy[time_col] = pd.to_datetime(df_copy[time_col])
                    cutoff_time = datetime.now() - timedelta(hours=4)
                    recent_mask = df_copy[time_col] > cutoff_time
                    recent_df = df[recent_mask]
                    if not recent_df.empty:
                        print(f"✅ Filtered by recent time ({time_col}): {original_count} → {len(recent_df)} rows")
                        return recent_df
                except Exception as e:
                    print(f"❌ Error filtering by {time_col}: {e}")
                    continue
        
        # ✅ STRATEGY 3: Demo/sample data filtering
        demo_columns = ['demo_mode', 'demo_status', 'sample_type']
        for col in demo_columns:
            if col in df.columns:
                demo_mask = df[col].astype(str).str.contains('demo|sample', case=False, na=False)
                demo_df = df[demo_mask]
                if not demo_df.empty:
                    print(f"✅ Filtered demo/sample data: {original_count} → {len(demo_df)} rows")
                    return demo_df
        
        # If no filtering worked, return original data but warn
        print(f"⚠️ No user filtering applied, returning all {original_count} rows")
        return df
    
    def show_debug_interface(self, username: str, st_module) -> None:
        """
        Show debug interface in Streamlit
        
        Args:
            username: Current authenticated user
            st_module: Streamlit module (pass 'st')
        """
        st = st_module
        
        st.markdown("#### 🔍 CSV File Debug Analysis")
        st.info(f"**Current user:** {username}")
        
        if st.button("🔍 Analyze My CSV Files", key="csv_debug_analyze"):
            
            # Get file analysis
            file_analysis = self.analyze_all_csv_files(username)
            
            if not file_analysis:
                st.error("❌ No CSV files found in directory!")
                st.info(f"📁 Current directory: {os.getcwd()}")
                st.info("💡 Try running the Empire Scraper first to generate some files")
                return
            
            st.success(f"✅ Found {len(file_analysis)} CSV files")
            
            # Create analysis DataFrame
            display_data = []
            for analysis in file_analysis:
                display_data.append({
                    "File": analysis["file"],
                    "Platform": analysis["platform"],
                    "Rows": analysis["rows"],
                    "Age (hours)": analysis["age_hours"],
                    "Size (KB)": analysis["size_kb"],
                    "User Columns": ", ".join(analysis["user_columns"]) if analysis["user_columns"] else "❌ None",
                    "Has Your Data": "✅ YES" if analysis["has_user_data"] else "❌ NO",
                    "Belongs to You": "✅ YES" if analysis["belongs_to_user"] else "❌ NO"
                })
            
            # Display table
            df_display = pd.DataFrame(display_data)
            st.dataframe(df_display, use_container_width=True)
            
            # Summary metrics
            self._show_debug_summary(file_analysis, username, st)
            
            # Detailed recommendations
            self._show_debug_recommendations(file_analysis, username, st)
        
        # Platform-specific testing
        if st.button("🧪 Test Platform Detection", key="csv_debug_platforms"):
            self._test_platform_detection(username, st)
    
    def _show_debug_summary(self, file_analysis: List[Dict], username: str, st) -> None:
        """Show debug summary metrics"""
        files_with_user = len([f for f in file_analysis if f["has_user_data"]])
        files_belonging = len([f for f in file_analysis if f["belongs_to_user"]])
        files_with_user_cols = len([f for f in file_analysis if f["user_columns"]])
        recent_files = len([f for f in file_analysis if f["is_recent"]])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if files_with_user > 0:
                st.success(f"✅ Contains your data: {files_with_user}")
            else:
                st.error(f"❌ Contains your data: {files_with_user}")
        
        with col2:
            if files_belonging > 0:
                st.success(f"✅ Belongs to you: {files_belonging}")
            else:
                st.error(f"❌ Belongs to you: {files_belonging}")
        
        with col3:
            if files_with_user_cols > 0:
                st.success(f"✅ Has user tracking: {files_with_user_cols}")
            else:
                st.warning(f"⚠️ Has user tracking: {files_with_user_cols}")
        
        with col4:
            if recent_files > 0:
                st.info(f"🕒 Recent files: {recent_files}")
            else:
                st.warning(f"🕒 Recent files: {recent_files}")
    
    def _show_debug_recommendations(self, file_analysis: List[Dict], username: str, st) -> None:
        """Show debug recommendations"""
        st.markdown("#### 💡 Analysis & Recommendations")
        
        files_with_user = [f for f in file_analysis if f["has_user_data"]]
        files_belonging = [f for f in file_analysis if f["belongs_to_user"]]
        files_with_user_cols = [f for f in file_analysis if f["user_columns"]]
        recent_files = [f for f in file_analysis if f["is_recent"]]
        
        if files_belonging:
            st.success("✅ **Great News:** Found files that belong to you!")
            st.markdown("**Your files:**")
            for f in files_belonging:
                st.text(f"📄 {f['file']} - {f['platform']} ({f['rows']} rows, {f['age_hours']:.1f}h ago)")
        
        elif files_with_user:
            st.success("✅ **Good News:** Found files with your data!")
            st.markdown("**Files containing your data:**")
            for f in files_with_user:
                st.text(f"📄 {f['file']} - {f['platform']} ({f['rows']} rows)")
        
        elif files_with_user_cols:
            st.warning("⚠️ **Issue:** Files have user tracking but your username isn't found")
            
            # Show what usernames ARE in the files
            all_users = set()
            for f in files_with_user_cols:
                all_users.update(f.get("user_values", []))
            
            if all_users:
                st.markdown("**Usernames found in files:**")
                for user in sorted(all_users)[:10]:
                    if user and user != 'nan' and len(str(user)) > 1:
                        st.text(f"👤 {user}")
                
                st.info(f"💡 **Check:** Is your username '{username}' spelled correctly? Are you logged in as the right user?")
        
        elif recent_files:
            st.info("🕒 **Fallback:** Using recent files (assuming they're yours)")
            st.markdown("**Recent files (last 2 hours):**")
            for f in recent_files:
                st.text(f"📄 {f['file']} - {f['platform']} ({f['rows']} rows)")
        
        else:
            st.error("🚨 **Problem:** No suitable files found!")
            st.markdown("""
            **This could mean:**
            - No files contain your username
            - No recent files available  
            - You may need to generate new leads
            
            **Solutions:**
            1. 🚀 Run the Empire Scraper to generate new leads
            2. 🔑 Check if you're logged in as the correct user
            3. 🔧 Verify your scrapers are saving username in filenames
            4. 📝 Check if scrapers are adding 'generated_by' columns
            """)
    
    def _test_platform_detection(self, username: str, st) -> None:
        """Test platform-specific file detection"""
        st.markdown("#### 🧪 Platform Detection Test")
        
        # Get user-specific patterns
        user_patterns = self.get_user_platform_patterns(username)
        
        for platform_name, pattern in user_patterns.items():
            with st.expander(f"{platform_name} Detection"):
                st.text(f"Pattern: {pattern}")
                
                files = glob.glob(pattern)
                if files:
                    latest = max(files, key=os.path.getmtime)
                    belongs = self._file_belongs_to_user(latest, username)
                    
                    status = "✅ Yours" if belongs else "❌ Not yours"
                    st.text(f"Found: {latest}")
                    st.text(f"Status: {status}")
                    
                    # Show file details
                    try:
                        df = pd.read_csv(latest, nrows=5)
                        st.text(f"Rows: {len(pd.read_csv(latest))}")
                        st.text(f"Columns: {list(df.columns)}")
                    except Exception as e:
                        st.text(f"Error reading file: {e}")
                else:
                    st.text("❌ No files found")
                    
                    # Suggest alternative patterns to try
                    alternatives = [
                        pattern.replace(f"_{username}_", "_*_"),
                        pattern.replace("unified_leads", "leads"),
                        f"*{platform_name.split()[1].lower()}*.csv"
                    ]
                    
                    st.text("🔍 Alternative patterns to check:")
                    for alt in alternatives:
                        alt_files = glob.glob(alt)
                        if alt_files:
                            st.text(f"  ✅ {alt}: {len(alt_files)} files")
                        else:
                            st.text(f"  ❌ {alt}: 0 files")

# ✅ FIXED: Convenience functions for easy import
def analyze_user_csv_files(username: str) -> List[Dict[str, Any]]:
    """Analyze CSV files for specific user - convenience function"""
    debugger = CSVUserDebugger()
    return debugger.analyze_all_csv_files(username)

def get_user_csv_file(pattern: str, username: str) -> Optional[str]:
    """Get user-specific CSV file - convenience function"""
    debugger = CSVUserDebugger()
    return debugger.get_user_csv_file(pattern, username)

def filter_csv_for_user(df: pd.DataFrame, username: str) -> pd.DataFrame:
    """Filter DataFrame for user - convenience function"""
    debugger = CSVUserDebugger()
    return debugger.filter_dataframe_for_user(df, username)

def show_csv_debug(username: str, st_module) -> None:
    """Show debug interface - convenience function"""
    debugger = CSVUserDebugger()
    debugger.show_debug_interface(username, st_module)

# ✅ TESTING FUNCTION
def test_debugger():
    """Test the debugger functionality"""
    debugger = CSVUserDebugger()
    test_username = "joey"
    
    print("🧪 Testing CSV User Debugger")
    print(f"📁 Current directory: {os.getcwd()}")
    
    # Test pattern generation
    patterns = debugger.get_user_platform_patterns(test_username)
    print(f"✅ Generated {len(patterns)} user patterns:")
    for platform, pattern in patterns.items():
        print(f"  {platform}: {pattern}")
    
    # Test file analysis
    analysis = debugger.analyze_all_csv_files(test_username)
    print(f"✅ Analyzed {len(analysis)} files")
    
    for file_info in analysis[:3]:  # Show first 3
        print(f"  📄 {file_info['file']}: {file_info['platform']} - Belongs: {file_info['belongs_to_user']}")

if __name__ == "__main__":
    test_debugger()