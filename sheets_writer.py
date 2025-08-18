# sheets_writer.py - Secure version using environment variables
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# Update with your sheet info
SPREADSHEET_ID = "1YL0AIzcLTZQgO_bVvE3SYwi-7ZNZqGeqPLJk5nOK42c"
SHEET_NAME = "Sheet1"

def get_google_credentials():
    """Get Google credentials from environment variables (secure)"""
    try:
        # Try environment variables first (production)
        if os.getenv("GOOGLE_PRIVATE_KEY"):
            credentials_dict = {
                "type": os.getenv("GOOGLE_SERVICE_ACCOUNT_TYPE", "service_account"),
                "project_id": os.getenv("GOOGLE_PROJECT_ID"),
                "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
                "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),  # Fix newlines
                "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "auth_uri": os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                "token_uri": os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL')}",
                "universe_domain": "googleapis.com"
            }
            
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
            print("✅ Using Google credentials from environment variables")
            return creds
            
        # Fallback to service account file (local development only)
        elif os.path.exists("service_account.json"):
            print("⚠️ Using service_account.json file (development mode)")
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
            return creds
            
        else:
            print("❌ No Google credentials found in environment variables or file")
            return None
            
    except Exception as e:
        print(f"❌ Error loading Google credentials: {e}")
        return None

def write_leads_to_google_sheets(leads: list[dict]):
    """Write leads to Google Sheets with standardized format"""
    try:
        # Get credentials securely
        creds = get_google_credentials()
        if not creds:
            print("❌ Cannot write to Google Sheets - no credentials available")
            return False
        
        # Initialize Google Sheets client
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
        
        # Add headers if the sheet is empty
        try:
            headers = sheet.row_values(1)
            if not headers:
                header_row = [
                    "Name", "Handle", "Bio", "URL", "Platform", "DM", 
                    "Location", "Headline", "Date Added"
                ]
                sheet.append_row(header_row, value_input_option="USER_ENTERED")
                print("✅ Added headers to Google Sheet")
        except Exception as e:
            print(f"⚠️ Header check/add failed: {e}")
            # Continue anyway - maybe headers already exist
            
        # Prepare rows for insertion
        rows = []
        for lead in leads:
            row = [
                lead.get("name", ""),
                lead.get("handle", lead.get("username", "")),  # Handle new format, fallback to old
                lead.get("bio", ""),
                lead.get("url", ""),
                lead.get("platform", ""),
                lead.get("dm", ""),
                lead.get("location", ""),
                lead.get("headline", lead.get("title", "")),  # Handle LinkedIn/Facebook differences
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ]
            rows.append(row)

        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"📤 Uploaded {len(rows)} leads to Google Sheets successfully!")
            return True
        else:
            print("⚠️ No leads to upload to Google Sheets.")
            return False
            
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Spreadsheet not found: {SPREADSHEET_ID}")
        print("💡 Make sure the spreadsheet exists and the service account has access")
        return False
        
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ Worksheet not found: {SHEET_NAME}")
        print("💡 Make sure the worksheet exists in the spreadsheet")
        return False
        
    except Exception as e:
        print(f"❌ Error writing to Google Sheets: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

def write_leads_to_google_sheet(leads: list[dict], sheet_name: str = None):
    """Compatibility wrapper - calls the main function (singular to plural)"""
    global SHEET_NAME
    if sheet_name:
        original_sheet_name = SHEET_NAME
        SHEET_NAME = sheet_name
        result = write_leads_to_google_sheets(leads)
        SHEET_NAME = original_sheet_name  # Restore original
        return result
    else:
        return write_leads_to_google_sheets(leads)

def test_google_sheets_connection():
    """Test Google Sheets connection"""
    try:
        creds = get_google_credentials()
        if not creds:
            return False, "No credentials available"
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        return True, f"✅ Connected to spreadsheet: {sheet.title}"
        
    except Exception as e:
        return False, f"❌ Connection failed: {e}"

# Test function for debugging
if __name__ == "__main__":
    print("🧪 Testing Google Sheets connection...")
    success, message = test_google_sheets_connection()
    print(message)
    
    if success:
        # Test with sample data
        test_leads = [
            {
                "name": "Test User",
                "handle": "@testuser",
                "bio": "Test bio",
                "url": "https://example.com",
                "platform": "twitter",
                "dm": "Test DM message",
                "location": "Test Location",
                "headline": "Test Headline"
            }
        ]
        
        print("🧪 Testing lead upload...")
        result = write_leads_to_google_sheets(test_leads)
        if result:
            print("✅ Test upload successful!")
        else:
            print("❌ Test upload failed!")