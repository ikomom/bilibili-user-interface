import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return password_hash.verify_and_update(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def get_or_create_encryption_key() -> str:
    key = settings.BILIBILI_CREDENTIALS_ENCRYPTION_KEY
    if not key:
        key = Fernet.generate_key().decode()
        raise ValueError(
            "缺少 BILIBILI_CREDENTIALS_ENCRYPTION_KEY 配置，请生成 Fernet 密钥后添加到 .env.local"
        )
    return key


def encrypt_credentials(credentials: dict) -> str:
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    json_str = json.dumps(credentials)
    encrypted = f.encrypt(json_str.encode())
    return encrypted.decode()


def decrypt_credentials(encrypted: str) -> dict:
    key = get_or_create_encryption_key()
    f = Fernet(key.encode())
    decrypted = f.decrypt(encrypted.encode())
    return json.loads(decrypted.decode())
