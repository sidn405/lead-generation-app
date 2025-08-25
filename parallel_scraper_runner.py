# parallel_scraper_runner.py - Run multiple scrapers simultaneously

import subprocess
import threading
import time
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class ParallelScraperRunner:
    def __init__(self, username, user_plan, search_term, max_scrolls):
        self.username = username
        self.user_plan = user_plan
        self.search_term = search_term
        self.max_scrolls = max_scrolls
        self.results = {}
        self.start_time = None
        
    def setup_environment(self):
        """Setup environment variables for all scrapers"""
        env = os.environ.copy()
        env.update({
            'SCRAPER_USERNAME': self.username,
            'USER_PLAN': self.user_plan,
            'FRONTEND_SEARCH_TERM': self.search_term,
            'FORCE_AUTHORIZATION': 'true',
            'PLAN_OVERRIDE': self.user_plan,
            'BYPASS_INDIVIDUAL_AUTH': 'true',
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONUTF8': '1'
        })
        return env
    
    def run_single_scraper(self, platform):
        """Run a single platform scraper"""
        print(f"🚀 Starting {platform.title()} scraper...")
        
        start_time = time.time()
        env = self.setup_environment()
        
        # Map platform names to scraper files
        scraper_files = {
            'twitter': 'twitter_scraper.py',
            'facebook': 'facebook_scraper.py',
            'linkedin': 'linkedin_scraper.py',
            'youtube': 'youtube_scraper.py',
            'tiktok': 'tiktok_scraper.py',
            'instagram': 'instagram_scraper.py',
            'medium': 'medium_scraper_ec.py',
            'reddit': 'reddit_scraper_ec.py'
        }
        
        scraper_file = scraper_files.get(platform)
        if not scraper_file:
            return {
                'platform': platform,
                'success': False,
                'error': f"Unknown platform: {platform}",
                'duration': 0,
                'leads': 0
            }
        
        if not os.path.exists(scraper_file):
            return {
                'platform': platform,
                'success': False,
                'error': f"Scraper file not found: {scraper_file}",
                'duration': 0,
                'leads': 0
            }
        
        try:
            # Run the scraper
            result = subprocess.run(
                ['python', scraper_file],
                capture_output=True,
                text=True,
                env=env,
                timeout=600  # 10 minutes per scraper
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                # Try to count leads from output files
                leads_count = self.count_recent_leads(platform)
                
                print(f"✅ {platform.title()} completed in {duration:.1f}s - {leads_count} leads")
                
                return {
                    'platform': platform,
                    'success': True,
                    'duration': duration,
                    'leads': leads_count,
                    'stdout': result.stdout[-500:] if result.stdout else '',  # Last 500 chars
                    'stderr': result.stderr[-500:] if result.stderr else ''
                }
            else:
                print(f"❌ {platform.title()} failed after {duration:.1f}s")
                
                return {
                    'platform': platform,
                    'success': False,
                    'duration': duration,
                    'leads': 0,
                    'error': f"Exit code: {result.returncode}",
                    'stdout': result.stdout[-500:] if result.stdout else '',
                    'stderr': result.stderr[-500:] if result.stderr else ''
                }
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ {platform.title()} timed out after {duration:.1f}s")
            
            return {
                'platform': platform,
                'success': False,
                'duration': duration,
                'leads': 0,
                'error': "Timeout (10 minutes)"
            }
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 {platform.title()} crashed after {duration:.1f}s: {e}")
            
            return {
                'platform': platform,
                'success': False,
                'duration': duration,
                'leads': 0,
                'error': str(e)
            }
    
    def count_recent_leads(self, platform):
        """Count leads from recent CSV files for this platform"""
        import glob
        from datetime import datetime, timedelta
        
        # Look for recent CSV files for this platform
        patterns = [
            f"*{platform}*leads*.csv",
            f"{platform}_leads_*.csv",
            f"{platform}_unified_leads_*.csv"
        ]
        
        recent_files = []
        cutoff_time = datetime.now() - timedelta(minutes=15)
        
        for pattern in patterns:
            files = glob.glob(pattern)
            for file in files:
                try:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file))
                    if mod_time > cutoff_time:
                        recent_files.append(file)
                except:
                    continue
        
        if recent_files:
            # Use the most recent file
            latest_file = max(recent_files, key=os.path.getmtime)
            
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f) - 1  # Subtract header
                return max(0, line_count)
            except:
                return 0
        
        return 0
    
    def save_session_summary(self, total_duration, successful_platforms, total_leads):
        """Save session summary for the frontend"""
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'user': self.username,
                'plan': self.user_plan,
                'search_term': self.search_term,
                'execution_mode': 'parallel',
                'total_duration_seconds': total_duration,
                'platforms_run': list(self.results.keys()),
                'total_leads': total_leads,
                'successful_platforms': successful_platforms,
                'results_by_platform': {
                    platform: {
                        'success': result['success'],
                        'leads': result['leads'],
                        'duration': result['duration']
                    }
                    for platform, result in self.results.items()
                }
            }
            
            with open('scraping_session_summary.json', 'w') as f:
                json.dump(summary, f, indent=2)
            
            print(f"💾 Session summary saved to: scraping_session_summary.json")
            
        except Exception as e:
            print(f"⚠️ Could not save session summary: {e}")

    def finalize_session(self):
        """Finalize session - consume credits and update dashboard"""
        
        print(f"\n🎯 FINALIZING PARALLEL SESSION...")
        
        # Calculate total leads
        total_leads = sum(r['leads'] for r in self.results.values())
        
        if total_leads > 0 and self.user_plan != 'demo':
            try:
                from postgres_credit_system import credit_system
                
                # Get current credits
                user_info = credit_system.get_user_info(self.username)
                current_credits = user_info.get('credits', 0) if user_info else 0
                print(f"💎 Current credits: {current_credits}")
                
                total_consumed = 0

                for platform, result in self.results.items():
                    if result['success'] and result['leads'] > 0:
                        platform_leads = result['leads']
                        platform_name = platform.lower()

                        try:
                            # ✅ FIXED: Pass all 4 required parameters
                            # consume_credits(username, credits_used, leads_downloaded, platform)
                            success = credit_system.consume_credits(
                                self.username,           # username: str
                                platform_leads,          # credits_used: int  
                                platform_leads,          # leads_downloaded: int (same as credits_used)
                                platform_name            # platform: str
                            )

                            if success:
                                total_consumed += platform_leads
                                print(f"✅ {platform.title()}: {platform_leads} credits consumed")
                            else:
                                print(f"❌ {platform.title()}: Credit consumption failed")
                                
                        except Exception as platform_error:
                            print(f"❌ {platform.title()}: Credit error - {platform_error}")

                if total_consumed > 0:
                    try:
                        credit_system.save_data()  # Force save
                        
                        # Verify consumption
                        updated_info = credit_system.get_user_info(self.username)
                        new_credits = updated_info.get('credits', 0) if updated_info else 0
                        actual_consumed = current_credits - new_credits
                        
                        print(f"✅ Total credits consumed: {actual_consumed}")
                        print(f"💎 Remaining credits: {new_credits}")
                    except Exception as save_error:
                        print(f"❌ Save error: {save_error}")
                else:
                    print(f"❌ No credits consumed")

            except ImportError:
                print(f"❌ Credit system not available")
            except Exception as e:
                print(f"❌ Credit system error: {e}")
        
        # Update dashboard data
        try:
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'username': self.username,
                'search_term': self.search_term,
                'total_leads': total_leads,
                'platforms': {platform: r['leads'] for platform, r in self.results.items()},
                'session_complete': True
            }
            
            # Save session data for dashboard
            with open('latest_session.json', 'w') as f:
                json.dump(dashboard_data, f, indent=2)
            
            # Update empire totals
            empire_file = f'empire_totals_{self.username}.json'
            if os.path.exists(empire_file):
                with open(empire_file, 'r') as f:
                    empire_totals = json.load(f)
            else:
                empire_totals = {'total_empire': 0, 'platforms': {}}
            
            # Add this session's results
            for platform, result in self.results.items():
                count = result['leads']
                empire_totals['platforms'][platform] = empire_totals['platforms'].get(platform, 0) + count
                empire_totals['total_empire'] += count
            
            empire_totals['last_updated'] = datetime.now().isoformat()
            
            with open(empire_file, 'w') as f:
                json.dump(empire_totals, f, indent=2)
            
            print(f"📊 Dashboard updated!")
            print(f"🏆 Total Empire: {empire_totals['total_empire']}")
            
        except Exception as e:
            print(f"❌ Dashboard error: {e}")

    def log_platform_consumption(self, platform, leads):
        """Log platform-specific consumption when the credit system doesn't track platforms"""
        try:
            consumption_log = f'platform_consumption_{self.username}.json'
            
            if os.path.exists(consumption_log):
                with open(consumption_log, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = {'total_by_platform': {}, 'sessions': []}
            
            # Update platform totals
            log_data['total_by_platform'][platform] = log_data['total_by_platform'].get(platform, 0) + leads
            
            # Add session record
            log_data['sessions'].append({
                'timestamp': datetime.now().isoformat(),
                'platform': platform,
                'leads': leads,
                'search_term': self.search_term
            })
            
            with open(consumption_log, 'w') as f:
                json.dump(log_data, f, indent=2)
                
            print(f"📝 Platform consumption logged: {platform} = {leads}")
            
        except Exception as e:
            print(f"⚠️ Could not log platform consumption: {e}")

    def save_session_summary(self, total_duration, successful_platforms, total_leads):
        """Save session summary for the frontend"""

        try:
            # ✅ CREATE CLEAN PLATFORM BREAKDOWN
            clean_results_by_platform = {}

            for platform, result in self.results.items():
                # Clean platform name for display
                clean_platform = platform.lower()

                clean_results_by_platform[clean_platform] = {
                    'success': result['success'],
                    'leads': result['leads'],
                    'duration': result['duration']
                }

            summary = {
                'timestamp': datetime.now().isoformat(),
                'user': self.username,
                'plan': self.user_plan,
                'search_term': self.search_term,
                'execution_mode': 'multi_platform',  # ✅ Changed from 'parallel'
                'total_duration_seconds': total_duration,
                'platforms_run': list(self.results.keys()),
                'total_leads': total_leads,
                'successful_platforms': successful_platforms,
                'results_by_platform': clean_results_by_platform  # ✅ Use clean names
            }

            with open('scraping_session_summary.json', 'w') as f:
                json.dump(summary, f, indent=2)

            print(f"💾 Session summary saved to: scraping_session_summary.json")

        except Exception as e:
            print(f"⚠️ Could not save session summary: {e}")

    def run_parallel(self, platforms, max_workers=None):
        """Run multiple scrapers in parallel"""
        print(f"🚀 PARALLEL SCRAPER LAUNCH")
        print(f"📋 Platforms: {', '.join(platforms)}")
        print(f"👤 User: {self.username} ({self.user_plan})")
        print(f"🔍 Search: '{self.search_term}'")
        print(f"📜 Intensity: {self.max_scrolls}")
        print("=" * 60)
        
        if max_workers is None:
            max_workers = min(len(platforms), 7)  # Max 4 concurrent scrapers
        
        self.start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scraper tasks
            future_to_platform = {
                executor.submit(self.run_single_scraper, platform): platform 
                for platform in platforms
            }
            
            # Process results as they complete
            for future in as_completed(future_to_platform):
                platform = future_to_platform[future]
                try:
                    result = future.result()
                    self.results[platform] = result
                    
                    if result['success']:
                        print(f"🎉 {platform.title()}: {result['leads']} leads in {result['duration']:.1f}s")
                    else:
                        print(f"💥 {platform.title()}: FAILED - {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"💥 {platform.title()}: CRASHED - {e}")
                    self.results[platform] = {
                        'platform': platform,
                        'success': False,
                        'error': str(e),
                        'duration': 0,
                        'leads': 0
                    }
        
        # Calculate final statistics
        total_duration = time.time() - self.start_time
        successful_platforms = sum(1 for r in self.results.values() if r['success'])
        total_leads = sum(r['leads'] for r in self.results.values())
        
        print("\n" + "=" * 60)
        print(f"🎉 PARALLEL SCRAPING COMPLETE!")
        print(f"⏰ Total time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        print(f"✅ Successful platforms: {successful_platforms}/{len(platforms)}")
        print(f"📊 Total leads: {total_leads}")
        
        # Show results by platform
        print(f"\n📋 RESULTS BY PLATFORM:")
        for platform, result in self.results.items():
            status = "✅" if result['success'] else "❌"
            duration = result['duration']
            leads = result['leads']
            print(f"  {status} {platform.title()}: {leads} leads ({duration:.1f}s)")
            
            if not result['success'] and 'error' in result:
                print(f"      Error: {result['error']}")

        # Test the class structure
        self.test_method()
        
        # Save summary
        self.save_session_summary(total_duration, successful_platforms, total_leads)

        # ✅ ADD THIS LINE - finalize the session
        self.finalize_session()
        
        total_leads = sum(r['leads'] for r in self.results.values())
        
        # --- DEMO CREDIT CONSUMPTION (so UI shows used 5/5) ---
        if total_leads > 0 and self.user_plan == 'demo':
            try:
                from postgres_credit_system import credit_system
                consumed = 0
                for _ in range(total_leads):
                    if credit_system.consume_demo_lead(self.username):
                        consumed += 1
                    else:
                        break
                try:
                    credit_system.save_data()
                except Exception:
                    pass
                print(f"📱 Demo consumption: used {consumed} of {total_leads} generated")
            except Exception as e:
                print(f"❌ Demo credit error: {e}")
                
        # --- build a stats delta from this run ---
        from datetime import datetime
        from pathlib import Path
        import json, os

        now_iso = datetime.utcnow().isoformat()
        platform_counts = {p: r.get("leads", 0) for p, r in (self.results or {}).items()}

        run_summary = {
            "timestamp": now_iso,
            "plan": self.user_plan,
            "search_term": self.search_term,
            "platforms_run": list(platform_counts.keys()),
            "platform_counts": platform_counts,
            "total_leads": int(total_leads),
            "duration_sec": int(self.total_duration_sec or 0),
            "success_count": sum(1 for r in (self.results or {}).values() if r.get("leads", 0) > 0),
            "attempted_count": len(self.results or {}),
        }

        def _default_stats():
            return {
                "totals": {"leads": 0, "campaigns": 0, "credits_used": 0},
                "platforms": {},          # e.g., "twitter": {"leads": 0, "last_run": "..."}
                "last_session": {},       # copy of run_summary
            }

        # --- merge into user record via credit_system ---
        try:
            from postgres_credit_system import credit_system
            info = credit_system.get_user_info(self.username) or {}
            stats = info.get("stats") or _default_stats()

            # totals
            stats["totals"]["leads"]     = int(stats["totals"].get("leads", 0)) + int(total_leads)
            stats["totals"]["campaigns"] = int(stats["totals"].get("campaigns", 0)) + 1

            # if you debit credits elsewhere, keep this as a display-only mirror
            stats["totals"]["credits_used"] = int(stats["totals"].get("credits_used", 0))

            # per-platform
            platforms_node = stats.setdefault("platforms", {})
            for p, c in platform_counts.items():
                node = platforms_node.setdefault(p, {"leads": 0, "last_run": None})
                node["leads"] = int(node.get("leads", 0)) + int(c)
                node["last_run"] = now_iso

            # last session snapshot
            stats["last_session"] = run_summary

            info["stats"] = stats
            credit_system.save_user_info(self.username, info)

            # file fallback (handy for Lead Results / refresh w/o DB hit)
            try:
                out = Path(f"client_configs/{self.username}_stats.json")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"[stats file] write failed: {e}")

            print(f"[stats] updated for {self.username}: leads+={total_leads}, campaigns+1")
        except Exception as e:
            print(f"[stats] update failed: {e}")



            return self.results
    
    
    
    def test_method(self):  # ← Same indentation as other methods
        """Test method to verify class structure"""
        print(f"✅ Test: username = {self.username}")
        print(f"✅ Test: search_term = {self.search_term}")
        return True
    
# --- Local, stable env reader: ALWAYS returns (username:str, plan:str, credits:int)
def _env_user_triplet():
    username = os.getenv("SCRAPER_USERNAME") or ""
    plan = (os.getenv("USER_PLAN")
            or os.getenv("SCRAPER_USER_PLAN")
            or "demo")
    if isinstance(plan, (tuple, list)):
        plan = plan[0] if plan else "demo"
    plan = str(plan).strip().lower() or "demo"

    credits_raw = (os.getenv("USER_CREDITS")
                   or os.getenv("SCRAPER_CREDITS")
                   or "0")
    try:
        credits = int(str(credits_raw).strip())
    except Exception:
        credits = 0

    return username, plan, credits


# Integration with your existing frontend
def run_parallel_scrapers(platforms, search_term, max_scrolls, username, user_plan):
    """
    Drop-in replacement for your sequential scraper
    Call this instead of run_all_platform_scrapers()
    """
    # Use environment-based user info instead of session state
    env_username, env_plan, env_credits = _env_user_triplet()
    active_username = env_username or username
    active_plan = env_plan or user_plan
    print(f"Scraping as user: {active_username} ({active_plan} plan)")
    
    runner = ParallelScraperRunner(active_username, active_plan, search_term, max_scrolls)
    results = runner.run_parallel(platforms)
 
    # Convert to format expected by frontend
    frontend_results = {}
    for platform, result in results.items():
        if result['success']:
            # Create fake leads list (since we don't return actual lead objects)
            fake_leads = [{'id': i, 'platform': platform} for i in range(result['leads'])]
            frontend_results[platform] = fake_leads
        else:
            frontend_results[platform] = []
    
    return frontend_results

# Update your frontend launch button
def update_frontend_launch_button():
    """Code to replace in your frontend launch button"""
    
    frontend_code = '''
# Replace this in your frontend launch button:

# OLD (Sequential):
# all_results = run_all_platform_scrapers(platforms)

# NEW (Parallel):
all_results = run_parallel_scrapers(
    platforms=instant_platforms,  # ['twitter', 'facebook', 'youtube']
    search_term=search_term,
    max_scrolls=max_scrolls,
    username=username,
    user_plan=user_plan
)

# Rest of your code stays the same...
if all_results:
    total_leads = sum(len(results) if results else 0 for results in all_results.values())
    st.success(f"🎉 Generated {total_leads} leads in parallel!")
'''
    
    print("📋 FRONTEND UPDATE CODE:")
    print(frontend_code)

# Quick test function
def test_parallel_scrapers():
    """Test the parallel scraper with sample data"""
    
    print("🧪 TESTING PARALLEL SCRAPERS...")
    
    # Test with safe platforms
    test_platforms = ['twitter', 'medium']  # Start small
    
    runner = ParallelScraperRunner(
        username='test_user',
        user_plan='ultimate',
        search_term='crypto trader',
        max_scrolls=3  # Small test
    )
    
    results = runner.run_parallel(test_platforms, max_workers=2)
    
    print(f"🧪 Test completed!")
    return results

if __name__ == "__main__":
    # Demo/test mode
    print("🚀 Parallel Scraper Runner")
    print("Choose mode:")
    print("1. Test mode (small test)")
    print("2. Show frontend integration code")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        test_parallel_scrapers()
    elif choice == "2":
        update_frontend_launch_button()
    else:
        print("💡 Usage examples:")
        print("  python parallel_scraper_runner.py")
        print("  Or import and use run_parallel_scrapers() in your app")