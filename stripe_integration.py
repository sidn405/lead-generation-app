import streamlit as st
import stripe
import sqlite3
from datetime import datetime
import os

# Set your Stripe keys
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")  # Replace with your actual secret key
STRIPE_PUBLISHABLE_KEY = "pk_test_..."  # Replace with your actual publishable key

def create_stripe_session(package_name, price, user_email, user_id):
    """Create Stripe checkout session"""
    try:
        # Package configurations
        packages = {
            "Niche Starter Pack": {
                "price": 9700,  # $97 in cents
                "file_path": "leads/fitness_wellness_500.csv"
            },
            "Industry Deep Dive": {
                "price": 29700,  # $297 in cents
                "file_path": "leads/fitness_wellness_2000.csv"
            },
            "Market Domination": {
                "price": 89700,  # $897 in cents
                "file_path": "leads/fitness_wellness_5000.csv"
            }
        }
        
        if package_name not in packages:
            return None
            
        package_info = packages[package_name]
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Lead Generator Empire - {package_name}',
                        'description': f'Fitness & Wellness Lead Package',
                    },
                    'unit_amount': package_info["price"],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{st.secrets.get('app_url', 'http://localhost:8501')}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{st.secrets.get('app_url', 'http://localhost:8501')}?canceled=true",
            customer_email=user_email,
            metadata={
                'user_id': user_id,
                'package_name': package_name,
                'file_path': package_info["file_path"]
            }
        )
        
        return session.url
        
    except Exception as e:
        st.error(f"Error creating payment session: {str(e)}")
        return None

def verify_payment_and_update_db(session_id):
    """Verify payment and update database"""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Get metadata
            user_id = session.metadata['user_id']
            package_name = session.metadata['package_name']
            file_path = session.metadata['file_path']
            
            # Check if already processed
            conn = sqlite3.connect('your_database.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id FROM purchases 
                WHERE stripe_payment_intent_id = ?
            ''', (session.payment_intent,))
            
            if cursor.fetchone() is None:
                # Add to purchases table
                cursor.execute('''
                    INSERT INTO purchases 
                    (user_id, email, package_name, package_price, stripe_payment_intent_id, file_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    session.customer_details.email,
                    package_name,
                    session.amount_total / 100,  # Convert cents to dollars
                    session.payment_intent,
                    file_path
                ))
                
                conn.commit()
                conn.close()
                return True
            
            conn.close()
            return True
            
    except Exception as e:
        st.error(f"Error verifying payment: {str(e)}")
        return False
    
    return False

def handle_payment_flow():
    """Handle the complete payment flow"""
   
    # Check for success/cancel parameters
    if "success" in st.query_params and "session_id" in st.query_params:
        session_id = st.query_params["session_id"]
       
        if verify_payment_and_update_db(session_id):
            st.success("🎉 Payment successful! Your leads are now available in your dashboard.")
            st.balloons()
           
            # Clear query parameters
            st.query_params.clear()
           
            # Show download button or redirect to dashboard
            if st.button("Go to My Downloads"):
                st.rerun()
        else:
            st.error("There was an issue processing your payment. Please contact support.")
   
    elif "canceled" in st.query_params:
        st.warning("Payment was canceled. You can try again anytime.")
        st.query_params.clear()

# Example usage in your main app
def show_purchase_buttons(user_id, user_email):
    """Show purchase buttons for each package"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Buy Starter Pack - $97"):
            checkout_url = create_stripe_session("Niche Starter Pack", 97, user_email, user_id)
            if checkout_url:
                st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_url}">', unsafe_allow_html=True)
    
    with col2:
        if st.button("Buy Deep Dive - $297"):
            checkout_url = create_stripe_session("Industry Deep Dive", 297, user_email, user_id)
            if checkout_url:
                st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_url}">', unsafe_allow_html=True)
    
    with col3:
        if st.button("Buy Domination - $897"):
            checkout_url = create_stripe_session("Market Domination", 897, user_email, user_id)
            if checkout_url:
                st.markdown(f'<meta http-equiv="refresh" content="0; url={checkout_url}">', unsafe_allow_html=True)