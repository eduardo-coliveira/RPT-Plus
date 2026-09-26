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


def _unexpected_external_call(*args, **kwargs):
    pytest.fail("Stub external services explicitly in tests")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "init_db", lambda: None)
    monkeypatch.setattr(api, "authenticate_user", _unexpected_external_call)
    monkeypatch.setattr(api, "log_action_entry", _unexpected_external_call)
    monkeypatch.setattr(api.requests, "post", _unexpected_external_call)
    monkeypatch.setattr(
        api.app.state,
        "client_wrapper",
        SimpleNamespace(call=_unexpected_external_call),
    )
    with TestClient(api.app) as test_client:
        yield test_client