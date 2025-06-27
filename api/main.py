from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import google.generativeai as genai

# إعداد التسجيل لتتبع الأخطاء في سجلات Vercel
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# قائمة النطاقات المسموح بها لـ CORS (تأكد من مطابقتها لنطاق موقع الودجت)
# من الأفضل تضمين كل من النسخة مع وبدون الشرطة المائلة الأخيرة
origins = [
    "https://smilecare-dentals.vercel.app",  # نطاق الواجهة الأمامية بدون الشرطة المائلة
    "https://smilecare-dentals.vercel.app/", # نطاق الواجهة الأمامية مع الشرطة المائلة
    # يمكنك إضافة "http://localhost:3000" أو أي نطاق آخر تستخدمه للتطوير المحلي
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # مهم إذا كنت سترسل ملفات تعريف الارتباط أو هيدر التخويل (مثل API Key)
    allow_methods=["*"], # اسمح بجميع أساليب HTTP (POST, GET, إلخ)
    allow_headers=["*"], # اسمح بجميع الرؤوس في الطلب
)

# تحميل مفتاح Gemini API من المتغيرات البيئية
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تحقق مما إذا كان مفتاح API موجوداً
if not GEMINI_API_KEY:
    logger.error("خطأ: المتغير البيئي 'GEMINI_API_KEY' غير مضبوط. لن يعمل Gemini API.")
    # يمكنك اختيار إنهاء التطبيق هنا إذا كان لا يمكن أن يعمل بدون المفتاح:
    # import sys
    # sys.exit(1)

# إعداد Gemini API فقط إذا كان المفتاح موجوداً
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("تم تكوين Gemini API بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في تكوين Gemini API: {e}", exc_info=True)
else:
    logger.warning("لم يتم تكوين Gemini API بسبب عدم وجود مفتاح API.")


# التعليمات البرمجية الأساسية لنظام الدردشة
DENTAL_CLINIC_SYSTEM_PROMPT = """
إنت مساعد ذكي بتشتغل مع عيادة "سمايل كير للأسنان" في القاهرة. رد على الناس كأنك واحد مصري عادي، وبشكل مختصر ومباشر.

**قواعد مهمة:**
1. **اتكلم بالمصري وبس**: استخدم لهجة مصرية طبيعية، زي "إزيك"، "عامل إيه"، "تحت أمرك"، "يا فندم"، "بص يا باشا"، وكده. خليك خفيف وودود.
2. **إنت مش بتاخد مواعيد**: قول للناس إنك مساعد ذكي ومبتحجزش بنفسك، لكن ممكن تساعدهم بمعلومة أو ترشدهم. لو حد سأل عن الحجز، قوله يتصل بالعيادة على +20 2 1234-5678.
3. **الخدمات والأسعار**: لو حد سأل عن حاجة، رد بالمعلومة من اللي تحت، بس دايمًا وضّح إن الأسعار تقريبية وممكن تختلف حسب الحالة.
4. **الرسائل الصوتية**: لم نعد ندعم الرسائل الصوتية في هذا الاندماج. إذا جاءت رسالة صوتية، اطلب من المستخدم أن يرسل رسالة نصية بدلاً من ذلك.
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

# دالة مساعدة للحصول على استجابة من Gemini
def get_gemini_response(user_input: str):
    """
    تُولد استجابة من Gemini بناءً على مدخل المستخدم النصي.
    """
    # تحقق مما إذا كان مفتاح API موجوداً قبل محاولة استخدام Gemini
    if not GEMINI_API_KEY:
        logger.error("مفتاح GEMINI_API_KEY غير مضبوط، لا يمكن استدعاء Gemini API.")
        return "آسف، حصلت مشكلة داخلية (مفتاح API غير مضبوط). يرجى الاتصال بالعيادة."

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # إنشاء مدخل Gemini مع رسالة المستخدم ونظام المساعد
        gemini_input_parts = [
            DENTAL_CLINIC_SYSTEM_PROMPT,
            f"User: \"{user_input}\""
        ]
        
        response = model.generate_content(gemini_input_parts)
        
        # تحقق من أن الاستجابة تحتوي على نص
        if response and response.text:
            return response.text.strip()
        else:
            logger.warning("استجابة Gemini فارغة أو لا تحتوي على نص.")
            return "آسف، استجابة غير متوقعة من المساعد. حاول تاني."
            
    except Exception as e:
        logger.error(f"خطأ في استدعاء Gemini API: {e}", exc_info=True)
        return "آسف، حصلت مشكلة في الاتصال بالمساعد. حاول تاني أو كلم العيادة على +20 2 1234-5678"

# نقطة نهاية فحص الصحة
@app.get("/")
def health_check():
    """نقطة نهاية بسيطة للتحقق من أن الـ API يعمل."""
    logger.info("تم تلقي طلب فحص الصحة.")
    return {"status": "OK", "message": "API الودجت يعمل بشكل جيد."}

# نقطة نهاية الدردشة للودجت
@app.post("/api/chat")
async def chat(request: Request):
    """
    تتعامل مع رسائل الدردشة الواردة من الودجت.
    """
    try:
        data = await request.json()
        user_input = data.get("message", "")
        
        if not user_input:
            logger.warning("تم استلام رسالة فارغة من الودجت.")
            return {"reply": "ياريت تكتب رسالة عشان أقدر أساعدك يا فندم."}

        logger.info(f"تم استلام رسالة المستخدم من الودجت: {user_input}")
        
        # الحصول على الاستجابة من Gemini
        reply = get_gemini_response(user_input)
        
        logger.info(f"استجابة Gemini للودجت: {reply}")
        return {"reply": reply}
        
    except Exception as e:
        logger.error(f"خطأ في نقطة نهاية المحادثة (API chat): {e}", exc_info=True)
        return {"reply": "فيه مشكلة حصلت، جرب تاني بعد شوية �"}
