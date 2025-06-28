###### SET Webhook for telegram
######   https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-deployed-app-url.com/webhook

from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import google.generativeai as genai
import logging
import asyncio # Import asyncio for to_thread

app = FastAPI()

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not all([TELEGRAM_BOT_TOKEN, GEMINI_API_KEY]):
    logging.error("Missing one or more required environment variables.")
    raise ValueError("Missing one or more required environment variables (TELEGRAM_BOT_TOKEN, GEMINI_API_KEY).")

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

# Initialize httpx client outside the request-handling functions
# This client will be reused across all requests.
# It's better to manage its lifecycle with FastAPI's lifespan events.
telegram_httpx_client: httpx.AsyncClient = None

@app.on_event("startup")
async def startup_event():
    """Event that runs when the FastAPI application starts."""
    global telegram_httpx_client
    telegram_httpx_client = httpx.AsyncClient()
    logging.info("httpx.AsyncClient initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    """Event that runs when the FastAPI application shuts down."""
    global telegram_httpx_client
    if telegram_httpx_client:
        await telegram_httpx_client.aclose()
        logging.info("httpx.AsyncClient closed.")

# --- FastAPI Webhook Endpoints ---

@app.get("/")
def health_check():
    """Simple health check endpoint."""
    logging.info("Health check requested.")
    return {"status": "OK", "message": "Telegram Bot is running."}

@app.post("/webhook")
async def handle_telegram_webhook(request: Request):
    """
    Handles incoming updates from Telegram.
    This endpoint receives all messages, including text and voice notes.
    """
    data = await request.json()
    logging.info(f"Received Telegram webhook: {data}")

    if "message" not in data:
        logging.warning("No message object in the update. Skipping.")
        return {"status": "ok"}

    message = data["message"]
    chat_id = message["chat"]["id"]
    
    gemini_input = []

    try:
        if "text" in message:
            user_text = message["text"]
            logging.info(f"Received text message from {chat_id}: {user_text}")
            gemini_input = [
                DENTAL_CLINIC_SYSTEM_PROMPT,
                f"User message: \"{user_text}\""
            ]
        elif "voice" in message:
            voice_file_id = message["voice"]["file_id"]
            mime_type = message["voice"]["mime_type"]
            logging.info(f"Received voice message from {chat_id}, file_id: {voice_file_id}")

            audio_bytes = await get_telegram_audio_bytes(voice_file_id)

            if audio_bytes:
                gemini_input = [
                    DENTAL_CLINIC_SYSTEM_PROMPT,
                    "The user sent a voice note. Transcribe it, understand the request, and answer in Egyptian Arabic based on the clinic's information. Make the response concise.",
                    {"mime_type": mime_type, "data": audio_bytes}
                ]
            else:
                await send_telegram_message(chat_id, "معلش، مقدرتش أسمع الرسالة الصوتية. ممكن تبعتها تاني أو تكتب سؤالك؟")
                return {"status": "ok"}
        else:
            logging.info(f"Received unsupported message type: {message.keys()}. Skipping.")
            await send_telegram_message(chat_id, "أنا أسف، أنا بفهم الرسائل النصية والصوتية بس.")
            return {"status": "ok"}
        
        if gemini_input:
            # Run the synchronous get_gemini_response in a separate thread pool
            response_text = await asyncio.to_thread(get_gemini_response, gemini_input)
            await send_telegram_message(chat_id, response_text)

    except Exception as e:
        logging.error(f"Error handling Telegram webhook for chat_id {chat_id}: {e}", exc_info=True)
        await send_telegram_message(chat_id, "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678")

    return {"status": "ok"}

# --- Helper Functions for Telegram API ---

async def get_telegram_audio_bytes(file_id: str):
    """
    Fetches audio file from Telegram and returns its bytes.
    Telegram requires two steps: get file path, then download file.
    """
    get_file_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
    try:
        response = await telegram_httpx_client.get(get_file_url, params={"file_id": file_id})
        response.raise_for_status()
        file_info = response.json()
        
        if not file_info.get("ok"):
            logging.error(f"Telegram getFile API error: {file_info.get('description', 'Unknown error')}")
            return None

        file_path = file_info["result"]["file_path"]
        logging.info(f"Retrieved file path from Telegram: {file_path}")

        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        audio_response = await telegram_httpx_client.get(download_url)
        audio_response.raise_for_status()

        logging.info(f"Successfully downloaded audio from Telegram: {len(audio_response.content)} bytes")
        return audio_response.content
    
    except httpx.RequestError as e:
        logging.error(f"Error communicating with Telegram API for file_id {file_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in get_telegram_audio_bytes for file_id {file_id}: {e}", exc_info=True)
        return None

async def send_telegram_message(chat_id: int, message_text: str):
    """ Sends a text message back to the user on Telegram """
    send_message_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text
    }
    
    try:
        response = await telegram_httpx_client.post(send_message_url, json=payload)
        response.raise_for_status()
        logging.info(f"Message sent to Telegram chat_id {chat_id}")
    except httpx.RequestError as e:
        logging.error(f"Error sending message to Telegram chat_id {chat_id}: {e}")
        logging.error(f"Telegram API Response Body: {response.text if response else 'No response'}")
    except Exception as e:
        logging.error(f"Unexpected error in send_telegram_message for chat_id {chat_id}: {e}", exc_info=True)

# --- Helper Functions for Gemini ---

def get_gemini_response(input_parts: list):
    """
    Generates a response from Gemini using the provided input parts (text and/or audio).
    This function is synchronous and will be run in a thread pool.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(input_parts)
        return response.text.strip()
        
    except Exception as e:
        logging.error(f"Error getting Gemini response: {e}", exc_info=True)
        return "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678"