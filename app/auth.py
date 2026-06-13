from __future__ import annotations

import secrets
from datetime import date

import bcrypt
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db


def _truncate_for_bcrypt(password: str, max_bytes: int = 72) -> str:
    """bcrypt يقبل حتى 72 بايت فقط."""
    raw = password.encode("utf-8")
    if len(raw) <= max_bytes:
        return password
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    password = _truncate_for_bcrypt(password)
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain = _truncate_for_bcrypt(plain_password)
    return bcrypt.checkpw(plain.encode("utf-8"), hashed_password.encode("utf-8"))


def create_session_token() -> str:
    return secrets.token_hex(32)


def register_user(data: schemas.UserRegisterRequest, db: Session) -> models.User:
    # التحقق من العمر 18+ أو تسجيل بواسطة ولي أمر (نسجل لكن يمكن استخدام فلاغ مستقبلاً)
    today = date.today()
    age = today.year - data.dob.year - (
        (today.month, today.day) < (data.dob.month, data.dob.day)
    )
    if age < 18:
        # نسمح بالتسجيل لكن يمكن لاحقاً إضافة حقل "has_guardian"
        pass

    # التأكد من أن الإيميل والرقم الوطني غير مستخدمَين مسبقاً
    if (
        db.query(models.User)
        .filter(models.User.email == data.email)
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا البريد الإلكتروني مستخدم مسبقاً",
        )
    if (
        db.query(models.User)
        .filter(models.User.national_id == data.national_id)
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا الرقم الوطني مستخدم مسبقاً",
        )

    if not data.agreed_privacy or not data.agreed_medical_sharing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يجب الموافقة على سياسة الخصوصية ومشاركة البيانات الطبية",
        )

    user = models.User(
        full_name=data.full_name,
        dob=data.dob,
        national_id=data.national_id,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password),
        agreed_privacy=data.agreed_privacy,
        agreed_medical_sharing=data.agreed_medical_sharing,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(
    data: schemas.UserLoginRequest, db: Session
) -> tuple[models.User, models.SessionToken]:
    if not data.email and not data.national_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يجب إدخال البريد الإلكتروني أو الرقم الوطني",
        )

    query = db.query(models.User)
    if data.email:
        query = query.filter(models.User.email == data.email)
    if data.national_id:
        query = query.filter(models.User.national_id == data.national_id)
    user = query.first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات تسجيل الدخول غير صحيحة",
        )

    token_value = create_session_token()
    token = models.SessionToken(user_id=user.id, token=token_value, is_active=True)
    db.add(token)
    db.commit()
    db.refresh(token)
    return user, token


def get_current_user(
    token: str, db: Session = Depends(get_db)
) -> models.User:
    session_token = (
        db.query(models.SessionToken)
        .filter(models.SessionToken.token == token, models.SessionToken.is_active == True)
        .first()
    )
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="جلسة غير صالحة، يرجى تسجيل الدخول مرة أخرى",
        )
    return session_token.user

