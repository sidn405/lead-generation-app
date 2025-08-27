# payment_auth_recovery.py - FIXED VERSION
"""
Payment Authentication Recovery Module
Handles authentication restoration after Stripe payment returns
"""
import streamlit as st
from emailer import send_admin_package_notification, EMAIL_ADDRESS
import os 
import json
import stripe
import time
from datetime import datetime
from typing import Tuple, Optional, Dict, Any


STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")

APP_BASE_URL = (
    os.environ.get("APP_BASE_URL", "https://leadgeneratorempire.com") 
)

def restore_payment_authentication() -> bool:
    """
    CRITICAL: Handle authentication restoration after Stripe payment
    Returns True if this is a payment return, False otherwise
    """
    query_params = st.query_params
    
    # Check if this is a payment return
    payment_indicators = ["success", "payment_success", "cancelled", "plan", "package", "amount", "tier", "credits"]
    is_payment_return = any(param in query_params for param in payment_indicators)
    
    if not is_payment_return:
        return False
    
    # CRITICAL FIX: Check if already processed to prevent loops
    if query_params.get("processed") == "1":
        print("✅ Payment already processed, skipping")
        return True
    
    is_package = "package" in query_params
    username_from_url = query_params.get("username", "")
    
    # CREATE DEDUPLICATION KEY to prevent multiple processing
    session_id = query_params.get("session_id") or ""
    package_key = query_params.get("package") or ""
    amount = query_params.get("amount") or "0"
    industry = query_params.get("industry") or ""
    location = query_params.get("location") or ""
    requires_build = str(query_params.get("requires_build", "0")).lower() in ("1", "true", "yes")
    
    dedupe_key = session_id or f"{username_from_url}|{package_key}|{amount}|{industry}|{location}|{int(requires_build)}"
    
    # Check if we've already processed this payment in this session
    processed_payments = st.session_state.setdefault("processed_payments", set())
    if dedupe_key in processed_payments:
        print(f"✅ Payment {dedupe_key} already processed in this session")
        try:
            st.query_params["processed"] = "1"
        except Exception:
            pass
        return True
    
    print(f"🔄 Payment return detected - User: {username_from_url}")
    
    # If user is already authenticated, we're good
    if st.session_state.get('authenticated', False):
        print("✅ User already authenticated")
        # Process the payment (idempotent)
        success = _process_payment_success(query_params, username_from_url or st.session_state.get("username", ""))
        if success:
            # Mark as processed to prevent loops
            processed_payments.add(dedupe_key)
            try:
                st.query_params["processed"] = "1"
            except Exception:
                pass
        return True
    
    # Attempt to restore authentication
    if username_from_url and username_from_url != "unknown":
        print(f"🔧 Attempting to restore auth for: {username_from_url}")
        
        # Try multiple restoration methods
        if _restore_from_credit_system(username_from_url):
            success = _process_payment_success(query_params, username_from_url)
            if success:
                processed_payments.add(dedupe_key)
                try:
                    st.query_params["processed"] = "1"
                except Exception:
                    pass
            return True
        
        if _restore_from_users_json(username_from_url):
            success = _process_payment_success(query_params, username_from_url)
            if success:
                processed_payments.add(dedupe_key)
                try:
                    st.query_params["processed"] = "1"
                except Exception:
                    pass
            return True
        
        if _create_emergency_session(username_from_url, query_params):
            success = _process_payment_success(query_params, username_from_url)
            if success:
                processed_payments.add(dedupe_key)
                try:
                    st.query_params["processed"] = "1"
                except Exception:
                    pass
            return True
        
        # Even if restoration failed, still process the payment
        if not is_package:
            success = _process_payment_success(query_params, username_from_url)
            if success:
                processed_payments.add(dedupe_key)
                try:
                    st.query_params["processed"] = "1"
                except Exception:
                    pass
        return True
    
    print("❌ Payment authentication restoration failed")
    return True  # Still a payment return, just failed to restore

