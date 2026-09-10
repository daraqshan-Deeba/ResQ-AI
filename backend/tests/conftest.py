import pytest

from app.main import app


@pytest.fixture(autouse=True)
def disable_supabase_for_tests(monkeypatch):
    """Keep unit tests on Firebase mocks unless explicitly testing Supabase."""
    monkeypatch.setattr("app.services.supabase_service.supabase_available", False)
    monkeypatch.setattr("app.services.supabase_service.client", None)


@pytest.fixture(autouse=True)
def disable_firebase_for_tests(monkeypatch):
    """Isolate tests from live Firebase credentials in developer .env."""
    monkeypatch.setattr("app.services.firebase_service.firebase_available", False)
    monkeypatch.setattr("app.services.firebase_service.db", None)
    monkeypatch.setattr(
        "app.services.firebase_service.firebase_error_detail",
        "Firebase disabled for tests",
    )


@pytest.fixture
def client():
    return app.test_client()
