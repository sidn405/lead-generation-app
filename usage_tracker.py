# usage_tracker.py - Centralized usage tracking and limit management

import os
import json
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

class UsageTracker:
    """Centralized usage tracking and limit management for all scrapers"""
    
    def __init__(self):
        self.enabled = False
        self.enhanced_auth = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the usage tracker with enhanced auth system"""
        try:
            from auth_system import enhanced_auth
            self.enhanced_auth = enhanced_auth
            self.enabled = True
            print("✅ Usage tracking enabled")
        except ImportError:
            print("⚠️ Enhanced auth not available - running without usage tracking")
            self.enabled = False
    
    def check_user_limits(self, username: Optional[str], estimated_leads: int, platform: str = "unknown") -> Tuple[bool, str]:
        """
        Check if user can proceed with scraping based on their limits
        FIXED: Proper demo user handling with 5-lead limit
        """
        if not self.enabled or not username:
            return True, "✅ No limits active"
        
        try:
            # 🚀 CHECK FOR BYPASS FLAGS FIRST
            bypass_auth = os.environ.get('BYPASS_INDIVIDUAL_AUTH', 'false').lower() == 'true'
            pre_auth_user = os.environ.get('PRE_AUTHORIZED_USER', '')
            authorized_leads = os.environ.get('AUTHORIZED_LEADS', '0')
            
            if bypass_auth and pre_auth_user == username:
                print(f"🚀 BYPASS MODE: {platform} scraper using pre-authorization")
                print(f"   Pre-authorized user: {pre_auth_user}")
                print(f"   Authorized leads: {authorized_leads}")
                print(f"   Bypassing individual scraper authorization")
                
                try:
                    max_leads = int(authorized_leads)
                    return True, f"✅ Pre-authorized for {max_leads} leads (bypass mode)"
                except ValueError:
                    return True, f"✅ Pre-authorized (bypass mode)"
            
            # 🎯 CHECK IF THIS IS A DEMO USER FIRST
            user_plan = os.environ.get('USER_PLAN', '')
            
            # Try to get user plan from credit system if not in environment
            if not user_plan:
                try:
                    from simple_credit_system import credit_system
                    user_info = credit_system.get_user_info(username)
                    if user_info:
                        user_plan = user_info.get('plan', 'demo')
                except:
                    user_plan = 'demo'  # Default to demo if can't determine
            
            print(f"🔍 check_user_limits for {username}:")
            print(f"   User plan: {user_plan}")
            print(f"   Estimated leads: {estimated_leads}")
            
            # 🎯 DEMO USER SPECIAL HANDLING
            if user_plan == 'demo':
                print(f"📱 Demo user detected - using demo system limits")
                
                try:
                    from simple_credit_system import credit_system
                    
                    # Check demo system specifically
                    can_demo, remaining = credit_system.can_use_demo(username)
                    
                    print(f"📊 Demo system status:")
                    print(f"   Can use demo: {can_demo}")
                    print(f"   Demo remaining: {remaining}")
                    print(f"   Demo limit (total): 5")
                    
                    if not can_demo:
                        print(f"❌ Demo leads exhausted")
                        return False, f"❌ Demo leads exhausted - upgrade to continue"
                    
                    # For demo users, limit to remaining demo leads (max 5)
                    demo_max_leads = min(estimated_leads, remaining, 5)
                    
                    print(f"📊 Demo authorization:")
                    print(f"   Requested: {estimated_leads}")
                    print(f"   Demo remaining: {remaining}")
                    print(f"   Authorized: {demo_max_leads}")
                    
                    if demo_max_leads > 0:
                        return True, f"✅ Demo authorized for {demo_max_leads} leads ({remaining} demo remaining)"
                    else:
                        return False, f"❌ No demo leads remaining - upgrade to continue"
                        
                except Exception as e:
                    print(f"⚠️ Demo system error: {e}")
                    # Fallback for demo users
                    return False, f"❌ Demo system unavailable"
            
            # 🔄 REGULAR USER HANDLING (non-demo)
            print(f"💎 Regular user - checking general usage limits")
            
            # Get environment overrides
            force_auth = os.environ.get('FORCE_AUTHORIZATION', 'false').lower() == 'true'
            plan_override = os.environ.get('PLAN_OVERRIDE', '')
            limit_override = os.environ.get('SESSION_LIMIT_OVERRIDE', '')
            
            print(f"   Force auth: {force_auth}")
            print(f"   Plan override: {plan_override}")
            print(f"   Limit override: {limit_override}")
            
            # 🚀 OVERRIDE 1: Force authorization with plan override
            if force_auth and plan_override:
                print(f"🚀 ENVIRONMENT OVERRIDE for {username}:")
                print(f"   Plan: {plan_override}")
                print(f"   Session limit: {limit_override}")
                print(f"✅ Usage limits bypassed for {plan_override} user")
                return True, f"✅ {plan_override.title()} user - bypass active"
            
            # 🚀 OVERRIDE 2: Session limit override
            if limit_override and limit_override.isdigit():
                session_limit = int(limit_override)
                print(f"🚀 SESSION LIMIT OVERRIDE: {session_limit}")
                return True, f"✅ Session limit override: {session_limit} leads"
            
            # 🚀 OVERRIDE 3: User plan environment variable
            if user_plan in ['pro', 'ultimate']:
                session_limits = {'pro': 2000, 'ultimate': 9999}
                session_limit = session_limits.get(user_plan, 2000)
                
                print(f"✅ {user_plan.title()} user authorized: {estimated_leads}/{session_limit} leads")
                return True, f"✅ {user_plan.title()} user within session limits"
            
            # 🔄 FALLBACK: Check auth system (with overrides if available)
            print(f"📋 Checking auth system status for {username}")
            
            # Try override-aware methods first
            if hasattr(self.enhanced_auth, 'get_download_limit_with_overrides'):
                download_limit = self.enhanced_auth.get_download_limit_with_overrides(username)
                status = self.enhanced_auth.get_user_status_with_overrides(username)
                print(f"📊 Auth system (with overrides) - Limit: {download_limit}, Status: {status}")
            else:
                download_limit = self.enhanced_auth.get_download_limit(username)
                status = self.enhanced_auth.get_user_status(username)
                print(f"📊 Auth system (original) - Limit: {download_limit}, Status: {status}")
            
            current_usage = self.enhanced_auth.usage_data.get(username, {}).get('total_downloads', 0)
            print(f"📈 Current usage: {current_usage}")
            
            # Check limits
            if download_limit != float('inf'):
                remaining_limit = download_limit - current_usage
                
                if remaining_limit <= 0:
                    return False, f"❌ Download limit reached ({download_limit} total)"
                
                if estimated_leads > remaining_limit:
                    return False, f"❌ Estimated {estimated_leads} leads exceeds remaining limit of {remaining_limit}"
            
            # Status-based messaging
            status_messages = {
                "starter_limited": f"✅ Starter access - up to 250 leads total (estimated: {estimated_leads})",
                "starter_monitored": f"✅ Starter period - monitored access (estimated: {estimated_leads})",
                "full_access": f"✅ Full access - up to {download_limit} leads (estimated: {estimated_leads})",
                "review_required": "❌ Account under review - contact support",
                "unauthorized": "❌ User not found or unauthorized"
            }
            
            message = status_messages.get(status, f"✅ Status: {status}")
            can_proceed = status not in ["review_required", "unauthorized"]
            
            if can_proceed:
                print(f"🔐 {platform.title()} scraper: {message}")
            
            return can_proceed, message
            
        except Exception as e:
            print(f"⚠️ Error checking limits for {platform}: {e}")
            # Error fallback - check environment
            user_plan = os.environ.get('USER_PLAN', 'starter')
            if user_plan in ['pro', 'ultimate']:
                print(f"🚀 Error fallback: {user_plan} user allowed")
                return True, f"✅ {user_plan.title()} user - error fallback"
            
            return True, "⚠️ Proceeding without limit check due to error"
    
    def track_scraping_results(self, username: Optional[str], platform: str, leads_found: int, 
                              search_term: str = "", export_type: str = "scraper") -> bool:
        """
        Track scraping results for usage monitoring
        
        Args:
            username: Username or None
            platform: Platform name (twitter, medium, etc.)
            leads_found: Number of leads found
            search_term: Search term used
            export_type: Type of export (scraper, manual, bulk, etc.)
            
        Returns:
            bool: Success status
        """
        if not self.enabled or not username:
            return False
        
        try:
            # Track the download
            self.enhanced_auth.track_download(username, leads_found, export_type)
            
            # Initialize user data if needed
            if username not in self.enhanced_auth.usage_data:
                self.enhanced_auth.usage_data[username] = {}
            
            user_data = self.enhanced_auth.usage_data[username]
            
            # Initialize platform usage tracking
            if 'platform_usage' not in user_data:
                user_data['platform_usage'] = {}
            
            if platform not in user_data['platform_usage']:
                user_data['platform_usage'][platform] = {
                    'total_leads': 0,
                    'scraping_sessions': 0,
                    'search_terms': [],
                    'last_scraped': None,
                    'avg_leads_per_session': 0
                }
            
            # Update platform-specific usage
            platform_data = user_data['platform_usage'][platform]
            platform_data['total_leads'] += leads_found
            platform_data['scraping_sessions'] += 1
            platform_data['last_scraped'] = datetime.now().isoformat()
            
            # Calculate average leads per session
            if platform_data['scraping_sessions'] > 0:
                platform_data['avg_leads_per_session'] = round(
                    platform_data['total_leads'] / platform_data['scraping_sessions'], 1
                )
            
            # Track unique search terms (for quality analysis)
            if search_term and search_term not in platform_data['search_terms']:
                platform_data['search_terms'].append(search_term)
                # Keep only last 10 search terms per platform
                if len(platform_data['search_terms']) > 10:
                    platform_data['search_terms'] = platform_data['search_terms'][-10:]
            
            # Save updated data
            self.enhanced_auth.save_usage_data()
            
            print(f"📊 Usage tracked: {leads_found} leads from {platform.title()}")
            
            # Check for auto-verification
            self._check_auto_verification(username)
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error tracking usage for {platform}: {e}")
            return False
    
    def get_user_status_info(self, username: Optional[str]) -> Dict[str, Any]:
        """Get comprehensive user status information - DEBUG VERSION"""
        print(f"\n🔍 ==> get_user_status_info DEBUG START")
        print(f"    Username: {username}")
        print(f"    Enabled: {self.enabled}")
        
        if not self.enabled or not username:
            result = {"enabled": False, "message": "Usage tracking not available"}
            print(f"    ❌ EARLY EXIT: {result}")
            print(f"🔍 ==> get_user_status_info DEBUG END")
            return result
        
        try:
            # Check environment variables first
            force_auth = os.environ.get('FORCE_AUTHORIZATION', 'false').lower() == 'true'
            plan_override = os.environ.get('PLAN_OVERRIDE', '')
            user_plan = os.environ.get('USER_PLAN', '')
            limit_override = os.environ.get('SESSION_LIMIT_OVERRIDE', '')
            
            print(f"\n    🌍 ENVIRONMENT VARIABLES:")
            print(f"        FORCE_AUTHORIZATION: {os.environ.get('FORCE_AUTHORIZATION', 'NOT SET')}")
            print(f"        PLAN_OVERRIDE: {os.environ.get('PLAN_OVERRIDE', 'NOT SET')}")
            print(f"        USER_PLAN: {os.environ.get('USER_PLAN', 'NOT SET')}")
            print(f"        SESSION_LIMIT_OVERRIDE: {os.environ.get('SESSION_LIMIT_OVERRIDE', 'NOT SET')}")
            
            # Use override-aware methods if available
            if hasattr(self.enhanced_auth, 'get_user_status_with_overrides'):
                status = self.enhanced_auth.get_user_status_with_overrides(username)
                print(f"    Using get_user_status_with_overrides: {status}")
            else:
                status = self.enhanced_auth.get_user_status(username)
                print(f"    Using original get_user_status: {status}")
            
            if hasattr(self.enhanced_auth, 'get_download_limit_with_overrides'):
                download_limit = self.enhanced_auth.get_download_limit_with_overrides(username)
                print(f"    Using get_download_limit_with_overrides: {download_limit}")
            else:
                download_limit = self.enhanced_auth.get_download_limit(username)
                print(f"    Using original get_download_limit: {download_limit}")
            
            usage_data = self.enhanced_auth.usage_data.get(username, {})
            current_usage = usage_data.get('total_downloads', 0)
            
            print(f"    Status: {status}")
            print(f"    Download limit: {download_limit}")
            print(f"    Current usage: {current_usage}")
            
            # Apply environment overrides to remaining calculation
            if force_auth and plan_override:
                if plan_override.lower() == 'ultimate':
                    remaining = "Unlimited"
                    usage_percentage = 0
                    print(f"    🚀 OVERRIDE: Ultimate user - unlimited")
                elif plan_override.lower() == 'pro':
                    remaining = 2000 - current_usage  # Pro monthly limit
                    usage_percentage = (current_usage / 2000) * 100 if current_usage > 0 else 0
                    print(f"    🚀 OVERRIDE: Pro user - {remaining} remaining")
                else:
                    # Calculate normally
                    if download_limit == float('inf'):
                        remaining = "Unlimited"
                        usage_percentage = 0
                    else:
                        remaining = download_limit - current_usage
                        usage_percentage = (current_usage / download_limit) * 100 if download_limit > 0 else 0
            
            elif user_plan in ['pro', 'ultimate']:
                if user_plan == 'ultimate':
                    remaining = "Unlimited"
                    usage_percentage = 0
                    print(f"    🚀 ENV OVERRIDE: Ultimate user - unlimited")
                elif user_plan == 'pro':
                    remaining = 2000 - current_usage
                    usage_percentage = (current_usage / 2000) * 100 if current_usage > 0 else 0
                    print(f"    🚀 ENV OVERRIDE: Pro user - {remaining} remaining")
            
            else:
                # Calculate normally
                if download_limit == float('inf'):
                    remaining = "Unlimited"
                    usage_percentage = 0
                else:
                    remaining = download_limit - current_usage
                    usage_percentage = (current_usage / download_limit) * 100 if download_limit > 0 else 0
            
            print(f"    Final remaining: {remaining}")
            print(f"    Final usage percentage: {usage_percentage}")
            
            # Get platform breakdown
            platform_usage = usage_data.get('platform_usage', {})
            platform_summary = {}
            for platform, data in platform_usage.items():
                platform_summary[platform] = {
                    'leads': data.get('total_leads', 0),
                    'sessions': data.get('scraping_sessions', 0),
                    'avg_per_session': data.get('avg_leads_per_session', 0)
                }
            
            result = {
                "enabled": True,
                "status": status,
                "download_limit": download_limit,
                "current_usage": current_usage,
                "remaining_limit": remaining,
                "usage_percentage": round(usage_percentage, 1),
                "verified": usage_data.get('verified', False),
                "platform_usage": platform_summary,
                "bulk_exports": usage_data.get('bulk_exports', 0),
                "account_age_days": self._get_account_age_days(username)
            }
            
            print(f"    ✅ FINAL RESULT: {result}")
            print(f"🔍 ==> get_user_status_info DEBUG END")
            return result
            
        except Exception as e:
            result = {"enabled": False, "error": str(e)}
            print(f"    ❌ EXCEPTION: {e}")
            print(f"    ❌ RESULT: {result}")
            print(f"🔍 ==> get_user_status_info DEBUG END")
            return result
    
    def get_effective_user_plan(self, username: str) -> str:
        """Get the effective user plan considering environment overrides"""
        # Check environment overrides first
        force_auth = os.environ.get('FORCE_AUTHORIZATION', 'false').lower() == 'true'
        plan_override = os.environ.get('PLAN_OVERRIDE', '')
        user_plan = os.environ.get('USER_PLAN', '')
        
        if force_auth and plan_override:
            return plan_override.lower()
        elif user_plan:
            return user_plan.lower()
        
        # Fallback to auth system
        try:
            status = self.enhanced_auth.get_user_status(username)
            if status == "full_access":
                return "pro"
            elif status in ["starter_limited", "starter_monitored"]:
                return "starter"
        except:
            pass
            
        return "starter"
    
    def get_effective_download_limit(self, username: str) -> float:
        """Get effective download limit considering user plan and overrides"""
        plan = self.get_effective_user_plan(username)
        
        # Environment override for session limits
        limit_override = os.environ.get('SESSION_LIMIT_OVERRIDE', '')
        if limit_override.isdigit():
            return float(limit_override)
        
        # Plan-based limits
        if plan == "ultimate":
            return float('inf')
        elif plan == "pro":
            return 2000  # 2000 leads per month for pro
        elif plan == "starter":
            return 250    # 250 leads total for starter
        else:
            return 10    # 10 leads for free
    
    def apply_usage_limits(self, username: Optional[str], leads: list, platform: str) -> list:
        """
        Apply usage limits to scraping results
        FIXED: Proper demo user handling with 5-lead max
        """
        if not self.enabled or not username or not leads:
            return leads
        
        try:
            # 🎯 CHECK IF THIS IS A DEMO USER FIRST
            user_plan = os.environ.get('USER_PLAN', '')
            
            # Try to get user plan from credit system if not in environment
            if not user_plan:
                try:
                    from simple_credit_system import credit_system
                    user_info = credit_system.get_user_info(username)
                    if user_info:
                        user_plan = user_info.get('plan', 'demo')
                except:
                    user_plan = 'demo'  # Default to demo if can't determine
            
            print(f"🔍 apply_usage_limits for {username}:")
            print(f"   User plan: {user_plan}")
            print(f"   Leads found: {len(leads)}")
            
            # 🎯 DEMO USER SPECIAL HANDLING
            if user_plan == 'demo':
                print(f"📱 Demo user - applying 5-lead maximum")
                
                try:
                    from simple_credit_system import credit_system
                    
                    # Check how many demo leads are available
                    can_demo, remaining = credit_system.can_use_demo(username)
                    
                    print(f"📊 Demo limits:")
                    print(f"   Demo remaining: {remaining}")
                    print(f"   Leads found: {len(leads)}")
                    
                    if not can_demo or remaining <= 0:
                        print(f"❌ No demo leads remaining - returning 0 leads")
                        return []
                    
                    # Limit to remaining demo leads (max 5 total for demo users)
                    max_demo_leads = min(len(leads), remaining, 5)
                    limited_leads = leads[:max_demo_leads]
                    
                    print(f"📱 Demo user result:")
                    print(f"   Original leads: {len(leads)}")
                    print(f"   Demo remaining: {remaining}")
                    print(f"   Final leads: {len(limited_leads)}")
                    
                    return limited_leads
                    
                except Exception as e:
                    print(f"⚠️ Demo limit error: {e}")
                    # Fallback: limit to 5 for demo users
                    demo_max = min(len(leads), 5)
                    print(f"📱 Demo fallback: limiting to {demo_max} leads")
                    return leads[:demo_max]
            
            # 🔄 REGULAR USER HANDLING (non-demo)
            print(f"💎 Regular user - checking general limits")
            
            # 🚀 CRITICAL: Check environment overrides FIRST
            force_auth = os.environ.get('FORCE_AUTHORIZATION', 'false').lower() == 'true'
            plan_override = os.environ.get('PLAN_OVERRIDE', '')
            limit_override = os.environ.get('SESSION_LIMIT_OVERRIDE', '')
            
            print(f"   Force auth: {force_auth}")
            print(f"   Plan override: {plan_override}")
            print(f"   Limit override: {limit_override}")
            
            # 🚀 OVERRIDE 1: Direct session limit override
            if limit_override and limit_override.isdigit():
                session_limit = int(limit_override)
                if len(leads) <= session_limit:
                    print(f"✅ Override limit OK: {len(leads)}/{session_limit} leads")
                    return leads
                else:
                    print(f"⚠️ Override limit applied: {session_limit} leads")
                    return leads[:session_limit]
            
            # 🚀 OVERRIDE 2: Force authorization bypass
            if force_auth and plan_override:
                if plan_override.lower() == 'ultimate':
                    print(f"✅ Ultimate override - no limits applied")
                    return leads
                elif plan_override.lower() == 'pro':
                    pro_limit = 500  # Pro session limit
                    if len(leads) <= pro_limit:
                        print(f"✅ Pro override OK: {len(leads)}/{pro_limit} leads")
                        return leads
                    else:
                        print(f"⚠️ Pro override limit: {pro_limit} leads")
                        return leads[:pro_limit]
            
            # 🚀 OVERRIDE 3: User plan environment variable
            if user_plan in ['pro', 'ultimate']:
                plan_limits = {'pro': 500, 'ultimate': 9999}
                session_limit = plan_limits[user_plan]
                
                if len(leads) <= session_limit:
                    print(f"✅ {user_plan.title()} plan OK: {len(leads)}/{session_limit} leads")
                    return leads
                else:
                    print(f"⚠️ {user_plan.title()} plan limit: {session_limit} leads")
                    return leads[:session_limit]
            
            # 🔄 FALLBACK: Use auth system (with overrides if available)
            print(f"📋 Checking auth system limits for {username}")
            
            # Try to use override-aware methods if available
            if hasattr(self.enhanced_auth, 'get_download_limit_with_overrides'):
                download_limit = self.enhanced_auth.get_download_limit_with_overrides(username)
                print(f"📊 Auth system limit (with overrides): {download_limit}")
            else:
                download_limit = self.enhanced_auth.get_download_limit(username)
                print(f"📊 Auth system limit (original): {download_limit}")
            
            # Get current usage
            current_usage = self.enhanced_auth.usage_data.get(username, {}).get('total_downloads', 0)
            print(f"📈 Current usage: {current_usage}")
            
            # Apply limits
            if download_limit != float('inf'):
                max_allowed = max(0, download_limit - current_usage)
                
                if len(leads) > max_allowed:
                    print(f"⚠️ Auth system limiting {platform} results to {max_allowed} leads")
                    return leads[:max_allowed]
            
            print(f"✅ No limits applied - returning {len(leads)} leads")
            return leads
            
        except Exception as e:
            print(f"⚠️ Error applying limits for {platform}: {e}")
            # In case of error, apply environment overrides as fallback
            user_plan = os.environ.get('USER_PLAN', 'free')
            if user_plan == 'demo':
                # For demo users, always limit to 5 on error
                demo_max = min(len(leads), 5)
                print(f"🚀 Error fallback: demo user gets max {demo_max} leads")
                return leads[:demo_max]
            elif user_plan in ['pro', 'ultimate']:
                print(f"🚀 Error fallback: {user_plan} user gets full leads")
                return leads
            
            return leads
    
    def _check_auto_verification(self, username: str):
        """Check if user should be auto-verified based on usage patterns"""
        try:
            usage_data = self.enhanced_auth.usage_data.get(username, {})
            
            if usage_data.get('verified', False):
                return  # Already verified
            
            total_downloads = usage_data.get('total_downloads', 0)
            platform_usage = usage_data.get('platform_usage', {})
            total_sessions = sum(p.get('scraping_sessions', 0) for p in platform_usage.values())
            unique_platforms = len(platform_usage)
            
            # Auto-verify conditions
            should_verify = (
                total_downloads >= 25 and  # At least 25 downloads
                total_sessions >= 3 and    # At least 3 scraping sessions
                unique_platforms >= 2      # Used at least 2 different platforms
            )
            
            if should_verify:
                self.enhanced_auth.verify_user(username, "auto_verified_pattern")
                print(f"🎉 User {username} auto-verified based on usage pattern!")
                
        except Exception as e:
            print(f"⚠️ Error checking auto-verification: {e}")
    
    def _get_account_age_days(self, username: str) -> int:
        """Get account age in days"""
        try:
            user = self.enhanced_auth.users.get(username, {})
            reg_date = datetime.fromisoformat(user.get('created_at', datetime.now().isoformat()))
            return (datetime.now() - reg_date).days
        except:
            return 0
    
    def get_username_from_env(self) -> Optional[str]:
        """Get username from environment variables or session"""
        # Try environment variable first (set by frontend)
        username = os.environ.get('SCRAPER_USERNAME')
        
        if username:
            return username
        
        # Try to get from streamlit session (if available)
        try:
            import streamlit as st
            return st.session_state.get('username')
        except:
            pass
        
        return None


# Global instance for easy importing
usage_tracker = UsageTracker()


# Convenience functions for scrapers
def check_user_limits(username: str, estimated_leads: int, platform: str = "unknown") -> Tuple[bool, str]:
    """Check user limits with demo support"""

    # ADD THIS AT THE BEGINNING:
    if os.environ.get('BYPASS_INDIVIDUAL_AUTH') == 'true':
        pre_auth_user = os.environ.get('PRE_AUTHORIZED_USER', '')
        authorized_leads = os.environ.get('AUTHORIZED_LEADS', '0')
        
        if pre_auth_user == username:
            print(f"✅ Usage tracker bypassed - pre-authorized by main scraper")
            print(f"📊 Auth system (with overrides) - Limit: 50, Status: authorized")
            print(f"📈 Current usage: 0")
            return True, f"Pre-authorized for {authorized_leads} leads"
    
    if not username:
        print(f"⚠️ No username provided")
        return False, "No username provided"
    
    try:
        # Import the credit system
        from simple_credit_system import credit_system
        
        # Get user info
        user_info = credit_system.get_user_info(username)
        if not user_info:
            print(f"❌ User {username} not found in system")
            return False, f"User {username} not found"
        
        user_plan = user_info.get('plan', 'demo')
        print(f"📋 User {username} plan: {user_plan}")
        
        # DEMO USER HANDLING
        if user_plan == 'demo':
            can_demo, remaining = credit_system.can_use_demo(username)
            
            print(f"📱 Demo user check:")
            print(f"   Can use demo: {can_demo}")
            print(f"   Remaining: {remaining}")
            print(f"   Estimated: {estimated_leads}")
            
            if not can_demo:
                return False, f"❌ Demo leads exhausted"
            
            if estimated_leads > remaining:
                # For demo users, limit to remaining demo leads
                print(f"⚠️ Limiting demo user to {remaining} leads instead of {estimated_leads}")
                return True, f"✅ Demo authorized for {remaining} leads (limited from {estimated_leads})"
            
            return True, f"✅ Demo authorized for {estimated_leads} leads ({remaining} available)"
        
        # PAID USER HANDLING
        else:
            can_proceed, message, current_credits = credit_system.check_credits(username, estimated_leads)
            
            print(f"💎 Paid user check:")
            print(f"   Plan: {user_plan}")
            print(f"   Credits: {current_credits}")
            print(f"   Estimated: {estimated_leads}")
            print(f"   Can proceed: {can_proceed}")
            
            if not can_proceed:
                return False, f"❌ Insufficient credits: {message}"
            
            return True, f"✅ Authorized for {estimated_leads} leads ({current_credits} credits available)"
    
    except Exception as e:
        print(f"❌ Authorization error: {str(e)}")
        return False, f"Authorization error: {str(e)}"


def track_results(platform: str, leads_found: int, search_term: str = "") -> bool:
    """Convenience function to track scraping results"""
    username = usage_tracker.get_username_from_env()
    return usage_tracker.track_scraping_results(username, platform, leads_found, search_term)


def apply_limits(leads: list, platform: str) -> list:
    """Convenience function to apply usage limits to results"""
    username = usage_tracker.get_username_from_env()
    return usage_tracker.apply_usage_limits(username, leads, platform)


def get_status_info() -> Dict[str, Any]:
    """Convenience function to get user status info"""
    username = usage_tracker.get_username_from_env()
    return usage_tracker.get_user_status_info(username)


# Helper function for scrapers
def setup_scraper_with_limits(platform: str, estimated_leads: int, search_term: str = "") -> Tuple[bool, str, Optional[str]]:
    """
    Setup scraper with automatic limit checking and user identification
    
    Returns:
        Tuple of (can_proceed: bool, message: str, username: Optional[str])
    """
    username = usage_tracker.get_username_from_env()
    
    if not username:
        print(f"⚠️ No username provided for {platform} scraper - running without usage tracking")
        return True, "No username - proceeding without limits", None
    
    can_proceed, message = usage_tracker.check_user_limits(username, estimated_leads, platform)
    
    if can_proceed:
        print(f"🔐 {platform.title()} scraper authorized for user: {username}")
    else:
        print(f"❌ {platform.title()} scraper blocked for user: {username}")
        print(f"   Reason: {message}")
    
    return can_proceed, message, username


def finalize_scraper_results(platform: str, leads: list, search_term: str = "", username: Optional[str] = None) -> list:
    """
    Finalize scraper results with tracking and limit application
    
    Args:
        platform: Platform name
        leads: List of scraped leads
        search_term: Search term used
        username: Username (optional, will auto-detect if not provided)
        
    Returns:
        list: Final list of leads (potentially limited)
    """
    if username is None:
        username = usage_tracker.get_username_from_env()
    
    if not leads:
        return leads
    
    # Apply usage limits
    limited_leads = usage_tracker.apply_usage_limits(username, leads, platform)
    
    # Track the results
    if username:
        usage_tracker.track_scraping_results(username, platform, len(limited_leads), search_term)
    
    return limited_leads