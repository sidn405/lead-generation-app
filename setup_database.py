"""
Database setup script for PostgreSQL
Run this once to create tables and migrate data
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

def get_database_connection():
    """Get database connection from environment"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set!")
        print("Set it to your PostgreSQL connection string")
        return None
    
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        print("✅ Connected to PostgreSQL successfully!")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return None

def create_tables(conn):
    """Create the required tables"""
    print("🔧 Creating database tables...")
    
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
    
    try:
        with conn.cursor() as cur:
            for sql in tables_sql:
                cur.execute(sql)
        print("✅ Tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def migrate_json_data(conn):
    """Migrate existing JSON data to PostgreSQL"""
    print("📦 Migrating existing JSON data...")
    
    # Check for existing JSON files
    json_files = ['users_credits.json', 'users.json']
    users_migrated = 0
    
    for json_file in json_files:
        if not os.path.exists(json_file):
            print(f"📄 {json_file} not found, skipping...")
            continue
        
        print(f"📄 Processing {json_file}...")
        
        try:
            with open(json_file, 'r') as f:
                users_data = json.load(f)
            
            with conn.cursor() as cur:
                for username, user_data in users_data.items():
                    try:
                        # Extract user fields
                        email = user_data.get('email', f"{username}@migrated.local")
                        password_hash = user_data.get('password_hash', 'needs_reset')
                        plan = user_data.get('plan', 'demo')
                        credits = user_data.get('credits', 0)
                        demo_leads_used = user_data.get('demo_leads_used', 0)
                        demo_limit = user_data.get('demo_limit', 5)
                        total_leads_downloaded = user_data.get('total_leads_downloaded', 0)
                        subscription_active = user_data.get('subscription_active', False)
                        monthly_credits = user_data.get('monthly_credits', 0)
                        agreed_to_terms = user_data.get('agreed_to_terms', False)
                        
                        # Insert user
                        cur.execute("""
                            INSERT INTO users (
                                username, email, password_hash, plan, credits,
                                demo_leads_used, demo_limit, total_leads_downloaded,
                                subscription_active, monthly_credits, agreed_to_terms,
                                created_at, last_login, password_updated_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (username) DO UPDATE SET
                                email = EXCLUDED.email,
                                password_hash = EXCLUDED.password_hash,
                                plan = EXCLUDED.plan,
                                credits = EXCLUDED.credits,
                                demo_leads_used = EXCLUDED.demo_leads_used,
                                total_leads_downloaded = EXCLUDED.total_leads_downloaded,
                                subscription_active = EXCLUDED.subscription_active,
                                monthly_credits = EXCLUDED.monthly_credits,
                                agreed_to_terms = EXCLUDED.agreed_to_terms,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            username, email, password_hash, plan, credits,
                            demo_leads_used, demo_limit, total_leads_downloaded,
                            subscription_active, monthly_credits, agreed_to_terms,
                            user_data.get('created_at', datetime.now().isoformat()),
                            user_data.get('last_login'),
                            user_data.get('password_updated_at')
                        ))
                        
                        # Migrate transactions
                        transactions = user_data.get('transactions', [])
                        for transaction in transactions:
                            try:
                                cur.execute("""
                                    INSERT INTO transactions (
                                        username, type, credits_used, credits_added, leads_downloaded,
                                        platform, plan, old_plan, new_plan, credits_set,
                                        monthly_credits, stripe_session_id, credits_remaining,
                                        credits_after, old_credits, new_credits, reason, timestamp
                                    ) VALUES (
                                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                                    )
                                    ON CONFLICT DO NOTHING
                                """, (
                                    username,
                                    transaction.get('type', 'unknown'),
                                    transaction.get('credits_used', 0),
                                    transaction.get('credits_added', 0),
                                    transaction.get('leads_downloaded', 0),
                                    transaction.get('platform'),
                                    transaction.get('plan'),
                                    transaction.get('old_plan'),
                                    transaction.get('new_plan'),
                                    transaction.get('credits_set', 0),
                                    transaction.get('monthly_credits', 0),
                                    transaction.get('stripe_session_id'),
                                    transaction.get('credits_remaining', 0),
                                    transaction.get('credits_after', 0),
                                    transaction.get('old_credits', 0),
                                    transaction.get('new_credits', 0),
                                    transaction.get('reason'),
                                    transaction.get('timestamp', datetime.now().isoformat())
                                ))
                            except Exception as e:
                                print(f"⚠️ Failed to migrate transaction for {username}: {e}")
                        
                        users_migrated += 1
                        print(f"✅ Migrated user: {username}")
                        
                    except Exception as e:
                        print(f"❌ Failed to migrate {username}: {e}")
                        
        except Exception as e:
            print(f"❌ Error processing {json_file}: {e}")
    
    print(f"🎉 Migration complete! {users_migrated} users migrated.")
    return users_migrated > 0

def verify_setup(conn):
    """Verify the database setup"""
    print("🔍 Verifying database setup...")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check tables exist
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            print(f"📋 Tables found: {', '.join(tables)}")
            
            # Check user count
            cur.execute("SELECT COUNT(*) as count FROM users")
            user_count = cur.fetchone()['count']
            
            # Check transaction count
            cur.execute("SELECT COUNT(*) as count FROM transactions")
            transaction_count = cur.fetchone()['count']
            
            print(f"👥 Users in database: {user_count}")
            print(f"📊 Transactions in database: {transaction_count}")
            
            # Show sample users
            if user_count > 0:
                cur.execute("SELECT username, email, plan, credits FROM users LIMIT 5")
                sample_users = cur.fetchall()
                
                print("👤 Sample users:")
                for user in sample_users:
                    print(f"   {user['username']} ({user['email']}) - {user['plan']} plan, {user['credits']} credits")
            
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 PostgreSQL Database Setup")
    print("=" * 40)
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        return False
    
    try:
        # Create tables
        if not create_tables(conn):
            return False
        
        # Migrate JSON data if it exists
        migrate_json_data(conn)
        
        # Verify setup
        if verify_setup(conn):
            print("\n✅ Database setup completed successfully!")
            print("🚀 Your app is now ready to use PostgreSQL!")
            return True
        else:
            print("\n❌ Setup verification failed!")
            return False
            
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)