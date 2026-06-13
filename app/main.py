from __future__ import annotations

import asyncio
import logging
import random
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import agents, auth, models, schemas
from .database import (
    Base,
    engine,
    get_db,
    SessionLocal,
    create_doctors_view,
    migrate_chat_sessions,
    ensure_evaluation_table,
    ensure_department_decisions_table,
    migrate_evaluation_traces_rubric,
    migrate_evaluation_logic_split,
    format_evaluation_json_columns,
    recompute_conversation_summary_columns,
)
from . import reminder_email
from .llm_clients import get_llm_client
from .emergency_rag import emergency_rag_index
from .rag import rag_index
from . import evaluation_agent as eval_mod

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

app = FastAPI(
    title="نظام فرز المراجعين وحجز المواعيد",
    description="نظام للمستشفيات الحكومية الأردنية مع شات بوت طبي و RAG و Multi-Agent.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _build_rag_indexes_background() -> None:
    """
    بناء فهارس RAG ثقيل؛ يُشغَّل في خيط حتى لا يحجب إقلاع السيرفر (/docs يفتح مباشرة).
    حتى ينتهي البناء قد يرجع الاسترجاع نتائج فارغة مؤقتاً.
    """
    try:
        logger.info("RAG: بدء بناء الفهرس في الخلفية…")
        # build_index يحمّل من كاش القرص إن وُجد وإلا يستدعي load_documents داخلياً
        rag_index.build_index()
        emergency_rag_index.load_documents()
        emergency_rag_index.build_index()
        logger.info("RAG: اكتمل بناء الفهرس في الخلفية.")
    except Exception:
        logger.exception("RAG: فشل بناء الفهرس في الخلفية")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_chat_sessions()
    ensure_evaluation_table()
    ensure_department_decisions_table()
    migrate_evaluation_traces_rubric()
    migrate_evaluation_logic_split()
    format_evaluation_json_columns()
    recompute_conversation_summary_columns()

    threading.Thread(
        target=_build_rag_indexes_background,
        name="rag-index-build",
        daemon=True,
    ).start()

    db = SessionLocal()
    try:
        seed_departments_doctors_appointments(db)
    finally:
        db.close()
    create_doctors_view()


# يطابق القائمة الرسمية agents.DEPARTMENT_NAMES (15 قسمًا)
DOCTOR_NAMES_BY_DEPARTMENT: dict[str, List[str]] = {
    "طب الأعصاب": [
        "د. لينا البزور",
        "د. فراس البلص",
        "د. عثمان العبيدات",
        "د. ميسون العساف",
        "د. طارق أبو سمرة",
    ],
    "الأورام": [
        "د. شادي القواسمة",
        "د. نسمة المجالي",
        "د. حازم العرايضة",
        "د. ريناد الدويري",
        "د. خليل العمايرة",
    ],
    "الأمراض الجلدية": [
        "د. نغم الحسن",
        "د. سعد السناجلة",
        "د. رنا العتيبي",
        "د. يوسف أبو شقرة",
        "د. لمى العبوة",
    ],
    "أمراض الجهاز الهضمي": [
        "د. باسم الرواشدة",
        "د. هناء الفاعوري",
        "د. مراد طشطوش",
        "د. ديما الحتاملة",
        "د. صالح المحاسنة",
    ],
    "أمراض القلب": [
        "د. عصام الطنطوري",
        "د. رهام دغيمات",
        "د. حاتم النعيمات",
        "د. نايف الكراسنة",
        "د. سوسن المعايطة",
    ],
    "طب العظام": [
        "د. فادي العتوم",
        "د. نادية مساعدة",
        "د. ياسر الزعبي",
        "د. رائد المومني",
        "د. نهى أبو دية",
    ],
    "النسائية والتوليد": [
        "د. دينا المومني",
        "د. رامي الشوابكة",
        "د. تغريد العمري",
        "د. رشا العبيدات",
        "د. عادل الامام",
    ],
    "طب العيون": [
        "د. سمر الكراسنة",
        "د. عماد القضاة",
        "د. غادة أبو شقرة",
        "د. معن الرواشدة",
        "د. دانا الجراح",
    ],
    "جراحة المسالك البولية": [
        "د. بدر الجبور",
        "د. سلمى العبداللات",
        "د. زياد العلاونة",
        "د. قيس مرعي",
        "د. عروب السناجلة",
    ],
    "الغدد الصماء": [
        "د. نور الشطناوي",
        "د. ثائر أبو عبيد",
        "د. آلاء الصبيحي",
        "د.ميان العبوة",
        "د. هيا القرعان",
    ],
    "أمراض الصدر": [
        "د. ماجد اللوباني",
        "د. ابتسام الجرادات",
        "د. قاسم أبو الهيجاء",
        "د. فرح الدباس",
        "د. أمجد العتيبي",
    ],
    "طب الأطفال": [
        "د. سامر الجراح",
        "د. ميساء الحديدي",
        "د. وليد الروسان",
        "د. همام العلاونة",
        "د. سهيل الحوامدة",
    ],
    "الأنف والأذن والحنجرة": [
        "د. وائل البطاينة",
        "د. رنا سهاونة",
        "د. كريم الدويري",
        "د. مها العزام",
        "د. خالد الربيع",
    ],
    "طب الأسنان": [
        "د. روان التميمي",
        "د. مؤيد الخصاونة",
        "د. سارة البطاينة",
        "د. أيهم الطهراوي",
        "د. يعقوب القبلان",
    ],
    "الطب النفسي": [
        "د. أحمد السعدي",
        "د. محمد السيد",
        "د. عمر العبابنة",
        "د. ليلى جرادات",
        "د. سارة السناجلة",
    ],
}


def _update_doctor_names_per_department(db: Session) -> None:
    """تصحيح أسماء الأطباء ليكون لكل قسم أسماء مختلفة، وحذف الزائدين من الدمج."""
    departments = db.query(models.Department).all()
    for dept in departments:
        names = DOCTOR_NAMES_BY_DEPARTMENT.get(dept.name)
        if not names:
            continue
        doctors = (
            db.query(models.Doctor)
            .filter(models.Doctor.department_id == dept.id)
            .order_by(models.Doctor.id)
            .all()
        )
        for i, doc in enumerate(doctors):
            if i < len(names):
                doc.full_name = names[i]
            else:
                db.query(models.Appointment).filter(
                    models.Appointment.doctor_id == doc.id
                ).delete()
                db.delete(doc)
    db.commit()


# ترحيل أسماء قديمة → أحد الأقسام الرسمية الـ15 (agents.DEPARTMENT_NAMES)
_OLD_TO_NEW_DEPT: dict[str, str] = {
    "العظام": "طب العظام",
    "جراحة العظام": "طب العظام",
    "التوليد وأمراض النساء": "النسائية والتوليد",
    "طب الاطفال": "طب الأطفال",
    "المسالك البولية": "جراحة المسالك البولية",
    "الأعصاب": "طب الأعصاب",
    "ألاعصاب": "طب الأعصاب",
    "طب الفم": "طب الأسنان",
    "الطب الباطني": "أمراض الجهاز الهضمي",
    "جلدية": "الأمراض الجلدية",
    "الطب العام": "أمراض الجهاز الهضمي",
    "التخدير": "أمراض الصدر",
    "الجراحة العامة": "أمراض الجهاز الهضمي",
    "الحساسية والمناعة": "الأمراض الجلدية",
    "جراحة الأطفال": "طب الأطفال",
    "جراحة الأوعية الدموية": "أمراض القلب",
    "جراحة الأعصاب": "طب الأعصاب",
    "جراحة الجهاز الهضمي": "أمراض الجهاز الهضمي",
    "جراحة الصدر": "أمراض الصدر",
    "جراحة الوجه والفكين": "طب الأسنان",
    "طب حديثي الولادة": "طب الأطفال",
    "أمراض الكلى": "جراحة المسالك البولية",
    "جراحة التجميل": "الأمراض الجلدية",
}


def _migrate_departments(db: Session) -> None:
    """
    ترحيل الأقسام القديمة إلى التسمية الجديدة وإضافة الأقسام المفقودة.
    - إعادة تسمية مباشرة لأقسام لها مكافئ واحد-لواحد.
    - دمج أقسام متعددة إلى قسم واحد (أطباء + مواعيد تُنقل).
    - إضافة أقسام جديدة تماماً مع أطبائها ومواعيدهم.
    """
    existing: dict[str, models.Department] = {
        d.name: d for d in db.query(models.Department).all()
    }
    if not existing:
        return

    target_names = set(agents.DEPARTMENT_NAMES)
    changed = False

    for old_name, new_name in _OLD_TO_NEW_DEPT.items():
        old_dept = existing.get(old_name)
        if old_dept is None:
            continue

        new_dept = existing.get(new_name)
        if new_dept is None:
            old_dept.name = new_name
            existing[new_name] = old_dept
            del existing[old_name]
            logger.info("DB migrate: renamed '%s' → '%s'", old_name, new_name)
        else:
            db.query(models.Doctor).filter(
                models.Doctor.department_id == old_dept.id
            ).update({models.Doctor.department_id: new_dept.id})
            db.query(models.Appointment).filter(
                models.Appointment.department_id == old_dept.id
            ).update({models.Appointment.department_id: new_dept.id})
            db.delete(old_dept)
            del existing[old_name]
            logger.info("DB migrate: merged '%s' into '%s'", old_name, new_name)
        changed = True

    emergency_dept = existing.get("الطوارئ")
    if emergency_dept is not None:
        db.query(models.Appointment).filter(
            models.Appointment.department_id == emergency_dept.id
        ).delete()
        db.query(models.Doctor).filter(
            models.Doctor.department_id == emergency_dept.id
        ).delete()
        db.delete(emergency_dept)
        del existing["الطوارئ"]
        logger.info("DB migrate: removed 'الطوارئ' department (no bookable appointments)")
        changed = True

    for name in agents.DEPARTMENT_NAMES:
        if name not in existing:
            dept = models.Department(name=name)
            db.add(dept)
            db.flush()
            existing[name] = dept
            doc_names = DOCTOR_NAMES_BY_DEPARTMENT.get(name, ["د. طبيب " + name[:10]])
            for full_name in doc_names:
                db.add(models.Doctor(full_name=full_name, department_id=dept.id))
            logger.info("DB migrate: added new department '%s' with %d doctors", name, len(doc_names))
            changed = True

    # دمج أي أقسام ما زالت خارج القائمة الرسمية إلى القسم الافتراضي
    official = set(agents.DEPARTMENT_NAMES)
    db.flush()
    fallback = (
        db.query(models.Department)
        .filter(models.Department.name == agents.FALLBACK_DEPT)
        .first()
    )
    if fallback is not None:
        for row in list(db.query(models.Department).all()):
            if row.name in official:
                continue
            orphan_name = row.name
            db.query(models.Doctor).filter(models.Doctor.department_id == row.id).update(
                {models.Doctor.department_id: fallback.id}
            )
            db.query(models.Appointment).filter(
                models.Appointment.department_id == row.id
            ).update({models.Appointment.department_id: fallback.id})
            db.delete(row)
            logger.info(
                "DB migrate: merged orphan department '%s' into '%s'",
                orphan_name,
                agents.FALLBACK_DEPT,
            )
            changed = True

    if changed:
        db.commit()
        logger.info("DB migrate: department migration complete.")


def _ensure_appointments_for_new_doctors(db: Session) -> None:
    """إنشاء مواعيد للأطباء الجدد (من أقسام مضافة حديثاً) الذين ليس لديهم أي مواعيد."""
    from sqlalchemy import func
    doctors_with_counts = (
        db.query(models.Doctor, func.count(models.Appointment.id))
        .outerjoin(models.Appointment, models.Appointment.doctor_id == models.Doctor.id)
        .group_by(models.Doctor.id)
        .all()
    )
    new_doctors = [doc for doc, cnt in doctors_with_counts if cnt == 0]
    if not new_doctors:
        return

    start_date = datetime(2027, 1, 1)
    end_date = datetime(2027, 3, 31)
    day_count = (end_date - start_date).days + 1
    added = 0
    for i in range(day_count):
        single_day = start_date + timedelta(days=i)
        for doctor in new_doctors:
            for hour in (9, 12, 15):
                appt_time = single_day.replace(hour=hour, minute=0, second=0, microsecond=0)
                db.add(models.Appointment(
                    department_id=doctor.department_id,
                    doctor_id=doctor.id,
                    start_time=appt_time,
                    status=models.AppointmentStatus.available,
                ))
                added += 1
    if added:
        db.commit()
        logger.info("DB: created %d appointments for %d new doctors.", added, len(new_doctors))


def seed_departments_doctors_appointments(db: Session) -> None:
    """
    التأكد من وجود أقسام وأطباء ومواعيد أولية في قاعدة البيانات.
    - المواعيد الأساسية: أول 3 أشهر من 2027 (كانون الثاني–آذار).
    - يُستدعى عند كل تشغيل: إضافة مواعيد آذار 2026 من 17 فما فوق (لاختبار التذكيرات).
    """
    has_appointments = db.query(models.Appointment).count() > 0

    _migrate_departments(db)

    departments: List[models.Department] = db.query(models.Department).all()
    if not departments:
        for name in agents.DEPARTMENT_NAMES:
            dept = models.Department(name=name)
            db.add(dept)
            departments.append(dept)
        db.flush()

    doctors = db.query(models.Doctor).all()
    if not doctors:
        for dept in departments:
            names = DOCTOR_NAMES_BY_DEPARTMENT.get(dept.name)
            if not names:
                names = ["د. طبيب " + dept.name[:10]]
            for full_name in names:
                doc = models.Doctor(full_name=full_name, department_id=dept.id)
                db.add(doc)
        db.flush()
        doctors = db.query(models.Doctor).all()
    else:
        _update_doctor_names_per_department(db)

    if not has_appointments:
        ensure_march_2026_appointments(db)
        start_date = datetime(2027, 1, 1)
        end_date = datetime(2027, 3, 31)
        day_count = (end_date - start_date).days + 1
        batch = 0
        for i in range(day_count):
            single_day = start_date + timedelta(days=i)
            for doctor in doctors:
                for hour in (9, 12, 15):
                    appt_time = single_day.replace(
                        hour=hour, minute=0, second=0, microsecond=0
                    )
                    appt = models.Appointment(
                        department_id=doctor.department_id,
                        doctor_id=doctor.id,
                        start_time=appt_time,
                        status=models.AppointmentStatus.available,
                    )
                    db.add(appt)
            batch += 1
            if batch % 30 == 0:
                db.commit()
        db.commit()

    _ensure_appointments_for_new_doctors(db)

    if has_appointments:
        ensure_march_2026_appointments(db)


def ensure_march_2026_appointments(db: Session) -> None:
    """
    إضافة مواعيد شهر آذار 2026 من يوم 17 حتى نهاية الشهر (لاختبار التذكير قبل الموعد بيومين).
    لا يُنشئ تكراراً إذا الموعد موجود مسبقاً.
    """
    from datetime import datetime as dt

    doctors = db.query(models.Doctor).all()
    if not doctors:
        return
    start = dt(2026, 3, 17)
    end = dt(2026, 3, 31)
    days = (end - start).days + 1
    added = 0
    for i in range(days):
        single_day = start + timedelta(days=i)
        for doctor in doctors:
            for hour in (9, 12, 15):
                appt_time = single_day.replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )
                exists = (
                    db.query(models.Appointment)
                    .filter(
                        models.Appointment.doctor_id == doctor.id,
                        models.Appointment.start_time == appt_time,
                    )
                    .first()
                )
                if not exists:
                    appt = models.Appointment(
                        department_id=doctor.department_id,
                        doctor_id=doctor.id,
                        start_time=appt_time,
                        status=models.AppointmentStatus.available,
                    )
                    db.add(appt)
                    added += 1
    if added:
        db.commit()


