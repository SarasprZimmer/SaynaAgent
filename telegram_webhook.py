import os
from fastapi import FastAPI, Request
import httpx
from dotenv import load_dotenv
from travel_gpt import process_message  # ✅ reuse your GPT logic

load_dotenv()
app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(req: Request):
    data = await req.json()
    chat_id = data["message"]["chat"]["id"]
    user_msg = data["message"]["text"]

    print(f"📨 Telegram from {chat_id}: {user_msg}")

    gpt_reply = process_message(user_msg)

    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": gpt_reply
        })

    return {"ok": True}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("telegram_webhook:app", host="0.0.0.0", port=10000)
