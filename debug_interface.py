# debug_interface.py - Streamlit debug interface for production issues
import streamlit as st
import json
from datetime import datetime
from pathlib import Path
import traceback

def show_debug_interface():
    """Show comprehensive debug interface in Streamlit"""
    
    st.title("🔧 Production Debug Center")
    st.markdown("---")
    
    # Quick action buttons
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 Run Full Diagnosis"):
            run_full_diagnosis()
    
    with col2:
        if st.button("🛠️ Quick Fix JSON"):
            quick_fix_json_issues()
    
    with col3:
        if st.button("📁 Fix Directories"):
            fix_missing_directories()
    
    with col4:
        if st.button("🚨 Emergency Reset"):
            emergency_reset_data()
    
    st.markdown("---")
    
    # Debug tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 System Status", 
        "🤖 Scraper Test", 
        "📄 File Inspector", 
        "🔧 Manual Fixes",
        "📊 Debug Logs"
    ])
    
    with tab1:
        show_system_status()
    
    with tab2:
        show_scraper_testing()
    
    with tab3:
        show_file_inspector()
    
    with tab4:
        show_manual_fixes()
    
    with tab5:
        show_debug_logs()

def run_full_diagnosis():
    """Run comprehensive system diagnosis"""
    st.subheader("🔍 Running Full System Diagnosis...")
    
    with st.spinner("Analyzing system..."):
        try:
            from debug_system import run_production_debug
            debug_results = run_production_debug()
            
            st.success("✅ Diagnosis completed!")
            
            # Show summary
            results = debug_results["results"]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Debug Entries", len(results["debug_log"]))
            with col2:
                st.metric("Fixes Applied", len(results["fixes_applied"]))
            
            # Show fixes applied
            if results["fixes_applied"]:
                st.subheader("🛠️ Fixes Applied:")
                for fix in results["fixes_applied"]:
                    st.success(f"✅ {fix}")
            
            # Show debug log
            with st.expander("📋 Full Debug Log"):
                for log_entry in results["debug_log"]:
                    if "ERROR" in log_entry:
                        st.error(log_entry)
                    elif "WARNING" in log_entry:
                        st.warning(log_entry)
                    else:
                        st.info(log_entry)
            
            # Store results in session state
            st.session_state['last_debug_results'] = debug_results
            
        except Exception as e:
            st.error(f"❌ Diagnosis failed: {e}")
            st.code(traceback.format_exc())

def quick_fix_json_issues():
    """Quick fix for JSON file issues"""
    st.subheader("🛠️ Quick Fix: JSON Files")
    
    with st.spinner("Fixing JSON files..."):
        try:
            from debug_system import quick_fix_json_files
            fixes = quick_fix_json_files()
            
            if fixes:
                st.success(f"✅ Applied {len(fixes)} JSON fixes:")
                for fix in fixes:
                    st.info(f"🔧 {fix}")
            else:
                st.info("ℹ️ No JSON fixes needed - files are healthy")
                
        except Exception as e:
            st.error(f"❌ JSON fix failed: {e}")

def fix_missing_directories():
    """Fix missing directories"""
    st.subheader("📁 Quick Fix: Missing Directories")
    
    with st.spinner("Creating missing directories..."):
        try:
            from debug_system import quick_fix_missing_dirs
            fixes = quick_fix_missing_dirs()
            
            if fixes:
                st.success(f"✅ Created {len(fixes)} directories:")
                for fix in fixes:
                    st.info(f"📁 {fix}")
            else:
                st.info("ℹ️ No directories needed - all exist")
                
        except Exception as e:
            st.error(f"❌ Directory fix failed: {e}")

def emergency_reset_data():
    """Emergency reset of user data"""
    st.subheader("🚨 Emergency Data Reset")
    
    st.warning("⚠️ This will reset all user data and create backups")
    
    if st.button("🔴 CONFIRM EMERGENCY RESET", type="primary"):
        with st.spinner("Performing emergency reset..."):
            try:
                from debug_system import emergency_reset_user_data
                result = emergency_reset_user_data()
                
                if "✅" in result:
                    st.success(result)
                    st.info("You can now restart the app with clean data")
                else:
                    st.error(result)
                    
            except Exception as e:
                st.error(f"❌ Emergency reset failed: {e}")

def show_system_status():
    """Show current system status"""
    st.subheader("🖥️ System Status")
    
    # Python environment
    import sys
    import os
    from pathlib import Path
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Python Environment:**")
        st.code(f"""
Python: {sys.version.split()[0]}
Working Dir: {os.getcwd()}
Home Dir: {Path.home()}
        """)
    
    with col2:
        st.write("**File System:**")
        
        # Check file existence
        important_files = [
            "simple_credit_system.py",
            "users_credits.json",
            "transactions.json"
        ]
        
        for filename in important_files:
            if Path(filename).exists():
                st.success(f"✅ {filename}")
            else:
                st.error(f"❌ {filename}")
    
    # Credit system status
    st.write("**Credit System Status:**")
    try:
        from simple_credit_system import credit_system
        if credit_system:
            health = credit_system.get_system_health()
            
            if health["status"] == "healthy":
                st.success("✅ Credit System: Healthy")
            else:
                st.warning(f"⚠️ Credit System: {health['status']}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Users", health.get("users_count", 0))
            with col2:
                st.metric("Transactions", health.get("transactions_count", 0))
            with col3:
                st.metric("Issues", len(health.get("issues", [])))
                
        else:
            st.error("❌ Credit system not initialized")
            
    except Exception as e:
        st.error(f"❌ Credit system error: {e}")

