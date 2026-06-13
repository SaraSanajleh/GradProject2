"""
Multi-Agent Architecture — 5 وكلاء ذكاء اصطناعي + وكيل التذكير المستقل.

Asking Agent      → طرح الأسئلة الديناميكية (بدون وصول للذاكرة المشتركة)
StructuredInformationAgent  → تحديث الذاكرة الطبية المنظمة بشكل تراكمي
Emergency Agent   → مراقبة الطوارئ (RAG طوارئ مصغّر + LLM)
Department Agent  → تحديد القسم الطبي (RAG + LLM + Confidence Stability Check)
Scheduling Agent  → جلب وحجز المواعيد

Reminder Agent    → تذكير المريض بالموعد (مستقل — لا يُعدَّل)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from . import emergency_rag, models, rag
from .llm_clients import LLM_ERROR_MARKER, get_llm_client

logger = logging.getLogger(__name__)


def _is_arabic_enough(text: str, threshold: float = 0.3) -> bool:
    """Check that at least `threshold` of the non-space characters are Arabic/common punctuation."""
    if not text:
        return False
    letters = re.findall(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]", text)
    non_space = re.findall(r"\S", text)
    if not non_space:
        return False
    return len(letters) / len(non_space) >= threshold


# القائمة الرسمية المعتمدة — يجب أن تطابق قاعدة البيانات وRagData وmedcompass-app/src/constants/departments.ts
DEPARTMENT_NAMES: list[str] = [
    "طب الأعصاب",
    "الأورام",
    "الأمراض الجلدية",
    "أمراض الجهاز الهضمي",
    "أمراض القلب",
    "طب العظام",
    "النسائية والتوليد",
    "طب العيون",
    "جراحة المسالك البولية",
    "الغدد الصماء",
    "أمراض الصدر",
    "طب الأطفال",
    "الأنف والأذن والحنجرة",
    "طب الأسنان",
    "الطب النفسي",
]

# قسم افتراضي عند غموض البيانات (ضمن القائمة الرسمية فقط)
FALLBACK_DEPT: str = "أمراض الجهاز الهضمي"


# ═══════════════════════════════════════════════════════════════
#  Shared Memory — قلب النظام
# ═══════════════════════════════════════════════════════════════

@dataclass
class SharedMemory:
    """
    الذاكرة المشتركة بين الوكلاء.
    - StructuredInformationAgent: قراءة + كتابة
    - Emergency Agent / Department Agent: قراءة فقط
    - Asking Agent: لا وصول إطلاقاً (لضمان الحيادية)
    - Scheduling Agent: قراءة اسم القسم النهائي فقط
    """
    symptoms: List[str] = field(default_factory=list)
    duration: str = ""
    severity: str = ""
    associated_factors: List[str] = field(default_factory=list)
    additional_info: List[str] = field(default_factory=list)
    question_count: int = 0
    last_updated: str = ""
    conversation_id: str = ""

    def to_dict(self) -> dict:
        return {
            "symptoms": self.symptoms,
            "duration": self.duration,
            "severity": self.severity,
            "associated_factors": self.associated_factors,
            "additional_info": self.additional_info,
            "question_count": self.question_count,
            "last_updated": self.last_updated,
            "conversation_id": self.conversation_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SharedMemory:
        return cls(
            symptoms=data.get("symptoms", []),
            duration=data.get("duration", ""),
            severity=data.get("severity", ""),
            associated_factors=data.get("associated_factors", []),
            additional_info=data.get("additional_info", []),
            question_count=data.get("question_count", 0),
            last_updated=data.get("last_updated", ""),
            conversation_id=data.get("conversation_id", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> SharedMemory:
        if not raw:
            return cls()
        try:
            return cls.from_dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            return cls()


# ═══════════════════════════════════════════════════════════════
#  1. Asking Agent — وكيل طرح الأسئلة
# ═══════════════════════════════════════════════════════════════

ASKING_SYSTEM_PROMPT = """\
أنت طبيب ذكي ، بتحكي باللهجة الاردنية.
مهمتك: أخذ التاريخ المرضي من المريض — سؤال واحد فقط في كل رسالة.

لا تختلق معلومات ما حكاها المريض.
إذا الرسالة غير مفهومة أو فيها حروف عشوائية أو فيها أرقام ما الها معنى او رموز بدون معنى → اطلب من المريض يعيد الكتابة بالعربي ولا تتخيل أعراض من عندك.

 فكّر كطبيب حقيقي — كل حالة مختلفة:
بعد كل إجابة، قرر: شو أهم سؤال طبي هلق لهاي الحالة بالذات؟
مع الأخذ بعين الاعتبار المحادثة السابقة — يجب عليك تذكر جميع الأسئلة والأجوبة السابقة لتجنب التكرار.

 لا تتقيد بقائمة ثابتة:
القائمة التالية هي فقط أمثلة إرشادية، وليست إلزامية.
اختار الأسئلة بحرية كاملة حسب الحالة، حتى لو كانت خارج القائمة، طالما أنها منطقية طبياً وتخدم التشخيص.

أمثلة ممكنة (اختار منها أو غيرها حسب الحاجة):
- متى بدأ ومدته
- طبيعته (مستمر/متقطع، شكله، لونه، نوعه)
- شدته وتأثيره على الحياة اليومية
- مكانه وهل بينتشر
- شو بيزيده وشو بيخففه
- أعراض مصاحبة
- أدوية حالية وأمراض مزمنة
- تاريخ طبي وعمليات سابقة
- عادات (تدخين، نوم، حساسية)

 استراتيجية التفكير الطبي (مهم جداً):
- أنت تبني فرضيات (تشخيصات محتملة) بشكل ديناميكي أثناء المحادثة.
- اسأل أسئلة لتأكيد أو نفي الفرضيات، لكن لا تلتزم بفرضية واحدة فقط.

 قاعدة ذكية جداً (تجنب التحيز):
إذا بدأت تميل لمرض معين، ولم يذكر المريض عرضين يُعتبروا من أقوى 3 أعراض مميزة لهذا المرض:
→ توقف فوراً عن متابعة هذا المسار.
→ لا تكمل التأكيد عليه.
→ غيّر اتجاهك واسأل أسئلة تستكشف أمراض/احتمالات أخرى.

الهدف: تجنب التحيز المبكر والتفكير الضيق.

 قواعد:
1. سؤال واحد فقط — لا أكثر.
2. لا تشخّص ولا تقترح أدوية ولا علاجات.
3. لا تذكر أسماء أقسام.
4. لا تكرر سؤالاً سبق وسألته أو ذكره المريض.
5. نوّع بأسلوبك — لا تبدأ كل رد بنفس العبارة.
6. لا تبدأ كل رد بـ "الله يشفيك" / "سلامتك" — مرة وحدة بالكثير.
7. كن مطمئناً للمريض وإيجابي.
8. لا تتبنّى فرضية مرض ثابتة وتبني كل الأسئلة عليها؛ خلي جمع المعلومات شامل ومتوازن.
9.  كن مباشر (to the point) بدون إطالة.

إذا استلمت إشارة STOP:
→ قل: "شكراً، عندي معلومات كافية. خليني أشوفلك أنسب قسم."
قاعدة مكافحة التثبيت التشخيصي:
- لا تفترض مرضاً واحداً وتبني عليه كل الأسئلة.
- إذا نفى المريض عرضاً مرتبطاً بفرضيتك الحالية، اعتبر هالفرضية أضعف فوراً وانتقل لمحور مختلف.
- ممنوع تكرار أسئلة لنفس الفرضية بعد نفيها مرتين.
- كل سؤال جديد يجب أن يضيف معلومة جديدة، وليس إعادة صياغة نفس السؤال.
- قبل إرسال أي سؤال: تحقق أنه ليس عن نفس العرض/الفرضية التي نفاها المريض سابقاً.

