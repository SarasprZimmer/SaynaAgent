import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
from datetime import datetime
# === Session memory
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
        "phone": None,
        "reserved": False
    }

# Initialize session if not exists
def get_session(chat_id):
    if chat_id not in sessions:
        reset_session(chat_id)
    return sessions[chat_id]

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
WEBHOOK_LOG_URL = os.getenv("LOG_WEBHOOK_URL")

# === Session memory ===
session = {
    "intent": None,
    "from": None,
    "to": None,
    "date": None,
    "adults": None,
    "children": None,
    "infants": None,
    "name": None,
    "phone": None,
    "reserved": False,
    "logged": False
}

# === Step 1: Detect intent ===
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

# === Step 2: Extract travel info ===
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

# === Step 3: Fetch data from Google Sheet (via webhook) ===
def fetch_sheet_data(sheet_name):
    SHEET_WEBHOOK = os.getenv("FLIGHT_WEBHOOK_URL") if sheet_name == "international_flights" else os.getenv("HOTEL_WEBHOOK_URL")
    try:
        res = requests.get(SHEET_WEBHOOK)
        return res.json()
    except Exception as e:
        print("❌ Failed to fetch sheet data:", e)
        return []

# === Step 4: Generate GPT reply ===
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

# === Step 5: Ask for missing info ===
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
شماره تماس: {context.get("phone")}

 فقط اطلاعاتی که وجود ندارد را خیلی مودبانه از کاربر بپرسید.
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content.strip()

# === Step 6: Log to Google Sheet via webhook ===
def log_to_sheet(context):
    try:
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": context.get("name", ""),
            "phone": context.get("phone", ""),
            "intent": context.get("intent", ""),
            "from": context.get("from", ""),
            "to": context.get("to", ""),
            "date": context.get("date", ""),
            "adults": context.get("adults", ""),
            "children": context.get("children", ""),
            "infants": context.get("infants", ""),
            "reserved": "✅" if context.get("reserved") else ""
        }
        requests.post(WEBHOOK_LOG_URL, json=payload)
        print("📤 Logged via webhook")
    except Exception as e:
        print("⚠️ Failed to send log via webhook:", e)

# === Step 7: Main handler ===
from logger import log_to_sheet
import os
import requests
def process_message(user_message, chat_id=None):
    # Reservation trigger
    if "رزرو" in user_message:
        name = session.get("name", "نامشخص")
        phone = session.get("phone", "نامشخص")
        intent = session.get("intent", "نامشخص")
        from_city = session.get("from", "نامشخص")
        to_city = session.get("to", "نامشخص")

        # 🔔 Notify agent via WhatsApp
        try:
            agent_number = os.getenv("AGENT_WHATSAPP_NUMBER")
            agent_msg = f"📥 رزرو جدید:\nنام: {name}\nشماره: {phone}\nدرخواست: {intent} از {from_city} به {to_city}"
            requests.get(f"https://api.ultramsg.com/instanceXXXX/messages/chat", params={
                "token": os.getenv("ULTRAMSG_TOKEN"),
                "to": agent_number,
                "body": agent_msg
            })
            print("📣 Agent notified.")
        except Exception as e:
            print(f"❌ Agent notification failed: {e}")

        return "✅ رزرو شما ثبت شد. یکی از کارشناسان ما به زودی با شما تماس خواهد گرفت."

    # Detect intent
    if session["intent"] is None:
        session["intent"] = detect_intent(user_message)
        print(f"📌 دسته‌بندی: {session['intent']}")

    if session["intent"] not in ["flight", "hotel"]:
        return "در حال حاضر فقط می‌تونم درباره پروازها و هتل‌ها کمکتون کنم."

    # Extract travel info
    extracted = extract_flight_info(user_message)
    for key in ["from", "to", "date", "adults", "children", "infants", "name", "phone"]:
        if extracted.get(key) is not None:
            session[key] = extracted[key]

    # If info missing, ask user
    if not all([session["from"], session["to"], session["date"], session["adults"] is not None]):
        return ask_for_missing_info(session)

    # ✅ Log entry if name and phone available
    if session.get("name") and session.get("phone"):
        log_to_google_sheet({
            "name": session["name"],
            "phone": session["phone"],
            "intent": session["intent"],
            "from": session.get("from", "نامشخص"),
            "to": session.get("to", "نامشخص"),
            "date": session.get("date", "نامشخص"),
            "adults": session.get("adults"),
            "children": session.get("children"),
            "infants": session.get("infants"),
            "proceeded_to_reservation": "خیر"
        })

    # Get sheet data
    sheet_name = "international_flights" if session["intent"] == "flight" else "international_hotels"
    try:
        data = fetch_sheet_data(sheet_name)
    except Exception as e:
        print(f"❌ Failed to fetch sheet data: {e}")
        return "خطایی در دریافت اطلاعات پیش آمد. لطفاً دوباره تلاش کنید."

    return generate_reply(data, session)

# === CLI ===
if __name__ == "__main__":
    print("🤖 TravelGPT Ready. Type 'exit' to quit.")
    print("""
سلام، ممنونم از اینکه سایناسفر رو انتخاب کردی 🙏  
من دستیار هوشمند تیم ساینا هستم و آماده‌ام بهت کمک کنم مناسب‌ترین گزینه‌های سفرت رو انتخاب کنی.

لطفاً برای پاسخ‌گویی سریع‌تر، اطلاعات زیر رو توی پیام اولت بنویس:

- مبدا و مقصد  
- تاریخ سفر (مثلاً ۱۰ خرداد)  
- تعداد نفرات (چند بزرگسال، کودک، نوزاد)  
- نام و شماره تماس

مثال: «می‌خوام از شیراز به دبی برم، ۳ بزرگسال، هفته آینده، اسمم سارا هست ۰۹۱۲۳۴۵۶۷۸۹»

در نهایت اگه خواستی رزرو کنی، فقط کافیه بنویسی: رزرو ✅

منتظرم تا بهت کمک کنم! ✈️🧳
""")
    while True:
        user_msg = input("📨 کاربر: ")
        if user_msg.lower() in ["exit", "quit"]:
            break
        print("🤖 GPT:", process_message(user_msg))
