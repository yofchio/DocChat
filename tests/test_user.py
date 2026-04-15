# Tests for core/domain/user.py
#
# Covers:
# - Validators (unit tests)
# - Password hashing/verification (unit tests)
# - User CRUD with mocked DB (integration tests)

from unittest.mock import AsyncMock, patch

import pytest

from core.domain.user import User
from core.exceptions import InvalidInputError


# Validators


class TestUserValidators:
    def test_valid_user(self):
        u = User(username="alice", email="alice@example.com", password_hash="hash123")
        assert u.username == "alice"
        assert u.email == "alice@example.com"

    def test_empty_username_raises(self):
        with pytest.raises(InvalidInputError):
            User(username="", email="a@b.com", password_hash="hash")

    def test_short_username_raises(self):
        with pytest.raises(InvalidInputError):
            User(username="a", email="a@b.com", password_hash="hash")

    def test_username_gets_stripped(self):
        u = User(username="  alice  ", email="a@b.com", password_hash="hash")
        assert u.username == "alice"

    def test_invalid_email_raises(self):
        with pytest.raises(InvalidInputError):
            User(username="alice", email="not-an-email", password_hash="hash")

    def test_email_normalized_to_lowercase(self):
        u = User(username="alice", email="Alice@Example.COM", password_hash="hash")
        assert u.email == "alice@example.com"


# Password hashing


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        hashed = User.hash_password("mypassword")
        assert hashed != "mypassword"

    def test_verify_correct_password(self):
        hashed = User.hash_password("secret123")
        assert User.verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = User.hash_password("secret123")
        assert User.verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = User.hash_password("same")
        h2 = User.hash_password("same")
        # bcrypt uses random salt, so hashes differ
        assert h1 != h2
        # But both should verify
        assert User.verify_password("same", h1)
        assert User.verify_password("same", h2)


# get_by_username


class TestGetByUsername:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "user:1", "username": "alice", "email": "a@b.com", "password_hash": "h"}
            ]
            user = await User.get_by_username("alice")

        assert user is not None
        assert user.username == "alice"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            user = await User.get_by_username("ghost")

        assert user is None


# get_by_email


class TestGetByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "user:1", "username": "alice", "email": "a@b.com", "password_hash": "h"}
            ]
            user = await User.get_by_email("a@b.com")

        assert user is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            user = await User.get_by_email("nobody@b.com")

        assert user is None


# get_by_id


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "user:1", "username": "alice", "email": "a@b.com", "password_hash": "h"}
            ]
            user = await User.get_by_id("user:1")

        assert user is not None
        assert user.id == "user:1"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            user = await User.get_by_id("user:999")

        assert user is None


# create


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_user_successfully(self):
        with (
            patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.domain.user.repo_create", new_callable=AsyncMock) as mock_create,
        ):
            # get_by_username and get_by_email return empty (no duplicates)
            mock_q.return_value = []
            mock_create.return_value = [
                {"id": "user:new", "username": "bob", "email": "bob@b.com", "password_hash": "h"}
            ]
            user = await User.create("bob", "bob@b.com", "password123")

        assert user.id == "user:new"
        assert user.username == "bob"

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_username(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            # First call (get_by_username) returns existing user
            mock_q.return_value = [
                {"id": "user:1", "username": "bob", "email": "bob@b.com", "password_hash": "h"}
            ]
            with pytest.raises(InvalidInputError, match="Username already exists"):
                await User.create("bob", "new@b.com", "password123")

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_email(self):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return []  # get_by_username: no match
            return [
                {"id": "user:1", "username": "other", "email": "taken@b.com", "password_hash": "h"}
            ]

        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.side_effect = side_effect
            with pytest.raises(InvalidInputError, match="Email already registered"):
                await User.create("newuser", "taken@b.com", "password123")


# update_email


class TestUpdateEmail:
    @pytest.mark.asyncio
    async def test_updates_email(self):
        with (
            patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_repo_q,
        ):
            mock_q.return_value = []  # no existing user with this email
            mock_repo_q.return_value = [{"id": "user:1"}]  # repo_update result
            user = User(id="user:1", username="alice", email="old@b.com", password_hash="h")
            await user.update_email("new@b.com")

        assert user.email == "new@b.com"

    @pytest.mark.asyncio
    async def test_rejects_invalid_email(self):
        user = User(id="user:1", username="alice", email="old@b.com", password_hash="h")
        with pytest.raises(InvalidInputError):
            await user.update_email("invalid")


# update_password


class TestUpdatePassword:
    @pytest.mark.asyncio
    async def test_rejects_short_password(self):
        user = User(id="user:1", username="alice", email="a@b.com", password_hash="h")
        with pytest.raises(InvalidInputError, match="at least 6"):
            await user.update_password("short")

    @pytest.mark.asyncio
    async def test_updates_password(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:1"}]
            user = User(id="user:1", username="alice", email="a@b.com", password_hash="old")
            await user.update_password("newsecret123")

        assert user.password_hash != "old"
        assert User.verify_password("newsecret123", user.password_hash)


# get_all_users / count_users


class TestUserQueries:
    @pytest.mark.asyncio
    async def test_get_all_users(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "user:1", "username": "alice", "email": "a@b.com", "password_hash": "h"},
                {"id": "user:2", "username": "bob", "email": "b@b.com", "password_hash": "h"},
            ]
            users = await User.get_all_users()

        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_count_users(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": 10}]
            count = await User.count_users()

        assert count == 10

    @pytest.mark.asyncio
    async def test_count_users_empty(self):
        with patch("core.domain.user.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": None}]
            count = await User.count_users()

        assert count == 0
