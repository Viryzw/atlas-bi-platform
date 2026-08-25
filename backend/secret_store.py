"""Authenticated encryption for database and LLM credentials.

The implementation uses HMAC-SHA256 as a pseudorandom stream plus a separate
encrypt-then-MAC key. Existing plaintext values remain readable and are
upgraded the next time they are saved.
"""

import base64
import hashlib
import hmac
import os
import secrets


PREFIX = "enc:v1:"


def _master_key() -> bytes:
    value = os.getenv("ATLAS_SECRET_KEY") or os.getenv("AUTH_SECRET") or "atlas-bi-development-secret-change-me"
    return hashlib.sha256(value.encode("utf-8")).digest()


def _keys() -> tuple[bytes, bytes]:
    master = _master_key()
    return (
        hmac.new(master, b"atlas-bi-encryption", hashlib.sha256).digest(),
        hmac.new(master, b"atlas-bi-authentication", hashlib.sha256).digest(),
    )


def _stream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = []
    counter = 0
    while sum(len(block) for block in blocks) < length:
        blocks.append(hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:length]


def encrypt_secret(value: str) -> str:
    clean = value or ""
    if not clean or clean.startswith(PREFIX):
        return clean
    encryption_key, authentication_key = _keys()
    nonce = secrets.token_bytes(16)
    plain = clean.encode("utf-8")
    stream = _stream(encryption_key, nonce, len(plain))
    cipher = bytes(left ^ right for left, right in zip(plain, stream))
    tag = hmac.new(authentication_key, nonce + cipher, hashlib.sha256).digest()
    payload = base64.urlsafe_b64encode(nonce + cipher + tag).decode("ascii")
    return PREFIX + payload


def decrypt_secret(value: str) -> str:
    stored = value or ""
    if not stored.startswith(PREFIX):
        return stored
    try:
        raw = base64.urlsafe_b64decode(stored[len(PREFIX):])
        nonce, cipher, supplied_tag = raw[:16], raw[16:-32], raw[-32:]
        encryption_key, authentication_key = _keys()
        expected_tag = hmac.new(authentication_key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_tag, expected_tag):
            raise ValueError("secret authentication failed")
        stream = _stream(encryption_key, nonce, len(cipher))
        return bytes(left ^ right for left, right in zip(cipher, stream)).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("已加密凭据无法解密，请检查 ATLAS_SECRET_KEY") from exc
