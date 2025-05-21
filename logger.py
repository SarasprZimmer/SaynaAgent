import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID")
LOG_TAB_NAME = "logs"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gclient = gspread.authorize(creds)

def log_to_sheet(context):
    try:
        sheet = gclient.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet(LOG_TAB_NAME)

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            context.get("name", ""),
            context.get("phone", ""),
            context.get("intent", ""),
            context.get("from", ""),
            context.get("to", ""),
            context.get("date", ""),
            context.get("adults", ""),
            context.get("children", ""),
            context.get("infants", ""),
            "✅" if context.get("reserved") else ""
        ]
        worksheet.append_row(row)
        print("📝 Logged to sheet.")
    except Exception as e:
        print("⚠️ Failed to log to sheet:", e)
        import httpx

def notify_agent(client_info):
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    AGENT_CHAT_ID = os.getenv("AGENT_CHAT_ID")
    TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    message = f"""
📢 رزرو جدید دریافت شد!

👤 نام: {client_info.get("name", "نامشخص")}
📞 شماره تماس: {client_info.get("phone", "نامشخص")}
📌 نوع درخواست: {client_info.get("intent", "نامشخص")}
✈️ مبدأ: {client_info.get("from", "نامشخص")}
🛬 مقصد: {client_info.get("to", "نامشخص")}
📅 تاریخ: {client_info.get("date", "نامشخص")}
👥 بزرگسال: {client_info.get("adults", "؟")} | کودک: {client_info.get("children", "۰")} | نوزاد: {client_info.get("infants", "۰")}
"""

    try:
        httpx.post(TELEGRAM_API, json={
            "chat_id": AGENT_CHAT_ID,
            "text": message
        })
    except Exception as e:
        print(f"❌ Failed to notify agent: {e}")

