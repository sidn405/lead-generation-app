import requests
import os
from datetime import datetime

def send_discord_notification(webhook_type, title, description, fields=None, color=None):
    """Send notification to appropriate Discord webhook"""
    
    webhook_urls = {
        "customer": os.getenv("WEBHOOK_CUSTOMER"),
        "admin": os.getenv("WEBHOOK_ADMIN"), 
        "system": os.getenv("WEBHOOK_SYSTEM")
    }
    
    webhook_url = webhook_urls.get(webhook_type)
    if not webhook_url:
        print(f"No webhook URL for type: {webhook_type}")
        return False
    
    embed = {
        "title": title,
        "description": description,
        "color": color or 3447003,
        "timestamp": datetime.now().isoformat()
    }
    
    if fields:
        embed["fields"] = fields
    
    try:
        response = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        return response.status_code == 204
    except Exception as e:
        print(f"Discord notification failed: {e}")
        return False

# Replace emailer.py functions
def send_password_reset_discord(username, email, reset_code):
    """Replace password reset email with Discord notification"""
    return send_discord_notification(
        webhook_type="customer",
        title="Password Reset Request",
        description=f"User {username} requested password reset",
        fields=[
            {"name": "Username", "value": username, "inline": True},
            {"name": "Email", "value": email, "inline": True}, 
            {"name": "Reset Code", "value": f"`{reset_code}`", "inline": False},
            {"name": "Instructions", "value": "Manually send this code to the user", "inline": False}
        ],
        color=16776960
    )
    
def send_linkedin_results_discord(username, user_email, search_term, lead_count, csv_filename):
    """Send LinkedIn results notification with customer message template"""
    
    # Create the customer message template
    customer_message = f"""Hi there!

Your LinkedIn lead generation is complete! 

Results Summary:
- Search Term: "{search_term}"
- Total LinkedIn Leads: {lead_count}
- Processing Date: {datetime.now().strftime('%B %d, %Y')}
- Quality: Manually verified profiles

What's Included:
✅ Real LinkedIn profiles (not bots)
✅ Verified job titles and companies  
✅ Professional email addresses when available
✅ Connection degree information
✅ Profile verification status

Your leads are attached as a CSV file, ready to import into your CRM or outreach tools.

Questions? Just reply to this email.

Best regards,
Lead Generator Empire Team
Conquering LinkedIn, one lead at a time!"""

    description = f"LinkedIn scraping completed for {username}. Ready to send results."
    
    fields = [
        {"name": "Customer", "value": f"{username}\n{user_email}", "inline": True},
        {"name": "Results", "value": f"Search: {search_term}\nLeads: {lead_count}\nFile: {csv_filename}", "inline": True},
        {"name": "Date", "value": datetime.now().strftime('%B %d, %Y'), "inline": True},
        {"name": "Customer Email Template", "value": customer_message, "inline": False}
    ]
    
    return send_discord_notification(
        webhook_type="customer",
        title="LinkedIn Results Ready - Send to Customer",
        description=description,
        fields=fields,
        color=65280
    )

def send_linkedin_confirmation_discord(username, user_email, search_term, estimated_leads):
    """Replace LinkedIn confirmation email with Discord notification"""
    return send_discord_notification(
        webhook_type="customer", 
        title="LinkedIn Processing Started",
        description=f"LinkedIn request queued for {username}",
        fields=[
            {"name": "User", "value": f"{username}\n{user_email}", "inline": True},
            {"name": "Search Term", "value": search_term, "inline": True},
            {"name": "Estimated Leads", "value": str(estimated_leads), "inline": True},
            {"name": "Status", "value": "Manual processing in progress", "inline": False}
        ],
        color=255
    )

def send_daily_leads_discord(csv_filename, recipient_email, lead_count):
    """Replace daily leads email with Discord notification"""
    return send_discord_notification(
        webhook_type="customer",
        title="Daily Leads Report Ready",
        description=f"Daily report generated with {lead_count} leads",
        fields=[
            {"name": "File", "value": csv_filename, "inline": True},
            {"name": "Recipient", "value": recipient_email, "inline": True},
            {"name": "Lead Count", "value": str(lead_count), "inline": True}
        ],
        color=3447003
    )