def _process_payment_success(query_params: Dict, username: str) -> bool:
    """
    Process payment success actions for plans and packages, with custom/prebuilt branching.
    Returns True if processing was successful, False otherwise.
    """
    try:
        if "success" not in query_params:
            return False

        # ----- Plan upgrades (unchanged) -----
        if "plan" in query_params:
            plan = query_params.get("plan", "")
            if plan:
                print(f"📋 Processing plan upgrade to: {plan}")
                try:
                    from postgres_credit_system import credit_system
                    credit_system.update_user_plan(username, plan)
                    if 'user_data' in st.session_state:
                        st.session_state.user_data['plan'] = plan
                    print(f"✅ Updated plan to: {plan}")
                    return True
                except Exception as e:
                    print(f"⚠️ Plan update warning: {e}")
                    return False

        # ----- Package purchases -----
        if "package" in query_params:
            package = query_params.get("package", "")
            amount = float(query_params.get("amount", "0") or 0)
            industry = (query_params.get("industry", "") or "").replace('+', ' ')
            location = (query_params.get("location", "") or "").replace('+', ' ')
            session_id = query_params.get("session_id") or ""
            requires_build = str(query_params.get("requires_build", "0")).lower() in ("1", "true", "yes")

            print(f"📦 Processing package purchase: {package} for ${amount} (custom={requires_build})")

            # Log transaction first
            transaction_logged = False
            try:
                from postgres_credit_system import credit_system
                tx = {
                    "type": "package_purchase",
                    "package_type": package,
                    "amount": float(amount),
                    "industry": industry,
                    "location": location,
                    "timestamp": datetime.now().isoformat(),
                    "status": "purchased",
                    "session_id": session_id,
                    "requires_build": requires_build
                }
                user_info = credit_system.get_user_info(username)
                if user_info:
                    user_info.setdefault("transactions", []).append(tx)
                    user_info["total_packages_purchased"] = user_info.get("total_packages_purchased", 0) + 1
                    credit_system.save_data()
                    print(f"✅ Logged package purchase for {username}")
                    transaction_logged = True
            except Exception as e:
                print(f"⚠️ Package logging warning: {e}")

            # Branching: custom vs pre-built
            if requires_build:
                # CUSTOM — email support, DO NOT add to downloads
                email_sent = False
                try:
                    # Get admin email from environment
                    admin_email = (
                        os.getenv("ADMIN_EMAIL") or 
                        os.getenv("SUPPORT_EMAIL") or 
                        EMAIL_ADDRESS
                    )
                    
                    # Get user email safely
                    user_email = ""
                    try:
                        user_data = st.session_state.get("user_data") or {}
                        user_email = user_data.get("email", "")
                        if not user_email:
                            user_email = f"{username}@leadgeneratorempire.com"
                    except:
                        user_email = f"{username}@leadgeneratorempire.com"
                    
                    print(f"📧 Attempting to send admin notification...")
                    print(f"   Admin email: {admin_email}")
                    print(f"   User email: {user_email}")
                    print(f"   Username: {username}")
                    print(f"   Package: {package}")
                    print(f"   Amount: ${amount}")
                    print(f"   Industry: {industry}")
                    print(f"   Location: {location}")
                    
                    # ENHANCED EMAIL NOTIFICATION WITH MULTIPLE FALLBACKS
                    email_sent = send_enhanced_admin_notification(
                        admin_email=admin_email,
                        username=username,
                        user_email=user_email,
                        package_type=package,
                        amount=float(amount),
                        industry=industry,
                        location=location,
                        session_id=session_id,
                        timestamp=query_params.get("timestamp") or str(int(time.time()))
                    )
                    
                    if email_sent:
                        print("📨 Admin notified for custom package")
                    else:
                        print("⚠️ Admin notification failed - all methods tried")
                        
                except Exception as e:
                    print(f"❌ Admin notification error: {e}")
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
                
                # Cache for UI messaging
                st.session_state["package_industry"] = industry
                st.session_state["package_location"] = location
                st.session_state["custom_package_processed"] = True
                
                return transaction_logged  # Success if we at least logged the transaction
                
            else:
                # PRE-BUILT — add to downloads
                download_added = False
                try:
                    from package_system import add_package_to_database
                    name_map = {
                        "starter": "Niche Starter Pack",
                        "deep_dive": "Industry Deep Dive", 
                        "domination": "Market Domination",
                    }
                    display_name = name_map.get(package, package.replace("_", " ").title())
                    add_package_to_database(username, display_name)
                    st.session_state["package_industry"] = industry
                    st.session_state["package_location"] = location
                    print(f"✅ Added {display_name} to downloads for {username}")
                    download_added = True
                except Exception as e:
                    print(f"⚠️ Package DB add warning: {e}")
                
                return transaction_logged and download_added
                
        return False  # No relevant payment type found

    except Exception as e:
        print(f"❌ Payment success processing error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

def send_enhanced_admin_notification(admin_email: str, username: str, user_email: str,
                                   package_type: str, amount: float, industry: str, 
                                   location: str, session_id: str, timestamp: str) -> bool:
    """
    Enhanced admin notification with multiple fallback methods.
    Returns True if ANY method succeeds.
    """
    
    # Prepare email content
    subject = f"🔥 NEW CUSTOM LEAD ORDER - {username} - ${amount}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 10px;">
            🔥 New Custom Lead Package Order
        </h2>
        
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3>Order Details</h3>
            <p><strong>Customer:</strong> {username}</p>
            <p><strong>Email:</strong> {user_email}</p>
            <p><strong>Package:</strong> {package_type.title()} Package</p>
            <p><strong>Amount:</strong> ${amount:.2f}</p>
            <p><strong>Target Industry:</strong> {industry or 'Not specified'}</p>
            <p><strong>Target Location:</strong> {location or 'Not specified'}</p>
            <p><strong>Stripe Session:</strong> {session_id or 'N/A'}</p>
            <p><strong>Order Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
            <h4>⚠️ ACTION REQUIRED</h4>
            <p>This is a <strong>CUSTOM BUILD</strong> order. Customer is waiting for:</p>
            <ul>
                <li>Custom lead list generation for their specific criteria</li>
                <li>Manual verification and quality control</li>
                <li>Delivery within 24-48 hours</li>
            </ul>
        </div>
        
        <div style="margin: 20px 0; text-align: center;">
            <p>Process this order ASAP to maintain customer satisfaction!</p>
        </div>
    </div>
    """
    
    text_content = f"""
NEW CUSTOM LEAD ORDER - URGENT
================================

Customer: {username}
Email: {user_email}
Package: {package_type.title()} Package
Amount: ${amount:.2f}
Target Industry: {industry or 'Not specified'}
Target Location: {location or 'Not specified'}
Stripe Session: {session_id or 'N/A'}
Order Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

⚠️ ACTION REQUIRED ⚠️
This is a CUSTOM BUILD order. Customer is waiting for:
- Custom lead list generation for their specific criteria
- Manual verification and quality control
- Delivery within 24-48 hours

Process this order ASAP to maintain customer satisfaction!
"""
    
    methods_tried = []
    
    # Method 1: SendGrid API
    try:
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if sendgrid_key:
            methods_tried.append("SendGrid")
            print("🔄 Trying SendGrid...")
            
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
            
            from_email = Email(admin_email)
            to_email = To(admin_email)
            
            mail = Mail(from_email, to_email, subject, Content("text/html", html_content))
            
            response = sg.send(mail)
            status_code = getattr(response, 'status_code', 0)
            
            print(f"SendGrid response: {status_code}")
            
            if 200 <= status_code < 300:
                print("✅ SendGrid email sent successfully!")
                return True
        else:
            print("⚠️ SENDGRID_API_KEY not configured")
            
    except Exception as e:
        print(f"❌ SendGrid failed: {str(e)}")
    
    # Method 2: SMTP
    try:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_user = os.getenv("SMTP_USER") 
        smtp_pass = os.getenv("SMTP_PASS")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        if smtp_host and smtp_user and smtp_pass:
            methods_tried.append("SMTP")
            print("🔄 Trying SMTP...")
            
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = admin_email
            msg["To"] = admin_email
            
            # Add both text and HTML parts
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            
            print("✅ SMTP email sent successfully!")
            return True
        else:
            print("⚠️ SMTP credentials not configured")
            
    except Exception as e:
        print(f"❌ SMTP failed: {str(e)}")
    
    # Method 3: Webhook
    try:
        webhook_url = os.getenv("SUPPORT_WEBHOOK_URL") or os.getenv("WEBHOOK_URL")
        if webhook_url:
            methods_tried.append("Webhook")
            print("🔄 Trying webhook...")
            
            import requests
            
            webhook_payload = {
                "type": "custom_order",
                "timestamp": timestamp,
                "username": username,
                "user_email": user_email,
                "package_type": package_type,
                "amount": amount,
                "industry": industry,
                "location": location,
                "session_id": session_id,
                "subject": subject,
                "message": text_content
            }
            
            response = requests.post(
                webhook_url,
                json=webhook_payload,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"Webhook response: {response.status_code}")
            
            if 200 <= response.status_code < 300:
                print("✅ Webhook notification sent successfully!")
                return True
        else:
            print("⚠️ Webhook URL not configured")
            
    except Exception as e:
        print(f"❌ Webhook failed: {str(e)}")
    
    # Method 4: Queue to database for later processing
    try:
        print("🔄 Trying database queue...")
        
        from sqlalchemy import create_engine, text
        db_url = os.getenv("DATABASE_URL")
        
        if db_url:
            methods_tried.append("Database Queue")
            
            engine = create_engine(db_url, pool_pre_ping=True)
            
            with engine.begin() as conn:
                # Create table if not exists
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS pending_notifications (
                        id BIGSERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        processed_at TIMESTAMPTZ,
                        type TEXT NOT NULL DEFAULT 'custom_order',
                        status TEXT NOT NULL DEFAULT 'pending',
                        session_id TEXT,
                        username TEXT,
                        subject TEXT,
                        html_content TEXT,
                        text_content TEXT,
                        payload JSONB
                    )
                """))
                
                # Insert notification
                conn.execute(text("""
                    INSERT INTO pending_notifications 
                    (type, session_id, username, subject, html_content, text_content, payload)
                    VALUES (:type, :session_id, :username, :subject, :html, :text, :payload)
                """), {
                    "type": "custom_order",
                    "session_id": session_id,
                    "username": username,
                    "subject": subject,
                    "html": html_content,
                    "text": text_content,
                    "payload": json.dumps({
                        "username": username,
                        "user_email": user_email,
                        "package_type": package_type,
                        "amount": amount,
                        "industry": industry,
                        "location": location,
                        "session_id": session_id,
                        "timestamp": timestamp
                    })
                })
            
            print("✅ Notification queued in database!")
            print("⚠️ Set up a cron job to process pending_notifications table")
            return True
        else:
            print("⚠️ DATABASE_URL not configured")
            
    except Exception as e:
        print(f"❌ Database queue failed: {str(e)}")
    
    # Method 5: File system fallback
    try:
        print("🔄 Trying file system fallback...")
        methods_tried.append("File System")
        
        import os
        os.makedirs("notifications", exist_ok=True)
        
        filename = f"notifications/custom_order_{username}_{int(time.time())}.txt"
        
        with open(filename, "w") as f:
            f.write(f"NOTIFICATION FAILED TO SEND\n")
            f.write(f"Methods tried: {', '.join(methods_tried)}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
            f.write(text_content)
        
        print(f"✅ Notification saved to file: {filename}")
        print("⚠️ Check the notifications/ directory for failed email attempts")
        return True  # Consider this a success since we at least saved it
        
    except Exception as e:
        print(f"❌ File system fallback failed: {str(e)}")
    
    # If we get here, everything failed
    print(f"❌ ALL NOTIFICATION METHODS FAILED!")
    print(f"Methods tried: {', '.join(methods_tried)}")
    
    # Show user a warning
    try:
        st.warning(
            "⚠️ Your order was processed but admin notification failed. "
            "Please email support@leadgeneratorempire.com with your order details."
        )
    except:
        pass
    
    return False

# Rest of the functions remain the same...
def _restore_from_credit_system(username: str) -> bool:
    """Try to restore from credit system"""
    try:
        from postgres_credit_system import credit_system
        user_info = credit_system.get_user_info(username)
        
        if user_info:
            print(f"✅ Found user in credit system: {user_info}")
            _set_session_state(username, user_info)
            return True
    except Exception as e:
        print(f"❌ Credit system restore error: {e}")
    
    return False

def _restore_from_users_json(username: str) -> bool:
    """Try to restore from users.json"""
    try:
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)
            
            if username in users:
                user_data = users[username]
                print(f"✅ Found user in users.json: {user_data}")
                _set_session_state(username, user_data)
                return True
    except Exception as e:
        print(f"❌ users.json restore error: {e}")
    
    return False

