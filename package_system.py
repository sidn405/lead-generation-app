
import streamlit as st
from payment_auth_recovery import create_package_stripe_session
import sqlite3
import pandas as pd
import os
import base64
from datetime import datetime
import stripe
import time
import sys
sys.path.append(os.path.dirname(__file__))


STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")  # Replace with your actual secret key

# Initialize Stripe with your API key
stripe.api_key = STRIPE_API_KEY

def create_package_stripe_session(api_key: str, username: str, package_key: str, price: float, package_name: str):
    """Create a Stripe checkout session for package purchase"""
    
    try:
        # Package definitions for file mapping
        package_files = {
            "starter": "fitness_wellness_500.csv",
            "deep_dive": "fitness_wellness_2000.csv", 
            "domination": "fitness_wellness_5000.csv"
        }
        
        # Show loading message
        with st.spinner('Creating checkout session...'):
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Fitness & Wellness Leads - {package_name}",
                            "description": f"Verified leads • Instant download"
                        },
                        "unit_amount": int(price * 100),  # Convert to cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"https://leadgeneratorempire.com/?package_success=true&username={username}&package={package_name}&timestamp={int(time.time())}",
                cancel_url="https://leadgeneratorempire.com/?package_cancelled=true&username={username}",
                customer_email=f"{username}@example.com",
                metadata={
                    "username": username,
                    "package_name": package_name,
                    "package_key": package_key,
                    "file_path": package_files.get(package_key, "")
                }
            )
        
        # Show success message and direct redirect
        st.success("✅ Checkout session created! Redirecting to Stripe...")
        
        # Direct redirect using meta refresh (more reliable than JavaScript)
        st.markdown(f"""
        <meta http-equiv="refresh" content="2;url={session.url}">
        <div style="text-align: center; padding: 20px;">
            <h3>🔄 Redirecting to Stripe...</h3>
            <p>If you're not redirected automatically in 2 seconds:</p>
            <a href="{session.url}" target="_blank" style="
                background-color: #635bff; 
                color: white; 
                padding: 15px 30px; 
                text-decoration: none; 
                border-radius: 8px; 
                font-weight: bold;
                display: inline-block;
                margin: 10px;
            ">🚀 Click Here to Complete Purchase</a>
        </div>
        """, unsafe_allow_html=True)
        
        return session
        
    except stripe.error.AuthenticationError as e:
        st.error(f"❌ Stripe Authentication Error: {e}")
        st.info("💡 Your API key is invalid. Get a new one from: https://dashboard.stripe.com/apikeys")
        return None
        
    except Exception as e:
        st.error(f"❌ Error creating checkout session: {e}")
        st.exception(e)  # This will show the full error for debugging
        return None

