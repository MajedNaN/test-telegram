import os
import asyncio
import logging
from typing import Any

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check if all environment variables are loaded
if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY]):
    logger.error("Missing one or more required environment variables.")
    raise ValueError("Missing one or more required environment variables (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY).")

# --- Configure Google Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)

# --- System Prompt for the Dental Clinic ---
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

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def get_gemini_response(input_parts: list) -> str:
    """
    Generates a response from Gemini using the provided input parts (text and/or audio).
    """
    try:
        # Use gemini-2.0-flash for fast responses with audio support
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Generate the content
        response = model.generate_content(input_parts)
        
        # Clean up the response to ensure it's a single block of text
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error getting Gemini response: {e}", exc_info=True)
        return "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678"

async def download_voice_file(bot: Bot, file_id: str) -> tuple[bytes, str]:
    """
    Downloads voice file from Telegram and returns bytes and mime type.
    """
    try:
        # Get file info
        file_info = await bot.get_file(file_id)
        
        # Download file
        file_bytes = await bot.download_file(file_info.file_path)
        
        # Voice messages are usually OGG format
        mime_type = "audio/ogg"
        
        logger.info(f"Successfully downloaded voice file: {len(file_bytes.getvalue())} bytes")
        return file_bytes.getvalue(), mime_type
        
    except Exception as e:
        logger.error(f"Error downloading voice file {file_id}: {e}", exc_info=True)
        return None, None

# Message handlers
@dp.message(lambda message: message.text and message.text.startswith('/start'))
async def start_command(message: types.Message):
    """Handle /start command"""
    welcome_text = """
أهلاً وسهلاً! 🦷✨

أنا مساعد عيادة سمايل كير للأسنان في القاهرة. إزيك؟ 

ممكن أساعدك في:
• معلومات عن خدماتنا وأسعارنا
• مواعيد العيادة
• أي استفسارات عن الأسنان

لو عايز تحجز موعد، اتصل بالعيادة على: +20 2 1234-5678

اسأل عن أي حاجة تحبها! 😊
    """
    await message.answer(welcome_text)

@dp.message(lambda message: message.text and message.text.startswith('/help'))
async def help_command(message: types.Message):
    """Handle /help command"""
    help_text = """
إزيك! دي الحاجات اللي أقدر أساعدك فيها:

🦷 **الخدمات والأسعار:**
• الكشف: 300 جنيه
• تنظيف الأسنان: 500 جنيه
• حشو سن: من 400 جنيه
• علاج عصب: من 1500 جنيه
• خلع سن: من 600 جنيه
• زراعة سن: من 8000 جنيه
• تبييض الأسنان: 2500 جنيه

📞 **للحجز:** +20 2 1234-5678
⏰ **المواعيد:** السبت-الخميس (9ص-8م)، الجمعة (2م-8م)

ممكن تبعت رسالة نصية أو صوتية وأنا هرد عليك! 😊
    """
    await message.answer(help_text)

@dp.message(lambda message: message.voice is not None)
async def handle_voice_message(message: types.Message):
    """Handle voice messages"""
    try:
        logger.info(f"Received voice message from user {message.from_user.id}")
        
        # Download voice file
        voice_bytes, mime_type = await download_voice_file(bot, message.voice.file_id)
        
        if not voice_bytes:
            await message.answer("معلش، مقدرتش أسمع الرسالة الصوتية. ممكن تبعتها تاني أو تكتب سؤالك؟")
            return
        
        # Prepare input for Gemini
        gemini_input = [
            DENTAL_CLINIC_SYSTEM_PROMPT,
            "The user sent a voice note. Transcribe it, understand the request, and answer in Egyptian Arabic based on the clinic's information. Make the response concise.",
            {"mime_type": mime_type, "data": voice_bytes}
        ]
        
        # Get response from Gemini
        response_text = get_gemini_response(gemini_input)
        
        # Send response
        await message.answer(response_text)
        
    except Exception as e:
        logger.error(f"Error handling voice message: {e}", exc_info=True)
        await message.answer("آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678")

@dp.message(lambda message: message.text is not None)
async def handle_text_message(message: types.Message):
    """Handle text messages"""
    try:
        user_text = message.text
        logger.info(f"Received text message from user {message.from_user.id}: {user_text}")
        
        # Prepare input for Gemini
        gemini_input = [
            DENTAL_CLINIC_SYSTEM_PROMPT,
            f"User message: \"{user_text}\""
        ]
        
        # Get response from Gemini
        response_text = get_gemini_response(gemini_input)
        
        # Send response
        await message.answer(response_text)
        
    except Exception as e:
        logger.error(f"Error handling text message: {e}", exc_info=True)
        await message.answer("آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678")

@dp.message()
async def handle_other_messages(message: types.Message):
    """Handle any other type of messages"""
    await message.answer("أنا أسف، أنا بفهم الرسائل النصية والصوتية بس. ممكن تكتب سؤالك أو تبعت رسالة صوتية؟")

# FastAPI app for Vercel
app = FastAPI()

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "OK", "message": "Telegram Bot is running on Vercel"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Handle Telegram webhook"""
    try:
        # Get the JSON data from the request
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        
        # Create Update object from the received data
        update = Update(**data)
        
        # Process the update through the dispatcher
        await dp.feed_update(bot, update)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# For Vercel, we need to expose the app
handler = app