# ─── Helper functions ─────────────────────────────────────────

def _save_assistant_msg(db: Session, session_id: int, content: str) -> models.ChatMessage:
    msg = models.ChatMessage(
        session_id=session_id,
        role=models.ChatMessageRole.assistant,
        content=content,
    )
    db.add(msg)
    db.commit()
    return msg


# ═══════════════════════════════════════════════════════════════
#  Evaluation Agent — observer hook (fire-and-forget)
# ═══════════════════════════════════════════════════════════════

def _record_department_decision(
    *,
    session: models.ChatSession,
    turn_index: int,
    department_result: "agents.DepartmentResult",
) -> None:
    """
    حفظ قرار Department Agent لكل turn في جدول مراقبة مستقل.
    يستخدم لاحقاً في تقييم ثبات القرار عبر كامل المحادثة.
    """
    try:
        eval_mod.persist_department_decision(
            session_id=session.id,
            turn_index=turn_index,
            top_department=department_result.top_department,
            confidence=department_result.confidence,
            scores=department_result.scores,
            reason=department_result.reason,
        )
    except Exception:
        logger.exception("Department decision observer failed — system unaffected")


def _get_department_decision_history(db: Session, session_id: int) -> list[dict]:
    rows = (
        db.query(models.EvaluationDepartmentDecision)
        .filter(models.EvaluationDepartmentDecision.session_id == session_id)
        .order_by(
            models.EvaluationDepartmentDecision.turn_index.asc(),
            models.EvaluationDepartmentDecision.id.asc(),
        )
        .all()
    )
    history: list[dict] = []
    import json as _json

    for row in rows:
        try:
            scores = _json.loads(row.scores_json or "{}")
        except Exception:
            scores = {}
        history.append(
            {
                "turn_index": row.turn_index,
                "top_department": row.top_department,
                "confidence": row.confidence,
                "scores": scores,
                "reason": row.reason,
            }
        )
    return history


