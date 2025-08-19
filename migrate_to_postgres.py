# migrate_to_postgres.py - Migrate from JSON to PostgreSQL
import streamlit as st
import os
import json
from postgres_credit_system import initialize_postgres_credit_system, postgres_credit_system

def show_migration_interface():
    """Streamlit interface for migration"""
    st.title("🔄 Migrate to PostgreSQL")
    
    # Check if PostgreSQL is available
    if not os.getenv('DATABASE_URL'):
        st.error("❌ DATABASE_URL not found. Please add PostgreSQL to your Railway project.")
        st.info("1. Go to Railway Dashboard → Your Project")
        st.info("2. Click 'New' → 'Database' → 'Add PostgreSQL'") 
        st.info("3. Railway will automatically set DATABASE_URL")
        return
    
    # Initialize PostgreSQL
    if st.button("🚀 Initialize PostgreSQL Credit System"):
        with st.spinner("Initializing PostgreSQL..."):
            success, message = initialize_postgres_credit_system()
            if success:
                st.success(message)
                st.balloons()
            else:
                st.error(message)
                return
    
    if not postgres_credit_system:
        st.warning("⚠️ Initialize PostgreSQL first")
        return
    
    st.markdown("---")
    
    # Manual user creation for sam
    st.subheader("👤 Recreate User Sam")
    
    with st.form("create_sam"):
        email = st.text_input("Email", value="sam@demo.com")
        password = st.text_input("Password", value="demo123", type="password")
        
        if st.form_submit_button("🆕 Create User Sam"):
            success, message = postgres_credit_system.create_user("sam", email, password)
            if success:
                st.success(message)
                
                # Auto-login
                st.session_state.username = 'sam'
                st.session_state.user_authenticated = True
                st.session_state.user_data = postgres_credit_system.get_user_info('sam')
                st.session_state.user_plan = 'demo'
                st.session_state.user_credits = 5
                
                st.success("🔓 Auto-logged in as sam!")
                st.rerun()
            else:
                st.error(message)
    
    st.markdown("---")
    
    # System status
    st.subheader("📊 PostgreSQL System Status")
    
    if st.button("📋 Check System Health"):
        health = postgres_credit_system.get_system_health()
        
        if health['status'] == 'healthy':
            st.success("✅ PostgreSQL system is healthy")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Users", health['users_count'])
            with col2:
                st.metric("Transactions", health['transactions_count'])
            with col3:
                st.metric("Database", "Connected" if health['database_connected'] else "Disconnected")
        else:
            st.error(f"❌ System unhealthy: {health.get('error')}")
    
    # Show existing users
    if st.button("👥 Show All Users"):
        users = postgres_credit_system.get_all_users()
        
        if users:
            st.subheader(f"📋 {len(users)} Users in Database")
            for user in users:
                with st.expander(f"👤 {user['username']} ({user['plan']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Email:** {user['email']}")
                        st.write(f"**Plan:** {user['plan']}")
                        st.write(f"**Credits:** {user['credits']}")
                    with col2:
                        st.write(f"**Demo Used:** {user['demo_leads_used']}/{user['demo_limit']}")
                        st.write(f"**Total Leads:** {user['total_leads_downloaded']}")
                        st.write(f"**Created:** {user['created_at']}")
        else:
            st.info("No users found in database")
    
    # Migration from existing JSON (if available)
    st.markdown("---")
    st.subheader("📂 Migrate from JSON (Optional)")
    
    st.info("If you have existing users_credits.json file, you can migrate the data")
    
    # File upload for JSON migration
    uploaded_file = st.file_uploader("Upload users_credits.json", type="json")
    
    if uploaded_file:
        try:
            json_data = json.load(uploaded_file)
            st.success(f"✅ JSON file loaded: {len(json_data)} users found")
            
            if st.button("🔄 Migrate JSON Data to PostgreSQL"):
                with st.spinner("Migrating data..."):
                    # Save uploaded file temporarily
                    with open("temp_users.json", "w") as f:
                        json.dump(json_data, f)
                    
                    # Migrate
                    success, message = postgres_credit_system.migrate_from_json("temp_users.json")
                    
                    # Clean up
                    os.remove("temp_users.json")
                    
                    if success:
                        st.success(message)
                        st.balloons()
                    else:
                        st.error(message)
                        
        except Exception as e:
            st.error(f"❌ Invalid JSON file: {e}")

# Main migration interface
if __name__ == "__main__":
    show_migration_interface()