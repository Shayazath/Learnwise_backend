
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import (
    OTP_SECRET_KEY,
    OTP_EXPIRE_MINUTES,
    OTP_RESEND_COOLDOWN_SECONDS,
    OTP_MAX_ATTEMPTS,
    SMTP_FROM_NAME,
)
from app.db import EmailVerification
from app.services.email.email_service import send_email


REGISTRATION_PURPOSE = "registration"


def generate_otp() -> str:
    """Generate a cryptographically secure six-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(email: str, purpose: str, otp: str) -> str:
    """Create an HMAC-SHA256 hash of an OTP."""
    message = f"{email.lower()}:{purpose}:{otp}".encode("utf-8")

    return hmac.new(
        OTP_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def send_registration_otp(
    db: Session,
    email: str,
    full_name: str,
    password_hash: str,
) -> None:
    """Create and send a registration verification OTP."""

    email = email.strip().lower()
    now = datetime.now(timezone.utc)

    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == REGISTRATION_PURPOSE,
        )
        .with_for_update()
        .first()
    )

    if verification:
        elapsed = (now - verification.last_sent_at).total_seconds()

        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            remaining = max(
                1,
                OTP_RESEND_COOLDOWN_SECONDS - int(elapsed),
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting another OTP.",
            )

    otp = generate_otp()
    otp_hash = hash_otp(email, REGISTRATION_PURPOSE, otp)

    if verification:
        verification.otp_hash = otp_hash
        verification.full_name = full_name
        verification.password_hash = password_hash
        verification.expires_at = now + timedelta(
            minutes=OTP_EXPIRE_MINUTES
        )
        verification.attempts = 0
        verification.last_sent_at = now
    else:
        verification = EmailVerification(
            email=email,
            purpose=REGISTRATION_PURPOSE,
            otp_hash=otp_hash,
            full_name=full_name,
            password_hash=password_hash,
            expires_at=now + timedelta(minutes=OTP_EXPIRE_MINUTES),
            attempts=0,
            last_sent_at=now,
        )
        db.add(verification)

    try:
        db.commit()
        db.refresh(verification)
    except Exception:
        db.rollback()
        raise

    safe_name = escape(full_name)

    subject = "Verify your LearnWise email address"

    body_text = (
        f"Hello {full_name},\n\n"
        f"Your LearnWise verification code is: {otp}\n\n"
        f"This code expires in {OTP_EXPIRE_MINUTES} minutes.\n"
        "If you did not request this code, please ignore this email."
    )

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto;">
        <h2>Welcome to {escape(SMTP_FROM_NAME)}!</h2>
        <p>Hello {safe_name},</p>
        <p>Use the following verification code to complete your registration:</p>
        <div style="font-size: 32px; font-weight: bold;
                    letter-spacing: 8px; padding: 20px;
                    background: #f3f4f6; text-align: center;">
            {otp}
        </div>
        <p>This code expires in {OTP_EXPIRE_MINUTES} minutes.</p>
        <p>If you did not request this code, please ignore this email.</p>
    </div>
    """

    try:
        send_email(
            to_email=email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
    except Exception:
        # Remove the OTP only if this is still the OTP we attempted to send.
        db.rollback()

        db.query(EmailVerification).filter(
            EmailVerification.id == verification.id,
            EmailVerification.otp_hash == otp_hash,
        ).delete(synchronize_session=False)

        db.commit()
        raise


def verify_registration_otp(
    db: Session,
    email: str,
    otp: str,
) -> EmailVerification:
    """
    Verify a registration OTP.

    On success, returns the locked verification record.
    The caller must create the user and delete this record
    in the same database transaction.
    """

    email = email.strip().lower()

    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == REGISTRATION_PURPOSE,
        )
        .with_for_update()
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    now = datetime.now(timezone.utc)
    expires_at = verification.expires_at

    # Handle databases that return naive datetimes.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now >= expires_at:
        db.delete(verification)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your verification code has expired. Please request a new one.",
        )

    if verification.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum verification attempts reached. Please request a new OTP.",
        )

    expected_hash = hash_otp(
        email,
        REGISTRATION_PURPOSE,
        otp,
    )

    if not hmac.compare_digest(
        verification.otp_hash,
        expected_hash,
    ):
        verification.attempts += 1
        db.commit()

        remaining = OTP_MAX_ATTEMPTS - verification.attempts

        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum verification attempts reached. Please request a new OTP.",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect verification code. {remaining} attempts remaining.",
        )

    return verification
