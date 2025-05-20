import os
from dotenv import load_dotenv
from openai import OpenAI
import gspread
from logger import log_to_sheet
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SHEET_ID = os.getenv("SHEET_ID")

# === Google Sheets Setup ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
gclient = gspread.authorize(creds)

# === Session memory
session = {
    "intent": None,
    "from": None,
    "to": None,
    "date": None,
    "adults": None,
    "children": None,
    "infants": None
    "name": None,
    "phone": None,
    "reserved": False,
    "logged": False  # to prevent duplicates

}

# === Step 1: Detect intent
def detect_intent(user_message):
    prompt = f"""
You are a classifier. Read the message below and reply with ONLY ONE WORD from this list:

- flight
- hotel
- unknown

User message:
{user_message}
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    reply = res.choices[0].message.content.strip().lower()

    if "flight" in reply:
        return "flight"
    elif "hotel" in reply:
        return "hotel"
    else:
        return "unknown"

# === Step 2: Extract travel info from user input
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
  "infants": int or None
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

# === Step 3: Fetch Sheet Data
def fetch_sheet_data(sheet_name):
    sheet = gclient.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(sheet_name)
    return worksheet.get_all_records()

# === Step 4: Generate reply based on sheet and context
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

# === Step 5: Ask for missing info
def ask_for_missing_info(context):
    prompt = f"""
شما یک بات دستیار سفر هستید. اطلاعاتی که از کاربر دارید ناقص است:

مبدأ: {context.get("from")}
مقصد: {context.get("to")}
تاریخ: {context.get("date")}
بزرگسال: {context.get("adults")}
کودک: {context.get("children")}
نوزاد: {context.get("infants")}

لطفاً فقط و فقط اطلاعاتی که وجود ندارد را خیلی مودبانه از کاربر بپرسید.
"""
    res = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content.strip()

# === Step 6: Process Message
def process_message(user_message):
    if "رزرو" in user_message:
        return "✅ رزرو شما ثبت شد. یکی از کارشناسان ما به زودی با شما تماس خواهد گرفت."

    if session["intent"] is None:
        session["intent"] = detect_intent(user_message)
        print(f"📌 دسته‌بندی: {session['intent']}")

    if session["intent"] not in ["flight", "hotel"]:
        return "در حال حاضر فقط می‌تونم درباره پروازها و هتل‌ها کمکتون کنم."

    extracted = extract_flight_info(user_message)
    for key in ["from", "to", "date", "adults", "children", "infants"]:
        if extracted.get(key) is not None:
            session[key] = extracted[key]

    if not all([session["from"], session["to"], session["date"], session["adults"] is not None]):
        return ask_for_missing_info(session)

    sheet_name = "international_flights" if session["intent"] == "flight" else "international_hotels"
    data = fetch_sheet_data(sheet_name)

    return generate_reply(data, session)

# === CLI Interface
if __name__ == "__main__":
    print("🤖 TravelGPT Ready. Type 'exit' to quit.")
    print("""
سلام، ممنونم از اینکه سایناسفر رو انتخاب کردی 🙏  
من دستیار هوشمند تیم ساینا هستم و آماده‌ام بهت کمک کنم مناسب‌ترین گزینه‌های سفرت رو انتخاب کنی.

لطفاً برای پاسخ‌گویی سریع‌تر، اطلاعات زیر رو توی پیام اولت بنویس:

- مبدا و مقصد  
- تاریخ سفر (مثلاً ۱۰ خرداد)  
- تعداد نفرات (چند بزرگسال، کودک، نوزاد)  

مثال: «می‌خوام از شیراز به دبی برم، ۳ بزرگسال، هفته آینده»

در نهایت اگه خواستی رزرو کنی، فقط کافیه بنویسی: رزرو ✅

منتظرم تا بهت کمک کنم! ✈️🧳
""")
    while True:
        user_msg = input("📨 کاربر: ")
        if user_msg.lower() in ["exit", "quit"]:
            break
        print("🤖 GPT:", process_message(user_msg))