def _dispatch_turn_evaluation(
    *,
    session: models.ChatSession,
    user_message: str,
    history: list,
    memory_before: dict,
    memory_after: "agents.SharedMemory",
    asking_output: str,
    emergency_result: "agents.EmergencyResult",
    department_result: "agents.DepartmentResult",
) -> None:
    """
    تقييم لكل turn فقط:
    - Asking rubric 1..5
    - Structured rubric 1..2
    """
    try:
        snapshot = eval_mod.build_turn_snapshot(
            session_id=session.id,
            turn_index=memory_after.question_count,
            user_message=user_message,
            chat_history=history,
            memory_before=memory_before,
            memory_after=memory_after.to_dict(),
            asking_output=asking_output or "",
            emergency_output={
                "is_emergency": emergency_result.is_emergency,
                "reason": emergency_result.reason,
                "alert_level": emergency_result.alert_level,
            },
            department_output={
                "top_department": department_result.top_department,
                "confidence": department_result.confidence,
                "scores": department_result.scores,
                "reason": department_result.reason,
                "needs_more_info": department_result.needs_more_info,
                "stop_asking": department_result.stop_asking,
            },
            session_state={
                "last_top_department": session.last_top_department,
                "stability_counter": session.stability_counter,
                "department_confidence": session.department_confidence,
                "question_count": memory_after.question_count,
                "is_emergency": session.is_emergency,
            },
        )
        eval_mod.schedule_evaluation(snapshot)
    except Exception:
        logger.exception("Turn evaluation dispatch failed — system unaffected")


