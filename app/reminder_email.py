"""
إرسال تذكير الموعد بالإيميل (قبل الموعد بيومين).
يُستخدم من endpoint أو كرون — إعداد SMTP عبر متغيرات البيئة.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# إعدادات SMTP (اختيارية — إذا ما ضُبطت، الإيميل ما يُرسل)
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
REMINDER_FROM_EMAIL = os.getenv("REMINDER_FROM_EMAIL", SMTP_USER or "noreply@hospital.local")
REMINDER_FROM_NAME = os.getenv("REMINDER_FROM_NAME", "مستشفى - التذكير")


def is_email_configured() -> bool:
    """هل إرسال الإيميل مفعّل (SMTP مضبوط)؟"""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_reminder_email(
    to_email: str,
    patient_name: str,
    appointment_date: str,
    appointment_time: str,
    department_name: str,
    doctor_name: str,
) -> bool:
    """
    إرسال إيميل تذكير لمريض بموعده.
    يرجع True إذا تم الإرسال، False إذا فشل أو SMTP غير مضبوط.
    """
    if not is_email_configured():
        return False

    subject = f"تذكير بموعدك — {appointment_date} الساعة {appointment_time}"
    body = f"""
مرحباً {patient_name},

هذا تذكير بموعدك في المستشفى:

• التاريخ: {appointment_date}
• الوقت: {appointment_time}
• القسم: {department_name}
• الطبيب: {doctor_name}

يرجى الحضور قبل الموعد بـ 15 دقيقة.
إذا لن تتمكن من الحضور، يرجى إلغاء الموعد أو إبلاغنا.

مع تحيات إدارة المستشفى
"""

    msg = MIMEText(body.strip(), "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((REMINDER_FROM_NAME, REMINDER_FROM_EMAIL))
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(REMINDER_FROM_EMAIL, [to_email], msg.as_string())
        return True
    except Exception:
        return False


def send_test_email(to_email: str) -> tuple[bool, str]:
    """
    إرسال إيميل اختباري للتأكد أن SMTP شغال.
    يرجع (نجح/فشل، رسالة بالعربي).
    """
    if not is_email_configured():
        return False, "SMTP غير مضبوط: أضف SMTP_HOST و SMTP_USER و SMTP_PASSWORD في .env"

    subject = "تجربة التذكير — MedCompass"
    body = "هذا إيميل تجريبي من نظام التذكير. إذا وصلك هذا الإيميل فالإعدادات صحيحة والتذكيرات رح توصل."
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((REMINDER_FROM_NAME, REMINDER_FROM_EMAIL))
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(REMINDER_FROM_EMAIL, [to_email], msg.as_string())
        return True, "تم إرسال الإيميل الاختباري. تحقق من صندوق الوارد (والسبام)."
    except Exception as e:
        return False, f"فشل الإرسال: {e!s}"
