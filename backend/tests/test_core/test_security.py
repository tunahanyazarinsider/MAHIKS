"""Unit tests for backend/core/security.py"""
import time
import pytest
from unittest.mock import patch
from datetime import timedelta

from backend.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_token_subject,
)


class TestPasswordHashing:
    @pytest.mark.unit
    def test_hash_returns_non_empty_string(self):
        result = hash_password("my_password")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.unit
    def test_hash_not_plaintext(self):
        result = hash_password("my_password")
        assert result != "my_password"

    @pytest.mark.unit
    def test_verify_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    @pytest.mark.unit
    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    @pytest.mark.unit
    def test_two_hashes_differ(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    @pytest.mark.unit
    def test_create_returns_string(self):
        token = create_access_token("42")
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.unit
    def test_decode_valid_token(self):
        token = create_access_token("42")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    @pytest.mark.unit
    def test_decode_with_extra_claims(self):
        token = create_access_token("7", claims={"email": "a@b.com"})
        payload = decode_access_token(token)
        assert payload["email"] == "a@b.com"

    @pytest.mark.unit
    def test_decode_invalid_token_returns_none(self):
        result = decode_access_token("not.a.token")
        assert result is None

    @pytest.mark.unit
    def test_decode_expired_token_returns_none(self):
        from backend.config import Config
        original = Config.ACCESS_TOKEN_EXPIRE_MINUTES
        Config.ACCESS_TOKEN_EXPIRE_MINUTES = 0
        try:
            token = create_access_token("99")
            time.sleep(1)
            result = decode_access_token(token)
            assert result is None
        finally:
            Config.ACCESS_TOKEN_EXPIRE_MINUTES = original

    @pytest.mark.unit
    def test_decode_refresh_token_with_access_returns_none(self):
        token = create_access_token("42")
        result = decode_refresh_token(token)
        assert result is None


class TestRefreshToken:
    @pytest.mark.unit
    def test_create_returns_string(self):
        token = create_refresh_token("42")
        assert isinstance(token, str)

    @pytest.mark.unit
    def test_decode_valid_refresh_token(self):
        token = create_refresh_token("42")
        payload = decode_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    @pytest.mark.unit
    def test_decode_access_token_with_refresh_returns_none(self):
        token = create_refresh_token("42")
        result = decode_access_token(token)
        assert result is None


class TestGetTokenSubject:
    @pytest.mark.unit
    def test_valid_access_token(self):
        token = create_access_token("123")
        assert get_token_subject(token) == "123"

    @pytest.mark.unit
    def test_invalid_token_returns_none(self):
        result = get_token_subject("garbage")
        assert result is None
