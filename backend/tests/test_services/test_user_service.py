"""Unit tests for backend/services/UserService.py"""
import pytest
from unittest.mock import MagicMock, patch
from backend.services.UserService import UserService
from backend.models.models import User
from backend.core.exceptions import ValidationError
from backend.controller.UserController.dto.LoginRequest import LoginRequest
from backend.controller.UserController.dto.RegisterRequest import RegisterRequest
from backend.controller.UserController.dto.ChangePasswordRequest import ChangePasswordRequest
from backend.utils.hash import hash_password


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def service(db_session):
    return UserService(db_session)


@pytest.fixture
def existing_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.password = hash_password("correct_password")
    return user


class TestLogin:
    @pytest.mark.unit
    def test_successful_login_returns_token(self, service, existing_user):
        service.user_repository.get_by_email = MagicMock(return_value=existing_user)
        req = LoginRequest(email="test@example.com", password="correct_password")
        result = service.login(req)
        assert result.access_token is not None
        assert result.token_type == "bearer"

    @pytest.mark.unit
    def test_user_not_found_raises_validation_error(self, service):
        service.user_repository.get_by_email = MagicMock(return_value=None)
        req = LoginRequest(email="ghost@example.com", password="pass")
        with pytest.raises(ValidationError) as exc:
            service.login(req)
        assert exc.value.code == "INVALID_CREDENTIALS"

    @pytest.mark.unit
    def test_wrong_password_raises_validation_error(self, service, existing_user):
        service.user_repository.get_by_email = MagicMock(return_value=existing_user)
        req = LoginRequest(email="test@example.com", password="wrong")
        with pytest.raises(ValidationError) as exc:
            service.login(req)
        assert exc.value.code == "INVALID_CREDENTIALS"

    @pytest.mark.unit
    def test_login_response_has_user_info(self, service, existing_user):
        service.user_repository.get_by_email = MagicMock(return_value=existing_user)
        req = LoginRequest(email="test@example.com", password="correct_password")
        result = service.login(req)
        assert result.user.email == "test@example.com"


class TestRegister:
    @pytest.mark.unit
    def test_successful_register_returns_token(self, service):
        service.user_repository.exists_by_email = MagicMock(return_value=False)

        def fake_create(user):
            user.id = 42

        service.user_repository.create_user = MagicMock(side_effect=fake_create)
        req = RegisterRequest(name="New User", email="new@example.com", password="pass123")
        result = service.register(req)
        assert result.access_token is not None

    @pytest.mark.unit
    def test_duplicate_email_raises_validation_error(self, service):
        service.user_repository.exists_by_email = MagicMock(return_value=True)
        req = RegisterRequest(name="Dup", email="existing@example.com", password="pass123")
        with pytest.raises(ValidationError) as exc:
            service.register(req)
        assert exc.value.code == "USER_ALREADY_EXISTS"


class TestTokenBlacklist:
    @pytest.mark.unit
    def test_invalidated_token_returns_none(self, service):
        from backend.core.security import create_access_token
        token = create_access_token("999")
        service.invalidate_token(token)
        result = service.validate_token(token)
        assert result is None

    @pytest.mark.unit
    def test_valid_token_with_known_user(self, service, existing_user):
        from backend.core.security import create_access_token
        token = create_access_token(str(existing_user.id), {"email": existing_user.email})
        service.user_repository.get_by_id = MagicMock(return_value=existing_user)
        result = service.validate_token(token)
        assert result is not None


class TestChangePassword:
    @pytest.mark.unit
    def test_correct_current_password_updates(self, service, existing_user):
        service.user_repository.get_by_id = MagicMock(return_value=existing_user)
        service.user_repository.update_user = MagicMock()
        req = ChangePasswordRequest(current_password="correct_password", new_password="new_password_123")
        service.change_password(existing_user.id, req)
        service.user_repository.update_user.assert_called_once()

    @pytest.mark.unit
    def test_wrong_current_password_raises(self, service, existing_user):
        service.user_repository.get_by_id = MagicMock(return_value=existing_user)
        req = ChangePasswordRequest(current_password="wrong", new_password="new_password_123")
        with pytest.raises(ValidationError) as exc:
            service.change_password(existing_user.id, req)
        assert exc.value.code == "INVALID_PASSWORD"

    @pytest.mark.unit
    def test_user_not_found_raises(self, service):
        service.user_repository.get_by_id = MagicMock(return_value=None)
        req = ChangePasswordRequest(current_password="any", new_password="newpassword123")
        with pytest.raises(ValidationError) as exc:
            service.change_password(999, req)
        assert exc.value.code == "USER_NOT_FOUND"
