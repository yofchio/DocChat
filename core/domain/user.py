from datetime import datetime
from typing import ClassVar, Optional

import bcrypt
from loguru import logger
from pydantic import BaseModel, field_validator

from core.database.repository import repo_create, repo_query
from core.exceptions import DatabaseOperationError, InvalidInputError


class User(BaseModel):
    # Simple user model with helpers for creating and looking up users.
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
        # Ensure username is not blank and has at least 2 chars.
        if not v or not v.strip():
            raise InvalidInputError("Username cannot be empty")
        if len(v) < 2:
            raise InvalidInputError("Username must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v):
        # Minimal email validation: must contain '@'.
        if not v or "@" not in v:
            raise InvalidInputError("Invalid email address")
        return v.strip().lower()

    @staticmethod
    def hash_password(password: str) -> str:
        # Hash the password using bcrypt and return the hash string.
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        # Check a plain password against a bcrypt hash.
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    @classmethod
    async def get_by_username(cls, username: str) -> Optional["User"]:
        # Load a user by username, return None if not found.
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
        # Load a user by email, normalized to lowercase.
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
        # Load a user by record id. Handles a couple edge cases from SurrealDB.
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
                    # Rare case: Surreal returned a string; re-query in the user table.
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
        # Create a new user after checking username and email uniqueness.
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


    async def update_email(self, new_email: str) -> None:
        # Change this user's email after checking it's not taken.
        new_email = new_email.strip().lower()
        if not new_email or "@" not in new_email:
            raise InvalidInputError("Invalid email address")
        existing = await self.__class__.get_by_email(new_email)
        if existing and existing.id != self.id:
            raise InvalidInputError("Email already registered")
        from core.database.repository import repo_update
        await repo_update("user", self.id, {"email": new_email})
        self.email = new_email

    async def update_password(self, new_password: str) -> None:
        # Change this user's password. Caller should verify the old one first.
        if not new_password or len(new_password) < 6:
            raise InvalidInputError("Password must be at least 6 characters")
        new_hash = self.hash_password(new_password)
        from core.database.repository import repo_update
        await repo_update("user", self.id, {"password_hash": new_hash})
        self.password_hash = new_hash

    @classmethod
    async def get_all_users(cls) -> list["User"]:
        # Return every user in the table.
        try:
            result = await repo_query("SELECT * FROM user ORDER BY created DESC")
            return [cls(**row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def count_users(cls) -> int:
        # Return the total number of users.
        try:
            result = await repo_query(
                "SELECT count() AS total FROM user GROUP ALL"
            )
            if result and result[0].get("total") is not None:
                return int(result[0]["total"])
            return 0
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            raise DatabaseOperationError(e)
