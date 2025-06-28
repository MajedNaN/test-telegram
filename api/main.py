from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, Audio
from aiogram.filters import Command
import httpx # Asynchronous HTTP client
import os
import google.generativeai as genai
import logging
import asyncio

# --- Configuration ---
# Load environment variables. Make sure these are set in your Vercel project settings.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Check if all environment variables are loaded
if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY]):
    logging.error("Missing one or more required environment variables.")
    raise ValueError("Missing one or more required environment variables (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY).")

# --- Configure Google Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)

# --- System Prompt for the Dental Clinic ---
# This prompt tells Gemini how to act. It's the "brain" of your chatbot.
DENTAL_CLINIC_SYSTEM_PROMPT = """
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

# Initialize FastAPI app
app = FastAPI()

# Initialize aiogram Bot and Dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- Gemini Model Initialization (can be done once) ---
gemini_model = genai.GenerativeModel('gemini-2.0-flash')

# --- Helper Functions for Gemini ---
async def get_gemini_response_async(input_parts: list) -> str:
    """
    Generates a response from Gemini using the provided input parts (text and/or audio) asynchronously.
    """
    try:
        response = await asyncio.to_thread(gemini_model.generate_content, input_parts)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error getting Gemini response: {e}", exc_info=True)
        return "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678"

# --- aiogram Handlers ---

@dp.message(Command("start", "help"))
async def send_welcome(message: Message):
    """
    Handles the /start and /help commands.
    """
    await message.reply("أهلاً وسهلاً بيك يا باشا! أنا مساعد ذكي لعيادة سمايل كير للأسنان. ممكن أساعدك بمعلومات عن العيادة وخدماتنا، بس أنا مبحجزش مواعيد. لو عايز تحجز، كلمنا على +20 2 1234-5678.")

@dp.message(lambda message: message.text)
async def handle_text_message(message: Message):
    """
    Handles incoming text messages.
    """
    logging.info(f"Received text message from {message.chat.id}: {message.text}")
    
    gemini_input = [
        DENTAL_CLINIC_SYSTEM_PROMPT,
        f"User message: \"{message.text}\""
    ]
    
    response_text = await get_gemini_response_async(gemini_input)
    await message.reply(response_text)

@dp.message(lambda message: message.voice)
async def handle_voice_message(message: Message):
    """
    Handles incoming voice messages.
    """
    logging.info(f"Received voice message from {message.chat.id}, file_id: {message.voice.file_id}")

    try:
        # Get file information from Telegram
        file_info = await bot.get_file(message.voice.file_id)
        file_path = file_info.file_path

        # Download the voice file using httpx
        async with httpx.AsyncClient() as client:
            voice_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            response = await client.get(voice_url)
            response.raise_for_status()
            audio_bytes = response.content

        logging.info(f"Successfully downloaded audio from Telegram: {len(audio_bytes)} bytes")

        gemini_input = [
            DENTAL_CLINIC_SYSTEM_PROMPT,
            "The user sent a voice note. Transcribe it, understand the request, and answer in Egyptian Arabic based on the clinic's information. Make the response concise.",
            {"mime_type": message.voice.mime_type, "data": audio_bytes}
        ]

        response_text = await get_gemini_response_async(gemini_input)
        await message.reply(response_text)

    except httpx.RequestError as e:
        logging.error(f"Error downloading voice file from Telegram: {e}")
        await message.reply("معلش، مقدرتش أسمع الرسالة الصوتية. ممكن تبعتها تاني أو تكتب سؤالك؟")
    except Exception as e:
        logging.error(f"Error handling voice message: {e}", exc_info=True)
        await message.reply("آسف، حصل مشكلة عندي وأنا بحاول أفهم رسالتك الصوتية. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678")

@dp.message() # Catches all other message types
async def handle_unsupported_message(message: Message):
    """
    Handles unsupported message types.
    """
    logging.info(f"Received unsupported message type from {message.chat.id}. Skipping.")
    await message.reply("أنا أسف، أنا بفهم الرسائل النصية والصوتية بس.")

# --- FastAPI Webhook Endpoint ---

@app.get("/")
async def health_check():
    """Simple health check endpoint."""
    logging.info("Health check requested.")
    return {"status": "OK", "message": "Telegram Bot is running."}

@app.post("/webhook")
async def handle_telegram_webhook_fastapi(request: Request):
    """
    Handles incoming updates from Telegram via webhook for FastAPI.
    Passes the update to aiogram's dispatcher.
    """
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    logging.info(f"Received Telegram webhook via FastAPI.")
    await dp.feed_update(bot, update)
    return {"status": "ok"}