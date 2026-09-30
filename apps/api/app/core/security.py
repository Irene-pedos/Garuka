from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import settings

# Argon2 password/PIN hasher
password_hash = PasswordHash((Argon2Hasher(),))

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_pin(plain_pin: str, hashed_pin: str | None) -> bool:
    if not hashed_pin:
        return False
    return password_hash.verify(plain_pin, hashed_pin)


def get_pin_hash(pin: str) -> str:
    return password_hash.hash(pin)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.JWT_REFRESH_DAYS)
    to_encode.update({"exp": expire, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])


def hash_visit_code(code: str, salt: str = "garuka-visit") -> str:
    import hashlib

    return hashlib.sha256(f"{salt}:{code.strip()}".encode()).hexdigest()


def verify_visit_code(code: str, hashed: str, salt: str = "garuka-visit") -> bool:
    import hashlib

    return hashlib.sha256(f"{salt}:{code.strip()}".encode()).hexdigest() == hashed

