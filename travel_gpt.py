
import os
from dotenv import load_dotenv
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SHEET_ID = os.getenv("SHEET_ID")
FLIGHT_WEBHOOK = os.getenv("FLIGHT_WEBHOOK_URL")
HOTEL_WEBHOOK = os.getenv("HOTEL_WEBHOOK_URL")
LOG_WEBHOOK = os.getenv("LOG_WEBHOOK_URL")

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gclient = gspread.authorize(creds)

# Session manager
sessions = {}

def reset_session(chat_id):
    sessions[chat_id] = {
        "intent": None,
        "from": None,
        "to": None,
        "date": None,
        "adults": None,
        "children": None,
        "infants": None,
        "name": None,
        "phone": None
    }

def detect_intent(user_message):
    prompt = f"""
You are a smart travel assistant. The user is asking a question. Your task is to classify the request as one of:

- flight
- hotel
- unknown

Respond with only one word.
Message: {user_message}
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return res.choices[0].message.content.strip().lower()

def extract_flight_info(user_message):
    prompt = f"""
You are a travel assistant. Extract the following from the user's message and return a valid Python dictionary (not JSON).

Use this exact structure:
{{
  "from": str or None,
  "to": str or None,
  "date": str or None,
  "adults": int or None,
  "children": int or None,
  "infants": int or None,
  "name": str or None,
  "phone": str or None
}}

User message:
{user_message}
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    try:
        text = res.choices[0].message.content.strip()
        safe_text = text.replace("null", "None")
        extracted = eval(safe_text)
        return extracted
    except Exception as e:
        print("⚠️ GPT parsing error:", e)
        return {}

def ask_for_missing_info(context):
    prompt = f"""
شما یک بات دستیار سفر هستید. اطلاعاتی که از کاربر دارید ناقص است:

مبدأ: {context.get("from")}
مقصد: {context.get("to")}
تاریخ: {context.get("date")}
بزرگسال: {context.get("adults")}
کودک: {context.get("children")}
نوزاد: {context.get("infants")}
نام: {context.get("name")}
تلفن: {context.get("phone")}

لطفاً فقط و فقط اطلاعاتی که وجود ندارد را خیلی مودبانه از کاربر بپرسید.
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content.strip()

def fetch_sheet_data(sheet_name):
    try:
        webhook = FLIGHT_WEBHOOK if sheet_name == "international_flights" else HOTEL_WEBHOOK
        response = requests.get(webhook, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("❌ Failed to fetch sheet data:", e)
        return []

def generate_reply(data_list, context):
    prompt = f"""
شما یک دستیار سفر هوشمند هستید که به زبان فارسی پاسخ می‌دهد.

اطلاعات کاربر:
- مبدأ: {context.get("from")}
- مقصد: {context.get("to")}
- تاریخ: {context.get("date")}
- بزرگسال: {context.get("adults")}
- کودک: {context.get("children")}
- نوزاد: {context.get("infants")}

بر اساس لیست داده‌های زیر، تا ۳ گزینه‌ی مناسب را انتخاب کن و خیلی خلاصه، به صورت لیستی نمایش بده. در انتها بپرس: «آیا مایل به رزرو هستید؟ برای رزرو بنویسید: رزرو ✅»

لیست پروازها یا هتل‌ها:
{data_list[:3]}
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return res.choices[0].message.content.strip()

def log_to_google_sheet(data):
    try:
        requests.post(LOG_WEBHOOK, json=data)
        print("📤 Logged via webhook")
    except Exception as e:
        print("❌ Failed to send log via webhook:", e)

def process_message(user_message, chat_id):
    if chat_id not in sessions:
        reset_session(chat_id)

    session = sessions[chat_id]

    if user_message.strip().lower() == "/start":
        reset_session(chat_id)
        return (
            "سلام، ممنونم از اینکه سایناسفر رو انتخاب کردی 🙏\n\n"
            "من دستیار هوشمند تیم ساینا هستم و آماده‌ام بهت کمک کنم مناسب‌ترین گزینه‌های سفرت رو انتخاب کنی.\n\n"
            "برای شروع لطفاً اطلاعات زیر رو بنویس:\n"
            "- مبدا و مقصد\n- تاریخ سفر\n- تعداد نفرات\n\n"
            "مثال: «پرواز از شیراز به دبی، هفته اول خرداد، دو نفر بزرگسال»"
        )

    if "رزرو" in user_message:
        log_data = {
            "name": session.get("name") or "نامشخص",
            "phone": session.get("phone") or "نامشخص",
            "category": session.get("intent") or "نامشخص",
            "from": session.get("from") or "نامشخص",
            "to": session.get("to") or "نامشخص",
            "date": session.get("date") or "نامشخص",
            "adults": session.get("adults"),
            "children": session.get("children"),
            "infants": session.get("infants"),
            "confirmed": "✅"
        }
        log_to_google_sheet(log_data)
        return "✅ رزرو شما ثبت شد. یکی از کارشناسان ما به زودی با شما تماس خواهد گرفت."

    if session["intent"] is None:
        session["intent"] = detect_intent(user_message)
        print(f"📌 دسته‌بندی: {session['intent']}")

    if session["intent"] not in ["flight", "hotel"]:
        return "در حال حاضر فقط می‌تونم درباره پروازها و هتل‌ها کمکتون کنم."

    extracted = extract_flight_info(user_message)
    for key in extracted:
        if extracted[key] is not None:
            session[key] = extracted[key]

    if not all([
        session.get("from"),
        session.get("to"),
        session.get("date"),
        session.get("adults") is not None,
        session.get("name"),
        session.get("phone")
    ]):
        return ask_for_missing_info(session)

    sheet_name = "international_flights" if session["intent"] == "flight" else "international_hotels"
    data = fetch_sheet_data(sheet_name)

    if not data:
        return "متاسفانه در حال حاضر اطلاعاتی برای نمایش ندارم."

    return generate_reply(data, session)
