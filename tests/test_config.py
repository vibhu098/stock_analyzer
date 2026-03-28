"""Basic tests for the application."""

import pytest
from src.config import settings


def test_settings_loaded():
    """Test that settings are loaded correctly."""
    assert settings is not None
    assert settings.redis_host == "localhost"


def test_redis_url_generation():
    """Test Redis URL generation without password."""
    url = settings.redis_url
    assert "localhost" in url
    assert "6379" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
