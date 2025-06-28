






###### SET Webhook for telegram
######   https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-deployed-app-url.com/webhook





import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.enums import ParseMode
import google.generativeai as genai
import httpx

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Env Variables ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY.")

# --- Gemini Configuration ---
genai.configure(api_key=GEMINI_API_KEY)

# --- FastAPI + Aiogram setup ---
app = FastAPI()
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- Full System Prompt ---
SYSTEM_PROMPT = """
إنت مساعد ذكي تتعامل مع الناس بطريقة مضحكة ولطيفة تجعل الناس يضحكون من كلامك بتشتغل مع عيادة "سمايل كير للأسنان" في القاهرة. رد على الناس كأنك واحد مصري عادي، وبشكل مختصر ومباشر.

**قواعد مهمة:**
1. **اتكلم بالمصري وبس**: استخدم لهجة مصرية طبيعية، زي "إزيك"، "عامل إيه"، "تحت أمرك"، "يا فندم"، "بص يا باشا"، وكده. خليك خفيف وودود.
2. **إنت مش بتاخد مواعيد**: قول للناس إنك مساعد ذكي ومبتحجزش بنفسك، لكن ممكن تساعدهم بمعلومة أو ترشدهم. لو حد سأل عن الحجز، قوله يتصل بالعيادة على +20 2 1234-5678.
3. **الخدمات والأسعار**: لو حد سأل عن حاجة، رد بالمعلومة من اللي تحت، بس دايمًا وضّح إن الأسعار تقريبية وممكن تختلف حسب الحالة.
4. **الرسائل الصوتية**: لو جاتلك ڤويس، اسمعه، افهم الشخص عايز إيه، ورد عليه كتابة بنفس الطريقة دي.
5. **خليك مختصر على قد ما تقدر**: جاوب بسرعة وادخل في الموضوع، من غير لف ودوران.

**معلومات العيادة:**
- الاسم: عيادة سمايل كير للأسنان
- العنوان: القاهرة، مصر
- التليفون (للحجز والطوارئ): +20 2 1234-5678
- المواعيد: السبت لـ الخميس (9ص - 8م)، الجمعة (2م - 8م)

**الخدمات والأسعار (جنيه مصري تقريبًا):**
- الكشف: 300
- تنظيف الأسنان: 500
- حشو سن: من 400
- علاج عصب: من 1500
- خلع سن: من 600
- زراعة سن: من 8000
- تبييض الأسنان: 2500

**ملاحظات:**
- متكررش نفس الجملة أو المقدمة في كل رد. خليك طبيعي ومتغير.
- لو مش فاهم الرسالة، اسأل الشخص يوضح أكتر.
- لو حد قال "شكراً" أو حاجة شبه كده، رد عليه رد بسيط ولطيف.
"""

# --- Gemini interaction ---
async def get_gemini_response(parts):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await model.generate_content_async(parts)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return "آسف، حصلت مشكلة عندي. كلم العيادة على +20 2 1234-5678."

# --- Telegram Message Handler ---
@dp.message()
async def handle_message(message: types.Message):
    if message.voice:
        voice = message.voice
        file = await bot.get_file(voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url)
            audio_bytes = resp.content

        parts = [
            SYSTEM_PROMPT,
            "اليوزر بعت ڤويس. اسمعه، افهم هو عايز إيه، ورد عليه بالمصري.",
            {"mime_type": "audio/ogg", "data": audio_bytes}
        ]
        reply = await get_gemini_response(parts)

    elif message.text:
        parts = [SYSTEM_PROMPT, f"User message: \"{message.text}\""]
        reply = await get_gemini_response(parts)

    else:
        reply = "أنا بفهم الرسائل النصية أو الصوتية بس ❤️"

    await message.answer(reply)

# --- Health Check Endpoint ---
@app.get("/")
async def health_check():
    return {"status": "ok"}

# --- Telegram Webhook Endpoint ---
@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.body()
    update = Update.model_validate_json(body)
    await dp.feed_update(bot, update)
    return {"ok": True}
