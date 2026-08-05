from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from .config import get_settings

settings = get_settings()
password_hasher = PasswordHasher()
fernet = Fernet(settings.encryption_key.encode())


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_token(subject: UUID | str, token_type: str, expires_delta: timedelta, **claims) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **claims,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(subject: UUID | str, **claims) -> str:
    return create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_minutes),
        **claims,
    )


def create_refresh_token(subject: UUID | str, **claims) -> str:
    return create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        **claims,
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def encrypt_secret(data: bytes) -> bytes:
    return fernet.encrypt(data)


def decrypt_secret(data: bytes) -> bytes:
    return fernet.decrypt(data)