def _dispatch_conversation_evaluation(
    *,
    db: Session,
    session: models.ChatSession,
    user_message: str,
    history: list,
    memory_after: "agents.SharedMemory",
    asking_output: str,
    emergency_result: "agents.EmergencyResult",
    department_result: "agents.DepartmentResult",
) -> None:
    """
    تقييم مرة واحدة للمحادثة كاملة:
    - Asking rubric 6 فقط
    - Department كله
    - Emergency كله
    """
    try:
        decision_history = _get_department_decision_history(db, session.id)
        snapshot = eval_mod.build_conversation_snapshot(
            session_id=session.id,
            turn_index=memory_after.question_count,
            user_message=user_message,
            chat_history=history,
            final_memory=memory_after.to_dict(),
            asking_output=asking_output or "",
            emergency_output={
                "is_emergency": emergency_result.is_emergency,
                "reason": emergency_result.reason,
                "alert_level": emergency_result.alert_level,
            },
            department_output={
                "top_department": department_result.top_department,
                "confidence": department_result.confidence,
                "scores": department_result.scores,
                "reason": department_result.reason,
                "needs_more_info": department_result.needs_more_info,
                "stop_asking": department_result.stop_asking,
            },
            department_decision_history=decision_history,
            session_state={
                "last_top_department": session.last_top_department,
                "stability_counter": session.stability_counter,
                "department_confidence": session.department_confidence,
                "question_count": memory_after.question_count,
                "is_emergency": session.is_emergency,
            },
        )
        eval_mod.schedule_evaluation(snapshot)
    except Exception:
        logger.exception("Conversation evaluation dispatch failed — system unaffected")


import re as _re

_ARABIC_RE = _re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

def _is_valid_arabic_input(text: str) -> bool:
    """فحص أساسي: هل الرسالة تحتوي على نص عربي كافٍ؟"""
    text = text.strip()
    if not text:
        return False
    if len(text) <= 3:
        return True
    arabic_chars = len(_ARABIC_RE.findall(text))
    letter_chars = sum(1 for c in text if c.isalpha())
    if letter_chars == 0:
        return True
    return arabic_chars / letter_chars >= 0.3

_INVALID_INPUT_MSGS = [
    "ما قدرت أفهم رسالتك — ممكن تكتبلي بالعربي؟",
    "يبدو إنه في مشكلة بالكتابة، ممكن تعيد بالعربي؟",
    "ما فهمت عليك، جرّب تكتب بالعربي شو اللي حاسس فيه.",
    "الرسالة مش واضحة — اكتبلي بالعربي وأنا بساعدك.",
    "ما قدرت أقرأ رسالتك، حاول تكتب بالعربي لو سمحت.",
    "يا ريت تكتبلي بالعربي عشان أقدر أفهم حالتك.",
    "شكلها الرسالة مش بالعربي — ممكن تعيد كتابتها؟",
]

def _invalid_input_msg() -> str:
    return random.choice(_INVALID_INPUT_MSGS)


async def _handle_department_decision(
    db: Session,
    session: models.ChatSession,
    dept_result: agents.DepartmentResult,
    user_message: str,
    model_name: str,
) -> schemas.ChatTurnOut:
    """عند تثبيت قرار القسم → عرض المواعيد المتاحة."""
    department = (
        db.query(models.Department)
        .filter(models.Department.name == dept_result.top_department)
        .first()
    )
    if not department:
        department = (
            db.query(models.Department)
            .filter(models.Department.name == agents.FALLBACK_DEPT)
            .first()
        )

    if not department:
        fallback_text = "ممكن توضحلي أكتر عن الأعراض اللي حاسس فيها؟"
        _save_assistant_msg(db, session.id, fallback_text)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=user_message,
            assistant_message=fallback_text,
            is_emergency=False,
            chosen_department=None,
            offered_appointments=None,
        )

    session.chosen_department_id = department.id
    session.appointments_shown_offset = 5
    db.commit()

    scheduling_agent = agents.SchedulingAgent(db)
    available_appts = scheduling_agent.get_available_appointments(department)

    is_fallback = dept_result.confidence < agents.DepartmentAgent.CONFIDENCE_THRESHOLD
    if is_fallback:
        intro = f"بناء على معلوماتك، سنوجهك لقسم {department.name} ليقيّم حالتك."
    else:
        intro = f"بناءً على الأعراض، القسم الأنسب لحالتك هو: {department.name}."

    if not available_appts:
        text = f"{intro}\nلكن للأسف حالياً ما في مواعيد متاحة، يرجى المحاولة لاحقاً."
        _save_assistant_msg(db, session.id, text)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=user_message,
            assistant_message=text,
            is_emergency=False,
            chosen_department=schemas.DepartmentOut.model_validate(department),
            offered_appointments=[],
        )

    lines = [
        intro,
        "هاي مجموعة مواعيد متاحة، اختر رقم الموعد المناسب إلك:",
    ]
    for idx, appt in enumerate(available_appts, start=1):
        dt = appt.start_time
        lines.append(
            f"{idx}) بتاريخ {dt.date()} الساعة {dt.strftime('%H:%M')} مع الطبيب {appt.doctor.full_name}"
        )
    lines.append("اكتب رقم الموعد اللي بناسبك، أو اكتب «المزيد» لعرض مواعيد إضافية.")
    reply_text = "\n".join(lines)

    _save_assistant_msg(db, session.id, reply_text)

    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=user_message,
        assistant_message=reply_text,
        is_emergency=False,
        chosen_department=schemas.DepartmentOut.model_validate(department),
        offered_appointments=[
            schemas.AppointmentOut.model_validate(appt) for appt in available_appts
        ],
    )