def _create_emergency_session(username: str, query_params: Dict) -> bool:
    """Create emergency session as last resort"""
    try:
        print(f"🚨 Creating emergency session for {username}")
        
        plan = query_params.get("plan", "starter")
        credits = int(query_params.get("credits", 250))
        
        emergency_user_data = {
            "username": username,
            "plan": plan,
            "credits": credits,
            "email": f"{username}@payment-recovery.com",
            "created_at": datetime.now().isoformat(),
            "emergency_recovery": True,
            "total_leads_downloaded": 0
        }
        
        _set_session_state(username, emergency_user_data)
        print(f"✅ Emergency session created for {username}")
        return True
        
    except Exception as e:
        print(f"❌ Emergency session creation failed: {e}")
        return False

def show_payment_success_message() -> bool:
    """
    Only handles plan upgrade success UI here.
    Package success is handled in stripe_checkout.handle_payment_success_url().
    Returns True if a message was shown.
    """
    qp = st.query_params
    if "success" not in qp:
        return False

    # Defer package purchases to stripe_checkout to avoid double-processing
    if "package" in qp:
        return False

    # Plan upgrade UI (keep existing look & feel)
    plan = qp.get("plan")
    if plan:
        st.success(f"Plan upgrade successful! Welcome to {plan.title()} plan!")
        if st.button("Continue to Dashboard", type="primary"):
            try:
                st.query_params.clear()
            except Exception:
                pass
            st.rerun()
        return True

    return False