def setup_package_tables():
    """Run this ONCE to add package tables"""
    conn = sqlite3.connect('lead_generator.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS package_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            package_name TEXT NOT NULL,
            lead_count INTEGER NOT NULL,
            price REAL NOT NULL,
            file_path TEXT NOT NULL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            download_count INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

def add_package_to_database(username: str, package_name: str):
    """Add package to database if not already exists"""
    
    # Package definitions (same as in your main function)
    packages = {
        "Niche Starter Pack": {"leads": 500, "price": 97, "file": "fitness_wellness_500.csv"},
        "Industry Deep Dive": {"leads": 2000, "price": 297, "file": "fitness_wellness_2000.csv"},
        "Market Domination": {"leads": 5000, "price": 897, "file": "fitness_wellness_5000.csv"}
    }
    
    if package_name in packages:
        pkg = packages[package_name]
        
        try:
            # Ensure database and table exist
            setup_package_tables()
            
            conn = sqlite3.connect('lead_generator.db')
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute('''
                SELECT id FROM package_purchases 
                WHERE username = ? AND package_name = ?
            ''', (username, package_name))
            
            existing = cursor.fetchone()
            
            if not existing:
                # Add if doesn't exist
                cursor.execute('''
                    INSERT INTO package_purchases (username, package_name, lead_count, price, file_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, package_name, pkg["leads"], pkg["price"], pkg["file"]))
                
                conn.commit()
                print(f"✅ Added package {package_name} for user {username}")
            else:
                print(f"📦 Package {package_name} already exists for user {username}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            st.error(f"Database error: {e}")
    else:
        print(f"❌ Unknown package name: {package_name}")
        st.error(f"Unknown package name: {package_name}")

def show_package_store(username: str, user_authenticated: bool):
    """The package store page with real Stripe integration"""

    # 1) Handle cancelled purchases
    if "package_cancelled" in st.query_params:
        st.warning("⚠️ Purchase was cancelled. You can try again anytime.")
        st.query_params.clear()

    # 2) Anchor & title
    st.markdown('<div id="top"></div>', unsafe_allow_html=True)
    st.markdown("# 📦 Pre-Built Lead Packages")

    # 3) Your targeting summary (styled HTML)
    st.markdown("## 📋 Your Targeting Summary")
    st.markdown("""
    <div style="background-color:#1e3a5f; padding:20px; border-radius:10px; margin-bottom:20px;">
      <div style="color:#60a5fa; margin-bottom:8px;">🏢 <strong>Industry:</strong> Fitness & Wellness</div>
      <div style="color:#60a5fa; margin-bottom:8px;">📍 <strong>Location:</strong> United States (All States)</div>
      <div style="color:#60a5fa;">👥 <strong>Lead Type:</strong> End Customers</div>
    </div>
    """, unsafe_allow_html=True)

    # 4) Status banner
    st.success("🚀 **FITNESS & WELLNESS LEADS PRE-BUILT & READY** — Instant download available")
    st.markdown("---")

    # 5) Package definitions
    packages = [
        {
            "key":  "starter",
            "name": "Niche Starter Pack",
            "badge": "STARTER",
            "badge_color": "#1f77b4",
            "leads": 500,
            "price": 97,
            "features": [
                "500 targeted leads in your chosen industry",
                "2-3 platforms included",
                "Basic filtering applied",
                "CSV + Google Sheets delivery",
                "48-hour delivery"
            ],
            "perfect_for": "Testing a new niche, quick campaigns"
        },
        {
            "key": "deep_dive",
            "name": "Industry Deep Dive",
            "badge": "MOST POPULAR",
            "badge_color": "#28a745",
            "leads": 2000,
            "price": 297,
            "features": [
                "2,000 highly-targeted leads in your industry",
                "Comprehensive industry research",
                "All 8 platforms",
                "Advanced relevance filtering",
                "Social media profiles included",
                "DMs pre-generated for your industry",
                "72-hour delivery"
            ],
            "perfect_for": "Serious campaigns, market research"
        },
        {
            "key": "domination",
            "name": "Market Domination",
            "badge": "ENTERPRISE",
            "badge_color": "#fd7e14",
            "leads": 5000,
            "price": 897,
            "features": [
                "5,000 premium leads across multiple related niches",
                "Advanced geographic targeting",
                "Phone/email enrichment when available",
                "Custom DM sequences for your industry",
                "30-day refresh guarantee",
                "5 business days delivery"
            ],
            "perfect_for": "Enterprise campaigns, market domination"
        }
    ]

    # 6) Render the three cards
    cols = st.columns(3)
    for pkg, col in zip(packages, cols):
        with col:
            # Badge
            st.markdown(f"""
                <div style="
                    background-color: {pkg['badge_color']};
                    color: white;
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-align: center;
                    font-weight: bold;
                    margin-bottom: 16px;
                ">
                    {pkg['badge']}
                </div>
            """, unsafe_allow_html=True)

            # Name, price, lead count
            st.markdown(f"### {pkg['name']}")
            st.markdown(f"## ${pkg['price']}")
            st.markdown(f"**{pkg['leads']:,} verified leads**")
            st.markdown("---")

            # Features
            st.markdown("**📦 What's Included:**")
            for feat in pkg["features"]:
                st.markdown(f"• {feat}")
            st.info(f"**Perfect for:** {pkg['perfect_for']}")

            # 7) Checkbox + Buy/Sign-In button
            agree_key = f"agree_{pkg['key']}"
            
            # Initialize checkbox state if not exists
            if agree_key not in st.session_state:
                st.session_state[agree_key] = False
            
            agreed = st.checkbox(
                "✅ Agree to terms",
                key=agree_key,
                help="I agree to the Terms of Service & No-Refund Policy",
                value=st.session_state.get(agree_key, False)
            )

            if user_authenticated:
                buy_key = f"buy_{pkg['key']}"
                
                # Style the button based on agreement status
                button_type = "primary" if agreed else "secondary"
                button_text = f"🛒 Buy {pkg['name']}" if agreed else f"🛒 Buy {pkg['name']} (Agree to terms first)"
                
                if st.button(
                    button_text,
                    key=buy_key,
                    disabled=not agreed,
                    use_container_width=True,
                    type=button_type
                ):
                    if agreed:
                        st.write(f"🔄 Processing purchase for {pkg['name']}...")
                        
                        # Create checkout session
                        session = create_package_stripe_session(
                            STRIPE_API_KEY,
                            username,
                            pkg["key"],
                            pkg["price"],
                            pkg["name"]
                        )
                        
                        if session:
                            # Don't rerun here - let the session state handle the redirect
                            pass
                        else:
                            st.error("❌ Failed to create checkout session")
                    else:
                        st.warning("⚠️ Please agree to terms first")
                        
            else:
                signin_key = f"signin_{pkg['key']}"
                if st.button(
                    "🔑 Sign In to Buy",
                    key=signin_key,
                    use_container_width=True
                ):
                    # flip the top-level flag; main app will render the form
                    st.session_state.show_login = True
                    st.rerun()

    

    with st.expander("📋 Digital Product Terms"):
        st.markdown("""
        **📦 Digital Product Terms:**
        • **Instant Delivery** - Credits added immediately after payment
        • **No Refunds** - All credit purchases are final
        • **90-Day Expiry** - Credits expire 90 days from purchase
        • **Legitimate Use** - For business purposes only
        • **Terms Required** - Must agree to Terms of Service
    """)
        
    st.markdown(
            '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
            'padding:12px 16px;border-radius:25px;'
            'background:linear-gradient(135deg,#0066cc,#4dabf7);'
            'color:white;font-weight:bold;text-decoration:none;'
            'z-index:9999;">⬆️ Top</a>',
            unsafe_allow_html=True,
    )
    
    st.markdown(
        """
        <style>
        /* make room for the footer so it doesn't cover content */
        .appview-container .main {
            padding-bottom: 60px;  
        }
        /* footer styling */
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 50px;
            background: rgba(0, 0, 0, 0.8);
            color: #aaa;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            z-index: 1000;
        }
        </style>

        <div class="footer">
        ⚙️ Lead Generator Empire Pre-Built Packages | Secure &amp; Private
        </div>
        """,
        unsafe_allow_html=True,
    )

def show_my_packages(username: str):
    """Show user's purchased packages with styling"""
    
    # Handle successful purchases from Stripe redirect
    if "package_success" in st.query_params:
        username_from_stripe = st.query_params.get("username", "unknown")
        package_name = st.query_params.get("package", "unknown")

        # Add to database immediately (in case webhook is slow)
        add_package_to_database(username_from_stripe, package_name)

        st.balloons()
        st.success(f"🎉 {package_name} purchased successfully!")
        st.info("📁 Your package is now available for download below")

        # Clear the URL parameters
        st.query_params.clear()
        
        # Force a rerun to refresh the packages list
        time.sleep(1)
        st.rerun()
    
    st.title("📁 My Downloaded Packages")
    
    try:
        conn = sqlite3.connect('lead_generator.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, package_name, lead_count, price, file_path, purchase_date, download_count
            FROM package_purchases 
            WHERE username = ?
            ORDER BY purchase_date DESC
        ''', (username,))
        packages = cursor.fetchall()
        conn.close()
        
        if not packages:
            st.info("📦 No packages purchased yet.")
            st.markdown("Visit the **Package Store** to get instant-download lead packages!")
            
            if st.button("🛒 Browse Packages", type="primary"):
                st.session_state.current_page = "Package Store"
                st.rerun()
            return
        
        st.success(f"You have {len(packages)} package(s) available for download")
        
        for pkg_id, name, leads, price, file_path, date, downloads in packages:
            # Create styled container for each package
            with st.container():
                # Package header
                st.markdown(f"### 📦 {name}")
                
                # Package details
                st.markdown(f"""
                **📊 Lead Count:** {leads:,} verified leads  
                **💰 Price Paid:** ${price}  
                **📅 Purchase Date:** {date}  
                **📥 Downloads:** {downloads} times
                """)
                
                # Status indicator and download link
                full_path = f"leads/{file_path}"
                if os.path.exists(full_path):
                    st.success("✅ Download ready! Click the green link below.")
                    
                    # Show download link directly (no button needed)
                    try:
                        with open(full_path, 'rb') as f:
                            data = f.read()
                        
                        b64 = base64.b64encode(data).decode()
                        filename = f"{name.replace(' ', '_').lower()}_fitness_wellness_leads.csv"
                        
                        # Centered download link with matching background styling
                        st.markdown(f"""
                        <div style="
                            background-color: #1e3a5f; 
                            padding: 20px; 
                            border-radius: 10px; 
                            margin: 20px 0; 
                            text-align: center;
                        ">
                            <a href="data:file/csv;base64,{b64}" download="{filename}" 
                               style="
                                   background-color: #28a745; 
                                   color: white; 
                                   padding: 15px 30px; 
                                   text-decoration: none; 
                                   border-radius: 8px; 
                                   font-weight: bold; 
                                   font-size: 16px; 
                                   display: inline-block;
                                   margin-bottom: 15px;
                               ">
                                📥 Download {filename}
                            </a>
                            <div style="
                                color: #60a5fa; 
                                font-size: 14px; 
                                margin-top: 15px;
                                padding: 10px;
                                background-color: rgba(96, 165, 250, 0.1);
                                border-radius: 6px;
                            ">
                                💡 <strong>Tip:</strong> Import this CSV into your CRM, email marketing tool, or social media automation platform to start reaching these fitness & wellness prospects!
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"Error preparing download: {e}")
                else:
                    st.error("❌ File missing")
                
                st.markdown("---")
                
    except Exception as e:
        st.error(f"Error loading packages: {e}")

def download_package(username: str, pkg_id: int, package_name: str, file_path: str):
    """Handle package download with better styling"""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        b64 = base64.b64encode(data).decode()
        filename = f"{package_name.replace(' ', '_').lower()}_fitness_wellness_leads.csv"
        
        # Success message
        st.success("✅ Download ready! Click the green button below.")
        
        # Centered download link with matching background styling
        st.markdown(f"""
        <div style="
            background-color: #1e3a5f; 
            padding: 20px; 
            border-radius: 10px; 
            margin: 20px 0; 
            text-align: center;
        ">
            <a href="data:file/csv;base64,{b64}" download="{filename}" 
               style="
                   background-color: #28a745; 
                   color: white; 
                   padding: 15px 30px; 
                   text-decoration: none; 
                   border-radius: 8px; 
                   font-weight: bold; 
                   font-size: 16px; 
                   display: inline-block;
                   margin-bottom: 15px;
               ">
                📥 Download {filename}
            </a>
            <div style="
                color: white; 
                font-size: 14px; 
                margin-top: 15px;
            ">
                💡 <strong>Tip:</strong> Import this CSV into your CRM, email marketing tool, or social media automation platform to start reaching these fitness & wellness prospects!
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Update download count
        conn = sqlite3.connect('lead_generator.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE package_purchases 
            SET download_count = download_count + 1 
            WHERE id = ? AND username = ?
        ''', (pkg_id, username))
        conn.commit()
        conn.close()
        
    except Exception as e:
        st.error(f"Download error: {e}")
    


st.markdown(
            '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
            'padding:12px 16px;border-radius:25px;'
            'background:linear-gradient(135deg,#0066cc,#4dabf7);'
            'color:white;font-weight:bold;text-decoration:none;'
            'z-index:9999;">⬆️ Top</a>',
            unsafe_allow_html=True,
)
    
st.markdown(
    """
    <style>
      /* make room for the footer so it doesn't cover content */
      .appview-container .main {
        padding-bottom: 60px;  
      }
      /* footer styling */
      .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 50px;
        background: rgba(0, 0, 0, 0.8);
        color: #aaa;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
        z-index: 1000;
      }
    </style>

    <div class="footer">
      ⚙️ Lead Generator Empire Settings | Secure &amp; Private
    </div>
    """,
    unsafe_allow_html=True,
)