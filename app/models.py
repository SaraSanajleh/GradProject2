from __future__ import annotations

import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base


class AppointmentStatus(str, enum.Enum):
    available = "available"
    booked = "booked"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(60), nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    national_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    agreed_privacy: Mapped[bool] = mapped_column(Boolean, default=False)
    agreed_medical_sharing: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="patient",
        order_by="Appointment.start_time",  # 2026 قبل 2027 — المواعيد بالتاريخ من الأقدم
    )


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship("User")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    doctors: Mapped[list["Doctor"]] = relationship(
        "Doctor", back_populates="department", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="department"
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))

    department: Mapped[Department] = relationship("Department", back_populates="doctors")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="doctor"
    )

    @property
    def department_name(self) -> str | None:
        """اسم القسم الذي يتبع له الطبيب (للعرض والـ API)."""
        return self.department.name if self.department else None


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id",
            "start_time",
            name="uq_doctor_start_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), default=AppointmentStatus.available, nullable=False
    )
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    department: Mapped[Department] = relationship(
        "Department", back_populates="appointments"
    )
    doctor: Mapped[Doctor] = relationship("Doctor", back_populates="appointments")
    patient: Mapped[User | None] = relationship(
        "User", back_populates="appointments", foreign_keys=[patient_id]
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chosen_department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True
    )
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    appointments_shown_offset: Mapped[int] = mapped_column(Integer, default=0)

    shared_memory: Mapped[str] = mapped_column(Text, default="{}")
    stop_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    stability_counter: Mapped[int] = mapped_column(Integer, default=0)
    last_top_department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped[User] = relationship("User")
    department: Mapped[Department | None] = relationship("Department")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    clinical_agent = "clinical_agent"
    scheduling_agent = "scheduling_agent"
    reminder_agent = "reminder_agent"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[ChatMessageRole] = mapped_column(Enum(ChatMessageRole))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    session: Mapped[ChatSession] = relationship(
        "ChatSession", back_populates="messages"
    )


class EvaluationTrace(Base):
    """
    سجل تقييم مستقل عن البيانات الطبية.
    يكتب فقط من قِبَل Evaluation Agent (read-only للنظام الرئيسي).
    لا يُستخدم إطلاقاً في أي قرار طبي.
    """

    __tablename__ = "evaluation_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    trace_scope: Mapped[str] = mapped_column(String(20), default="turn", nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)

    asking_total: Mapped[int] = mapped_column(Integer, default=0)
    asking_max: Mapped[int] = mapped_column(Integer, default=18)
    asking_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    department_total: Mapped[int] = mapped_column(Integer, default=0)
    department_max: Mapped[int] = mapped_column(Integer, default=9)
    department_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    structured_total: Mapped[int] = mapped_column(Integer, default=0)
    structured_max: Mapped[int] = mapped_column(Integer, default=6)
    structured_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    emergency_total: Mapped[int] = mapped_column(Integer, default=0)
    emergency_max: Mapped[int] = mapped_column(Integer, default=4)
    emergency_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    system_conversation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationDepartmentDecision(Base):
    """
    تاريخ قرارات Department Agent لكل turn.
    جدول مراقبة فقط لدعم تقييم الاستقرار عبر المحادثة كاملة.
    """

    __tablename__ = "evaluation_department_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    top_department: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(Text, default="")