def _handle_scheduling_phase(
    db: Session,
    session: models.ChatSession,
    user_message: str,
) -> schemas.ChatTurnOut:
    """عند وجود قسم محدد مسبقاً — عرض مواعيد إضافية."""
    department = db.query(models.Department).get(session.chosen_department_id)
    if department is None:
        reply = "حدث خطأ، يرجى المحاولة مرة أخرى."
        _save_assistant_msg(db, session.id, reply)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=user_message,
            assistant_message=reply,
            is_emergency=False,
            chosen_department=None,
            offered_appointments=None,
        )

    scheduling_agent = agents.SchedulingAgent(db)
    offset = session.appointments_shown_offset or 0
    next_appts = scheduling_agent.get_available_appointments(department, limit=5, offset=offset)

    if next_appts:
        session.appointments_shown_offset = offset + len(next_appts)
        db.commit()
        lines = ["هاي مجموعة مواعيد إضافية، اختر رقم الموعد المناسب إلك:"]
        for idx, appt in enumerate(next_appts, start=1):
            dt = appt.start_time
            lines.append(
                f"{idx}) بتاريخ {dt.date()} الساعة {dt.strftime('%H:%M')} مع الطبيب {appt.doctor.full_name}"
            )
        lines.append("اكتب رقم الموعد اللي بناسبك من القائمة أعلاه.")
        reply_text = "\n".join(lines)
        _save_assistant_msg(db, session.id, reply_text)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=user_message,
            assistant_message=reply_text,
            is_emergency=False,
            chosen_department=schemas.DepartmentOut.model_validate(department),
            offered_appointments=[
                schemas.AppointmentOut.model_validate(a) for a in next_appts
            ],
        )

    reply_text = (
        "للأسف ما في مواعيد إضافية متاحة حالياً. "
        "اختر من المواعيد اللي عرضتها عليك سابقاً، أو جرّب لاحقاً."
    )
    _save_assistant_msg(db, session.id, reply_text)
    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=user_message,
        assistant_message=reply_text,
        is_emergency=False,
        chosen_department=schemas.DepartmentOut.model_validate(department),
        offered_appointments=None,
    )


def _build_emergency_response(
    db: Session,
    session: models.ChatSession,
    user_message: str,
) -> schemas.ChatTurnOut:
    session.is_emergency = True
    session.is_active = False
    db.commit()
    emergency_message = random.choice(agents.EMERGENCY_MESSAGES)
    _save_assistant_msg(db, session.id, emergency_message)
    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=user_message,
        assistant_message=emergency_message,
        is_emergency=True,
        chosen_department=None,
        offered_appointments=None,
    )


# ─── Static pages ────────────────────────────────────────────

def _serve_html(filename: str) -> HTMLResponse:
    html_path = FRONTEND_DIR / filename
    if not html_path.exists():
        return HTMLResponse("<h1>الواجهة غير جاهزة بعد</h1>", status_code=200)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def serve_frontend() -> HTMLResponse:
    return _serve_html("index.html")


@app.get("/login", response_class=HTMLResponse)
def serve_login() -> HTMLResponse:
    return _serve_html("login.html")


@app.get("/register", response_class=HTMLResponse)
def serve_register() -> HTMLResponse:
    return _serve_html("register.html")


@app.get("/chat", response_class=HTMLResponse)
def serve_chat() -> HTMLResponse:
    return _serve_html("chat.html")


# ─── Auth ─────────────────────────────────────────────────────

@app.post("/auth/register", response_model=schemas.RegisterResponse)
def register(
    data: schemas.UserRegisterRequest, db: Session = Depends(get_db)
) -> schemas.RegisterResponse:
    user = auth.register_user(data, db)
    today = date.today()
    age = today.year - data.dob.year - (
        (today.month, today.day) < (data.dob.month, data.dob.day)
    )
    warning = None
    if age < 18:
        warning = "العمر أقل من 18 سنة. يفضّل أن يتم التسجيل عبر ولي أمر المريض."
    return schemas.RegisterResponse(
        user=schemas.UserInfo.model_validate(user),
        warning=warning,
    )


@app.post("/auth/login", response_model=schemas.SessionTokenResponse)
def login(
    data: schemas.UserLoginRequest, db: Session = Depends(get_db)
) -> schemas.SessionTokenResponse:
    user, token = auth.login_user(data, db)
    return schemas.SessionTokenResponse(
        token=token.token,
        user=schemas.UserInfo.model_validate(user),
    )


def get_current_user_from_header(
    db: Session = Depends(get_db),
    token: str | None = Header(None, alias="token"),
) -> models.User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="مطلوب رمز الجلسة",
        )
    return auth.get_current_user(token, db)


# ═══════════════════════════════════════════════════════════════
#  Chat — Multi-Agent Orchestration
# ═══════════════════════════════════════════════════════════════

