import os
from fastapi import FastAPI, Request
import httpx
from dotenv import load_dotenv
from travel_gpt import process_message, reset_session, sessions

load_dotenv()
app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    user_msg = message.get("text", "").strip()
    print(f"📨 Telegram from {chat_id}: {user_msg}")

    if user_msg.lower() == "/start":
        reset_session(chat_id)
        welcome_msg = """سلام، ممنونم از اینکه سایناسفر رو انتخاب کردی 🙏  
من دستیار هوشمند تیم ساینا هستم و آماده‌ام بهت کمک کنم مناسب‌ترین گزینه‌های سفرت رو انتخاب کنی.

لطفاً برای پاسخ‌گویی سریع‌تر، اطلاعات زیر رو توی پیام اولت بنویس:

- مبدا و مقصد  
- تاریخ سفر (مثلاً ۱۰ خرداد)  
- تعداد نفرات (چند بزرگسال، کودک، نوزاد)  

مثال: «می‌خوام از شیراز به دبی برم، ۳ بزرگسال، هفته آینده»

در نهایت اگه خواستی رزرو کنی، فقط کافیه بنویسی: رزرو ✅"""
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": welcome_msg.strip()
            })
        return {"ok": True}

    gpt_reply = process_message(user_msg, chat_id)

    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": gpt_reply
        })

    return {"ok": True}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("telegram_webhook:app", host="0.0.0.0", port=10000, reload=False)
