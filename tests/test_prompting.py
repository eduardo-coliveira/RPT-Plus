from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.prompting import LLMClientWrapper, LLMConfig
from backend.schemas import RefactoringSteps


def make_client(create):
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create),
        ),
    )


def test_call_renders_prompt_without_mutating_input_data():
    response = object()
    create = Mock(return_value=response)
    config = LLMConfig(api_key="test-key", model="test-model", max_tokens=512)
    wrapper = LLMClientWrapper(make_client(create), config)
    prompt_data = {
        "previous_code": "return true;",
        "submitted_code": "return false;",
    }
    original_prompt_data = prompt_data.copy()

    result = wrapper.call("PRESENT", prompt_data, max_tokens=128)

    assert result is response
    assert prompt_data == original_prompt_data
    call_args = create.call_args.kwargs
    assert call_args["model"] == "test-model"
    assert call_args["response_model"] is RefactoringSteps
    assert call_args["max_tokens"] == 128
    assert "return true;" in call_args["messages"][1]["content"]
    assert "return false;" in call_args["messages"][1]["content"]
    assert "present_refactorings" in call_args["messages"][1]["content"]


def test_call_rejects_unknown_prompt_type_without_calling_client():
    create = Mock()
    wrapper = LLMClientWrapper(
        make_client(create),
        LLMConfig(api_key="test-key", model="test-model"),
    )

    with pytest.raises(ValueError, match="Unknown prompt_type: UNKNOWN"):
        wrapper.call("UNKNOWN", {})

    create.assert_not_called()


def test_llm_config_reads_environment_without_exposing_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-secret")
    monkeypatch.setenv("MISTRAL_MODEL", "test-model")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")

    config = LLMConfig.from_env()

    assert config.api_key == "test-secret"
    assert config.model == "test-model"
    assert config.max_tokens == 256
    assert "test-secret" not in repr(config)


def test_llm_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    with pytest.raises(ValueError, match="MISTRAL_API_KEY is required"):
        LLMConfig.from_env()