@app.post("/chat/start", response_model=schemas.ChatTurnOut)
async def start_chat(
    data: schemas.ChatMessageIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_from_header),
) -> schemas.ChatTurnOut:

    session = models.ChatSession(
        user_id=user.id,
        is_active=True,
        shared_memory="{}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    msg_user = models.ChatMessage(
        session_id=session.id,
        role=models.ChatMessageRole.user,
        content=data.message,
    )
    db.add(msg_user)
    db.commit()

    # ── فحص: هل الرسالة عربية ومفهومة؟ ──
    if not _is_valid_arabic_input(data.message):
        reply = _invalid_input_msg()
        _save_assistant_msg(db, session.id, reply)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=data.message,
            assistant_message=reply,
            is_emergency=False,
            chosen_department=None,
            offered_appointments=None,
        )

    # ── Step 1 (متوازي): Summarizer + Asking Agent بنفس الوقت ──
    history = [msg_user]
    current_memory = agents.SharedMemory(conversation_id=str(session.id))
    memory_before_snapshot = current_memory.to_dict()
    summarizer = agents.StructuredInformationAgent(data.model_name)
    asking = agents.AskingAgent(data.model_name)

    updated_memory, welcome = await asyncio.gather(
        summarizer.update_memory(history, current_memory),
        asking.generate_welcome(data.message),
    )

    session.shared_memory = updated_memory.to_json()
    db.commit()

    # ── Step 2 (متوازي): Emergency Agent + Department Agent بنفس الوقت ──
    emergency_agent = agents.EmergencyAgent(data.model_name)
    dept_agent = agents.DepartmentAgent(db, data.model_name)
    emergency_result, dept_result = await asyncio.gather(
        emergency_agent.check(data.message, updated_memory),
        dept_agent.evaluate(updated_memory, session),
    )
    db.commit()

    # ── Step 3 (observer): حفظ قرار القسم + تقييم turn ──
    _record_department_decision(
        session=session,
        turn_index=updated_memory.question_count,
        department_result=dept_result,
    )
    _dispatch_turn_evaluation(
        session=session,
        user_message=data.message,
        history=history,
        memory_before=memory_before_snapshot,
        memory_after=updated_memory,
        asking_output=welcome,
        emergency_result=emergency_result,
        department_result=dept_result,
    )

    if emergency_result.is_emergency:
        _dispatch_conversation_evaluation(
            db=db,
            session=session,
            user_message=data.message,
            history=history,
            memory_after=updated_memory,
            asking_output=welcome,
            emergency_result=emergency_result,
            department_result=dept_result,
        )
        return _build_emergency_response(db, session, data.message)

    if dept_result.stop_asking:
        _dispatch_conversation_evaluation(
            db=db,
            session=session,
            user_message=data.message,
            history=history,
            memory_after=updated_memory,
            asking_output=welcome,
            emergency_result=emergency_result,
            department_result=dept_result,
        )
        return await _handle_department_decision(
            db, session, dept_result, data.message, data.model_name
        )

    _save_assistant_msg(db, session.id, welcome)

    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=data.message,
        assistant_message=welcome,
        is_emergency=False,
        chosen_department=None,
        offered_appointments=None,
    )


@app.get("/chat/evaluation/{session_id}")
def get_evaluation_trace(
    session_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_from_header),
) -> dict:
    """
    قراءة سجل Evaluation Agent لجلسة معينة (read-only).
    مفصول تماماً عن القرار الطبي — هذا للمراقبة/التحليل فقط.
    """
    import json as _json

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id, models.ChatSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    traces = (
        db.query(models.EvaluationTrace)
        .filter(models.EvaluationTrace.session_id == session_id)
        .order_by(
            models.EvaluationTrace.trace_scope.asc(),
            models.EvaluationTrace.turn_index.asc(),
            models.EvaluationTrace.id.asc(),
        )
        .all()
    )
    decision_rows = (
        db.query(models.EvaluationDepartmentDecision)
        .filter(models.EvaluationDepartmentDecision.session_id == session_id)
        .order_by(
            models.EvaluationDepartmentDecision.turn_index.asc(),
            models.EvaluationDepartmentDecision.id.asc(),
        )
        .all()
    )

    turn_items = []
    conversation_items = []
    for t in traces:
        try:
            scores = _json.loads(t.scores_json or "{}")
        except Exception:
            scores = {}
        item = {
            "id": t.id,
            "trace_scope": t.trace_scope,
            "turn_index": t.turn_index,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "model_used": t.model_used,
            "totals": {
                "asking": {"score": t.asking_total, "max": t.asking_max},
                "department": {"score": t.department_total, "max": t.department_max},
                "structured": {"score": t.structured_total, "max": t.structured_max},
                "emergency": {"score": t.emergency_total, "max": t.emergency_max},
            },
            "conversation_summary": {
                "asking_ratio": t.asking_ratio,
                "department_ratio": t.department_ratio,
                "structured_ratio": t.structured_ratio,
                "emergency_ratio": t.emergency_ratio,
                "system_conversation_score": t.system_conversation_score,
            },
            "dimensions": scores.get("dimensions", {}),
            "error": t.error,
        }
        if t.trace_scope == "conversation":
            conversation_items.append(item)
        else:
            turn_items.append(item)

    department_decision_history = []
    for row in decision_rows:
        try:
            scores = _json.loads(row.scores_json or "{}")
        except Exception:
            scores = {}
        department_decision_history.append(
            {
                "turn_index": row.turn_index,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "top_department": row.top_department,
                "confidence": row.confidence,
                "scores": scores,
                "reason": row.reason,
            }
        )

    return {
        "session_id": session_id,
        "model_used": eval_mod.EvaluationAgent.MODEL_NAME,
        "turn_traces": turn_items,
        "conversation_traces": conversation_items,
        "department_decision_history": department_decision_history,
        "counts": {
            "turn_traces": len(turn_items),
            "conversation_traces": len(conversation_items),
            "department_decision_history": len(department_decision_history),
        },
    }


@app.get("/chat/session-info/{session_id}")
def get_session_info(
    session_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_from_header),
) -> dict:
    """عرض حالة الجلسة والذاكرة المشتركة — للمراقبة والـ debugging."""
    import json as _json

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id, models.ChatSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    try:
        memory = _json.loads(session.shared_memory or "{}")
    except Exception:
        memory = {}

    dept_name = None
    if session.chosen_department_id:
        dept = db.query(models.Department).get(session.chosen_department_id)
        dept_name = dept.name if dept else None

    return {
        "session_id": session.id,
        "is_active": session.is_active,
        "is_emergency": session.is_emergency,
        "shared_memory": memory,
        "stop_signal": session.stop_signal,
        "stability_counter": session.stability_counter,
        "last_top_department": session.last_top_department,
        "department_confidence": session.department_confidence,
        "chosen_department": dept_name,
        "appointments_shown_offset": session.appointments_shown_offset,
    }


