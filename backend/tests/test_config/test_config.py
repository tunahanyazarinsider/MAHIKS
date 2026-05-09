"""Unit tests for backend/config.py"""
import os
import pytest
from backend.config import Config


class TestConfigDefaults:
    @pytest.mark.unit
    def test_mysql_default_host(self):
        assert Config.MYSQL_HOST is not None

    @pytest.mark.unit
    def test_qdrant_collection_name_default(self):
        assert Config.QDRANT_COLLECTION_NAME == "sut_documents"

    @pytest.mark.unit
    def test_jwt_algorithm_default(self):
        assert Config.JWT_ALGORITHM == "HS256"

    @pytest.mark.unit
    def test_chunk_size_is_int(self):
        assert isinstance(Config.CHUNK_SIZE, int)
        assert Config.CHUNK_SIZE > 0

    @pytest.mark.unit
    def test_data_dir_default(self):
        assert "raw_documents" in Config.DATA_DIR

    @pytest.mark.unit
    def test_kg_extraction_method_default(self):
        assert Config.KG_EXTRACTION_METHOD in ("ollama", "local", "gemini", "vertex", "openrouter")


class TestConfigValidate:
    @pytest.mark.unit
    def test_validate_passes_when_env_set(self, monkeypatch):
        monkeypatch.setattr(Config, "MYSQL_PASSWORD", "pass")
        monkeypatch.setattr(Config, "NEO4J_PASSWORD", "pass")
        monkeypatch.setattr(Config, "JWT_SECRET", "secret")
        Config.validate()  # should not raise

    @pytest.mark.unit
    def test_validate_raises_missing_jwt_secret(self, monkeypatch):
        monkeypatch.setattr(Config, "MYSQL_PASSWORD", "pass")
        monkeypatch.setattr(Config, "NEO4J_PASSWORD", "pass")
        monkeypatch.setattr(Config, "JWT_SECRET", "")
        with pytest.raises(ValueError) as exc:
            Config.validate()
        assert "JWT_SECRET" in str(exc.value)

    @pytest.mark.unit
    def test_validate_raises_missing_mysql_password(self, monkeypatch):
        monkeypatch.setattr(Config, "MYSQL_PASSWORD", "")
        monkeypatch.setattr(Config, "NEO4J_PASSWORD", "pass")
        monkeypatch.setattr(Config, "JWT_SECRET", "secret")
        with pytest.raises(ValueError) as exc:
            Config.validate()
        assert "MYSQL_PASSWORD" in str(exc.value)

    @pytest.mark.unit
    def test_validate_reports_all_missing(self, monkeypatch):
        monkeypatch.setattr(Config, "MYSQL_PASSWORD", "")
        monkeypatch.setattr(Config, "NEO4J_PASSWORD", "")
        monkeypatch.setattr(Config, "JWT_SECRET", "")
        with pytest.raises(ValueError) as exc:
            Config.validate()
        msg = str(exc.value)
        assert "MYSQL_PASSWORD" in msg
        assert "NEO4J_PASSWORD" in msg
        assert "JWT_SECRET" in msg


class TestMySQLUri:
    @pytest.mark.unit
    def test_uri_format(self, monkeypatch):
        monkeypatch.setattr(Config, "MYSQL_USER", "user")
        monkeypatch.setattr(Config, "MYSQL_PASSWORD", "pass")
        monkeypatch.setattr(Config, "MYSQL_HOST", "localhost")
        monkeypatch.setattr(Config, "MYSQL_PORT", 3306)
        monkeypatch.setattr(Config, "MYSQL_DATABASE", "mydb")
        uri = Config.get_mysql_uri()
        assert uri.startswith("mysql+pymysql://user:pass@localhost:3306/mydb")
