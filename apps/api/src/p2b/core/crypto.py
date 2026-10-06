"""Small cryptographic helpers over audited libraries (SECURITY section 1, principle 5: no custom
crypto). Keyed hashes for identifiers in rate limits and security events; AES-GCM for values the
system must read back once (the OTP code until its delivery job has sent it)."""

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12


def keyed_hash(key: str, value: str) -> str:
    """HMAC-SHA256, hex. Lets the system count and match a contact or IP without storing it."""
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


def _aesgcm(key_b64: str) -> AESGCM:
    key = base64.b64decode(key_b64)
    if len(key) != 32:
        raise ValueError("encryption key must be 32 bytes (base64)")
    return AESGCM(key)


def encrypt(key_b64: str, plaintext: str, associated_data: bytes) -> bytes:
    """Nonce followed by ciphertext. The associated data binds the ciphertext to its row."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + _aesgcm(key_b64).encrypt(nonce, plaintext.encode(), associated_data)


def decrypt(key_b64: str, blob: bytes, associated_data: bytes) -> str:
    nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    return _aesgcm(key_b64).decrypt(nonce, ciphertext, associated_data).decode()
