






###### SET Webhook for telegram
######   https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-deployed-app-url.com/webhook












from fastapi import FastAPI, Request, HTTPException
import requests
import os
import google.generativeai as genai
import logging

app = FastAPI()

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
أنت مساعد ذكي تتواصل مع الأشخاص بأسلوب لطيف وظريف يرسم الابتسامة على وجوههم. تعمل لدى "عيادة سمايل كير للأسنان" في القاهرة. تحدث مع الناس بطريقة مهذبة، مباشرة، وموجزة.

**قواعد مهمة:**
1. **استخدم اللغة العربية الفصحى فقط**: تكلّم بأسلوب مهذب وطبيعي، دون لهجات عامية. مثال: "مرحبًا"، "كيف يمكنني مساعدتك؟"، "تفضل"، "عذرًا"، وهكذا.
2. **أنت لا تقوم بحجز المواعيد**: أخبر الشخص بأنك مساعد ذكي ولا تملك صلاحية الحجز، لكن يمكنك تقديم المعلومات والإرشاد. إذا سأل أحد عن الحجز، فقل له أن يتواصل مع العيادة على الرقم +20 2 1234-5678.
3. **الخدمات والأسعار**: عند السؤال عن خدمة ما، استخدم المعلومات أدناه، ووضح دائمًا أن الأسعار تقريبية وقد تختلف حسب الحالة.
4. **الرسائل الصوتية**: إذا وصلتك رسالة صوتية، استمع إليها، افهم طلب الشخص، ثم أجب كتابيًا بنفس الأسلوب.
5. **اختصر قدر الإمكان**: أجب بسرعة وبدون إطالة أو تكرار.

**معلومات العيادة:**
- الاسم: عيادة سمايل كير للأسنان
- العنوان: القاهرة، مصر
- رقم الهاتف (للحجز والطوارئ): +20 2 1234-5678
- المواعيد: من السبت إلى الخميس (من 9 صباحًا حتى 8 مساءً)، الجمعة (من 2 مساءً حتى 8 مساءً)

**الخدمات والأسعار (تقريبًا بالجنيه المصري):**
- كشف: 300
- تنظيف الأسنان: 500
- حشو سن: ابتداءً من 400
- علاج العصب: ابتداءً من 1500
- خلع سن: ابتداءً من 600
- زراعة سن: ابتداءً من 8000
- تبييض الأسنان: 2500

**ملاحظات:**
- لا تكرر نفس الجمل أو العبارات في كل رد. كن طبيعيًا ومتجددًا في أسلوبك.
- إذا لم تفهم الرسالة، اطلب من الشخص توضيحها.
- إذا قال أحدهم "شكرًا" أو ما يشبه ذلك، رد عليه برد بسيط ولطيف.
"""



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
    msg_type = None
    
    gemini_input = []

    try:
        if "text" in message:
            msg_type = "text"
            user_text = message["text"]
            logging.info(f"Received text message from {chat_id}: {user_text}")
            gemini_input = [
                DENTAL_CLINIC_SYSTEM_PROMPT,
                f"User message: \"{user_text}\""
            ]
        elif "voice" in message:
            msg_type = "voice"
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
            # Handle other message types if needed, or simply ignore
            logging.info(f"Received unsupported message type: {message.keys()}. Skipping.")
            await send_telegram_message(chat_id, "أنا أسف، أنا بفهم الرسائل النصية والصوتية بس.")
            return {"status": "ok"}
        
        if gemini_input:
            response_text = get_gemini_response(gemini_input)
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
    # Step 1: Get file path
    get_file_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
    try:
        response = requests.get(get_file_url, params={"file_id": file_id})
        response.raise_for_status()
        file_info = response.json()
        
        if not file_info.get("ok"):
            logging.error(f"Telegram getFile API error: {file_info.get('description', 'Unknown error')}")
            return None

        file_path = file_info["result"]["file_path"]
        logging.info(f"Retrieved file path from Telegram: {file_path}")

        # Step 2: Download the actual audio file
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        audio_response = requests.get(download_url)
        audio_response.raise_for_status()

        logging.info(f"Successfully downloaded audio from Telegram: {len(audio_response.content)} bytes")
        return audio_response.content
    
    except requests.exceptions.RequestException as e:
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
        response = requests.post(send_message_url, json=payload)
        response.raise_for_status()
        logging.info(f"Message sent to Telegram chat_id {chat_id}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending message to Telegram chat_id {chat_id}: {e}")
        logging.error(f"Telegram API Response Body: {response.text if response else 'No response'}")
    except Exception as e:
        logging.error(f"Unexpected error in send_telegram_message for chat_id {chat_id}: {e}", exc_info=True)


# --- Helper Functions for Gemini (remains largely the same) ---

def get_gemini_response(input_parts: list):
    """
    Generates a response from Gemini using the provided input parts (text and/or audio).
    """
    try:
        # We use gemini-1.5-flash because it's fast and supports audio input.
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Generate the content
        response = model.generate_content(input_parts)
        
        # Clean up the response to ensure it's a single block of text
        return response.text.strip()
        
    except Exception as e:
        logging.error(f"Error getting Gemini response: {e}", exc_info=True)
        return "آسف، حصل مشكلة عندي. ممكن تكلم العيادة على طول على الرقم ده: +20 2 1234-5678"

