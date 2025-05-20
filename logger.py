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
