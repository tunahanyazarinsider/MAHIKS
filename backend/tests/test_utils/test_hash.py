"""Unit tests for backend/utils/hash.py"""
import pytest
from backend.utils.hash import hash_password, verify_password


@pytest.mark.unit
def test_hash_returns_string():
    result = hash_password("password123")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
def test_hash_not_plaintext():
    assert hash_password("password123") != "password123"


@pytest.mark.unit
def test_verify_correct():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True


@pytest.mark.unit
def test_verify_wrong():
    hashed = hash_password("secret")
    assert verify_password("notsecret", hashed) is False


@pytest.mark.unit
def test_verify_empty_string():
    hashed = hash_password("")
    assert verify_password("", hashed) is True
    assert verify_password("a", hashed) is False


@pytest.mark.unit
def test_different_salts_per_hash():
    h1 = hash_password("abc")
    h2 = hash_password("abc")
    assert h1 != h2
