# app_wrapper.py - Production-ready Streamlit app wrapper
import streamlit as st
import sys
import traceback
import os
from datetime import datetime

# Set page config first (must be first Streamlit command)
st.set_page_config(
    page_title="Lead Generation Empire",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_credit_system():
    """Initialize credit system with comprehensive error handling"""
    try:
        # Show initialization status
        with st.spinner("🚀 Initializing Lead Generation Empire..."):
            
            # Try to import the credit system
            try:
                from simple_credit_system import credit_system, CreditSystem
                
                if credit_system is None:
                    st.error("❌ Credit system failed to initialize during import")
                    return None, "Credit system instance is None"
                
                # Test basic functionality
                health = credit_system.get_system_health()
                
                if health["status"] == "healthy":
                    st.success("✅ Credit system initialized successfully")
                elif health["status"] == "degraded":
                    st.warning(f"⚠️ Credit system running with issues: {', '.join(health['issues'])}")
                else:
                    st.error(f"❌ Credit system unhealthy: {health.get('error', 'Unknown error')}")
                
                # Show system info in expander
                with st.expander("🔍 System Information", expanded=False):
                    st.json(health)
                
                return credit_system, None
                
            except ImportError as e:
                error_msg = f"Import Error: {str(e)}"
                st.error(f"❌ Could not import credit system: {error_msg}")
                st.code(traceback.format_exc())
                return None, error_msg
                
            except Exception as e:
                error_msg = f"Initialization Error: {str(e)}"
                st.error(f"❌ Credit system initialization failed: {error_msg}")
                st.code(traceback.format_exc())
                return None, error_msg
    
    except Exception as e:
        error_msg = f"Wrapper Error: {str(e)}"
        st.error(f"❌ App wrapper error: {error_msg}")
        st.code(traceback.format_exc())
        return None, error_msg

def show_system_diagnostics():
    """Show comprehensive system diagnostics"""
    st.subheader("🔧 System Diagnostics")
    
    # Environment information
    with st.expander("🌍 Environment Information"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Python Environment:**")
            st.write(f"- Python Version: {sys.version.split()[0]}")
            st.write(f"- Working Directory: {os.getcwd()}")
            st.write(f"- Environment: {os.getenv('ENVIRONMENT', 'unknown')}")
            
        with col2:
            st.write("**File System:**")
            import tempfile
            from pathlib import Path
            st.write(f"- Home Directory: {Path.home()}")
            st.write(f"- Temp Directory: {tempfile.gettempdir()}")
            st.write(f"- Current Dir Writable: {_check_write_permission('.')}")
    
    # Credit system diagnostics
    try:
        from simple_credit_system import credit_system
        if credit_system:
            health = credit_system.get_system_health()
            
            with st.expander("💳 Credit System Status"):
                if health["status"] == "healthy":
                    st.success("✅ Credit System: Healthy")
                elif health["status"] == "degraded":
                    st.warning("⚠️ Credit System: Degraded")
                else:
                    st.error("❌ Credit System: Error")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Users", health.get("users_count", 0))
                    st.metric("Total Transactions", health.get("transactions_count", 0))
                
                with col2:
                    files_exist = health.get("files_exist", {})
                    st.write("**Data Files:**")
                    st.write(f"- Users File: {'✅' if files_exist.get('users') else '❌'}")
                    st.write(f"- Transactions File: {'✅' if files_exist.get('transactions') else '❌'}")
                
                if health.get("issues"):
                    st.warning("**Issues Found:**")
                    for issue in health["issues"]:
                        st.write(f"- {issue}")
                
                st.write(f"**Data Directory:** `{health.get('data_directory', 'Unknown')}`")
                
    except Exception as e:
        with st.expander("💳 Credit System Status"):
            st.error(f"❌ Could not get credit system status: {e}")

def _check_write_permission(path: str) -> bool:
    """Check if directory is writable"""
    try:
        test_file = os.path.join(path, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except:
        return False

def show_error_recovery_options(error_message: str):
    """Show error recovery options to users"""
    st.error(f"❌ System Error: {error_message}")
    
    st.subheader("🔧 Recovery Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Retry Initialization"):
            st.rerun()
    
    with col2:
        if st.button("🔍 Show Diagnostics"):
            show_system_diagnostics()
    
    with col3:
        if st.button("💌 Report Issue"):
            st.info("Please contact support with the error details above")
    
    # Emergency contact mode
    with st.expander("🆘 Emergency Demo Mode"):
        st.warning("⚠️ Use this only if the system is completely broken")
        if st.button("🔓 Enable Demo Mode"):
            st.session_state['emergency_demo'] = True
            st.success("Demo mode enabled - limited functionality available")

def create_emergency_demo_system():
    """Create a minimal demo system for emergencies"""
    class EmergencyDemo:
        def __init__(self):
            self.users = {"demo": {"plan": "demo", "credits": 5}}
        
        def is_demo_user(self, username):
            return True
        
        def can_use_demo(self, username):
            return True, 5
        
        def get_user_stats(self, username):
            return {"plan": "demo", "current_credits": 5}
    
    return EmergencyDemo()

def main():
    """Main app entry point with error handling"""
    
    # Show header
    st.title("🎯 Lead Generation Empire")
    st.markdown("---")
    
    # Check for emergency demo mode
    if st.session_state.get('emergency_demo', False):
        st.warning("⚠️ Running in Emergency Demo Mode - Limited Functionality")
        credit_system = create_emergency_demo_system()
        # Continue with limited app functionality
        st.info("Basic demo functionality available")
        return
    
    # Initialize credit system
    credit_system, error_message = initialize_credit_system()
    
    if credit_system is None:
        # Show error and recovery options
        show_error_recovery_options(error_message)
        
        # Still show diagnostics
        st.markdown("---")
        show_system_diagnostics()
        return
    
    # Store in session state for other components
    st.session_state['credit_system'] = credit_system
    
    # Show success and continue with your main app
    st.success("🎉 Lead Generation Empire is ready!")
    
    # Add your main app components here
    # For example:
    if 'user' not in st.session_state:
        show_login_page(credit_system)
    else:
        show_main_dashboard(credit_system)

def show_login_page(credit_system):
    """Show login/registration page"""
    st.subheader("🔐 Login / Register")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            identifier = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit and identifier and password:
                success, message, user_data = credit_system.login_user(identifier, password)
                if success:
                    st.session_state['user'] = user_data
                    st.session_state['username'] = identifier
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with tab2:
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Create Demo Account")
            
            if submit and username and email and password:
                success, message = credit_system.create_user(username, email, password)
                if success:
                    st.success(message)
                    st.info("Please login with your new account")
                else:
                    st.error(message)

def show_main_dashboard(credit_system):
    """Show main dashboard after login"""
    username = st.session_state.get('username', 'Unknown')
    
    st.subheader(f"👋 Welcome back, {username}!")
    
    # Show user stats
    stats = credit_system.get_user_stats(username)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Plan", stats.get('plan', 'demo').title())
    with col2:
        st.metric("Credits", stats.get('current_credits', 0))
    with col3:
        st.metric("Leads Downloaded", stats.get('total_leads_downloaded', 0))
    with col4:
        if st.button("🚪 Logout"):
            del st.session_state['user']
            del st.session_state['username']
            st.rerun()
    
    # Add your main app functionality here
    st.info("🚧 Add your lead generation tools here!")

if __name__ == "__main__":
    main()