def _normalize_plan_from_user_data(user_data: dict) -> str:
    """Return one of {'demo','starter','pro','ultimate'} from DB row."""
    ud = user_data or {}
    sp = (ud.get("subscribed_plan") or "").lower()
    ss = (ud.get("subscription_status") or "").lower()
    bp = (ud.get("plan") or "").lower()

    if sp == "demo" or bp == "demo":
        return "demo"
    if ss == "active" and sp in {"starter", "pro", "ultimate"}:
        return sp
    if bp in {"starter", "pro", "ultimate"}:
        return bp
    return "demo"

def update_simple_auth_state(simple_auth_instance) -> None:
    """Update simple_auth state after session restoration WITHOUT clobbering plan."""
    if not st.session_state.get('authenticated', False):
        return

    username  = st.session_state.get('username')
    user_data = st.session_state.get('user_data') or {}
    if not username:
        return

    # Sync simple_auth
    simple_auth_instance.current_user = username
    simple_auth_instance.user_data     = user_data

    # Keep credits in sync
    st.session_state['credits'] = user_data.get('credits', st.session_state.get('credits', 0))

    # Only set plan if it's missing/invalid; NEVER default to 'starter'
    current_plan = st.session_state.get('plan')
    if current_plan not in {'demo','starter','pro','ultimate'}:
        st.session_state['plan'] = _normalize_plan_from_user_data(user_data)

    print(f"Updated simple_auth state for {username} (plan={st.session_state.get('plan')})")
    print("[PLAN_GUARD] after update_simple_auth_state =>", st.session_state.get("plan"))

