import os
from types import SimpleNamespace

os.environ.update(
    {
        "DB_HOST": "test",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_NAME": "test",
        "MISTRAL_API_KEY": "test-key",
    }
)

import pytest
from fastapi.testclient import TestClient

from backend import app as api
from backend.routers import actions, auth
from backend.services import judge0


def _unexpected_external_call(*args, **kwargs):
    pytest.fail("Stub external services explicitly in tests")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "init_db", lambda config: None)
    monkeypatch.setattr(
        api,
        "get_client_wrapper",
        lambda config: SimpleNamespace(call=_unexpected_external_call),
    )
    monkeypatch.setattr(auth, "authenticate_user", _unexpected_external_call)
    monkeypatch.setattr(actions, "log_action_entry", _unexpected_external_call)
    monkeypatch.setattr(judge0.requests, "post", _unexpected_external_call)
    test_app = api.create_app()
    with TestClient(test_app) as test_client:
        yield test_client