@app.post("/chat/continue", response_model=schemas.ChatTurnOut)
async def continue_chat(
    session_id: int,
    data: schemas.ChatMessageIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_from_header),
) -> schemas.ChatTurnOut:

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id, models.ChatSession.user_id == user.id)
        .first()
    )
    if session is None or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="جلسة الشات غير متاحة",
        )

    user_msg = models.ChatMessage(
        session_id=session.id,
        role=models.ChatMessageRole.user,
        content=data.message,
    )
    db.add(user_msg)
    db.commit()

    # إذا القسم محدد مسبقاً → مرحلة حجز المواعيد (Scheduling Phase)
    if session.chosen_department_id is not None:
        return _handle_scheduling_phase(db, session, data.message)

    # ── فحص: هل الرسالة عربية ومفهومة؟ ──
    if not _is_valid_arabic_input(data.message):
        reply = _invalid_input_msg()
        _save_assistant_msg(db, session.id, reply)
        return schemas.ChatTurnOut(
            session_id=session.id,
            user_message=data.message,
            assistant_message=reply,
            is_emergency=False,
            chosen_department=None,
            offered_appointments=None,
        )

    # ═══ Multi-Agent Orchestration (متوازي) ═══

    # ── Step 1 (متوازي): Summarizer + Asking Agent بنفس الوقت ──
    history = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session.id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    current_memory = agents.SharedMemory.from_json(session.shared_memory or "{}")
    memory_before_snapshot = current_memory.to_dict()
    summarizer = agents.StructuredInformationAgent(data.model_name)
    asking = agents.AskingAgent(data.model_name)

    updated_memory, question = await asyncio.gather(
        summarizer.update_memory(history, current_memory),
        asking.generate_question(history, stop_signal=False),
    )

    session.shared_memory = updated_memory.to_json()
    db.commit()

    # ── Step 2 (متوازي): Emergency Agent + Department Agent بنفس الوقت ──
    emergency_agent = agents.EmergencyAgent(data.model_name)
    dept_agent = agents.DepartmentAgent(db, data.model_name)
    emergency_result, dept_result = await asyncio.gather(
        emergency_agent.check(data.message, updated_memory),
        dept_agent.evaluate(updated_memory, session),
    )
    db.commit()

    # ── Step 3 (observer): حفظ قرار القسم + تقييم turn ──
    _record_department_decision(
        session=session,
        turn_index=updated_memory.question_count,
        department_result=dept_result,
    )
    _dispatch_turn_evaluation(
        session=session,
        user_message=data.message,
        history=history,
        memory_before=memory_before_snapshot,
        memory_after=updated_memory,
        asking_output=question,
        emergency_result=emergency_result,
        department_result=dept_result,
    )

    if emergency_result.is_emergency:
        _dispatch_conversation_evaluation(
            db=db,
            session=session,
            user_message=data.message,
            history=history,
            memory_after=updated_memory,
            asking_output=question,
            emergency_result=emergency_result,
            department_result=dept_result,
        )
        return _build_emergency_response(db, session, data.message)

    if dept_result.stop_asking:
        _dispatch_conversation_evaluation(
            db=db,
            session=session,
            user_message=data.message,
            history=history,
            memory_after=updated_memory,
            asking_output=question,
            emergency_result=emergency_result,
            department_result=dept_result,
        )
        return await _handle_department_decision(
            db, session, dept_result, data.message, data.model_name
        )

    _save_assistant_msg(db, session.id, question)

    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=data.message,
        assistant_message=question,
        is_emergency=False,
        chosen_department=None,
        offered_appointments=None,
    )


# ─── Booking ─────────────────────────────────────────────────

@app.post("/chat/book", response_model=schemas.ChatTurnOut)
async def book_from_chat(
    session_id: int,
    appointment_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_from_header),
) -> schemas.ChatTurnOut:
    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id, models.ChatSession.user_id == user.id)
        .first()
    )
    if session is None or not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="جلسة الشات غير متاحة",
        )
    if session.chosen_department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لم يتم تحديد القسم بعد",
        )

    chosen_appt = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.id == appointment_id,
            models.Appointment.department_id == session.chosen_department_id,
            models.Appointment.status == models.AppointmentStatus.available,
        )
        .first()
    )
    if chosen_appt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الموعد غير متاح أو غير صحيح",
        )
    scheduling_agent = agents.SchedulingAgent(db)
    try:
        booked = scheduling_agent.book_appointment(chosen_appt.id, user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    session.is_active = False
    db.commit()

    dt = booked.start_time
    summary_lines = [
        "تم حجز موعدك بنجاح، تفاصيل الموعد كالتالي:",
        f"- القسم: {booked.department.name}",
        f"- الطبيب: {booked.doctor.full_name}",
        f"- التاريخ: {dt.date()}",
        f"- الوقت: {dt.strftime('%H:%M')}",
        "",
        "تعليمات للمريض:",
        "- يرجى الحضور قبل 15 دقيقة من موعدك.",
        "- إحضار أي تقارير طبية سابقة أو صور أشعة/تحاليل إن وجدت.",
        "- إحضار بطاقة الهوية (البطاقة الشخصية) والبطاقة التأمينية إن وجدت.",
        "- إحضار قائمة الأدوية الحالية إن وجدت.",
        "",
        "كرت الموعد:",
        f"المريض: {user.full_name}",
        f"القسم: {booked.department.name}",
        f"الطبيب: {booked.doctor.full_name}",
        f"التاريخ: {dt.date()}",
        f"الوقت: {dt.strftime('%H:%M')}",
    ]
    text = "\n".join(summary_lines)

    _save_assistant_msg(db, session.id, text)

    return schemas.ChatTurnOut(
        session_id=session.id,
        user_message=str(appointment_id),
        assistant_message=text,
        is_emergency=False,
        chosen_department=schemas.DepartmentOut.model_validate(booked.department),
        offered_appointments=[
            schemas.AppointmentOut.model_validate(booked),
        ],
    )


# ═══════════════════════════════════════════════════════════════
#  Reminder Endpoints — مستقل عن الـ Multi-Agent
# ═══════════════════════════════════════════════════════════════

@app.get("/reminder/status", response_model=dict)
def reminder_status() -> dict:
    smtp_ok = reminder_email.is_email_configured()
    if smtp_ok:
        msg_ar = (
            "جاهز: إعدادات الإيميل (SMTP) مضبوطة. "
            "عند استدعاء GET أو POST /reminder/send-due رح توصل التذكيرات على الإيميل."
        )
    else:
        msg_ar = (
            "الإيميل غير مضبوط: أضف في ملف .env القيم التالية ثم أعد تشغيل السيرفر: "
            "SMTP_HOST (مثلاً smtp.gmail.com)، SMTP_PORT=587، SMTP_USER، SMTP_PASSWORD. "
            "بعدها استدعِ GET /reminder/status مرة ثانية وتأكد بـ POST /reminder/test-email?to=إيميلك."
        )
    return {
        "ready": smtp_ok,
        "smtp_configured": smtp_ok,
        "message_ar": msg_ar,
        "how_to_send": "يوم التذكير (قبل الموعد بيومين) افتح أو استدعِ GET/POST /reminder/send-due?days_ahead=2 أو شغّل Task Scheduler يطلبه يومياً.",
    }


@app.post("/reminder/test-email", response_model=dict)
def reminder_test_email(to: str) -> dict:
    if not to or "@" not in to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="أضف معامل to بإيميل صحيح، مثلاً: ?to=your@email.com",
        )
    ok, message_ar = reminder_email.send_test_email(to.strip())
    return {"sent": ok, "message_ar": message_ar, "to": to}


