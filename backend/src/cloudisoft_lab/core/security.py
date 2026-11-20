"""Credential vault (encryption at rest), password hashing and JWT helpers."""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_hasher = PasswordHasher()


class CredentialVaultError(RuntimeError):
    pass


class CredentialVault:
    """Encrypts provider API credentials. Plaintext never leaves the backend."""

    def __init__(self, key: str | bytes | None) -> None:
        if not key:
            raise CredentialVaultError(
                "CLAB_CREDENTIAL_ENCRYPTION_KEY is not set; refusing to store credentials."
            )
        self._fernet = Fernet(key if isinstance(key, bytes) else key.encode())

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:  # pragma: no cover - message path tested
            raise CredentialVaultError("Credential could not be decrypted (wrong key?)") from exc

    @staticmethod
    def mask(value: str) -> str:
        return "****" if len(value) <= 8 else f"{value[:4]}…{value[-4:]}"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, role: str, secret: str, ttl_minutes: int) -> str:
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