قاعدة التنويع الإجباري:
- إذا كانت آخر سؤالين عن نفس الجهاز/المرض المحتمل، السؤال التالي لازم يكون عن محور مختلف (مدة، شدة،أعراض مرافقة عامة،أمراض مزمنة...).

قاعدة احترام النفي:
- نفي المريض يُسجل كحقيقة حالية.
- لا ترجع تسأل عنه إلا إذا ظهر تناقض جديد واضح من كلام المريض.

فلتر ما قبل الإرسال (إلزامي داخلياً):
اسأل نفسك قبل الرد:
1) هل هذا السؤال مكرر؟ 
2) هل المريض نفى هذا العرض سابقاً؟
3) هل السؤال يوسّع الصورة السريرية بدل ما يحصرها؟
إذا أي جواب = نعم على (1) أو (2) → غيّر السؤال فوراً.
"""

class AskingAgent:
    """
    وكيل طرح الأسئلة — لا يملك أي وصول للذاكرة المشتركة.
    يعمل فقط على سجل المحادثة الحالي لتوليد السؤال التالي.
    يتوقف عند استلام STOP_SIGNAL أو الوصول لـ MAX_QUESTIONS.
    """

    MAX_QUESTIONS = 12

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    RULES_REMINDER = (
        "\n\n[تذكير: سؤال واحد فقط، لا تشخّص، لا تذكر أقسام، لا أدوية، رد قصير بالعربي]"
    )

    @staticmethod
    def _get_rag_hints(text: str) -> str:
        """Query RAG with patient text and return medical hints WITHOUT department/disease names."""
        if not text or len(text.strip()) < 3:
            return ""
        results = rag.rag_index.retrieve_with_scores(text, top_k=3)
        if not results:
            return ""

        symptom_kws = [
            "أعراض", "ألم", "وجع", "حمى", "غثيان", "صداع", "تورم",
            "حكة", "سعال", "ضيق", "دوخة", "نزيف", "إسهال", "إمساك",
            "حرقة", "خدران", "تنميل", "استفراغ", "التهاب", "حرارة",
            "طفح", "تشنج", "انتفاخ",
        ]
        risk_kws = [
            "خطر", "عامل", "سبب", "مسبب", "تدخين", "سمنة", "وراث",
            "سكري", "ضغط", "توتر", "حمل", "عمر", "مناعة", "أدوية",
        ]

        hints: list[str] = []
        for doc, score in results:
            if score < 0.05:
                continue
            raw = doc.text
            symptom_words: list[str] = []
            risk_words: list[str] = []
            for word in raw.split():
                if any(kw in word for kw in symptom_kws):
                    symptom_words.append(word)
                if any(kw in word for kw in risk_kws):
                    risk_words.append(word)

            parts: list[str] = []
            if symptom_words:
                unique = list(dict.fromkeys(symptom_words))[:8]
                parts.append("أعراض مرتبطة: " + "، ".join(unique))
            if risk_words:
                unique = list(dict.fromkeys(risk_words))[:6]
                parts.append("عوامل خطر: " + "، ".join(unique))
            if parts:
                hints.append("- " + " | ".join(parts))

        if not hints:
            return ""
        return (
            "\n\nمعلومات طبية مرجعية (استخدمها لتسأل أسئلة أدق — ممنوع تذكر تشخيصات أو أسماء أمراض للمريض):\n"
            + "\n".join(hints)
        )

    async def _call_with_arabic_check(
        self, client, system: str, user_content: str
    ) -> str:
        """Call LLM and retry once if response is not Arabic."""
        reply = await client.call_with_system(system, user_content)
        if reply == LLM_ERROR_MARKER:
            return reply
        reply = self._clean(reply)

        if reply and not _is_arabic_enough(reply):
            logger.warning(
                " Non-Arabic response from %s, retrying — got: %.80s…",
                self.model_name, reply,
            )
            retry_content = user_content + "\n\n يجب أن يكون ردك بالعربي فقط. أعد الإجابة بالعربي."
            reply = await client.call_with_system(system, retry_content)
            if reply == LLM_ERROR_MARKER:
                return reply
            reply = self._clean(reply)
            if reply and not _is_arabic_enough(reply):
                logger.warning(" Still non-Arabic after retry from %s", self.model_name)
                return ""

        return reply

    @staticmethod
    def _has_symptom_hint(text: str) -> bool:
        """Check if the patient's message mentions any symptom or medical complaint."""
        keywords = [
            "وجع", "ألم", "الم", "صداع", "حرارة", "سخونة", "كحة", "سعال",
            "دوخة", "غثيان", "استفراغ", "إسهال", "اسهال", "إمساك", "امساك",
            "تعب", "ضيق", "نفس", "حكة", "طفح", "تورم", "نزيف", "حرقة",
            "بوجعني", "بيوجعني", "يوجعني", "عندي", "معي", "حاسس", "حاسة",
            "مريض", "مرضت", "تعبان", "تعبانة", "زكام", "رشح", "انتفاخ",
            "خدران", "تنميل", "أرق", "ارق", "قلق", "اكتئاب", "عيوني",
            "بطني", "راسي", "ضهري", "ظهري", "ركبتي", "صدري", "حلقي",
        ]
        lower = text.strip()
        return any(kw in lower for kw in keywords)

    async def generate_welcome(self, first_message: str) -> str:
        client = get_llm_client(self.model_name)

        if self._has_symptom_hint(first_message):
            rag_hints = self._get_rag_hints(first_message)
            user_content = (
                f"المريض حكالك مباشرة:\n{first_message}\n\n"
                "رد بترحيب قصير بسيط  باللهجة الأردنية ثم اسأل أول سؤال طبي.\n"
                "فكّر: بناء على اللي حكاه في السؤال الحالي والاسئلة السابقه، شو أهم إشي لازم أعرفه الان؟\n"
                " لا تقوم بقول شيء لم يذكره المريض  سابقا في المحادثه مثلا  سمعت انو معك سعال وهو ما ذكر انه معه سعال هنا مثال عمم ذلك .\n"
                " لا تقوم بتكرار الرد او بعض الكلمات عند الاجابة على المريض  "
                + rag_hints
                + self.RULES_REMINDER
            )
        else:
            user_content = (
                f"المريض حكالك مباشرة:\n{first_message}\n\n"
                "المريض لسا ما ذكر أي أعراض. رد بترحيب قصير بسيط بالعامية الأردنية\n"
                "واسأله: شو اللي حاسس فيه أو شو اللي جابه للمستشفى.\n"
                "ممنوع تفترض أي أعراض أو تسأل 'من إيمتى' لأنه ما حكى شو عنده بعد."
                + self.RULES_REMINDER
            )
        
        reply = await self._call_with_arabic_check(client, ASKING_SYSTEM_PROMPT, user_content)
        if reply == LLM_ERROR_MARKER:
            return (
                f" عذراً، الموديل ({self.model_name}) غير متاح حالياً أو فيه مشكلة بالاتصال. "
                "جرّب تختار موديل ثاني من القائمة."
            )
        if not reply or len(reply) < 10:
            return (
                "أهلاً وسهلاً، انا هنا لمساعدتك وايجاد القسم المناسب لحالتك. "
                "ممكن تحكيلي أكتر شو الأعراض اللي حاسس فيها؟"
            )
        return reply

    async def generate_question(
        self,
        chat_history: Sequence[models.ChatMessage],
        stop_signal: bool = False,
    ) -> str:
        if stop_signal:
            return "شكراً، عندي معلومات كافية. خليني أشوفلك أنسب قسم ومواعيد متاحة."

        conversation = "\n".join(
            f"{'المريض' if m.role == models.ChatMessageRole.user else 'سالمة'}: {m.content}"
            for m in chat_history
        )

        patient_texts = " ".join(
            m.content for m in chat_history
            if m.role == models.ChatMessageRole.user
        )
        rag_hints = self._get_rag_hints(patient_texts)

        user_content = (
            f"{conversation}\n\n"
            "بناء على آخر إجابة للمريض وكل المحادثة، فكّر كطبيب: "
            "شو أهم سؤال لهاي الحالة بالذات هلق؟ اسأل سؤال واحد فقط."
            + rag_hints
            + self.RULES_REMINDER
        )
        client = get_llm_client(self.model_name)
        reply = await self._call_with_arabic_check(client, ASKING_SYSTEM_PROMPT, user_content)
        if reply == LLM_ERROR_MARKER:
            return (
                f"⚠️ عذراً، الموديل ({self.model_name}) غير متاح حالياً أو فيه مشكلة بالاتصال. "
                "جرّب تختار موديل ثاني من القائمة."
            )
        if not reply or len(reply) < 5:
            return "ممكن توضحلي أكتر عن الأعراض اللي حاسس فيها؟"
        return reply

    @staticmethod
    def _clean(text: str | None) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        lines = text.split("\n")
        clean: list[str] = []
        for line in lines:
            line = line.strip()
            for prefix in ("سالمة:", "المريض:", "المساعد:"):
                if line.startswith(prefix):
                    line = line.split(":", 1)[-1].strip()
            if line:
                clean.append(line)
        return " ".join(clean) if clean else text