@app.get("/reminder/due", response_model=schemas.ReminderDueOut)
def reminder_due(
    days_ahead: int = 2,
    db: Session = Depends(get_db),
) -> schemas.ReminderDueOut:
    due_date = date.today() + timedelta(days=days_ahead)
    start_of_day = datetime.combine(due_date, datetime.min.time())
    end_of_day = datetime.combine(due_date, datetime.max.time().replace(microsecond=0))

    appts = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status == models.AppointmentStatus.booked,
            models.Appointment.reminder_sent == False,
            models.Appointment.start_time >= start_of_day,
            models.Appointment.start_time <= end_of_day,
        )
        .order_by(models.Appointment.start_time.asc())
        .all()
    )
    items: List[schemas.ReminderDueItem] = []
    for appt in appts:
        if appt.patient_id is None:
            continue
        user = db.query(models.User).get(appt.patient_id)
        if not user:
            continue
        items.append(
            schemas.ReminderDueItem(
                appointment=schemas.AppointmentOut.model_validate(appt),
                patient_email=user.email,
                patient_name=user.full_name,
            )
        )
    return schemas.ReminderDueOut(due_date=due_date, appointments=items)


def _do_send_reminder_due(days_ahead: int, db: Session) -> dict:
    due_date = date.today() + timedelta(days=days_ahead)
    start_of_day = datetime.combine(due_date, datetime.min.time())
    end_of_day = datetime.combine(due_date, datetime.max.time().replace(microsecond=0))

    appts = (
        db.query(models.Appointment)
        .filter(
            models.Appointment.status == models.AppointmentStatus.booked,
            models.Appointment.reminder_sent == False,
            models.Appointment.start_time >= start_of_day,
            models.Appointment.start_time <= end_of_day,
        )
        .order_by(models.Appointment.start_time.asc())
        .all()
    )
    sent = 0
    failed = []
    for appt in appts:
        if appt.patient_id is None:
            continue
        user = db.query(models.User).get(appt.patient_id)
        if not user:
            continue
        dt = appt.start_time
        ok = reminder_email.send_reminder_email(
            to_email=user.email,
            patient_name=user.full_name,
            appointment_date=str(dt.date()),
            appointment_time=dt.strftime("%H:%M"),
            department_name=appt.department.name if appt.department else "",
            doctor_name=appt.doctor.full_name if appt.doctor else "",
        )
        appt.reminder_sent = True
        if ok:
            sent += 1
        else:
            failed.append(user.email)
    db.commit()
    return {
        "due_date": str(due_date),
        "total_due": len(appts),
        "emails_sent": sent,
        "emails_failed": failed,
        "smtp_configured": reminder_email.is_email_configured(),
    }


@app.get("/reminder/send-due", response_model=dict)
@app.post("/reminder/send-due", response_model=dict)
def reminder_send_due(
    days_ahead: int = 2,
    db: Session = Depends(get_db),
) -> dict:
    return _do_send_reminder_due(days_ahead, db)


@app.post("/reminder/mark-sent/{appointment_id}", response_model=dict)
def reminder_mark_sent(
    appointment_id: int,
    db: Session = Depends(get_db),
) -> dict:
    appt = db.query(models.Appointment).get(appointment_id)
    if appt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الموعد غير موجود",
        )
    appt.reminder_sent = True
    db.commit()
    return {"appointment_id": appointment_id, "reminder_sent": True}


@app.post("/reminder/respond", response_model=schemas.ReminderResult)
def reminder_respond(
    appointment_id: int,
    will_attend: bool,
    db: Session = Depends(get_db),
) -> schemas.ReminderResult:
    appt = db.query(models.Appointment).get(appointment_id)
    if appt is None or appt.patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الموعد غير مرتبط بمريض",
        )
    user = db.query(models.User).get(appt.patient_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المريض غير موجود",
        )

    reminder_agent = agents.ReminderAgent(db)
    updated = reminder_agent.mark_attendance(appt, will_attend)
    status_text = "سيحضر" if will_attend else "لن يحضر، تم إعادة الموعد كمتاح"

    return schemas.ReminderResult(
        appointment_id=updated.id,
        email=user.email,
        status=status_text,
    )