def show_scraper_testing():
    """Show scraper testing interface"""
    st.subheader("🤖 Scraper Testing")
    
    # Platform selection
    platform = st.selectbox("Select Platform to Test:", [
        "instagram", "twitter", "linkedin", "tiktok", "facebook", "youtube", "medium", "reddit"
    ])
    
    username = st.text_input("Test Username:", value="test_user")
    
    if st.button(f"🧪 Test {platform.title()} Scraper"):
        with st.spinner(f"Testing {platform} scraper..."):
            try:
                from debug_system import ProductionDebugger
                debugger = ProductionDebugger()
                
                # Test scraper
                success = debugger.run_scraper_test(platform, username)
                
                if success:
                    st.success(f"✅ {platform.title()} scraper test passed!")
                else:
                    st.error(f"❌ {platform.title()} scraper test failed!")
                
                # Show debug log
                with st.expander("📋 Test Log"):
                    for log_entry in debugger.debug_log:
                        if "ERROR" in log_entry:
                            st.error(log_entry)
                        elif "WARNING" in log_entry:
                            st.warning(log_entry)
                        else:
                            st.info(log_entry)
                        
            except Exception as e:
                st.error(f"❌ Scraper test failed: {e}")
                st.code(traceback.format_exc())
    
    # Show available scrapers
    st.write("**Available Scraper Files:**")
    scraper_files = [
        "instagram_scraper.py",
        "twitter_scraper.py", 
        "linkedin_scraper.py",
        "tiktok_scraper.py",
        "facebook_scraper.py",
        "youtube_scraper.py",
        "medium_scraper_ec",
        "reddit_scraper_ec.py"
    ]
    
    for scraper_file in scraper_files:
        if Path(scraper_file).exists():
            st.success(f"✅ {scraper_file}")
        else:
            st.error(f"❌ {scraper_file} missing")

def show_file_inspector():
    """Show file inspector"""
    st.subheader("📄 File Inspector")
    
    # List files in current directory
    from pathlib import Path
    
    files = list(Path('.').glob('*'))
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.write("**Select File to Inspect:**")
        selected_file = st.selectbox("File:", [f.name for f in files if f.is_file()])
    
    with col2:
        if selected_file:
            file_path = Path(selected_file)
            
            st.write(f"**File: {selected_file}**")
            st.write(f"Size: {file_path.stat().st_size} bytes")
            
            # Show file content
            try:
                if selected_file.endswith('.json'):
                    content = file_path.read_text(encoding='utf-8')
                    st.json(json.loads(content))
                elif selected_file.endswith('.py'):
                    content = file_path.read_text(encoding='utf-8')
                    st.code(content, language='python')
                else:
                    content = file_path.read_text(encoding='utf-8')
                    st.text(content)
                    
            except UnicodeDecodeError:
                st.error("❌ File contains binary data or encoding issues")
                
                # Show raw bytes
                raw_content = file_path.read_bytes()
                st.write(f"Raw bytes (first 100): {raw_content[:100]}")
                
            except Exception as e:
                st.error(f"❌ Cannot read file: {e}")

def show_manual_fixes():
    """Show manual fix options"""
    st.subheader("🔧 Manual Fixes")
    
    # Create missing DM library
    st.write("**DM Library Management:**")
    username = st.text_input("Username for DM Library:")
    if st.button("📝 Create DM Library") and username:
        try:
            from debug_system import ProductionDebugger
            debugger = ProductionDebugger()
            debugger.create_missing_dm_library(username)
            st.success(f"✅ Created DM library for {username}")
        except Exception as e:
            st.error(f"❌ Failed to create DM library: {e}")
    
    # File encoding fix
    st.write("**File Encoding Fix:**")
    if st.button("🔤 Fix All File Encodings"):
        try:
            from debug_system import ProductionDebugger
            debugger = ProductionDebugger()
            debugger.check_json_files()
            st.success("✅ File encoding check completed")
            
            for fix in debugger.fixes_applied:
                st.info(f"🔧 {fix}")
                
        except Exception as e:
            st.error(f"❌ Encoding fix failed: {e}")
    
    # Force credit system reload
    st.write("**Credit System Management:**")
    if st.button("🔄 Reload Credit System"):
        try:
            from simple_credit_system import credit_system
            if credit_system:
                credit_system.reload_user_data()
                st.success("✅ Credit system reloaded")
            else:
                st.error("❌ Credit system not available")
        except Exception as e:
            st.error(f"❌ Reload failed: {e}")

def show_debug_logs():
    """Show debug logs from session"""
    st.subheader("📊 Debug Logs")
    
    if 'last_debug_results' in st.session_state:
        results = st.session_state['last_debug_results']
        
        # Show report summary
        report = results["report"]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Files", len(report.get("file_listing", [])))
        with col2:
            st.metric("Debug Entries", len(report.get("debug_log", [])))
        with col3:
            st.metric("Fixes Applied", len(report.get("fixes_applied", [])))
        
        # Show full report
        with st.expander("📋 Full Debug Report"):
            st.json(report)
    else:
        st.info("ℹ️ No debug logs available. Run a diagnosis first.")

# Main function to add to your Streamlit app
def add_debug_interface_to_app():
    """Add debug interface to main Streamlit app"""
    
    # Add to sidebar
    with st.sidebar:
        st.markdown("---")
        if st.button("🔧 Debug Center"):
            st.session_state['show_debug'] = True
    
    # Show debug interface if requested
    if st.session_state.get('show_debug', False):
        show_debug_interface()
        
        # Close button
        if st.button("❌ Close Debug Center"):
            st.session_state['show_debug'] = False
            st.rerun()