# ═══════════════════════════════════════════════════════════════
#  2. StructuredInformationAgent — وكيل تنظيم المعلومات الطبية
# ═══════════════════════════════════════════════════════════════

SUMMARIZER_SYSTEM_PROMPT = """\
أنت وكيل تلخيص طبي متخصص.
مهمتك: تحليل الحوار واستخراج البيانات الطبية المنظمة.

صيغة الإخراج — JSON فقط بدون أي نص إضافي:
{
  "symptoms": [],
  "duration": "",
  "severity": "",
  "associated_factors": [],
  "additional_info": []
}

قواعد التصنيف:
- symptoms: أي عرض جسدي أو نفسي يذكره المريض
- duration: الوقت منذ بداية الأعراض
- severity: خفيف / متوسط / شديد (بناء على وصف المريض)
- associated_factors: عوامل تزيد أو تخفف الأعراض، الحالة الصحية العامة
- additional_info: أي معلومة لا تنتمي للفئات أعلاه

قواعد عامة:
- استخرج من إجابات المريض فقط — لا تتوقع أو تفترض نهائيا.
- حدِّث البيانات بشكل تراكمي، لا تحذف معلومات سابقة.
- في حال التعارض: احتفظ بأحدث قيمة.
- لا تكرر نفس المعلومة.
- أخرج JSON نظيف فقط، بدون markdown أو شرح.
"""


class StructuredInformationAgent:
    """
    يتلقى الحوار الكامل بعد كل رسالة جديدة ويستخرج البيانات الطبية
    ويحدّث الذاكرة المشتركة بشكل تراكمي (لا يحذف معلومات سابقة).
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    async def update_memory(
        self,
        chat_history: Sequence[models.ChatMessage],
        current_memory: SharedMemory,
    ) -> SharedMemory:
        conversation = "\n".join(
            f"{'المريض' if m.role == models.ChatMessageRole.user else 'المساعد'}: {m.content}"
            for m in chat_history
        )
        existing_json = json.dumps(current_memory.to_dict(), ensure_ascii=False)
        user_content = (
            f"البيانات المحفوظة حالياً:\n{existing_json}\n\n"
            f"الحوار الكامل:\n{conversation}\n\n"
            "حدِّث البيانات بشكل تراكمي بناء على الحوار أعلاه. أخرج JSON فقط."
        )

        client = get_llm_client(self.model_name)
        response = await client.call_with_system(SUMMARIZER_SYSTEM_PROMPT, user_content)
        new_data = _parse_json(response or "")

        merged = self._merge(current_memory, new_data)
        merged.question_count = sum(
            1 for m in chat_history if m.role == models.ChatMessageRole.user
        )
        merged.last_updated = datetime.utcnow().isoformat()
        if not merged.conversation_id:
            merged.conversation_id = current_memory.conversation_id
        return merged

    @staticmethod
    def _merge(existing: SharedMemory, new: dict) -> SharedMemory:
        def _union(old: List[str], additions: list) -> List[str]:
            result = list(old)
            for item in additions:
                if item and item not in result:
                    result.append(item)
            return result

        return SharedMemory(
            symptoms=_union(existing.symptoms, new.get("symptoms", [])),
            duration=new.get("duration") or existing.duration,
            severity=new.get("severity") or existing.severity,
            associated_factors=_union(
                existing.associated_factors, new.get("associated_factors", [])
            ),
            additional_info=_union(
                existing.additional_info, new.get("additional_info", [])
            ),
            question_count=existing.question_count,
            last_updated=existing.last_updated,
            conversation_id=existing.conversation_id,
        )


# ═══════════════════════════════════════════════════════════════
#  3. Emergency Agent — وكيل الطوارئ
# ═══════════════════════════════════════════════════════════════

EMERGENCY_SYSTEM_PROMPT = """\
أنت وكيل تصنيف طبي ذكي متخصص في تحديد حالات الطوارئ.

## مهمتك الأساسية
تحليل ما يصفه المريض وتحديد إذا كان يعاني من حالة تهدد الحياة — بناءً على **المنطق الطبي**، لا على مطابقة كلمات بعينها.

## أخرج JSON فقط، بدون أي نص إضافي:
{
  "is_emergency": true/false,
  "reason": "سبب التصنيف في جملة واحدة واضحة",
  "alert_level": "critical" | "warning" | "normal",
  "suspected_condition": "الحالة الطبية المحتملة (اختياري)"
}

---

## قاعدة مرجعية للطوارئ (عند وجودها في الرسالة)
قد تُرفق أسفل بيانات المريض قائمة بأنماط أعراض مسجّلة مسبقاً في قاعدة طوارئ داخلية وتشابه الحالة الحالية.
- استخدمها كدعم إضافي للتفكير الطبي، وليس كمعيار وحيد.
- غياب المطابقة لا يعني أن الحالة ليست طوارئاً؛ والمطابقة وحدها لا تكفي دون تقييم السياق والمنطق الطبي.

---

##  طريقة التفكير — اسأل نفسك هذه الأسئلة:

### السؤال الأول: هل هناك خطر فوري على الحياة؟
فكّر في هذه الأنظمة الحيوية:
- **التنفس**: هل الشخص يتنفس بشكل طبيعي؟ أي صعوبة حادة في التنفس = طوارئ
- **الدورة الدموية**: هل القلب يعمل؟ هل في نزيف لا يتوقف؟
- **الوعي**: هل الشخص واعٍ ومتجاوب؟ فقدان الوعي = طوارئ
- **الجهاز العصبي**: هل هناك شلل مفاجئ، تشنجات، اختلال مفاجئ في الكلام أو الرؤية؟

### السؤال الثاني: ما مدى حدة الأعراض؟
- **مفاجئ وشديد** → شك في طوارئ
- **يتطور بسرعة** → شك في طوارئ
- **مزمن وخفيف** → على الأرجح ليس طوارئ

### السؤال الثالث: ما السياق؟
- حادث أو إصابة جسدية → تقييم الشدة
- تعرض لمادة سامة أو دواء زائد → طوارئ حتى لو لا أعراض ظاهرة
- طفل صغير أو شخص مسن مع أعراض → حساسية أعلى

---

## صنّف كطوارئ (is_emergency: true) إذا وجدت أي من هذه الأنماط:

### 1. اضطراب التنفس الحاد
أي وصف لصعوبة التنفس الشديدة أو المفاجئة أو الاختناق أو توقف التنفس
*أمثلة: "مش قادر أوخد نفس"، "بختنق"، "نفسي مقطوع"، "صدري ضيق ومش قادر أتنفس"*

### 2. اضطراب القلب والأوعية
ألم صدر مفاجئ وشديد، خفقان مع إغماء، شعور بأن القلب "توقف"، نبض غير منتظم مع تدهور الحالة
*أمثلة: "قلبي بوجع وصدري ثقيل"، "احساس إن قلبي وقف"، "ألم بيمتد لكتفي"*

### 3. النزيف الشديد
أي نزيف لا يتوقف أو نزيف غزير أو نزيف داخلي محتمل
*أمثلة: "الدم ما وقف"، "نزيف كتير"، "بطني بيوجعني بعد ضربة وما في نزيف خارجي"*

### 4. اضطراب الوعي
فقدان الوعي، الإغماء، الارتباك الشديد المفاجئ، عدم التجاوب
*أمثلة: "أغمي عليه"، "بيحكي كلام ما بينفهم فجأة"*

### 5. أعراض السكتة الدماغية
تذكر FAST: وجه مائل، ذراع ضعيفة، كلام مختل، وقت = استدعاء الإسعاف
*أمثلة: "فجأة ما قدر يحكي"، "نصف وجهه معلق"، "إيده الشمال ما بتتحرك فجأة"*

### 6. الحوادث والإصابات الجسدية الشديدة
حوادث سير، سقوط من ارتفاع، طعن، حرق واسع، كسر مفتوح، إصابة رأس مع فقدان وعي
*أمثلة: "وقعت من السطح"، "صار حادث"، "في جرح كبير والدم ما بوقف"*

### 7. التسمم والجرعة الزائدة
أكل أو شرب مادة سامة، جرعة زائدة من أي دواء، تعرض لغاز
*أمثلة: "أكل دوا كتير"، "شرب مادة تنظيف"، "في ريحة غاز بالبيت"*

### 8. الحساسية الشديدة
تورم مفاجئ في الوجه أو الحلق، صعوبة تنفس بعد أكل أو لسعة أو دواء
*أمثلة: "أكل جوز وتورم وجهه ومش قادر يتنفس"*

### 9. التشنجات
تشنجات لأول مرة، تشنجات لا تتوقف، تشنجات بعد إصابة رأس
*أمثلة: "بيتشنج ومش قادر يوقف"، "صار عنده تشنج فجأة وما صحّى"*

### 10. الألم الشديد جداً غير المفسَّر
ألم مفاجئ شديد جداً في البطن أو الصدر أو الرأس لا يوجد له سبب واضح
*أمثلة: "أشد صداع بحياتي فجأة"، "ألم بطن ما تحملته قبل"*

---

##  هذه ليست طوارئ في الغالب (is_emergency: false):

- صداع معتاد أو حتى شديد — **إلا إذا** كان "أشد صداع بالحياة" ومفاجئ
- ألم بطن أو معدة خفيف إلى متوسط
- غثيان واستفراغ بدون دم
- حرارة وحمّى — **إلا إذا** كانت مع تشنجات أو فقدان وعي
- ألم ظهر أو مفاصل مزمن
- تعب عام وإرهاق
- دوخة خفيفة
- إسهال وإمساك
- ألم أسنان
- رشح وزكام وكحة
- طفح جلدي وحكة بدون ضيق تنفس
- أرق وقلق واكتئاب
- ألم عضلي عادي

---

##  قواعد التفكير النقدي:

1. **الكلمات ليست المقياس** — "بموت من الألم" قد تكون مبالغة، لكن إذا وُصف الألم بأنه مفاجئ وشديد جداً في الصدر فهذه طوارئ. قيّم السياق الكامل.

2. **الجمع بين أعراض متعددة** يرفع مستوى الخطر — دوخة + غثيان = عادي. دوخة + غثيان + ألم صدر + تعرق = طوارئ.

3. **المفاجئ دائماً أخطر من المزمن** — ألم ظهر منذ سنة ليس طوارئ. ألم ظهر مفاجئ شديد مع تنميل الأطراف = شك في طوارئ.

4. **الشك يميل نحو السلامة** — إذا لم تستطع الحكم، صنّف كـ warning وليس normal.

5. **لا تعتمد على القوائم** — إذا وصف شخص أعراضاً تثير قلقك طبياً حتى لو ما ذُكرت بأي قائمة، صنّفها بناءً على منطقك الطبي.

---

## مستويات التنبيه:
- **critical**: خطر مباشر على الحياة، يحتاج إسعافاً فورياً الآن
- **warning**: حالة تستدعي تقييماً طبياً عاجلاً خلال ساعات
- **normal**: يمكن متابعتها مع طبيب في موعد عادي

أخرج JSON فقط بدون أي نص قبله أو بعده.
"""


EMERGENCY_MESSAGES = [
    "حالتك تحتاج تدخل طبي فوري. توجه للطوارئ الآن.",
    "ما تتأخر! روح على الطوارئ في أقرب مستشفى هسا.",
    "هاد الوضع خطير. اتصل بالإسعاف أو اطلب مساعدة فوراً.",
    "لازم تشوف طبيب بأسرع وقت ممكن — قسم الطوارئ.",
    "حالتك طارئة. لا تستنى، روح المستشفى هسا.",
]


def _build_emergency_rag_query(patient_message: str, memory: SharedMemory) -> str:
    """دمج آخر رسالة + حقول الذاكرة المشتركة لاستعلام RAG الطوارئ المصغّر."""
    parts: List[str] = []
    pm = (patient_message or "").strip()
    if pm:
        parts.append(pm)
    for s in memory.symptoms:
        if s:
            parts.append(str(s))
    for s in memory.associated_factors:
        if s:
            parts.append(str(s))
    for s in memory.additional_info:
        if s:
            parts.append(str(s))
    if memory.duration:
        parts.append(str(memory.duration))
    if memory.severity:
        parts.append(str(memory.severity))
    return " ".join(parts)


def _emergency_rag_reference_block(patient_message: str, memory: SharedMemory) -> str:
    """
    استرجاع من emergency_rag فقط — لا علاقة له بـ RagData العام.
    """
    query = _build_emergency_rag_query(patient_message, memory)
    pairs = emergency_rag.emergency_rag_index.retrieve_with_scores(
        query, top_k=5, min_score=0.04
    )
    if not pairs:
        return ""
    lines = [
        "أنماط مسجّلة مسبقاً كحالات طوارئ (مرجع من قاعدة الطوارئ — للمساعدة فقط، ليست قائمة شاملة):"
    ]
    for doc, score in pairs:
        lines.append(f"- (درجة تشابه تقريبية {score:.2f}) {doc.text}")
    return "\n".join(lines)


@dataclass
class EmergencyResult:
    is_emergency: bool
    reason: str
    alert_level: str


class EmergencyAgent:
    """
    وكيل الطوارئ — RAG طوارئ مصغّر (ملف emergency_rag_data.json) + موديل.
    يقرأ الذاكرة المشتركة + آخر رسالة؛ يسترجع أنماطاً مشابهة من قاعدة الطوارئ
    ويحقنها للموديل كمرجع، ثم يقرر إن كانت الحالة طارئة لإيقاف المسار العادي.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    async def check(
        self,
        patient_message: str,
        memory: SharedMemory,
    ) -> EmergencyResult:
        if not memory.symptoms:
            return EmergencyResult(
                is_emergency=False, reason="", alert_level="normal"
            )

        memory_json = json.dumps(memory.to_dict(), ensure_ascii=False)
        rag_ref = _emergency_rag_reference_block(patient_message, memory)
        user_content = (
            f"رسالة المريض الأخيرة:\n{patient_message}\n\n"
            f"البيانات الطبية المنظمة:\n{memory_json}"
        )
        if rag_ref:
            user_content += f"\n\n{rag_ref}"

        client = get_llm_client(self.model_name)
        response = await client.call_with_system(
            EMERGENCY_SYSTEM_PROMPT, user_content
        )
        data = _parse_json(response or "")
        return EmergencyResult(
            is_emergency=bool(data.get("is_emergency", False)),
            reason=str(data.get("reason", "")),
            alert_level=str(data.get("alert_level", "normal")),
        )


