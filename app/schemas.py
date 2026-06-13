from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


FULL_NAME_REGEX = r"^[A-Za-z\u0600-\u06FF\s]{8,60}$"
NATIONAL_ID_REGEX = r"^[0-9]{10}$"
PHONE_REGEX = r"^07[789][0-9]{7}$"
PASSWORD_MIN_LENGTH = 8


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=8, max_length=60, pattern=FULL_NAME_REGEX)
    dob: date
    national_id: str = Field(..., min_length=10, max_length=10, pattern=NATIONAL_ID_REGEX)
    phone: str = Field(..., min_length=10, max_length=10, pattern=PHONE_REGEX)
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    confirm_password: str
    agreed_privacy: bool
    agreed_medical_sharing: bool

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(not c.isalnum() for c in v)
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "كلمة المرور يجب أن تحتوي على حرف كبير، حرف صغير، رقم، ورمز خاص على الأقل"
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        password = info.data.get("password")
        if password is not None and v != password:
            raise ValueError("كلمتا المرور غير متطابقتين")
        return v

    @field_validator("dob")
    @classmethod
    def validate_age(cls, v: date) -> date:
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 0:
            raise ValueError("تاريخ الميلاد لا يمكن أن يكون في المستقبل")
        if age > 120:
            raise ValueError("العمر المدخل غير منطقي (أكبر من 120 سنة)")
        return v


class UserLoginRequest(BaseModel):
    national_id: Optional[str] = Field(
        None, min_length=10, max_length=10, pattern=NATIONAL_ID_REGEX
    )
    email: Optional[EmailStr] = None
    password: str


class UserInfo(BaseModel):
    id: int
    full_name: str
    dob: date
    national_id: str
    phone: str
    email: EmailStr

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """استجابة التسجيل مع تنبيه اختياري (مثلاً عند العمر أقل من 18)."""
    user: UserInfo
    warning: Optional[str] = None


class SessionTokenResponse(BaseModel):
    token: str
    user: UserInfo


class DepartmentOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class DoctorOut(BaseModel):
    id: int
    full_name: str
    department_id: int
    department_name: Optional[str] = None  # اسم القسم (أي قسم الطبيب تابع له)

    class Config:
        from_attributes = True


class AppointmentOut(BaseModel):
    id: int
    department: DepartmentOut
    doctor: DoctorOut
    start_time: datetime
    status: str

    class Config:
        from_attributes = True

    @field_validator("status", mode="before")
    @classmethod
    def status_to_str(cls, v):
        return v.value if hasattr(v, "value") else str(v)


class ChatMessageIn(BaseModel):
    model_config = {"protected_namespaces": ()}

    message: str
    model_name: str = Field(..., description="اسم نموذج الـ LLM المختار")


class ChatTurnOut(BaseModel):
    session_id: int
    user_message: str
    assistant_message: str
    is_emergency: bool
    chosen_department: Optional[DepartmentOut] = None
    offered_appointments: Optional[List[AppointmentOut]] = None


class ReminderResult(BaseModel):
    appointment_id: int
    email: str
    status: str


class ReminderDueItem(BaseModel):
    """موعد مستحق للتذكير (قبل الموعد بيومين) مع بيانات المريض للإرسال."""
    appointment: AppointmentOut
    patient_email: str
    patient_name: str


class ReminderDueOut(BaseModel):
    """قائمة المواعيد التي يجب إرسال تذكير لها اليوم (موعدها بعد يومين)."""
    due_date: date
    appointments: List[ReminderDueItem]