def create_package_stripe_session(
    stripe,
    username: str,
    package_type: str,
    amount: float,
    description: str,
    industry: str,
    location: str,
    requires_build: bool = True,
):
    """Create Stripe session for package purchases (one-time payments)."""
    import time
    from urllib.parse import quote_plus

    # Get user email safely
    try:
        user_data = st.session_state.get('user_data', {})
        user_email = user_data.get('email', f"{username}@empire.com")
    except:
        user_email = f"{username}@empire.com"

    base = APP_BASE_URL.rstrip("/")
    stamp = int(time.time())

    # Build success/cancel URLs (include requires_build + session_id)
    success_url = (
        f"{base}/?success=1"
        f"&package_success=1"
        f"&package={package_type}"
        f"&username={username}"
        f"&amount={amount}"
        f"&industry={quote_plus(industry or '')}"
        f"&location={quote_plus(location or '')}"
        f"&requires_build={'1' if requires_build else '0'}"
        f"&timestamp={stamp}"
        f"&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = (
        f"{base}/?success=0"
        f"&package_cancelled=1"
        f"&package={package_type}"
        f"&username={username}"
        f"&industry={quote_plus(industry or '')}"
        f"&location={quote_plus(location or '')}"
    )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": description,
                    "description": f"Industry: {industry} | Location: {location}"
                },
                "unit_amount": int(amount * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={
            "purchase_type": "package",
            "username": username,
            "package_type": package_type,
            "target_industry": industry,
            "target_location": location,
            "amount": str(amount),
            "requires_build": "1" if requires_build else "0",
            "order_type": "custom" if requires_build else "prebuilt",
        },
    )
    return session

