import yagmail
import os
from datetime import datetime
import glob

# ---------- CONFIGURATION ----------
GMAIL_USER = "aileadsguy@gmail.com"  # Replace with your Gmail address
APP_PASSWORD = "kwud qppa vlus zyyj"  # Replace with your Gmail app password
TO_EMAIL = "info@sidneym.com"  # Who should receive the leads
SUBJECT = "🧠 Your Daily Scraped Leads Report"
BODY = "Attached is your automatically scraped lead report for today.\n\nLet me know if you'd like changes!"
CSV_EXPORT_DIR = "."  # Directory where your CSVs are saved
# -----------------------------------

def find_latest_csv():
    csv_files = glob.glob(os.path.join(CSV_EXPORT_DIR, "*_leads_*.csv"))
    if not csv_files:
        raise FileNotFoundError("No CSV leads found in directory.")
    latest_file = max(csv_files, key=os.path.getmtime)
    return latest_file

def send_daily_leads_email():
    print("📬 Preparing to send daily leads email...")

    latest_csv = find_latest_csv()
    filename = os.path.basename(latest_csv)

    print(f"📎 Attaching: {filename}")

    yag = yagmail.SMTP(GMAIL_USER, APP_PASSWORD)
    yag.send(
        to=TO_EMAIL,
        subject=f"{SUBJECT} - {datetime.now().strftime('%Y-%m-%d')}",
        contents=[BODY, latest_csv]
    )

    print(f"✅ Email sent to {TO_EMAIL} with attachment {filename}")

if __name__ == "__main__":
    send_daily_leads_email()