#!/usr/bin/env python3
import os
import time

# Test your email function directly
try:
    from emailer import send_admin_package_notification, EMAIL_ADDRESS
    
    print("Testing email function...")
    print(f"ADMIN_EMAIL: {os.getenv('ADMIN_EMAIL')}")
    print(f"SMTP_HOST: {os.getenv('SMTP_HOST')}")
    print(f"EMAIL_ADDRESS: {EMAIL_ADDRESS}")
    
    start_time = time.time()
    
    result = send_admin_package_notification(
        admin_email=os.getenv("ADMIN_EMAIL") or EMAIL_ADDRESS,
        username="test_user",
        user_email="sbsid99@yahoo.com",
        package_type="test_package", 
        amount=100.0,
        industry="Test Industry",
        location="Test Location",
        session_id="test_123",
        timestamp=str(int(time.time()))
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Result: {result}")
    print(f"Duration: {duration:.2f} seconds")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()