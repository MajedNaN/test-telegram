import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Message, Update
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiohttp import ClientSession
import google.generativeai as genai

# --- Config ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()
genai.configure(api_key=GEMINI_API_KEY)

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- System Prompt ---
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

# --- Telegram Handlers ---
@dp.message(Command("start"))
async def command_start_handler(message: Message):
    await message.answer("إزيك يا نجم! 👋 أنا مساعد عيادة سمايل كير. ابعتلي سؤالك نص أو ڤويس.")

@dp.message()
async def handle_user_message(message: Message):
    try:
        if message.voice:
            file = await bot.get_file(message.voice.file_id)
            file_path = file.file_path

            async with ClientSession() as session:
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
                async with session.get(file_url) as resp:
                    audio_bytes = await resp.read()

            gemini_input = [
                SYSTEM_PROMPT,
                "اليوزر بعت ڤويس. افهم هو بيقول إيه ورد عليه بالمصري.",
                {
                    "mime_type": "audio/ogg",
                    "data": audio_bytes
                }
            ]
        elif message.text:
            gemini_input = [
                SYSTEM_PROMPT,
                f"User message: \"{message.text}\""
            ]
        else:
            await message.answer("أنا بفهم بس الرسائل النصية والڤويس. ابعتلي حاجة من دول.")
            return

        response = await generate_gemini_response(gemini_input)
        await message.answer(response)

    except Exception as e:
        logging.exception("Error handling message")
        await message.answer("حصل حاجة غلط عندي 😅. كلّم العيادة على +20 2 1234-5678.")

# --- Gemini ---
async def generate_gemini_response(input_parts):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(input_parts)
        return response.text.strip()
    except Exception as e:
        logging.exception("Gemini API error")
        return "آسف، مخي فصل 😅. جرب تبعتلي تاني أو كلّم العيادة على طول."

# --- FastAPI Webhook ---
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
def root():
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook("https://test-telegram-fawn.vercel.app/webhook")
