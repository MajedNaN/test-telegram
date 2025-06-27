from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import google.generativeai as genai

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://smilecare-dentals.vercel.app/"],  # ✅ Replace with your actual frontend domain
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# Load Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in environment.")

genai.configure(api_key=GEMINI_API_KEY)

DENTAL_CLINIC_SYSTEM_PROMPT = """
إنت مساعد ذكي بتشتغل مع عيادة "سمايل كير للأسنان" في القاهرة. رد على الناس كأنك واحد مصري عادي، وبشكل مختصر ومباشر.

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

def get_gemini_response(input_parts):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(input_parts)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return "آسف، حصلت مشكلة. حاول تاني أو كلم العيادة على +20 2 1234-5678"

@app.post("/api/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_input = data.get("message", "")
        gemini_input = [DENTAL_CLINIC_SYSTEM_PROMPT, f"User: \"{user_input}\""]
        reply = get_gemini_response(gemini_input)
        return {"reply": reply}
    except Exception as e:
        logging.error(f"Chat endpoint error: {e}")
        return {"reply": "فيه مشكلة حصلت، جرب تاني بعد شوية 🙏"}
