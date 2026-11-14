
import os
import uuid

from datetime import datetime, timedelta, timezone

import jwt

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.db import SessionLocal, User


password_hash = PasswordHash.recommended()

bearer_scheme = HTTPBearer(auto_error=False)

ACCESS_COOKIE_NAME = "learnwise_access_token"

COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        "type": "access",
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def set_auth_cookie(response, token: str):
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )

def clear_auth_cookie(response):
    response.delete_cookie(
    key=ACCESS_COOKIE_NAME,
    path="/",
    secure=True,
    httponly=True,
    samesite="none",
    )


def get_current_user(
    access_token: str | None = Cookie(
        default=None,
        alias=ACCESS_COOKIE_NAME,
    ),
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Cookie is preferred. Bearer is retained for Swagger/API testing.
    token = access_token

    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise unauthorized

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != "access":
            raise unauthorized

        user_id = uuid.UUID(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise unauthorized

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise unauthorized

    return user
