






###### SET Webhook for telegram
######   https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-deployed-app-url.com/webhook
######   https://api.telegram.org/bot8141958410:AAHqHtPoUsM7ei3JOB7maFniUEFVcAamm6Q/setWebhook?url=https://11b3-41-45-64-65.ngrok-free.app/webhook



import asyncio
import os
import logging
from io import BytesIO

# Aiogram imports
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message


# FastAPI imports
from fastapi import FastAPI, Request, HTTPException









#### for local ngrok
from dotenv import load_dotenv







import google.generativeai as genai
from contextlib import asynccontextmanager # For FastAPI lifespan events

# --- Configuration ---
# Load environment variables from .env file.
# In production environments (like Vercel, Render), these variables
# should be set directly in the platform's configuration, not via a .env file.







#### for local ngrok
load_dotenv()








# Load environment variables for Telegram Bot Token, Gemini API Key, and Webhook URL.
# Ensure these are set in your .env file or deployment environment.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # This should be the public URL of your deployed application

# Configure logging for better visibility into application behavior.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Critical check: Ensure all necessary environment variables are loaded.
# If any are missing, the application will not start.
if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, WEBHOOK_URL]):
    logging.error("Missing required environment variables. Please check your .env file or deployment settings.")
    raise ValueError("Missing required environment variables (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, WEBHOOK_URL).")

# --- Configure Google Gemini API ---
# Initialize the Gemini API client with your API key.
genai.configure(api_key=GEMINI_API_KEY)

# --- System Prompt for the Dental Clinic ---
# This prompt guides the Gemini model on its persona, tone, and the information it should use
# when responding to user queries. It's written in Egyptian Arabic as per the requirement.
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

# Initialize the Telegram Bot and Dispatcher.
# The Bot instance is used to interact with the Telegram Bot API.
# The Dispatcher is responsible for routing incoming updates to the correct handlers.
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

async def get_gemini_response_async(input_parts: list):
    """
    Generates a response from the Gemini model asynchronously.
    This function handles both text and voice inputs by preparing the
    appropriate `input_parts` list for the Gemini API.
    """
    try:
        # Use 'gemini-1.5-flash' for its speed and multimodal capabilities (text and audio).
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Call the generate_content_async method for asynchronous API interaction.
        response = await model.generate_content_async(input_parts)
        # Extract and return the generated text, stripping any leading/trailing whitespace.
        return response.text.strip()
    except Exception as e:
        # Log any errors that occur during the Gemini API call.
        logging.error(f"Error getting Gemini response: {e}", exc_info=True)
        # Return a user-friendly error message in Egyptian Arabic.
        return "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678"

# --- Message Handlers ---
# These functions define how the bot responds to different types of messages.

@dp.message(F.text)
async def handle_text_message(message: Message):
    """
    Handles incoming text messages from users.
    It constructs the input for Gemini by combining the system prompt with the user's text.
    """
    logging.info(f"Received text message from {message.chat.id}: '{message.text}'")
    gemini_input = [
        DENTAL_CLINIC_SYSTEM_PROMPT,
        f"User message: \"{message.text}\""
    ]
    # Get the response from Gemini and send it back to the user.
    response_text = await get_gemini_response_async(gemini_input)
    await message.answer(response_text)

@dp.message(F.voice)
async def handle_voice_message(message: Message):
    """
    Handles incoming voice messages from users.
    It downloads the voice note from Telegram, prepares it for Gemini,
    and then sends Gemini's text response back to the user.
    """
    logging.info(f"Received voice message from {message.chat.id}, file_id: {message.voice.file_id}, mime_type: {message.voice.mime_type}")
    
    # Use BytesIO to store the downloaded audio in memory.
    with BytesIO() as audio_buffer:
        # Download the voice file from Telegram.
        await bot.download(file=message.voice.file_id, destination=audio_buffer)
        audio_bytes = audio_buffer.getvalue() # Get the raw bytes of the audio.

    # Prepare the input for Gemini, including the system prompt and the audio data.
    gemini_input = [
        DENTAL_CLINIC_SYSTEM_PROMPT,
        "The user sent a voice note. Transcribe it, understand the request, and answer in Egyptian Arabic.",
        {"mime_type": message.voice.mime_type, "data": audio_bytes}
    ]
    # Get the response from Gemini and send it back to the user.
    response_text = await get_gemini_response_async(gemini_input)
    await message.answer(response_text)

@dp.message()
async def handle_unsupported_message(message: Message):
    """
    Handles any message types that are not explicitly covered by other handlers (e.g., photos, stickers).
    It informs the user that only text and voice messages are supported.
    """
    logging.info(f"Received unsupported message type from {message.chat.id}: {message.content_type}. Replying with a standard message.")
    await message.reply("أنا أسف، أنا بفهم الرسائل النصية والصوتية بس.")

# --- FastAPI Lifespan Events ---
# This context manager handles startup and shutdown logic for the FastAPI application.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for handling startup and shutdown events.
    This replaces the aiohttp-specific on_startup and on_shutdown functions.
    """
    # Changed webhook_path to a generic one without the token
    webhook_path = "/webhook"
    webhook_url = f"{WEBHOOK_URL}{webhook_path}"
    logging.info(f"Setting webhook to: {webhook_url}")
    # Set the webhook when the FastAPI app starts
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logging.info("Webhook set successfully.")
    
    # Start polling for updates in the background if you want to run without webhooks
    # or if you want to ensure updates are processed even if webhook fails
    # asyncio.create_task(dp.start_polling(bot))

    yield # This yields control to the FastAPI application to start serving requests

    # This code runs when the FastAPI app is shutting down
    logging.info("Deleting webhook...")
    await bot.delete_webhook()
    logging.info("Webhook deleted successfully.")
    # Stop the dispatcher gracefully
    await dp.stop_polling()


# Create the FastAPI application instance, integrating the lifespan events.
app = FastAPI(lifespan=lifespan)

# --- FastAPI Webhook Endpoint ---
# Changed the endpoint path to a generic one without the token
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    FastAPI endpoint to receive Telegram webhook updates.
    This endpoint receives the raw JSON update from Telegram and feeds it to Aiogram's Dispatcher.
    """
    logging.info("Received Telegram webhook via FastAPI.")
    update_data = await request.json()
    # Process the update using Aiogram's Dispatcher
    await dp.feed_update(bot, types.Update(**update_data))
    return {"ok": True}

# --- Health Check Endpoint (Optional but Recommended) ---
@app.get("/")
async def health_check():
    """
    Simple health check endpoint for monitoring the application's status.
    """
    logging.info("Health check requested.")
    return {"status": "OK", "message": "Telegram Bot (FastAPI) is running."}

# --- Main Application Entry Point ---
# This block ensures the FastAPI application is run when the script is executed directly.