def create_improved_stripe_session(stripe, username: str, plan_type: str, amount: float, description: str):
    """Create improved Stripe checkout session with better return handling"""
    
    # Get user email safely
    try:
        user_data = st.session_state.get('user_data', {})
        user_email = user_data.get('email', f"{username}@empire.com")
    except:
        user_email = f"{username}@empire.com"
        
    base = APP_BASE_URL.rstrip("/")
    # Create more robust success URL
    success_url = f"https://leadgeneratorempire.com/?success=true&plan={plan_type}&username={username}&amount={amount}&timestamp={int(time.time())}"
    cancel_url = (
        f"{base}/?cancel=1"
        f"&type=credits"
        f"&tier={plan_type.lower().replace(' ', '_')}"
        f"&username={username}"
    )
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": description
                },
                "unit_amount": int(amount * 97),
                "recurring": {"interval": "month"} if plan_type in ["starter", "pro", "ultimate"] else None
            },
            "quantity": 1,
        }],
        mode="subscription" if plan_type in ["starter", "pro", "ultimate"] else "payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=user_email,
        metadata={
            "username": username,
            "plan_type": plan_type,
            "amount": str(amount)
        }
    )
    
    return session

def debug_authentication_state(simple_auth_instance, credit_system) -> None:
    """Debug authentication state - for troubleshooting"""
    
    if st.button("Debug Authentication State"):
        st.subheader("Authentication Debug Info")
        
        # Session state
        st.markdown("**Streamlit Session State:**")
        auth_keys = ['authenticated', 'username', 'user_data', 'credits', 'login_time']
        for key in auth_keys:
            value = st.session_state.get(key, "NOT SET")
            st.text(f"{key}: {value}")
        
        # Simple auth state
        st.markdown("**Simple Auth State:**")
        st.text(f"current_user: {simple_auth_instance.current_user}")
        st.text(f"user_data: {simple_auth_instance.user_data}")
        st.text(f"is_authenticated(): {simple_auth_instance.is_authenticated()}")
        
        # URL parameters
        st.markdown("**URL Parameters:**")
        query_params = st.query_params
        if query_params:
            for key, value in query_params.items():
                st.text(f"{key}: {value}")
        else:
            st.text("No URL parameters")
        
        # Credit system check
        st.markdown("**Credit System Check:**")
        try:
            username = st.session_state.get('username', 'none')
            if username and username != 'none':
                user_info = credit_system.get_user_info(username)
                st.text(f"Credit system has user: {bool(user_info)}")
                if user_info:
                    st.json(user_info)
            else:
                st.text("No username to check")
        except Exception as e:
            st.text(f"Credit system error: {e}")
        
        # Quick fix button
        st.markdown("**Force Re-authentication:**")
        username = st.text_input("Enter username:", key="debug_username")
        if username and st.button("Force Login", key="debug_force_login"):
            try:
                user_info = credit_system.get_user_info(username)
                if user_info:
                    _set_session_state(username, user_info)
                    update_simple_auth_state(simple_auth_instance)
                    st.success("Force login successful!")
                    st.rerun()
                else:
                    st.error("User not found")
            except Exception as e:
                st.error(f"Force login failed: {e}")

def scroll_to_top():
    """Force scroll to top of page using JavaScript"""
    scroll_script = """
    <script>
        // Scroll to top immediately
        window.scrollTo(0, 0);
        
        // Also scroll after a small delay in case of timing issues
        setTimeout(function() {
            window.scrollTo(0, 0);
        }, 100);
        
        // Force focus to top of page
        document.body.scrollTop = 0;
        document.documentElement.scrollTop = 0;
    </script>
    """
    st.markdown(scroll_script, unsafe_allow_html=True)

def _set_session_state(username: str, user_data: Dict) -> None:
    """Set session state for authenticated user"""
    # FORCE restore session state
    st.session_state.authenticated = True
    st.session_state.username = username
    st.session_state.user_data = user_data
    st.session_state.credits = user_data.get('credits', 0)
    st.session_state.login_time = datetime.now().isoformat()
    
    # Also restore simple_auth state (import here to avoid circular imports)
    try:
        # We'll need to access simple_auth from the main module
        # This will be handled in the main app
        pass
    except:
        pass