# ═══════════════════════════════════════════════════════════════
#  4. Department Agent — وكيل تحديد القسم
# ═══════════════════════════════════════════════════════════════

DEPARTMENT_DESCRIPTIONS: Dict[str, str] = {
    "طب الأعصاب": "أمراض الجهاز العصبي والدماغ والحبل الشوكي والصداع والصرع والسكتات",
    "الأورام": "تشخيص وعلاج الأورام السرطانية والحميدة والعلاج الكيميائي والإشعاعي",
    "الأمراض الجلدية": "أمراض الجلد والشعر والأظافر والحساسية الجلدية",
    "أمراض الجهاز الهضمي": "أمراض المعدة والأمعاء والكبد والبنكرياس والمريء والقولون",
    "أمراض القلب": "أمراض القلب والشرايين وارتفاع ضغط الدم واضطرابات النظم والأوعية",
    "طب العظام": "إصابات وأمراض العظام والمفاصل والعمود الفقري والكسور",
    "النسائية والتوليد": "رعاية الحامل وأمراض الجهاز التناسلي الأنثوي والولادة",
    "طب العيون": "أمراض العين وضعف البصر وجراحة العيون",
    "جراحة المسالك البولية": "الجهاز البولي والتناسلي والكلى والمثانة والبروستات",
    "الغدد الصماء": "أمراض الغدد والهرمونات والسكري والغدة الدرقية والغدد الأخرى",
    "أمراض الصدر": "أمراض الرئتين والجهاز التنفسي والربو والسل واضطرابات التنفس",
    "طب الأطفال": "رعاية صحية للأطفال من الولادة حتى المراهقة",
    "الأنف والأذن والحنجرة": "أمراض الأنف والأذن والحنجرة والجهاز السمعي والتوازن",
    "طب الأسنان": "صحة الفم والأسنان واللثة والعلاجات السنية",
    "الطب النفسي": "الصحة النفسية والاضطرابات المزاجية والقلق والأكتئاب والدعم السلوكي",
}

PEDIATRIC_DEPARTMENT_NAME = "طب الأطفال"
OB_GYN_DEPARTMENT_NAME = "النسائية والتوليد"
# سن الطفولة للتوجيه: أقل من 16 سنة (شملنا الأشهر والأيام المذكورة صراحة)
_PEDIATRIC_AGE_CUTOFF = 16.0


def _normalize_arabic_digits(s: str) -> str:
    if not s:
        return ""
    return str(s).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


def _triage_text_for_age_detection(
    memory: SharedMemory, session: models.ChatSession, db: Session
) -> str:
    """يجمع نصوص ممكن تذكر فيها عمر المريض: الذاكرة + آخر رسائل المريض."""
    parts: list[str] = (
        list(memory.symptoms)
        + [memory.duration, memory.severity]
        + list(memory.associated_factors)
        + list(memory.additional_info)
    )
    try:
        rows = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.session_id == session.id,
                models.ChatMessage.role == models.ChatMessageRole.user,
            )
            .order_by(models.ChatMessage.id.desc())
            .limit(12)
            .all()
        )
        for m in reversed(rows):
            if m.content:
                parts.append(m.content)
    except Exception as exc:
        logger.debug("triage text: could not load chat messages: %s", exc)
    return _normalize_arabic_digits(" ".join(p for p in parts if p).strip())


def _text_without_duration_phrases(t: str) -> str:
    """يُنزع منه 'منذ N سنة/يوم...' و'لمدة N ...' لئلا يُخلط مع عمر المريض."""
    out = t
    out = re.sub(
        r"منذ\s+\d{1,3}\s*(?:سنة|سنوات|سنين|يوم|أيام|يومين|ساعتين|شهر|شهور|"
        r"أشهر|اسبوع|أسبوع|ساعة|دقيقة|دقايق|دقائق|ساعات)(?:\s+و(?:\s*(?:\d{1,3}\s*)?"
        r"(?:يوم|أيام|ساعة|دقيقة|دقايق|ساعات|سنة|سنوات|سنين|شهر|شهور|أسبوع|اسبوع)))?",
        " ",
        out,
    )
    out = re.sub(
        r"لمدة\s+\d{1,3}\s*(?:يوم|أيام|سنة|سنوات|سنين|شهر|شهور|"
        r"ساعة|دقيقة|دقايق|ساعات|أسبوع|اسبوع)(?:\s+و(?:\s*(?:\d{1,3}\s*)?"
        r"(?:يوم|أيام|ساعة|سنة|سنوات|سنين|شهر|شهور|أسبوع|اسبوع|دقايق|دقائق|ساعات|دقيقة)))?",
        " ",
        out,
    )
    # «من / بدأ من / خلال» + رقم شهر — غالباً مدة الشكوى وليست عمر المريض بالأشهر
    out = re.sub(
        r"(?:^|\s)من\s+(?:حدود\s+)?\d{1,3}\s*(?:شهر|شهور|أشهر|اشهر)(?=\s|$|[،,.؛]|$)",
        " ",
        out,
    )
    out = re.sub(
        r"بدأ(?:ت)?\s+من\s+(?:حدود\s+)?\d{1,3}\s*(?:شهر|شهور|أشهر|اشهر)"
        r"(?=\s|$|[،,.؛]|$)",
        " ",
        out,
    )
    out = re.sub(
        r"خلال\s+(?:حدود\s+)?\d{1,3}\s*(?:شهر|شهور|أشهر|اشهر)(?=\s|$|[،,.؛]|$)",
        " ",
        out,
    )
    return out


