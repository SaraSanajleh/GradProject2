from __future__ import annotations

import logging
import os
import asyncio
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Ollama: الموديل الافتراضي DeepSeek Cloud؛ يمكن التبديل من الواجهة أو .env
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# مطلوب لموديلات Cloud عبر ollama.com فقط: إنشاء المفتاح من https://ollama.com/settings/keys
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

LLM_ERROR_MARKER = "__LLM_ERROR__"
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))

# Model Selector: معرفات الواجهة → اسم موديل Ollama Cloud الفعلي
OLLAMA_MODEL_MAP = {
    "deepseek-v3.1:671b-cloud": "deepseek-v3.1:671b-cloud",
    "qwen3.5:cloud": "qwen3.5:cloud",
    "gpt-oss:120b-cloud": "gpt-oss:120b-cloud",
    "qwen3-vl:235b-cloud": "qwen3-vl:235b-cloud",
    "nemotron-3-super:cloud": "nemotron-3-super:cloud",
}

# System Prompt ثابت — يُحمّل مع بداية المحادثة ويُمرّر مع كل استدعاء للموديل
SYSTEM_PROMPT = """أنت مساعد طبي ذكي يعمل في مستشفى أردني. وظيفتك التحدث مع المرضى بالعربية الفصحى مع فهم اللهجة الأردنية.

مهمتك هي جمع الأعراض من المريض عبر أسئلة طبية متسلسلة ومنطقية لفهم الحالة بدقة.

يجب عليك:
- طرح سؤال واحد فقط في كل رسالة.
- الحفاظ على أسلوب متعاطف ومطمئن.
- جمع معلومات مثل موقع الألم ومدته وشدته والأعراض المصاحبة.

يجب عليك عدم إعطاء تشخيص نهائي أبداً.

وظيفتك الأساسية هي توجيه المريض إلى القسم الطبي المناسب فقط.

في حال الاشتباه بوجود حالة طارئة يجب تنبيه المريض فوراً بضرورة التوجه إلى الطوارئ دون تأخير.

الأقسام الطبية المتاحة هي:
طب الأعصاب
الأورام
الأمراض الجلدية
أمراض الجهاز الهضمي
أمراض القلب
طب العظام
النسائية والتوليد
طب العيون
جراحة المسالك البولية
الغدد الصماء
أمراض الصدر
طب الأطفال
الأنف والأذن والحنجرة
طب الأسنان
الطب النفسي"""


class LlmClient:
    """
    عميل LLM لاستدعاء النموذج عبر Ollama API.
    يدعم Model Selector: اختيار الموديل من الواجهة (DeepSeek أو Llama) دون تغيير هيكل النظام.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        env_model = (OLLAMA_MODEL or "").strip()
        if model_name and model_name in OLLAMA_MODEL_MAP:
            self.model_name = OLLAMA_MODEL_MAP[model_name]
        else:
            self.model_name = env_model or "deepseek-v3.1:671b-cloud"
        print(f"🤖 Model: {self.model_name}")

    async def call_model(self, prompt: str) -> str:
        """إرسال المحادثة إلى الموديل مع System Prompt وترجيع رد المساعد."""
        if not self.model_name:
            return ""

        base_url = (OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        headers = {"Content-Type": "application/json"}
        if OLLAMA_API_KEY and "ollama.com" in base_url:
            headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

        model_name = self.model_name

        def _call_sync() -> str:
            try:
                resp = requests.post(
                    url,
                    json={"model": model_name, "messages": messages, "stream": False},
                    headers=headers,
                    timeout=LLM_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                msg = data.get("message") or {}
                return (msg.get("content") or "").strip()
            except requests.exceptions.Timeout:
                logger.error("⏱️ LLM timeout (%ds) for model=%s url=%s", LLM_TIMEOUT, model_name, url)
                return LLM_ERROR_MARKER
            except requests.exceptions.ConnectionError:
                logger.error("🔌 LLM connection error for model=%s url=%s", model_name, url)
                return LLM_ERROR_MARKER
            except requests.exceptions.HTTPError as exc:
                logger.error(
                    "❌ LLM HTTP error for model=%s: %s — response: %s",
                    model_name, exc, exc.response.text[:500] if exc.response is not None else "N/A",
                )
                return LLM_ERROR_MARKER
            except Exception as exc:
                logger.error("❌ LLM unexpected error for model=%s: %s", model_name, exc)
                return LLM_ERROR_MARKER

        return await asyncio.to_thread(_call_sync)

    async def call_with_system(self, system_content: str, user_content: str) -> str:
        """استدعاء الموديل مع system prompt مخصص (مثلاً لاختيار القسم من الأعراض + RAG)."""
        if not self.model_name:
            return ""
        base_url = (OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        headers = {"Content-Type": "application/json"}
        if OLLAMA_API_KEY and "ollama.com" in base_url:
            headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

        model_name = self.model_name

        def _call_sync() -> str:
            try:
                resp = requests.post(
                    url,
                    json={"model": model_name, "messages": messages, "stream": False},
                    headers=headers,
                    timeout=LLM_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                msg = data.get("message") or {}
                return (msg.get("content") or "").strip()
            except requests.exceptions.Timeout:
                logger.error("⏱️ LLM timeout (%ds) for model=%s url=%s", LLM_TIMEOUT, model_name, url)
                return LLM_ERROR_MARKER
            except requests.exceptions.ConnectionError:
                logger.error("🔌 LLM connection error for model=%s url=%s", model_name, url)
                return LLM_ERROR_MARKER
            except requests.exceptions.HTTPError as exc:
                logger.error(
                    "❌ LLM HTTP error for model=%s: %s — response: %s",
                    model_name, exc, exc.response.text[:500] if exc.response is not None else "N/A",
                )
                return LLM_ERROR_MARKER
            except Exception as exc:
                logger.error("❌ LLM unexpected error for model=%s: %s", model_name, exc)
                return LLM_ERROR_MARKER

        return await asyncio.to_thread(_call_sync)


EVALUATION_MODEL_NAME = "deepseek-v3.1:671b-cloud"


def get_evaluation_llm_client() -> LlmClient:
    """
    عميل LLM مخصّص لـ Evaluation Agent فقط.
    مثبّت على DeepSeek v3.1 (Ollama Cloud) لضمان تقييم موضوعي
    مستقل عن الموديل المختار من المريض في الواجهة.
    """
    return LlmClient(EVALUATION_MODEL_NAME)


def get_llm_client(model_name: str) -> LlmClient:
    """
    Chat handler: إرجاع عميل LLM حسب الموديل المختار من الواجهة.
    يدعم حالياً: deepseek-v3.1:671b-cloud (افتراضي)، llama3.1:8b. قابل للتوسع.

    تفعيل DeepSeek:
    - محلي (Ollama على الجهاز): ollama signin ثم ollama pull deepseek-v3.1:671b-cloud
    - من .env لا تضبط OLLAMA_MODEL أو ضبطه deepseek-v3.1:671b-cloud، واختر DeepSeek من القائمة في الشات
    - عبر Ollama Cloud مباشرة: OLLAMA_BASE_URL=https://ollama.com و OLLAMA_API_KEY=مفتاحك
    """
    return LlmClient(model_name or None)
