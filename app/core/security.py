import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher()

# A fixed dummy hash verified against on "user not found" so that login
# always takes roughly the same time, regardless of whether the email exists.
_DUMMY_HASH = _password_hasher.hash(secrets.token_hex(16))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        _password_hasher.verify(hashed or _DUMMY_HASH, password)
        return hashed is not None
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_csrf_secret() -> str:
    return secrets.token_urlsafe(32)


def generate_csrf_token(csrf_secret: str) -> str:
    return hmac.new(csrf_secret.encode(), b"csrf", hashlib.sha256).hexdigest()


def verify_csrf_token(csrf_secret: str, submitted_token: str) -> bool:
    expected = generate_csrf_token(csrf_secret)
    return hmac.compare_digest(expected, submitted_token or "")