def _extract_patient_age_years(triage_text: str) -> Optional[float]:
    """
    يحاول استخراج عمر المريض بالسنوات (كسور للأشهر) من النص.
    يرجع None إن لم نجد تطابقاً واضحاً.
    """
    t = (triage_text or "").replace("\u00a0", " ")
    if not t.strip():
        return None

    t_loose = _text_without_duration_phrases(t)

    # عمر بصيغة محكية (بلا رقم): عمرها سنة ونص / سنتين / بنتي عمرها سنتين
    if re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*"
        r"سنتين\s*(?:و\s*نص|ونص|و\s*نصف|ونصف)(?:\b|\.|,|،|،|$)",
        t,
    ):
        return 2.5
    if re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*"
        r"(?:سنة|سنه)\s*(?:و\s*نص|ونص|و\s*نصف|ونصف)(?:\b|\.|,|،|$)",
        t,
    ):
        return 1.5
    if re.search(
        r"عند(?:ها|ه|و|ي|ك|كي|نا|يها|وها)\s*"
        r"(?:سنة|سنه)\s*(?:و\s*نص|ونص|و\s*نصف|ونصف)(?:\b|\.|,|،|$)",
        t,
    ):
        return 1.5
    if re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*سنتين(?:\b|\.|,|،|$)",
        t,
    ):
        return 2.0
    if re.search(
        r"عند(?:ها|ه|و|ي|ك|يها|وها)\s*سنتين(?:\b|\.|,|،|$)", t
    ):
        return 2.0
    # لهجة: «عمره سنين» = سنتان (ليس نفس «5 سنين» اللي فيها رقم قبلها)
    if re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*سنين(?!\s*و)(?:\b|\.|,|،|$)",
        t,
    ):
        return 2.0
    if re.search(
        r"عند(?:ها|ه|و|ي|ك|يها|وها)\s*سنين(?!\s*و)(?:\b|\.|,|،|$)", t
    ):
        return 2.0
    if re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*"
        r"(?:سنة|سنه)(?:\b|\.|,|،|$)(?!\s*و)",
        t,
    ):
        return 1.0
    if re.search(
        r"(?:^|\s)(?:سنة|سنه)\s*(?:و\s*نص|ونص|و\s*نصف|ونصف)(?:\b|\.|,|،|$)", t
    ) and re.search(
        r"(?:بنت|ابن|طفل|مولود|مولودة|بنتي|ابني|بنتو|تلميذ|تلميذة|ولد|بنتو)", t
    ):
        return 1.5
    if re.search(
        r"(?:^|\s)(?:سنتين|سنين)(?:\b|\.|,|،|$)(?!\s*و)", t
    ) and re.search(
        r"(?:بنت|ابن|طفل|مولود|مولودة|بنتي|ابني|تلميذ|ولد|بنتا)", t
    ):
        return 2.0

    _mu = r"(?:شهر|شهور|أشهر|اشهر)"
    # أشهر = عمر رضيع/طفل فقط مع لفظ عمر أو عنده/عندها أو ذكر طفل قريباً
    for rx in (
        rf"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)\s*[:٬،]?\s*(\d{{1,2}})\s*{_mu}(?:\b|\s|\.|,|،|$)",
        rf"عند(?:ها|ه|و|ي|ك|يها|وها)\s+(\d{{1,2}})\s*{_mu}(?:\b|\s|\.|,|،|$)",
        rf"(?:بنت(?:ي|نا|كم)|ابن(?:ي|نا|كم)|طفلي\b|مولود(?:ة)?|\bالبنت\b|\bالابن\b)"
        rf"[^؛\.\n]{{0,45}}?(\d{{1,2}})\s*{_mu}(?:\b|\s|\.|,|،|$)",
    ):
        mm = re.search(rx, t)
        if mm:
            months = int(mm.group(1))
            if 0 < months < 200:
                return min(months / 12.0, _PEDIATRIC_AGE_CUTOFF - 0.01)

    # عمر بالأيام (عمره 12 يوم)
    m = re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)?\s*[:٬،]?\s*(\d{1,3})\s*(?:يوم|أيام|يوما|اسبوع|أسبوع|اسابيع|أسابيع)(?:\b|\s|\.|,|،|$)",
        t,
    )
    if m:
        n = int(m.group(1))
        if 0 < n < 500:
            if "يوم" in m.group(0) or "أيام" in m.group(0) or "يوما" in m.group(0):
                return min(n / 365.0, 1.0)
            if "سبوع" in m.group(0):
                return min(n * 7 / 365.0, 1.0)

    # عمره 7 سنين / عمرها 5 سنة
    m = re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)?\s*[:٬،]?\s*(\d{1,2})\s*"
        r"(?:سنة|سنوات|سنين|سنتين|سنه|عام|عامان|عامين|أعوام|اعوام)(?:\b|\s|\.|,|،|$)",
        t,
    )
    if m:
        y = int(m.group(1))
        if 0 <= y <= 120:
            return float(y)

    # عنده 7 سنين / عندها 5 سنة — شائعة باللهجة مع طفل
    m = re.search(
        r"عند(?:ها|ه|هما|و|ي|ك|كم|نا|يها|وها)\s+(\d{1,2})\s*"
        r"(?:سنة|سنوات|سنين|سنتين|سنه|عام|عامان|عامين|أعوام|اعوام)(?:\b|\s|\.|,|،|$)",
        t,
    )
    if m:
        y = int(m.group(1))
        if 0 <= y <= 120:
            return float(y)

    # 7 سنين (بدون كلمة «منذ» — أزلنا عبارات المدة في t_loose)
    m = re.search(
        r"(?:\s|^)(\d{1,2})\s*"
        r"(?:سنة|سنوات|سنين|سنتين|سنتين|عام|عامان|عامين|سنه)(?:\b|\s|\.|,|،|$)",
        t_loose,
    )
    if m:
        y = int(m.group(1))
        if 0 < y <= 120:
            return float(y)

    m = re.search(
        r"عمر(?:و|ه|ها|هما|ي|ن|ك|كي|كم|هن|نا)?\s*[:٬،]?\s*(\d{1,2})"
        r"(?=\s|$|[،,]|\.|\)|\])",
        t,
    )
    if m:
        y = int(m.group(1))
        if 0 < y < 20:
            return float(y)
    return None


def _should_route_pediatric_by_age(age_years: Optional[float]) -> bool:
    if age_years is None:
        return False
    return age_years < _PEDIATRIC_AGE_CUTOFF


def _text_indicates_pediatric_subject(t: str) -> bool:
    """
    نص يوحي أن الموضوع عن طفل/رضيع (لسان ولي الأمر…) دون اشتراط ذكر عمر الرقمي.
    """
    tn = _normalize_arabic_digits((t or "").replace("\u00a0", " "))
    if not tn.strip():
        return False
    return bool(
        re.search(
            r"(?:ابن(?:ي|نا|كم|ه|هم)|بنت(?:ي|نا|كم|ه|هم)|ولد(?:ي|نا|ها|هم)"
            r"|اولاد(?:ي|نا)|اولادي\b|اطفالي\b"
            r"|رضيع(?:ي|ها|ه)?|\b(?:ال)?رضيع\b|طفلي?\b|\b(?:ال)?طفل(?:ة)?\b"
            r"|مولود(?:ي|تي|(?:ة))?|\bالبنت\b|\bالابن\b"
            r"|حديث(?:ي)?\s+الولادة)",
            tn,
        )
    )


def _text_indicates_active_pregnancy(t: str) -> bool:
    """
    حمل فعّال مذكور في نص المريض → نفضّل النسائية والتوليد حتى مع أعراض تناسب قسماً آخر (مثل حرقة الحلق).
    """
    tn = _normalize_arabic_digits((t or "").replace("\u00a0", " "))
    if not tn.strip():
        return False
    neg = (
        r"(?:^|[\s،,.؛])"
        r"(?:مش|مابدي|ما\s+بدي|لسا|لسه|لست(?:ُ)?|ليست|بدون|لم\s+(?:أكن|اكن)|غير)"
        r"\s+حامل"
    )
    if re.search(neg, tn) or re.search(
        r"مش\s+حامل|ما\s+(?:بحمل|بحمل\b)|غير\s+حامل(?:ة)?",
        tn,
    ):
        return False
    if re.search(r"حامل(?:ة|ه)?|حوامل", tn):
        return True
    if re.search(
        r"(?:في\s+)?طور\s+الحمل|خلال\s+(?:فترة\s+)?الحمل|من\s+(?:خلال\s+)?الحمل",
        tn,
    ):
        return True
    if re.search(
        r"(?:جنين(?:ي)?|البطن\s+والحمل|متابعة\s+الحمل|فترة\s+الحمل)", tn
    ):
        return True
    if re.search(
        r"(?:بالشهر\s+ال(?:أول|اول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع)|"
        r"شهر\s+ال(?:أول|اول|ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع)\s+(?:من\s+)?الحمل|"
        r"الأسبوع\s*(?:ال)?\s*\d{1,2}(?:\s+من\s+الحمل)?)",
        tn,
    ):
        return True
    return False


