import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id with library defaults

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

# A short deny-list of very common passwords; a breached-password check can be added with a provider.
_COMMON = {
    "password1234", "123456789012", "qwertyuiopas", "passwordpassword", "letmein12345",
    "welcome12345", "administrator", "iloveyou1234", "000000000000", "111111111111",
}


def validate_password(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password.lower() in _COMMON:
        return "Password is too common."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Used to keep login timing similar for unknown emails.
DUMMY_HASH = _hasher.hash("not-a-real-password-placeholder")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
