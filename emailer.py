import smtplib
from email.message import EmailMessage
import os
from datetime import datetime

# 🔒 Replace these with your credentials
EMAIL_ADDRESS = "aileadsguy@gmail.com"
EMAIL_PASSWORD = "kwud qppa vlus zyyj"  # 16-digit Gmail App Password

# 📤 Function to send leads file
def send_daily_leads_email(csv_file_path, recipient_email):
    try:
        # Check if file exists
        if not os.path.exists(csv_file_path):
            print(f"❌ File not found: {csv_file_path}")
            return

        # Compose email
        msg = EmailMessage()
        msg["Subject"] = f"📊 Daily Leads Report – {datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient_email
        msg.set_content(
            f"""
Hi,

Please find attached your leads scraped on {datetime.now().strftime('%Y-%m-%d')}.
Let us know if you'd like these sorted or filtered differently.

Best,  
LeadScraper Bot
            """.strip()
        )

        # Attach CSV
        with open(csv_file_path, "rb") as f:
            file_data = f.read()
            file_name = os.path.basename(csv_file_path)
            msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

        # Send email using Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"✅ Email with leads sent to {recipient_email}")

    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# 📧 LinkedIn Results Email
def send_linkedin_results_email(csv_file_path, recipient_email, search_term, lead_count):
    """Send LinkedIn results with professional formatting"""
    try:
        if not os.path.exists(csv_file_path):
            print(f"❌ LinkedIn CSV not found: {csv_file_path}")
            return False

        msg = EmailMessage()
        msg["Subject"] = f"💼 LinkedIn Leads Ready - {search_term} ({lead_count} leads)"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient_email
        
        email_body = f"""
Hi there!

Your LinkedIn lead generation is complete! 🎉

📊 **Results Summary:**
• Search Term: "{search_term}"
• Total LinkedIn Leads: {lead_count}
• Processing Date: {datetime.now().strftime('%B %d, %Y')}
• Quality: Manually verified profiles

💼 **What's Included:**
✅ Real LinkedIn profiles (not bots)
✅ Verified job titles and companies  
✅ Professional email addresses when available
✅ Connection degree information
✅ Profile verification status

📁 Your leads are attached as a CSV file, ready to import into your CRM or outreach tools.

Questions? Just reply to this email.

Best regards,
Lead Generator Empire Team
🚀 Conquering LinkedIn, one lead at a time!
        """.strip()
        
        msg.set_content(email_body)

        # Attach CSV
        with open(csv_file_path, "rb") as f:
            file_data = f.read()
            file_name = f"linkedin_leads_{search_term.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

        # Send email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"✅ LinkedIn results emailed to {recipient_email}")
        return True

    except Exception as e:
        print(f"❌ LinkedIn email failed: {e}")
        return False

# 📧 LinkedIn Confirmation Email
def send_linkedin_confirmation_email(user_email, search_term, estimated_leads):
    """Send immediate confirmation that LinkedIn request is queued"""
    try:
        msg = EmailMessage()
        msg["Subject"] = f"⏳ LinkedIn Processing Started - {search_term}"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = user_email
        
        confirmation_body = f"""
Hi!

Thanks for your LinkedIn lead request! 🚀

📋 **Request Details:**
• Search Term: "{search_term}"
• Estimated Leads: ~{estimated_leads}
• Status: Queued for manual processing

⏰ **Timeline:**
Your LinkedIn leads will be manually processed and emailed within 2-4 hours.

🔍 **Why Manual Processing?**
LinkedIn has advanced anti-bot detection
• Accurate job titles and companies
• Valid contact information
• Higher engagement rates

📧 **What's Next:**
You'll receive another email with your CSV file attached once processing is complete.

Thanks for your patience!

Best regards,
Lead Generator Empire Team
        """.strip()
        
        msg.set_content(confirmation_body)
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        
        print(f"✅ LinkedIn confirmation sent to {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Confirmation email failed: {e}")
        return False