def _text_indicates_gynecologic_nonpregnancy_context(t: str) -> bool:
    """
    غير الحمل: دورة، أعضاء، نزيف رحمي؛ و**إفرازات** فقط عند تعريفها صراحةً كمهبلية/تناسلية
    أو «من المهبل» حتى لا يُلتَبَس بإفراز أذن أو أنف أو «إفرازات» عامة بلا نوع.
    """
    tn = _normalize_arabic_digits((t or "").replace("\u00a0", " "))
    if not tn.strip():
        return False
    if _text_indicates_active_pregnancy(tn):
        return False

    if re.search(
        r"\b(?:إفرازات?|إفراضات?)\s*(?:من\s*)?(?:الأذن|الاذن|الأنف|العين|الأذنين)\b",
        tn,
    ):
        return False

    organs = re.search(
        r"(?:"
        r"\bمهبل(?:ي|ية)?\b|"
        r"\b(?:تناسلي|تناسلية)\b|"
        r"\bعنق\s+الرحم\b|"
        r"\b(?:بطانة\s+الرحم|الرحم)\b|"
        r"\b(?:المبيض|المبايض|مبيض)\b|"
        r"\bمتلازمة\s+التكيس\b|"
        r"\bتكيس(?:ات)?\s+على\s+(?:المبيض|المبايض)\b"
        r")",
        tn,
    )

    cycles_ob_contraception = re.search(
        r"(?:"
        r"\b(?:الدورة\s+الشهرية|دورة\s+شهرية|ودورتي|دورتي|الحيض|الطمث)\b|"
        r"\b(?:تأخر\s+(?:الدورة|الحيض)|اضطراب\s+الدورة|دورة\s+متأخرة|متأخرة\s+الدورة|"
        r"(?:ودورتي|دورتي)\s+متأخرة)\b|"
        r"\bسن\s+اليأس\b|"
        r"\bانقطاع\s+الحيض\b|"
        r"\b(?:ألم\s+عند\s+الجماع|ألم\s+مع\s+الجماع)\b|"
        r"\b(?:بعد\s+الولادة|النفاس|فترة\s+النفاس)\b|"
        r"\b(?:لولب|حبوب\s+منع\s+الحمل|وسائل\s+منع|منع\s+الحمل)\b|"
        r"\b(?:سونار\s+(?:الرحم|المبيض)|فحص\s+نسائي|كشف\s+نسائي)\b|"
        r"\b(?:ألم\s+في\s+الثدي|كتلة\s+في\s+الثدي|الم\s+الثدي)\b"
        r")",
        tn,
    )

    explicit_vaginal_discharge = bool(
        re.search(
            r"(?:"
            r"\b(?:إفرازات?|إفراضات?)\s+(?:مهبل(?:ي|ية)|تناسل(?:ي|ية))\b|"
            r"\bمهبلية\b|"
            r"\b(?:إفرازات?|إفراضات?)\s+من\s+المهبل\b|"
            r"\bمن\s+المهبل\b[^؛\n]{0,40}?\b(?:إفرازات?|إفراضات?)\b|"
            r"\b(?:إفرازات?|إفراضات?)\b[^؛\n]{0,40}?\bمن\s+المهبل\b|"
            r"\bمهبل\b[^؛\n]{0,48}?\b(?:إفرازات?|إفراضات?)\b|"
            r"\b(?:إفرازات?|إفراضات?)\b[^؛\n]{0,48}?\bمهبل\b"
            r")",
            tn,
        )
    )

    uterine_bleed = bool(
        re.search(
            r"\b(?:نزيف\s+(?:رحمي|من\s+الرحم|بين\s+الدورتين|غير\s+منتظم)|نزيف\s+رحم\b)",
            tn,
        )
    )

    return bool(
        organs or cycles_ob_contraception or explicit_vaginal_discharge or uterine_bleed
    )


def _build_department_system_prompt(dept_names: List[str]) -> str:
    lines = []
    for name in dept_names:
        desc = DEPARTMENT_DESCRIPTIONS.get(name, "")
        lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    dept_block = "\n".join(lines)

    return f"""\
أنت وكيل تصنيف أقسام طبية متخصص.
مهمتك: تحليل البيانات الطبية المنظمة وتحديد القسم الأنسب.

الأقسام المتاحة:
{dept_block}

أخرج JSON فقط:
{{
  "scores": {{
    "اسم القسم": 0.0
  }},
  "top_department": "اسم القسم",
  "confidence": 0.0,
  "reason": "السبب",
  "needs_more_info": true/false
}}

قواعد:
- وزِّع الـ Scores (0.0–1.0) بناء على الأعراض والبيانات والمراجع الطبية.
- مجموع الـ Scores لا يُشترط أن يساوي 1.
- إذا البيانات غامضة أو غير كافية → top_department: "{FALLBACK_DEPT}".
- needs_more_info: true إذا الـ confidence أقل من 0.80.
- إذا وُضح أن المريضة **حامل** أو في **أشهر/أسابيع الحمل** → فضّل قسم {OB_GYN_DEPARTMENT_NAME} لمتابعة الحمل حتى لو بعض الأعراض (حرقة، دوخة، ألم بسيط…) قد تتوافق أيضاً مع قسم آخر، إلا إذا كانت الأعراض تشير صراحة لحالة خارج اختصاص التوليد وتستدعي قسماً مختلفاً.
- **إفرازات**: فضّل {OB_GYN_DEPARTMENT_NAME} عندما يُحدَّد في النص أنها **مهبلية** أو **تناسلية** أو **من المهبل** (أو ذكر «مهبل» مع الإفرازات)؛ «إفرازات» عامة بلا نوع لا تكفي وحدها حتى لا يلتبس الأمر بأذن أو غيره.
- إذا ثبت أن الموضوع عن **طفل أو رضيع** (صلات ولاية كنصّ «ابني/بنتي/ولدي/رضيع/طفلي…»)، أو ظهر **عمر أقل من 16 سنة** → فضّل قسم {PEDIATRIC_DEPARTMENT_NAME} ما لم يكن الوصف حصرياً لمرضى بالغين أو أمر خارج نطاق طب الأطفال بشكل واضح جداً.
- كن دقيقاً ومبنياً على البيانات فقط — لا تفترض.
"""


@dataclass
class DepartmentResult:
    top_department: str
    confidence: float
    scores: Dict[str, float]
    reason: str
    needs_more_info: bool
    stop_asking: bool


