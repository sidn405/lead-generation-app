import sqlite3
from datetime import datetime
import uuid

def setup_purchase_tables():
    """Add purchase and download tables to existing database"""
    conn = sqlite3.connect('your_database.db')  # Replace with your DB name
    cursor = conn.cursor()
    
    # Purchases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            email TEXT NOT NULL,
            package_name TEXT NOT NULL,
            package_price REAL NOT NULL,
            stripe_payment_intent_id TEXT UNIQUE,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'completed',
            file_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Downloads table for tracking download history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (purchase_id) REFERENCES purchases (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Purchase tables created successfully!")

# Run this once to set up the tables
if __name__ == "__main__":
    setup_purchase_tables()