
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    get_db,
    get_current_user,
    hash_password,
    verify_password,
    create_access_token,
    set_auth_cookie,
    clear_auth_cookie,
)
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.db import User, EmailVerification
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    ProfileUpdateRequest,
    ChangePasswordRequest,
    VerifyEmailRequest,
    ResendOTPRequest,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest,
)
from app.services.otp.otp_service import (
    send_registration_otp,
    verify_registration_otp,
    REGISTRATION_PURPOSE,
    send_password_reset_otp,
    verify_password_reset_otp,
    complete_password_reset,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    full_name = payload.full_name.strip()

    if len(full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name must contain at least 2 characters.",
        )

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    password_hash = hash_password(payload.password)

    send_registration_otp(
        db=db,
        email=email,
        full_name=full_name,
        password_hash=password_hash,
    )

    return {
        "message": "Verification code sent to your email address.",
        "email": email,
        "expires_in": 300,
    }

@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        user.id,
        remember_me=payload.rememberMe,
    )

    expires_in = (
        30 * 24 * 60 * 60
        if payload.rememberMe
        else ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return {
        "access_token": token,
        "expires_in": expires_in,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }
@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    try:
        verification = verify_registration_otp(
            db=db,
            email=email,
            otp=payload.otp,
        )

        if not verification.full_name or not verification.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid registration verification request.",
            )

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            db.delete(verification)
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            full_name=verification.full_name,
            email=email,
            password_hash=verification.password_hash,
        )

        db.add(user)
        db.delete(verification)

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    except Exception:
        db.rollback()
        raise

    token = create_access_token(user.id)
    # set_auth_cookie(response, token)

    return {
        "message": "Email verified and account created successfully.",
        "user": UserResponse.model_validate(user),
        "access_token": token,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/resend-otp")
def resend_otp(
    payload: ResendOTPRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.email == email,
            EmailVerification.purpose == REGISTRATION_PURPOSE,
        )
        .first()
    )

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending registration found. Please register again.",
        )

    send_registration_otp(
        db=db,
        email=email,
        full_name=verification.full_name,
        password_hash=verification.password_hash,
    )

    return {
        "message": "A new verification code has been sent.",
        "email": email,
        "expires_in": 300,
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # Always return the same response to prevent email enumeration.
    if user:
        send_password_reset_otp(
            db=db,
            user=user,
        )

    return {
        "message": "If an account exists with this email, a password reset code has been sent.",
        "email": email,
        "expires_in": 300,
    }


@router.post("/verify-reset-otp")
def verify_reset_otp(
    payload: VerifyResetOTPRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    reset_token = verify_password_reset_otp(
        db=db,
        email=email,
        otp=payload.otp,
    )

    return {
        "message": "OTP verified successfully.",
        "reset_token": reset_token,
        "expires_in": 600,
    }


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    complete_password_reset(
        db=db,
        email=email,
        reset_token=payload.reset_token,
        new_password=payload.new_password,
    )

    return {
        "message": "Your password has been reset successfully. Please log in with your new password."
    }


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    full_name = payload.full_name.strip()

    if len(full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name must contain at least 2 characters.",
        )

    existing_user = (
        db.query(User)
        .filter(
            User.email == email,
            User.id != current_user.id,
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already associated with another account.",
        )

    current_user.full_name = full_name
    current_user.email = email

    try:
        db.commit()
        db.refresh(current_user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already in use.",
        )

    return current_user


@router.put("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(
        payload.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is incorrect.",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your new password must be different from your current password.",
        )

    current_user.password_hash = hash_password(
        payload.new_password
    )

    db.commit()
    db.refresh(current_user)

    # Issue a fresh access token after changing the password.
    token = create_access_token(current_user.id)
    # set_auth_cookie(response, token)

    return {
        "message": "Password changed successfully.",
        "access_token": token,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)

    return {
        "message": "Logged out successfully."
    }
