from datetime import datetime
from typing import ClassVar, Optional

import bcrypt
from loguru import logger
from pydantic import BaseModel, field_validator

from core.database.repository import repo_create, repo_query
from core.exceptions import DatabaseOperationError, InvalidInputError


class User(BaseModel):
    id: Optional[str] = None
    username: str
    email: str
    password_hash: str
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    table_name: ClassVar[str] = "user"

    @field_validator("username")
    @classmethod
    def username_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise InvalidInputError("Username cannot be empty")
        if len(v) < 2:
            raise InvalidInputError("Username must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        if not v or "@" not in v:
            raise InvalidInputError("Invalid email address")
        return v.strip().lower()

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    @classmethod
    async def get_by_username(cls, username: str) -> Optional["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE username = $username",
                {"username": username},
            )
            if result:
                return cls(**result[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by username: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_by_email(cls, email: str) -> Optional["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE email = $email",
                {"email": email.strip().lower()},
            )
            if result:
                return cls(**result[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_by_id(cls, user_id: str) -> Optional["User"]:
        try:
            from core.database.repository import ensure_record_id

            rid = ensure_record_id(user_id)
            result = await repo_query(
                "SELECT * FROM $id",
                {"id": rid},
            )
            logger.debug(f"get_by_id result type={type(result)}, len={len(result) if result else 0}")
            if result:
                item = result[0]
                logger.debug(f"get_by_id item type={type(item)}, val={str(item)[:200]}")
                if isinstance(item, dict):
                    return cls(**item)
                elif isinstance(item, str):
                    logger.warning(f"Got string instead of dict for user {user_id}, re-querying")
                    result2 = await repo_query(
                        f"SELECT * FROM user WHERE id = $id",
                        {"id": rid},
                    )
                    if result2 and isinstance(result2[0], dict):
                        return cls(**result2[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching user by id {user_id}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def create(cls, username: str, email: str, password: str) -> "User":
        existing = await cls.get_by_username(username)
        if existing:
            raise InvalidInputError("Username already exists")
        existing = await cls.get_by_email(email)
        if existing:
            raise InvalidInputError("Email already registered")

        password_hash = cls.hash_password(password)
        data = {
            "username": username.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
        }
        try:
            result = await repo_create("user", data)
            result_item = result[0] if isinstance(result, list) else result
            return cls(**result_item)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise DatabaseOperationError(e)
