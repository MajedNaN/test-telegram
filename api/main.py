






###### SET Webhook for telegram
######   https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-deployed-app-url.com/webhook












from fastapi import FastAPI, Request
from aigram import Dispatcher, Bot, Router
from aigram.types import Update, Message
from aigram.webhook import AiohttpWebhook
import google.generativeai as genai
import os
import logging
import httpx

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Load environment variables ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY.")

# --- Gemini Configuration ---
genai.configure(api_key=GEMINI_API_KEY)

# --- App and Bot Setup ---
app = FastAPI()
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
webhook = AiohttpWebhook(bot)

# --- System Prompt ---
SYSTEM_PROMPT = """
إنت مساعد ذكي تتعامل مع الناس بطريقة مضحكة ...
(استخدم النص الكامل هنا، تم تقصيره لأغراض العرض)
"""

# --- Gemini Interaction ---
async def get_gemini_response(parts):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await model.generate_content_async(parts)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini Error: {e}", exc_info=True)
        return "آسف، حصل مشكلة عندي. كلم العيادة على +20 2 1234-5678."

# --- Handlers ---
@router.message()
async def handle_message(msg: Message):
    chat_id = msg.chat.id

    if msg.text:
        user_input = msg.text
        logging.info(f"Text from {chat_id}: {user_input}")
        parts = [SYSTEM_PROMPT, f"User message: \"{user_input}\""]
        reply = await get_gemini_response(parts)
        await msg.answer(reply)

    elif msg.voice:
        file_id = msg.voice.file_id
        logging.info(f"Voice from {chat_id}: {file_id}")

        try:
            file = await bot.get_file(file_id)
            voice_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

            async with httpx.AsyncClient() as client:
                resp = await client.get(voice_url)
                resp.raise_for_status()
                audio_bytes = resp.content

            mime_type = "audio/ogg"  # Telegram voice mime
            parts = [
                SYSTEM_PROMPT,
                "اليوزر بعت ڤويس. اسمعه، افهم هو عايز إيه، ورد عليه بالمصري.",
                {"mime_type": mime_type, "data": audio_bytes}
            ]
            reply = await get_gemini_response(parts)
            await msg.answer(reply)

        except Exception as e:
            logging.error(f"Error handling voice: {e}")
            await msg.answer("مقدرتش أسمع الرسالة. ممكن تبعتها تاني أو تكتبها؟")

    else:
        await msg.answer("أنا بفهم النصوص والڤويس بس ❤️")

# --- Health Check ---
@app.get("/")
async def health():
    return {"status": "OK", "message": "Telegram bot is up and running"}

# --- Webhook ---
@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.body()
    update = Update.model_validate_json(body)
    await dp.feed_update(bot, update)
    return {"ok": True}

# --- Start Dispatcher ---
dp.include_router(router)

