import os
import httpx
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GROQ_MODEL = "llama-3.3-70b-versatile"

chat_messages: dict[int, list[str]] = {}

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })

async def ask_groq(system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "max_tokens": 600, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]}
        )
        return res.json()["choices"][0]["message"]["content"]

def build_system(messages: list[str]) -> str:
    history = "\n".join(messages[-200:])
    return f"""אתה עוזר חכם לקבוצת טלגרם שמתכננת מסיבה.
זהה מי הבטיח להביא מה — כולל כשמישהו כותב על אחר.
ענה תמיד בעברית, קצר וידידותי עם אמוג'י.

היסטוריית הצ'אט:
{history}"""

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    sender = message.get("from", {}).get("first_name", "מישהו")
    if chat_id not in chat_messages:
        chat_messages[chat_id] = []
    if text and not text.startswith("/"):
        chat_messages[chat_id].append(f"{sender}: {text}")
    if text in ("/start", "/help"):
        await send_message(chat_id, "🎉 *בוט מסיבה*\n\n/summary — מי מביא מה?\n/missing — מה חסר?\n\nאו שאל חופשי: _\"מי מביא עוגה?\"_")
    elif text == "/summary":
        if not chat_messages.get(chat_id):
            await send_message(chat_id, "עדיין אין הודעות 🤷")
        else:
            answer = await ask_groq(build_system(chat_messages[chat_id]), "סכם מי מביא מה. רשימה ברורה: שם — מה מביא.")
            await send_message(chat_id, f"📋 *סיכום:*\n\n{answer}")
    elif text == "/missing":
        if not chat_messages.get(chat_id):
            await send_message(chat_id, "עדיין אין הודעות 🤷")
        else:
            answer = await ask_groq(build_system(chat_messages[chat_id]), "מה חסר? צלחות, כלים, שתייה, קינוח וכו'?")
            await send_message(chat_id, f"⚠️ *חסר:*\n\n{answer}")
    elif not text.startswith("/"):
        if ("?" in text or "בוט" in text) and chat_messages.get(chat_id):
            answer = await ask_groq(build_system(chat_messages[chat_id]), text)
            await send_message(chat_id, answer)
    return {"ok": True}

@app.get("/")
async def root():
    return {"status": "ok"}
