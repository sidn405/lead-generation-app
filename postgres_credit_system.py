# postgres_credit_system.py - 100% Compatible PostgreSQL replacement for simple_credit_system.py
import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List

class CreditSystem:
    """PostgreSQL-based credit system - 100% compatible with original"""
    
    def __init__(self):
        """Initialize PostgreSQL connection and create tables"""
        print("🔧 Credit system initializing...")
        
        # Check if we should use PostgreSQL or fallback to JSON
        self.database_url = os.getenv('DATABASE_URL')
        self.use_postgres = bool(self.database_url)
        
        if self.use_postgres:
            try:
                self.conn = psycopg2.connect(self.database_url)
                self.conn.autocommit = True
                self._create_tables()
                print(f"✅ PostgreSQL credit system initialized: connected to database")
            except Exception as e:
                print(f"❌ PostgreSQL failed, falling back to JSON: {e}")
                self.use_postgres = False
                self._init_json_fallback()
        else:
            print("⚠️ No DATABASE_URL found, using JSON fallback")
            self._init_json_fallback()
        
        if self.use_postgres:
            self._load_users_count()
        
        print(f"🔧 Credit system initialized: {len(self.get_all_users_dict())} users loaded")
    
    def _init_json_fallback(self):
        """Initialize JSON fallback system"""
        self.users_file = "users_credits.json"
        self.transactions_file = "transactions.json"
        self.load_data()
    
    def _create_tables(self):
        """Create PostgreSQL tables"""
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(50) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                plan VARCHAR(20) DEFAULT 'demo',
                credits INTEGER DEFAULT 5,
                demo_leads_used INTEGER DEFAULT 0,
                demo_limit INTEGER DEFAULT 5,
                total_leads_downloaded INTEGER DEFAULT 0,
                subscription_active BOOLEAN DEFAULT FALSE,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                billing_status TEXT,
                billing_current_period_end BIGINT;
                monthly_credits INTEGER DEFAULT 0,
                agreed_to_terms BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                password_updated_at TIMESTAMP,
                plan_updated_at TIMESTAMP,
                terms_agreed_at TIMESTAMP,
                force_synced BOOLEAN DEFAULT FALSE,
                sync_timestamp TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
                type VARCHAR(50) NOT NULL,
                credits_used INTEGER DEFAULT 0,
                credits_added INTEGER DEFAULT 0,
                leads_downloaded INTEGER DEFAULT 0,
                platform VARCHAR(50),
                plan VARCHAR(50),
                old_plan VARCHAR(50),
                new_plan VARCHAR(50),
                credits_set INTEGER DEFAULT 0,
                monthly_credits INTEGER DEFAULT 0,
                stripe_session_id VARCHAR(255),
                credits_remaining INTEGER DEFAULT 0,
                credits_after INTEGER DEFAULT 0,
                old_credits INTEGER DEFAULT 0,
                new_credits INTEGER DEFAULT 0,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
            "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan);",
            "CREATE INDEX IF NOT EXISTS idx_transactions_username ON transactions(username);",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);"
        ]
        
        for sql in tables_sql:
            self._execute_query(sql)
    
    def _execute_query(self, query, params=None, fetch=False):
        """Execute SQL query"""
        if not self.use_postgres:
            return [] if fetch else 0
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return cur.rowcount
        except Exception as e:
            print(f"❌ Query error: {e}")
            return [] if fetch else 0
    
    def _load_users_count(self):
        """Load user count for initialization"""
        if self.use_postgres:
            try:
                result = self._execute_query("SELECT COUNT(*) as count FROM users", fetch=True)
                self.user_count = result[0]['count'] if result else 0
            except:
                self.user_count = 0
        else:
            self.user_count = len(getattr(self, '_users', {}))
            
    def record_lead_download(self, username: str, platform: str, leads_count: int):
        """
        Persist a lead download event so dashboards can rebuild history after deploy.
        Uses the transactions table you already have.
        """
        q = """
        INSERT INTO transactions
        (username, type, platform, leads_downloaded, credits_used, timestamp)
        VALUES
        (%s, 'lead_download', %s, %s, %s, NOW())
        """
        with self.conn.cursor() as cur:
            cur.execute(q, (username, platform, leads_count, leads_count))
            self.conn.commit()
            
    def get_usage_summary(self, username: str, since_days: int = 180):
        """
        Returns totals + per-platform stats from transactions, not from CSVs.
        """
        q = """
        WITH recent_tx AS (
        SELECT *
        FROM transactions
        WHERE username = %s
            AND timestamp >= NOW() - INTERVAL '%s days'
        )
        SELECT
        COALESCE(SUM(CASE WHEN type='lead_download'
                            THEN COALESCE(leads_downloaded, credits_used, 0) END), 0) AS total_leads,
        COALESCE(COUNT(CASE WHEN type='lead_download' THEN 1 END), 0) AS total_campaigns,
        MIN(timestamp) AS first_ts,
        MAX(timestamp) AS last_ts
        FROM recent_tx
        """
        q_plat = """
        SELECT LOWER(COALESCE(platform, 'unknown')) AS platform,
            COALESCE(SUM(COALESCE(leads_downloaded, credits_used, 0)), 0) AS leads
        FROM transactions
        WHERE username=%s
        AND timestamp >= NOW() - INTERVAL '%s days'
        AND type='lead_download'
        GROUP BY LOWER(COALESCE(platform, 'unknown'))
        ORDER BY leads DESC
        """
        with self.conn.cursor() as cur:
            cur.execute(q, (username, since_days))
            row = cur.fetchone()
            total_leads = int(row[0] or 0)
            total_campaigns = int(row[1] or 0)
            first_ts, last_ts = row[2], row[3]

            cur.execute(q_plat, (username, since_days))
            platform_rows = cur.fetchall()
            per_platform = {r[0]: int(r[1]) for r in platform_rows}

        return {
            "total_leads": total_leads,
            "total_campaigns": total_campaigns,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "per_platform": per_platform
        }

    # === JSON FALLBACK METHODS ===
    def load_data(self):
        """Load user credits and transaction data (JSON fallback)"""
        if self.use_postgres:
            return
            
        # Load users with credits
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self._users = json.load(f)
        else:
            self._users = {}
        
        # Load transaction history
        if os.path.exists(self.transactions_file):
            with open(self.transactions_file, 'r') as f:
                self.transactions = json.load(f)
        else:
            self.transactions = []

    def save_data(self):
        """Save all data to files (JSON fallback)"""
        if self.use_postgres:
            return
            
        with open(self.users_file, 'w') as f:
            json.dump(self._users, f, indent=4)
        
        with open(self.transactions_file, 'w') as f:
            json.dump(self.transactions, f, indent=4)

    # === UNIFIED METHODS (work with both PostgreSQL and JSON) ===
    def get_all_users_dict(self) -> Dict:
        """Get all users as dictionary (for compatibility)"""
        if self.use_postgres:
            users = self._execute_query("SELECT * FROM users", fetch=True)
            return {user['username']: dict(user) for user in users} if users else {}
        else:
            return getattr(self, '_users', {})

    @property 
    def users(self) -> Dict:
        """Property to maintain compatibility with original users access"""
        return self.get_all_users_dict()

    def hash_password(self, password: str) -> str:
        """Simple password hashing"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, email: str, password: str) -> Tuple[bool, str]:
        """Create new user with demo mode"""
        if self.use_postgres:
            # Check if user exists
            existing = self._execute_query(
                "SELECT username FROM users WHERE username = %s OR email = %s",
                (username, email), fetch=True
            )
            if existing:
                return False, "Username already exists"
            
            # Create user
            self._execute_query("""
                INSERT INTO users (username, email, password_hash, plan, credits, demo_leads_used, demo_limit, total_leads_downloaded, agreed_to_terms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, email, self.hash_password(password), "demo", 0, 0, 5, 0, False))
            
        else:
            # JSON fallback
            if username in self._users:
                return False, "Username already exists"
            
            self._users[username] = {
                "email": email,
                "password_hash": self.hash_password(password),
                "credits": 0,
                "plan": "demo",
                "created_at": datetime.now().isoformat(),
                "last_login": None,
                "total_leads_downloaded": 0,
                "transactions": [],
                "agreed_to_terms": False,
                "demo_leads_used": 0,
                "demo_limit": 5
            }
            self.save_data()
        
        return True, "Demo account created with 5 free demo leads"
    
    # In your postgres_credit_system.py, add this method:
    def delete_user(self, username: str) -> bool:
        """Delete user completely from PostgreSQL"""
        try:
            if not self.conn:  # Changed from self.connection to self.conn
                return False
            
            cursor = self.conn.cursor()  # Changed from self.connection to self.conn
            
            # Delete from users table
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))
            deleted_count = cursor.rowcount
            
            self.conn.commit()  # Changed from self.connection to self.conn
            cursor.close()
            
            # Also remove from memory cache if it exists
            if hasattr(self, 'users') and username in self.users:
                del self.users[username]
            
            print(f"Deleted user {username} from PostgreSQL (rows affected: {deleted_count})")
            return deleted_count > 0
            
        except Exception as e:
            print(f"PostgreSQL user deletion failed: {e}")
            if self.conn:  # Changed from self.connection to self.conn
                self.conn.rollback()
            return False

    def get_demo_status(self, username: str) -> Tuple[bool, int, int]:
        """Get demo status: (is_demo, used, remaining)"""
        user = self.get_user_info(username)
        if not user or user.get("plan") != "demo":
            return False, 0, 0
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        remaining = max(0, limit - used)
        
        return True, used, remaining

    def can_use_demo(self, username: str) -> Tuple[bool, int]:
        """Check if user can still use demo leads"""
        user = self.get_user_info(username)
        if not user or not self.is_demo_user(username):
            return False, 0
        
        used = user.get("demo_leads_used", 0)
        limit = user.get("demo_limit", 5)
        remaining = max(0, limit - used)
        
        return remaining > 0, remaining

    def consume_demo_lead(self, username: str) -> bool:
        """Consume one demo lead"""
        if self.use_postgres:
            # Check and update in one query
            rows = self._execute_query("""
                UPDATE users 
                SET demo_leads_used = demo_leads_used + 1 
                WHERE username = %s AND plan = 'demo' AND demo_leads_used < demo_limit
            """, (username,))
            return rows > 0
        else:
            # JSON fallback
            if username not in self._users:
                return False
            
            user = self._users[username]
            if not self.is_demo_user(username):
                return False
            
            used = user.get("demo_leads_used", 0)
            limit = user.get("demo_limit", 5)
            
            if used >= limit:
                return False
            
            user["demo_leads_used"] = used + 1
            self.save_data()
            return True

    def login_user(self, identifier: str, password: str) -> Tuple[bool, str, Dict]:
        """Authenticate user by username OR email"""
        password_hash = self.hash_password(password)
        
        if self.use_postgres:
            # Try username or email (case-insensitive)
            user = self._execute_query("""
                SELECT * FROM users 
                WHERE (LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)) 
                AND password_hash = %s
            """, (identifier, identifier, password_hash), fetch=True)
            
            if user:
                user_data = dict(user[0])
                # Update last login
                self._execute_query(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s",
                    (user_data['username'],)
                )
                return True, f"Login successful for {user_data['username']}", user_data
            else:
                return False, "Invalid password", {}
        else:
            # JSON fallback - original logic
            if identifier in self._users:
                user = self._users[identifier]
                if user["password_hash"] == password_hash:
                    user["last_login"] = datetime.now().isoformat()
                    self.save_data()
                    return True, f"Login successful for {identifier}", user
                else:
                    return False, "Invalid password", {}
            
            # Try email lookup
            for username, user_data in self._users.items():
                if user_data.get("email", "").lower() == identifier.lower():
                    if user_data["password_hash"] == password_hash:
                        user_data["last_login"] = datetime.now().isoformat()
                        self.save_data()
                        return True, f"Login successful for {username} (via email)", user_data
                    else:
                        return False, "Invalid password", {}
            
            return False, f"User not found: {identifier}", {}

    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        if self.use_postgres:
            user = self._execute_query(
                "SELECT * FROM users WHERE username = %s", (username,), fetch=True
            )
            return dict(user[0]) if user else None
        else:
            return self._users.get(username)

    def is_demo_user(self, username: str) -> bool:
        """Check if user is in demo mode"""
        user = self.get_user_info(username)
        return user.get("plan", "demo") == "demo" if user else True

    def check_credits(self, username: str, required_credits: int) -> Tuple[bool, str, int]:
        """Check if user has enough credits"""
        user = self.get_user_info(username)
        if not user:
            return False, "User not found", 0
        
        current_credits = user.get("credits", 0)
        
        if current_credits >= required_credits:
            return True, f"{current_credits} credits available", current_credits
        else:
            return False, f"Insufficient credits: {current_credits}/{required_credits}", current_credits

    def consume_credits(self, username: str, credits_used: int, leads_downloaded: int, platform: str) -> bool:
        """Consume credits and log the transaction"""
        user = self.get_user_info(username)
        if not user or user.get("credits", 0) < credits_used:
            return False
        
        if self.use_postgres:
            # Update user credits
            self._execute_query("""
                UPDATE users 
                SET credits = credits - %s, total_leads_downloaded = total_leads_downloaded + %s
                WHERE username = %s
            """, (credits_used, leads_downloaded, username))
            
            # Log transaction
            self._execute_query("""
                INSERT INTO transactions (username, type, credits_used, leads_downloaded, platform, credits_remaining)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, "lead_download", credits_used, leads_downloaded, platform, user["credits"] - credits_used))
            
        else:
            # JSON fallback
            user["credits"] -= credits_used
            user["total_leads_downloaded"] += leads_downloaded
            
            transaction = {
                "username": username,
                "type": "lead_download",
                "credits_used": credits_used,
                "leads_downloaded": leads_downloaded,
                "platform": platform,
                "timestamp": datetime.now().isoformat(),
                "credits_remaining": user["credits"]
            }
            
            user.setdefault("transactions", []).append(transaction)
            self.transactions.append(transaction)
            self.save_data()
        
        return True

    def add_credits(self, username: str, credits: int, plan: str, stripe_session_id: str = None) -> bool:
        """Add credits to user account (from purchase) with proper plan handling"""
        user = self.get_user_info(username)
        if not user:
            print(f"❌ User {username} not found for credit addition")
            return False

        old_credits = user.get("credits", 0)
        new_credits = old_credits + credits
        
        # Plan handling logic (same as original)
        if plan and plan.lower() not in ["unknown", "", "credit_purchase"]:
            new_plan = plan.lower()
            print(f"🔧 Plan upgraded: {username} {user.get('plan', 'demo')} → {plan}")
        elif plan == "credit_purchase":
            new_plan = user.get("plan", "demo")
            print(f"💳 Credits added: {username} +{credits} (plan unchanged: {new_plan})")
        else:
            # Infer plan from credits
            current_plan = user.get("plan", "demo")
            if current_plan == "demo":
                if new_credits >= 10000:
                    new_plan = "ultimate"
                elif new_credits >= 2000:
                    new_plan = "pro"
                elif new_credits >= 500:
                    new_plan = "starter"
                else:
                    new_plan = "demo"
                print(f"🔧 Plan inferred from credits: {username} → {new_plan}")
            else:
                new_plan = current_plan

        print(f"💎 Credits: {old_credits} → {new_credits}")

        if self.use_postgres:
            # Update user
            self._execute_query("""
                UPDATE users SET credits = %s, plan = %s WHERE username = %s
            """, (new_credits, new_plan, username))
            
            # Log transaction
            self._execute_query("""
                INSERT INTO transactions (username, type, credits_added, plan, stripe_session_id, credits_after)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, "credit_purchase" if plan == "credit_purchase" else "plan_upgrade", 
                  credits, new_plan, stripe_session_id or "unknown", new_credits))
        else:
            # JSON fallback
            user["credits"] = new_credits
            user["plan"] = new_plan
            
            transaction = {
                "username": username,
                "type": "credit_purchase" if plan == "credit_purchase" else "plan_upgrade",
                "credits_added": credits,
                "plan": new_plan,
                "stripe_session_id": stripe_session_id or "unknown",
                "timestamp": datetime.now().isoformat(),
                "credits_after": new_credits
            }
            
            user.setdefault("transactions", []).append(transaction)
            self.transactions.append(transaction)
            self.save_data()

        return True

    def activate_subscription(self, username: str, plan: str, monthly_credits: int, stripe_session_id: str) -> bool:
        """Activate a monthly subscription plan"""
        user = self.get_user_info(username)
        if not user:
            print(f"❌ User {username} not found for subscription activation")
            return False

        old_plan = user.get("plan", "demo")
        old_credits = user.get("credits", 0)
        
        print(f"✅ Subscription activated: {username}")
        print(f"   Plan: {old_plan} → {plan}")
        print(f"   Credits: {old_credits} → {monthly_credits}/month")

        if self.use_postgres:
            # Update user
            self._execute_query("""
                UPDATE users 
                SET plan = %s, credits = %s, subscription_active = TRUE, monthly_credits = %s
                WHERE username = %s
            """, (plan.lower(), monthly_credits, monthly_credits, username))
            
            # Log transaction
            self._execute_query("""
                INSERT INTO transactions (username, type, plan, old_plan, monthly_credits, stripe_session_id, credits_set)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, "subscription_activation", plan, old_plan, monthly_credits, stripe_session_id or "unknown", monthly_credits))
        else:
            # JSON fallback
            user["plan"] = plan.lower()
            user["credits"] = monthly_credits
            user["subscription_active"] = True
            user["subscription_started"] = datetime.now().isoformat()
            user["monthly_credits"] = monthly_credits
            
            transaction = {
                "username": username,
                "type": "subscription_activation",
                "plan": plan,
                "old_plan": old_plan,
                "monthly_credits": monthly_credits,
                "stripe_session_id": stripe_session_id or "unknown",
                "timestamp": datetime.now().isoformat(),
                "credits_set": monthly_credits
            }
            
            user.setdefault("transactions", []).append(transaction)
            self.transactions.append(transaction)
            self.save_data()

        return True
    
    def set_stripe_billing(self, username: str, customer_id: str | None,
                       subscription_id: str | None, current_period_end_epoch: int = 0) -> bool:
        """Persist Stripe identifiers and (optionally) the current period end."""
        try:
            if self.use_postgres:
                self._execute_query("""
                    UPDATE users
                    SET stripe_customer_id = COALESCE(%s, stripe_customer_id),
                        stripe_subscription_id = COALESCE(%s, stripe_subscription_id),
                        billing_current_period_end = CASE WHEN %s > 0 THEN %s ELSE billing_current_period_end END
                    WHERE username = %s
                """, (customer_id, subscription_id, current_period_end_epoch, current_period_end_epoch, username))
            else:
                u = self._users.get(username, {})
                if customer_id:            u["stripe_customer_id"] = customer_id
                if subscription_id:        u["stripe_subscription_id"] = subscription_id
                if current_period_end_epoch:
                    u["billing_current_period_end"] = int(current_period_end_epoch)
                self._users[username] = u
                self.save_data()
            return True
        except Exception as e:
            print(f"[billing] set_stripe_billing error: {e}")
            return False


    def check_subscription_status(self, username: str) -> tuple[bool, str]:
        """
        Return (active, status_string). If Stripe says the sub is canceled/past_due,
        we flip subscription_active=false and optionally downgrade plan.
        """
        try:
            # 1) read what we have
            if self.use_postgres:
                row = self._execute_query("""
                    SELECT stripe_subscription_id, plan, monthly_credits
                    , subscription_active
                    FROM users WHERE username=%s
                """, (username,), fetch=True)
                if not row:
                    return False, "missing_user"
                r = dict(row[0])
                sub_id = r.get("stripe_subscription_id")
            else:
                r = self._users.get(username, {})
                sub_id = r.get("stripe_subscription_id")

            if not sub_id:
                return bool(r.get("subscription_active")), "no_subscription_id"

            # 2) ask Stripe
            import stripe
            sub = stripe.Subscription.retrieve(sub_id)
            status = getattr(sub, "status", "unknown") or "unknown"
            active = status in ("active", "trialing")

            # 3) persist status + take action
            if self.use_postgres:
                self._execute_query("""
                    UPDATE users
                    SET billing_status=%s,
                        subscription_active=%s
                    WHERE username=%s
                """, (status, active, username))
            else:
                r["billing_status"] = status
                r["subscription_active"] = active
                self._users[username] = r
                self.save_data()

            # Optional: downgrade on cancel
            if not active:
                try:
                    self.update_user_plan(username, "starter")
                except Exception:
                    pass

            return active, status
        except Exception as e:
            print(f"[billing] check_subscription_status error: {e}")
            return False, "error"


    def get_user_stats(self, username: str) -> Dict:
        """Get user statistics"""
        user = self.get_user_info(username)
        if not user:
            return {}

        if self.use_postgres:
            # Get transaction stats from database
            stats = self._execute_query("""
                SELECT 
                    COALESCE(SUM(
                        CASE 
                        WHEN type IN ('credit_purchase','plan_upgrade') THEN credits_added
                        WHEN type = 'subscription_activation'            THEN credits_set
                        ELSE 0
                        END
                    ),0) AS total_purchased,
                    COALESCE(SUM(CASE WHEN type='lead_download' THEN credits_used ELSE 0 END),0) AS total_used
                    FROM transactions
                    WHERE username = %s
            """, (username,), fetch=True)
            
            if stats:
                total_purchased = stats[0]['total_purchased'] or 0
                total_used = stats[0]['total_used'] or 0
            else:
                total_purchased = 0
                total_used = 0
        else:
            # JSON fallback
            transactions = user.get("transactions", [])
            total_purchased = sum(t.get("credits_added", 0) for t in transactions if t.get("type") in ["credit_purchase", "plan_upgrade", "subscription_activation"])
            total_used = sum(t.get("credits_used", 0) for t in transactions if t.get("type") == "lead_download")

        credits_used = user.get("total_leads_downloaded", 0)  # 1 lead = 1 credit used
        
        return {
            "current_credits": user.get("credits", 0),
            "total_purchased": total_purchased,
            "credits_used": credits_used,
            "total_leads_downloaded": user.get("total_leads_downloaded", 0),
            "plan": user.get("plan", "demo"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "agreed_to_terms": user.get("agreed_to_terms", False),
            "subscription_active": user.get("subscription_active", False),
            "monthly_credits": user.get("monthly_credits", 0)
        }

    def get_pricing_tiers(self) -> List[Dict]:
        """Get available pricing tiers"""
        return [
            {
                "name": "Lead Starter",
                "credits": 500,
                "price": 97,
                "description": "Perfect for small campaigns",
                "features": ["500 leads", "All platforms", "Basic DMs", "CSV export"]
            },
            {
                "name": "Lead Pro", 
                "credits": 2000,
                "price": 297,
                "description": "Most popular for agencies",
                "features": ["2,000 leads", "All platforms", "Advanced DMs", "Priority support", "Geo-targeting"]
            },
            {
                "name": "Lead Empire",
                "credits": 5000, 
                "price": 897,
                "description": "Enterprise campaigns",
                "features": ["5,000 leads", "All platforms", "Custom DMs", "Dedicated support", "Advanced filtering"]
            }
        ]

    def generate_invoice_data(self, username: str, transaction_id: str) -> Dict:
        """Generate invoice data for PDF export"""
        user = self.get_user_info(username)
        if not user:
            return {}
        
        # Find the transaction
        if self.use_postgres:
            transaction = self._execute_query(
                "SELECT * FROM transactions WHERE stripe_session_id = %s", 
                (transaction_id,), fetch=True
            )
            transaction = dict(transaction[0]) if transaction else None
        else:
            transaction = None
            for t in self.transactions:
                if t.get("stripe_session_id") == transaction_id:
                    transaction = t
                    break
        
        if not transaction:
            return {}
        
        return {
            "invoice_number": f"LGE-{transaction_id[-8:].upper()}",
            "date": transaction.get("timestamp", datetime.now().isoformat()),
            "customer": {
                "username": username,
                "email": user.get("email", "")
            },
            "items": [{
                "description": f"{transaction.get('plan', 'Unknown').title()} Credits",
                "credits": transaction.get("credits_added", 0),
                "amount": self._get_price_for_plan(transaction.get("plan", ""))
            }],
            "total": self._get_price_for_plan(transaction.get("plan", "")),
            "payment_method": "Credit Card (Stripe)",
            "terms": "No refunds. Credits expire after 90 days."
        }

    def _get_price_for_plan(self, plan: str) -> float:
        """Get price for plan name"""
        pricing = {
            "lead starter": 97,
            "lead pro": 297, 
            "lead empire": 897
        }
        return pricing.get(plan.lower(), 0)

    def agree_to_terms(self, username: str) -> bool:
        """Record that user agreed to terms"""
        if self.use_postgres:
            rows = self._execute_query("""
                UPDATE users 
                SET agreed_to_terms = TRUE, terms_agreed_at = CURRENT_TIMESTAMP 
                WHERE username = %s
            """, (username,))
            return rows > 0
        else:
            if username not in self._users:
                return False
            
            self._users[username]["agreed_to_terms"] = True
            self._users[username]["terms_agreed_at"] = datetime.now().isoformat()
            self.save_data()
            return True

    def update_user_plan(self, username: str, new_plan: str) -> bool:
        """Update user's plan and add appropriate credits"""
        user = self.get_user_info(username)
        if not user:
            print(f"❌ User {username} not found for plan update")
            return False
        
        old_plan = user.get("plan", "demo")
        
        # Add plan-specific credits for plan upgrades
        plan_credits = {
            'starter': 250,
            'pro': 2000,
            'ultimate': 9999
        }
        
        credits_to_add = plan_credits.get(new_plan, 0)
        
        if self.use_postgres:
            if credits_to_add > 0:
                self._execute_query("""
                    UPDATE users 
                    SET plan = %s, credits = %s, plan_updated_at = CURRENT_TIMESTAMP 
                    WHERE username = %s
                """, (new_plan, credits_to_add, username))
            else:
                self._execute_query("""
                    UPDATE users 
                    SET plan = %s, plan_updated_at = CURRENT_TIMESTAMP 
                    WHERE username = %s
                """, (new_plan, username))
            
            # Log transaction
            self._execute_query("""
                INSERT INTO transactions (username, type, old_plan, new_plan, credits_set)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, "plan_upgrade", old_plan, new_plan, credits_to_add))
        else:
            self._users[username]["plan"] = new_plan
            self._users[username]["plan_updated_at"] = datetime.now().isoformat()
            
            if credits_to_add > 0:
                self._users[username]["credits"] = credits_to_add
                print(f"💎 Set {new_plan} plan credits to {credits_to_add}")
            
            # Log plan change transaction
            transaction = {
                "username": username,
                "type": "plan_upgrade",
                "old_plan": old_plan,
                "new_plan": new_plan,
                "credits_set": credits_to_add,
                "timestamp": datetime.now().isoformat()
            }
            
            self._users[username].setdefault("transactions", []).append(transaction)
            self.transactions.append(transaction)
            self.save_data()
        
        print(f"✅ Plan updated: {username} {old_plan} → {new_plan}")
        return True

    def fix_user_credits(self, username: str) -> bool:
        """Fix user credits to match their plan"""
        user = self.get_user_info(username)
        if not user:
            return False
        
        current_plan = user.get("plan", "demo")
        
        # Set correct credits based on plan
        correct_credits = {
            'demo': 5,
            'starter': 250,
            'pro': 2000,
            'ultimate': 9999
        }
        
        if current_plan in correct_credits:
            old_credits = user.get("credits", 0)
            new_credits = correct_credits[current_plan]
            
            if self.use_postgres:
                self._execute_query(
                    "UPDATE users SET credits = %s WHERE username = %s",
                    (new_credits, username)
                )
                
                # Log the fix
                self._execute_query("""
                    INSERT INTO transactions (username, type, plan, old_credits, new_credits, reason)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (username, "credit_fix", current_plan, old_credits, new_credits, "Credit correction to match plan"))
            else:
                self._users[username]["credits"] = new_credits
                
                # Log the fix
                transaction = {
                    "username": username,
                    "type": "credit_fix",
                    "plan": current_plan,
                    "old_credits": old_credits,
                    "new_credits": new_credits,
                    "timestamp": datetime.now().isoformat(),
                    "reason": "Credit correction to match plan"
                }
                
                self._users[username].setdefault("transactions", []).append(transaction)
                self.transactions.append(transaction)
                self.save_data()
            
            print(f"✅ Fixed credits for {username}: {current_plan} plan → {new_credits} credits")
            return True
        
        return False

    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update user password in credit system"""
        user = self.get_user_info(username)
        if not user:
            print(f"❌ User {username} not found in credit system")
            return False
        
        old_hash = user.get("password_hash", "")
        new_hash = self.hash_password(new_password)
        
        if self.use_postgres:
            self._execute_query("""
                UPDATE users 
                SET password_hash = %s, password_updated_at = CURRENT_TIMESTAMP 
                WHERE username = %s
            """, (new_hash, username))
        else:
            self._users[username]["password_hash"] = new_hash
            self._users[username]["password_updated_at"] = datetime.now().isoformat()
            self.save_data()
        
        print(f"✅ Credit system password updated for {username}")
        print(f"🔧 Old hash: {old_hash[:20]}...")
        print(f"🔧 New hash: {new_hash[:20]}...")
        return True

    def reload_user_data(self):
        """Force reload user data from files"""
        print("🔄 Reloading credit system data...")
        
        if self.use_postgres:
            self._load_users_count()
            new_user_count = self.user_count
            print(f"✅ PostgreSQL data reloaded: {new_user_count} users")
        else:
            old_user_count = len(self._users)
            self.load_data()
            new_user_count = len(self._users)
            print(f"✅ JSON data reloaded: {new_user_count} users (was {old_user_count})")
            
            # Debug: Show what users we have
            for username in list(self._users.keys())[:5]:
                user = self._users[username]
                print(f"👤 {username}: {user.get('email', 'no email')} | {user.get('plan', 'no plan')}")

    def debug_user_password(self, username: str, password: str) -> Dict:
        """Debug password checking in credit system"""
        all_users = self.get_all_users_dict()
        
        if username not in all_users:
            available_users = list(all_users.keys())
            return {
                "error": "User not found in credit system",
                "available_users": available_users[:10],
                "total_users": len(available_users)
            }
        
        user = all_users[username]
        stored_hash = user.get("password_hash", "")
        test_hash = self.hash_password(password)
        
        return {
            "username": username,
            "email": user.get("email", ""),
            "stored_hash": stored_hash[:20] + "..." if stored_hash else "NO HASH",
            "test_hash": test_hash[:20] + "...", 
            "hashes_match": stored_hash == test_hash,
            "plan": user.get("plan", "unknown"),
            "credits": user.get("credits", 0),
            "last_login": user.get("last_login", "never"),
            "password_updated_at": user.get("password_updated_at", "never")
        }

    def force_user_sync(self, username: str, email: str, password: str, plan: str = "demo", credits: int = 5) -> bool:
        """Force create/update user with specific data (for fixing sync issues)"""
        password_hash = self.hash_password(password)
        
        if self.use_postgres:
            # Upsert user
            self._execute_query("""
                INSERT INTO users (username, email, password_hash, plan, credits, demo_leads_used, demo_limit, 
                                 total_leads_downloaded, agreed_to_terms, force_synced, sync_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (username) DO UPDATE SET
                    email = EXCLUDED.email,
                    password_hash = EXCLUDED.password_hash,
                    plan = EXCLUDED.plan,
                    credits = EXCLUDED.credits,
                    force_synced = TRUE,
                    sync_timestamp = CURRENT_TIMESTAMP,
                    last_login = CURRENT_TIMESTAMP
            """, (username, email, password_hash, plan, credits, 0, 5, 0, True, True))
        else:
            # JSON fallback - get existing data if available
            existing_user = self._users.get(username, {})
            
            user_data = {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "plan": plan,
                "credits": credits,
                "created_at": existing_user.get("created_at", datetime.now().isoformat()),
                "last_login": datetime.now().isoformat(),
                "password_updated_at": datetime.now().isoformat(),
                "total_leads_downloaded": existing_user.get("total_leads_downloaded", 0),
                "transactions": existing_user.get("transactions", []),
                "demo_leads_used": existing_user.get("demo_leads_used", 0),
                "demo_limit": existing_user.get("demo_limit", 5),
                "force_synced": True,
                "sync_timestamp": datetime.now().isoformat()
            }
            
            self._users[username] = user_data
            self.save_data()
        
        print(f"🔧 Force synced user: {username}")
        print(f"🔧 Email: {email}")
        print(f"🏷️ Plan: {plan}")
        print(f"💎 Credits: {credits}")
        return True

    def get_user_by_email(self, email: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Find user by email address"""
        if self.use_postgres:
            user = self._execute_query(
                "SELECT * FROM users WHERE email = %s", (email,), fetch=True
            )
            if user:
                user_data = dict(user[0])
                return user_data['username'], user_data
            return None, None
        else:
            for username, user_data in self._users.items():
                if user_data.get("email", "").lower() == email.lower():
                    return username, user_data
            return None, None

    def verify_system_integrity(self) -> Dict:
        """Verify the integrity of the credit system"""
        all_users = self.get_all_users_dict()
        
        issues = []
        stats = {
            "total_users": len(all_users),
            "users_with_emails": 0,
            "users_with_passwords": 0,
            "demo_users": 0,
            "paid_users": 0,
            "issues": []
        }
        
        for username, user_data in all_users.items():
            # Check email
            if user_data.get("email"):
                stats["users_with_emails"] += 1
            else:
                issues.append(f"❌ {username}: No email")
            
            # Check password hash
            if user_data.get("password_hash"):
                stats["users_with_passwords"] += 1
            else:
                issues.append(f"❌ {username}: No password hash")
            
            # Check plan
            plan = user_data.get("plan", "unknown")
            if plan == "demo":
                stats["demo_users"] += 1
            else:
                stats["paid_users"] += 1
        
        stats["issues"] = issues
        return stats

    def get_admin_stats(self) -> Dict:
        """Get admin statistics"""
        all_users = self.get_all_users_dict()
        
        total_users = len(all_users)
        starter_users = len([u for u in all_users.values() if u.get("plan") == "starter"])
        paid_users = total_users - starter_users
        
        if self.use_postgres:
            # Calculate from database
            revenue_result = self._execute_query("""
                SELECT SUM(credits_added * 
                    CASE 
                        WHEN plan = 'lead starter' THEN 97
                        WHEN plan = 'lead pro' THEN 297
                        WHEN plan = 'lead empire' THEN 897
                        ELSE 0
                    END) as total_revenue
                FROM transactions WHERE type = 'credit_purchase'
            """, fetch=True)
            
            leads_result = self._execute_query("""
                SELECT SUM(leads_downloaded) as total_leads
                FROM transactions WHERE type = 'lead_download'
            """, fetch=True)
            
            total_revenue = revenue_result[0]['total_revenue'] or 0 if revenue_result else 0
            total_leads_served = leads_result[0]['total_leads'] or 0 if leads_result else 0
            total_transactions = self._execute_query("SELECT COUNT(*) as count FROM transactions", fetch=True)[0]['count']
        else:
            # Calculate from JSON
            total_revenue = sum(self._get_price_for_plan(t.get("plan", "")) for t in self.transactions if t.get("type") == "credit_purchase")
            total_leads_served = sum(t.get("leads_downloaded", 0) for t in self.transactions if t.get("type") == "lead_download")
            total_transactions = len(self.transactions)
        
        return {
            "total_users": total_users,
            "starter_users": starter_users,
            "paid_users": paid_users,
            "total_revenue": total_revenue,
            "total_leads_served": total_leads_served,
            "total_transactions": total_transactions
        }

# Global instance
credit_system = CreditSystem()

# Backwards compatibility alias 
postgres_credit_system = credit_system

# Initialize functions for backwards compatibility
def initialize_postgres_credit_system():
    """Initialize the PostgreSQL credit system (for compatibility)"""
    return credit_system

# Convenience functions for scrapers (100% compatible)
def check_user_credits(username: str, estimated_leads: int) -> Tuple[bool, str]:
    """Check if user has enough credits for estimated leads"""
    return credit_system.check_credits(username, estimated_leads)

def consume_user_credits(username: str, leads_downloaded: int, platform: str) -> bool:
    """Consume credits after successful scraping"""
    return credit_system.consume_credits(username, leads_downloaded, leads_downloaded, platform)