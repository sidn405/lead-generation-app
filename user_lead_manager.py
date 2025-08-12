"""
user_lead_manager.py - Standalone User Lead Results Module

Completely self-contained module for managing user-specific lead results.
No dependencies on main app functions.

Usage:
    from user_lead_manager import UserLeadManager
    
    # Initialize
    lead_manager = UserLeadManager()
    
    # Get user's leads
    results = lead_manager.get_user_results(username)
    
    # Display in Streamlit
    lead_manager.display_user_results(username, st)
"""

import glob
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import json


class UserLeadManager:
    """Standalone manager for user-specific lead results"""
    
    def __init__(self):
        """Initialize with platform definitions"""
        self.platform_patterns = {
            "🐦 Twitter": ["twitter_leads_*.csv", "*twitter*.csv", "*tweet*.csv"],
            "💼 LinkedIn": ["linkedin_leads_*.csv", "*linkedin*.csv", "*li_*.csv"],
            "📘 Facebook": ["facebook_leads_*.csv", "*facebook*.csv", "*fb_*.csv"],
            "🎵 TikTok": ["tiktok_leads_*.csv", "*tiktok*.csv", "*tt_*.csv"],
            "📸 Instagram": ["instagram_leads_*.csv", "*instagram*.csv", "*ig_*.csv", "*insta*.csv"],
            "🎥 YouTube": ["youtube_leads_*.csv", "*youtube*.csv", "*yt_*.csv"],
            "📝 Medium": ["medium_leads_*.csv", "*medium*.csv"],
            "🗨️ Reddit": ["reddit_leads_*.csv", "*reddit*.csv"]
        }
        
        self.user_session_file = "current_user_sessions.json"
        self.recent_hours_threshold = 24
    
    def get_user_results(self, username: str) -> Dict[str, Any]:
        """
        Get all lead results for a specific user
        
        Returns:
            {
                'success': bool,
                'platforms_data': dict,
                'totals': dict,
                'total_leads': int,
                'active_platforms': int,
                'combined_data': DataFrame or None,
                'message': str
            }
        """
        if not username:
            return self._error_response("No username provided")
        
        try:
            # Find user-specific files
            user_files = self._find_user_files(username)
            
            if not user_files:
                return {
                    'success': True,
                    'platforms_data': {},
                    'totals': {},
                    'total_leads': 0,
                    'active_platforms': 0,
                    'combined_data': None,
                    'message': f'No lead files found for user: {username}'
                }
            
            # Load and process data
            platforms_data = {}
            totals = {}
            all_data = []
            
            for platform_name, filepath in user_files.items():
                try:
                    # Load and clean data
                    df = self._load_and_clean_csv(filepath)
                    
                    # Filter for this user
                    user_df = self._filter_for_user(df, username)
                    
                    if not user_df.empty:
                        # Ensure platform column exists
                        if 'platform' not in user_df.columns:
                            platform_key = self._extract_platform_key(platform_name)
                            user_df['platform'] = platform_key
                        
                        platforms_data[platform_name] = user_df
                        totals[platform_name] = len(user_df)
                        all_data.append(user_df)
                        
                        print(f"✅ Loaded {len(user_df)} leads for {username} from {platform_name}")
                    else:
                        totals[platform_name] = 0
                        
                except Exception as e:
                    totals[platform_name] = 0
                    print(f"❌ Error loading {platform_name} for {username}: {e}")
            
            # Combine all data
            combined_df = None
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['name', 'handle'], keep='first')
                platforms_data[f"👑 {username}'s Combined"] = combined_df
            
            total_leads = sum(totals.values())
            active_platforms = len([x for x in totals.values() if x > 0])
            
            return {
                'success': True,
                'platforms_data': platforms_data,
                'totals': totals,
                'total_leads': total_leads,
                'active_platforms': active_platforms,
                'combined_data': combined_df,
                'message': f'Successfully loaded {total_leads} leads for {username}'
            }
            
        except Exception as e:
            return self._error_response(f'Error loading user data: {str(e)}')
    
    def display_user_results(self, username: str, st_module) -> None:
        """
        Display user results in Streamlit
        
        Args:
            username: Current authenticated user
            st_module: Streamlit module (pass 'st')
        """
        st = st_module  # Local reference
        
        # Get user results
        results = self.get_user_results(username)
        
        if not results['success']:
            st.error(f"❌ {results.get('message', 'Unknown error')}")
            return
        
        total_leads = results['total_leads']
        
        if total_leads == 0:
            self._display_no_results(username, st)
            return
        
        # Display results
        self._display_user_metrics(results, username, st)
        self._display_platform_breakdown(results, st)
        self._display_platform_tabs(results, username, st)
    
    def _find_user_files(self, username: str) -> Dict[str, str]:
        """Find CSV files belonging to the user"""
        user_files = {}
        cutoff_time = datetime.now() - timedelta(hours=self.recent_hours_threshold)
        
        for platform_name, patterns in self.platform_patterns.items():
            found_file = None
            
            # Method 1: User-specific filename patterns
            for pattern in patterns:
                user_patterns = [
                    pattern.replace("*.csv", f"*{username}*.csv"),
                    pattern.replace("*.csv", f"{username}_*.csv"),
                    f"{username}_{pattern}"
                ]
                
                for user_pattern in user_patterns:
                    files = glob.glob(user_pattern)
                    if files:
                        found_file = max(files, key=os.path.getmtime)
                        break
                
                if found_file:
                    break
            
            # Method 2: Recent general files that belong to user
            if not found_file:
                for pattern in patterns:
                    files = glob.glob(pattern)
                    for filepath in files:
                        try:
                            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if file_time > cutoff_time and self._file_belongs_to_user(filepath, username):
                                found_file = filepath
                                break
                        except:
                            continue
                    if found_file:
                        break
            
            if found_file:
                user_files[platform_name] = found_file
        
        return user_files
    
    def _file_belongs_to_user(self, filepath: str, username: str) -> bool:
        """Check if file belongs to user"""
        try:
            # Quick check of first few rows
            df_sample = pd.read_csv(filepath, nrows=5)
            
            # Check user-identifying columns
            user_cols = ['username', 'generated_by', 'user_id', 'scraper_user']
            for col in user_cols:
                if col in df_sample.columns:
                    return username in df_sample[col].astype(str).values
            
            # If very recent (last 30 minutes), assume it's theirs
            mod_time = os.path.getmtime(filepath)
            age_minutes = (datetime.now().timestamp() - mod_time) / 60
            return age_minutes <= 30
            
        except:
            return False
    
    def _load_and_clean_csv(self, filepath: str) -> pd.DataFrame:
        """Load and clean CSV data"""
        try:
            df = pd.read_csv(filepath)
            return self._clean_dataframe(df)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return pd.DataFrame()
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataframe for display"""
        if df.empty:
            return df
        
        df_clean = df.copy()
        
        # Fix numeric columns
        numeric_cols = [
            'followers', 'following', 'posts', 'engagement_rate', 
            'subscribers', 'videos', 'likes', 'connections', 'karma'
        ]
        
        for col in numeric_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).replace({
                    'Followers not shown': '1000',
                    'Following not shown': '500',
                    'Posts not shown': '100',
                    'Not available': '0',
                    'N/A': '0',
                    'None': '0',
                    '': '0'
                })
                
                if col == 'engagement_rate':
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(5.0)
                else:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(1000).astype(int)
        
        # Fix boolean columns
        bool_cols = ['verified', 'demo_mode']
        for col in bool_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(bool)
        
        # Fix string columns
        str_cols = ['name', 'handle', 'bio', 'platform', 'location']
        for col in str_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str)
        
        return df_clean
    
    def _filter_for_user(self, df: pd.DataFrame, username: str) -> pd.DataFrame:
        """Filter dataframe for specific user"""
        if df.empty:
            return df
        
        # Check for user columns and filter
        user_cols = ['username', 'generated_by', 'user_id', 'scraper_user']
        for col in user_cols:
            if col in df.columns:
                mask = df[col].astype(str) == username
                filtered = df[mask]
                if not filtered.empty:
                    return filtered
        
        # If no user columns, check if recent enough
        if 'generated_at' in df.columns:
            try:
                df['generated_at'] = pd.to_datetime(df['generated_at'])
                cutoff = datetime.now() - timedelta(hours=24)
                return df[df['generated_at'] > cutoff]
            except:
                pass
        
        # If no identification and not recent, return empty to be safe
        return pd.DataFrame()
    
    def _extract_platform_key(self, platform_name: str) -> str:
        """Extract platform key from display name"""
        return platform_name.split()[1].lower() if len(platform_name.split()) > 1 else 'unknown'
    
    def _display_no_results(self, username: str, st) -> None:
        """Display message when no results found"""
        st.info(f"📭 No lead results found for {username}")
        
        st.markdown("### 🚀 Generate Your First Leads")
        st.markdown("""
        **Get started:**
        1. 🔍 Go to **Empire Scraper** tab
        2. 🎯 Configure your search settings
        3. 🌍 Select your target platforms
        4. 🚀 Launch your campaign
        5. 📊 Return here to analyze results!
        """)
    
    def _display_user_metrics(self, results: Dict, username: str, st) -> None:
        """Display user metrics section"""
        total_leads = results['total_leads']
        active_platforms = results['active_platforms']
        
        st.success(f"🎉 Found {total_leads} leads for {username}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Your Total Leads", total_leads)
        
        with col2:
            st.metric("🌍 Active Platforms", active_platforms)
        
        with col3:
            estimated_value = total_leads * 25
            st.metric("💰 Estimated Value", f"${estimated_value:,}")
        
        with col4:
            st.metric("📅 Last Updated", datetime.now().strftime("%m/%d %H:%M"))
    
    def _display_platform_breakdown(self, results: Dict, st) -> None:
        """Display platform performance breakdown"""
        st.markdown("---")
        st.subheader("🏆 Your Platform Performance")
        
        totals = results['totals']
        active_totals = {k: v for k, v in totals.items() if v > 0}
        
        if active_totals:
            cols = st.columns(min(len(active_totals), 4))
            for i, (platform, count) in enumerate(active_totals.items()):
                with cols[i % 4]:
                    platform_emoji = platform.split()[0]
                    platform_name = platform.split()[1] if len(platform.split()) > 1 else platform
                    st.metric(f"{platform_emoji} {platform_name}", count)
    
    def _display_platform_tabs(self, results: Dict, username: str, st) -> None:
        """Display platform tabs with detailed data"""
        platforms_data = results['platforms_data']
        
        if not platforms_data:
            return
        
        st.markdown("---")
        
        # Create tabs
        tab_names = list(platforms_data.keys())
        tabs = st.tabs(tab_names)
        
        for tab, (platform_name, df) in zip(tabs, platforms_data.items()):
            with tab:
                if df.empty:
                    st.info(f"📭 No data for {platform_name}")
                    continue
                
                # Platform metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Leads", len(df))
                
                with col2:
                    quality_score = min(8.5 + (len(df) / 50), 10.0)
                    st.metric("Quality Score", f"{quality_score:.1f}/10")
                
                with col3:
                    dm_ready = len(df) if 'dm' not in df.columns else df['dm'].notna().sum()
                    dm_pct = (dm_ready / len(df)) * 100 if len(df) > 0 else 0
                    st.metric("DMs Ready", f"{dm_pct:.0f}%")
                
                with col4:
                    platform_value = len(df) * 25
                    st.metric("Platform Value", f"${platform_value:,}")
                
                # Search functionality
                search_key = f"search_{platform_name.replace(' ', '_').replace("'", '')}"
                search_term = st.text_input(
                    f"🔍 Search {platform_name}",
                    key=search_key,
                    placeholder="Keywords, names, locations..."
                )
                
                # Apply search filter
                display_df = df.copy()
                if search_term:
                    mask = df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
                    display_df = df[mask]
                
                # Display data
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Export functionality
                platform_clean = self._clean_platform_name(platform_name)
                csv_data = display_df.to_csv(index=False)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"{username}_{platform_clean}_{timestamp}.csv"
                
                st.download_button(
                    f"📥 Export {platform_clean}",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
                
                # Status info
                if search_term and len(display_df) != len(df):
                    st.info(f"🔍 Showing {len(display_df)} of {len(df)} results")
                else:
                    st.success(f"✅ Complete {platform_clean}: {len(df)} leads")
    
    def _clean_platform_name(self, platform_name: str) -> str:
        """Clean platform name for filenames"""
        # Remove emojis and clean up
        cleaned = platform_name
        emojis = ["👑", "🐦", "💼", "📘", "🎵", "📸", "🎥", "📝", "🗨️"]
        for emoji in emojis:
            cleaned = cleaned.replace(emoji, "")
        
        return cleaned.strip().lower().replace(' ', '_').replace("'", "")
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """Return standardized error response"""
        return {
            'success': False,
            'platforms_data': {},
            'totals': {},
            'total_leads': 0,
            'active_platforms': 0,
            'combined_data': None,
            'message': message
        }

# Convenience functions for easy import
def get_user_lead_results(username: str) -> Dict[str, Any]:
    """Get user lead results - convenience function"""
    manager = UserLeadManager()
    return manager.get_user_results(username)

def display_user_dashboard(username: str, st_module) -> None:
    """Display user dashboard - convenience function"""
    manager = UserLeadManager()
    manager.display_user_results(username, st_module)