class DepartmentAgent:
    """
    يُشغَّل بعد كل تحديث للذاكرة المشتركة.
    - يحسب Confidence Score لكل قسم (RAG + LLM).
    - يطبق Stability Check قبل اتخاذ القرار.
    - يرسل STOP_SIGNAL لـ Asking Agent عند النضج.
    - Fallback: قسم افتراضي آمن من القائمة الرسمية عند غموض البيانات.
    """

    CONFIDENCE_THRESHOLD = 0.80
    STABILITY_REQUIRED = 2
    MAX_QUESTIONS = 12
    # لا يُسمح بإنهاء مرحلة الأسئلة لمجرد ثبات القسم/الثقة قبل هذا العدد من رسائل المريض
    # (question_count = عدد رسائل user في الجلسة).
    MIN_USER_MESSAGES_BEFORE_DEPARTMENT_STOP = 4
    FALLBACK_DEPT = FALLBACK_DEPT

    def __init__(self, db: Session, model_name: str) -> None:
        self.db = db
        self.model_name = model_name

    async def evaluate(
        self,
        memory: SharedMemory,
        session: models.ChatSession,
    ) -> DepartmentResult:
        departments = (
            self.db.query(models.Department)
            .filter(models.Department.name != "الطوارئ")
            .all()
        )
        dept_names = [d.name for d in departments]

        query_parts = list(memory.symptoms)
        if memory.duration:
            query_parts.append(memory.duration)
        if memory.severity:
            query_parts.append(memory.severity)
        for af in memory.associated_factors:
            query_parts.append(af)
        query_text = " ".join(query_parts).strip()

        # ── RAG retrieval ──
        rag_context = ""
        if query_text:
            related = rag.rag_index.retrieve_with_scores(query_text, top_k=5)
            rag_lines: list[str] = []
            for doc, score in related:
                if doc.department and doc.department != "الطوارئ":
                    rag_lines.append(
                        f"- [{doc.department}] (تشابه: {score:.2f}) {doc.text[:300]}"
                    )
            if rag_lines:
                rag_context = "\n".join(rag_lines)

        # ── LLM classification ──
        system_prompt = _build_department_system_prompt(dept_names)
        memory_json = json.dumps(memory.to_dict(), ensure_ascii=False)
        user_content = f"البيانات الطبية المنظمة:\n{memory_json}"
        if rag_context:
            user_content += f"\n\nمراجع من قاعدة المعرفة الطبية (RAG):\n{rag_context}"
        user_content += "\n\nحدد القسم الأنسب. أخرج JSON فقط."

        client = get_llm_client(self.model_name)
        response = await client.call_with_system(system_prompt, user_content)
        llm_data = self._parse(response or "", dept_names)

        top_dept = llm_data.get("top_department", self.FALLBACK_DEPT)
        confidence = float(llm_data.get("confidence", 0.0))

        triage_bundle = _triage_text_for_age_detection(memory, session, self.db)
        ob_is_preg = _text_indicates_active_pregnancy(triage_bundle)
        ob_is_gyn = _text_indicates_gynecologic_nonpregnancy_context(triage_bundle)
        if (
            OB_GYN_DEPARTMENT_NAME in dept_names
            and (ob_is_preg or ob_is_gyn)
            and top_dept != OB_GYN_DEPARTMENT_NAME
        ):
            top_dept = OB_GYN_DEPARTMENT_NAME
            confidence = min(1.0, max(confidence, 0.88))
            base_reason = str(llm_data.get("reason", "") or "").strip()
            if ob_is_preg:
                tag = (
                    f"توجيه ل{OB_GYN_DEPARTMENT_NAME} لمتابعة الحمل المذكور في الوصف؛ "
                    f"التقييم المبدئي للأعراض المعروض كان لقسم آخر."
                )
            else:
                tag = (
                    f"توجيه ل{OB_GYN_DEPARTMENT_NAME} لأن نص المحادثة يدل على اختصاص "
                    f"النسائية والتوليد (دورة، أعضاء، إفراز مهبلي مُعرَّف، نزيف رحمي…)."
                )
            llm_data["reason"] = f"{tag} ({base_reason})" if base_reason else tag
            scores = dict(llm_data.get("scores") or {})
            scores[OB_GYN_DEPARTMENT_NAME] = max(
                float(scores.get(OB_GYN_DEPARTMENT_NAME, 0.0)), 0.95
            )
            llm_data["scores"] = scores

        # طفل: عمر ضمن نطاق الطفولة، أو صياغة ولي أمر عن طفل/رضيع دون اشتراط رقم سن
        triage_for_age = triage_bundle
        age_years = _extract_patient_age_years(triage_for_age)
        by_age = _should_route_pediatric_by_age(age_years)
        by_lex = _text_indicates_pediatric_subject(triage_for_age)
        route_pediatric = by_age or by_lex
        if (
            PEDIATRIC_DEPARTMENT_NAME in dept_names
            and route_pediatric
            and top_dept != PEDIATRIC_DEPARTMENT_NAME
            and not _text_indicates_active_pregnancy(triage_bundle)
        ):
            top_dept = PEDIATRIC_DEPARTMENT_NAME
            confidence = min(1.0, max(confidence, 0.88))
            base_reason = str(llm_data.get("reason", "") or "").strip()
            if by_age:
                tag = (
                    f"توجيه ل{PEDIATRIC_DEPARTMENT_NAME} لأن العمر المذكور ضمن نطاق سن الطفولة."
                )
            else:
                tag = (
                    f"توجيه ل{PEDIATRIC_DEPARTMENT_NAME} لأن الوصف يدل أن المريض طفلاً أو رضيعًا "
                    f"(دون اشتراط ذكر العمر بالأرقام)."
                )
            llm_data["reason"] = f"{tag} (تصنيف مبدئي: {base_reason})" if base_reason else tag
            scores = dict(llm_data.get("scores") or {})
            scores[PEDIATRIC_DEPARTMENT_NAME] = max(
                float(scores.get(PEDIATRIC_DEPARTMENT_NAME, 0.0)), 0.95
            )
            llm_data["scores"] = scores

        # ── Stability Check ──
        last_top = session.last_top_department
        counter = session.stability_counter or 0

        if top_dept == last_top and confidence >= self.CONFIDENCE_THRESHOLD:
            counter += 1
        else:
            counter = 1

        session.last_top_department = top_dept
        session.stability_counter = counter
        session.department_confidence = confidence

        stability_stop = (
            counter >= self.STABILITY_REQUIRED
            and memory.question_count >= self.MIN_USER_MESSAGES_BEFORE_DEPARTMENT_STOP
        )
        max_questions_stop = memory.question_count >= self.MAX_QUESTIONS
        should_stop = stability_stop or max_questions_stop
        if should_stop:
            session.stop_signal = True

        return DepartmentResult(
            top_department=top_dept,
            confidence=confidence,
            scores=llm_data.get("scores", {}),
            reason=llm_data.get("reason", ""),
            needs_more_info=not should_stop,
            stop_asking=should_stop,
        )

    def _parse(self, text: str, valid_names: List[str]) -> dict:
        data = _parse_json(text)
        if data.get("top_department") not in valid_names:
            for name in valid_names:
                if name in str(data.get("top_department", "")):
                    data["top_department"] = name
                    break
            else:
                data.setdefault("top_department", self.FALLBACK_DEPT)
        return data


# ═══════════════════════════════════════════════════════════════
#  5. Scheduling Agent — وكيل الحجز
# ═══════════════════════════════════════════════════════════════

class SchedulingAgent:
    """
    يُفعَّل بعد تثبيت قرار القسم النهائي.
    - يجلب أول 5 مواعيد متاحة بتواريخ متنوعة.
    - يدعم Pagination لعرض مواعيد إضافية.
    - يحجز الموعد المختار ويحدّث حالته في DB.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_available_appointments(
        self,
        department: models.Department,
        limit: int = 5,
        offset: int = 0,
    ) -> List[models.Appointment]:
        return (
            self.db.query(models.Appointment)
            .filter(
                models.Appointment.department_id == department.id,
                models.Appointment.status == models.AppointmentStatus.available,
            )
            .order_by(models.Appointment.start_time.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def book_appointment(
        self, appointment_id: int, user: models.User
    ) -> models.Appointment:
        appt = (
            self.db.query(models.Appointment)
            .filter(models.Appointment.id == appointment_id)
            .with_for_update()
            .first()
        )
        if appt is None or appt.status != models.AppointmentStatus.available:
            raise ValueError("الموعد غير متاح للحجز")
        appt.status = models.AppointmentStatus.booked
        appt.patient_id = user.id
        self.db.commit()
        self.db.refresh(appt)
        return appt


# ═══════════════════════════════════════════════════════════════
#  Reminder Agent — مستقل تماماً عن نظام الـ Multi-Agent
# ═══════════════════════════════════════════════════════════════

class ReminderAgent:
    """
    وكيل التذكير:
    - يرسل تذكير قبل الموعد بيومين (من خلال وظيفة تُستدعى دورياً مثلاً).
    - إذا ردّ المريض (نعم/لا)، يتم تحديث حالة الموعد.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def mark_attendance(
        self, appointment: models.Appointment, will_attend: bool
    ) -> models.Appointment:
        if not will_attend:
            appointment.status = models.AppointmentStatus.available
            appointment.patient_id = None
        appointment.reminder_sent = True
        self.db.commit()
        self.db.refresh(appointment)
        return appointment


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _parse_json(text: str) -> dict:
    """استخراج كائن JSON من مخرجات LLM (مع معالجة markdown و noise)."""
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}
