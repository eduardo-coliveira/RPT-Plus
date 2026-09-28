"""Set up prompts and the LLM client."""

from dataclasses import dataclass, field
from typing import Type, get_args, get_origin
from pydantic import BaseModel
# Monkey patch mistralai to provide top-level Mistral import for instructor compatibility
import mistralai
from mistralai.client import Mistral as RealMistral
mistralai.Mistral = RealMistral
from mistralai import Mistral

import instructor
import os
from backend.prompts import (
    error_system_prompt,
    error_user_prompt,
    present_rf_system_prompt,
    present_rf_user_prompt,
    step_based_error_system_prompt,
    step_based_error_user_prompt,
    suggested_rf_system_prompt,
    suggested_rf_user_prompt,
)
from backend.schemas import RefactoringSteps, SimpleError, SuggestedRefactoringsWithHints


@dataclass(frozen=True)
class PromptDefinition:
    """Store a prompt template and its response model."""

    system_prompt: str
    user_prompt_template: str
    response_model: Type[BaseModel]


@dataclass(frozen=True)
class LLMConfig:
    """Settings for the LLM client."""

    api_key: str = field(repr=False)
    model: str
    max_tokens: int = 1000

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Build LLM settings from the environment."""

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is required")

        try:
            max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))
        except ValueError as error:
            raise ValueError("LLM_MAX_TOKENS must be an integer") from error
        if max_tokens <= 0:
            raise ValueError("LLM_MAX_TOKENS must be positive")

        return cls(
            api_key=api_key,
            model=os.getenv("MISTRAL_MODEL", "mistral-large-2512"),
            max_tokens=max_tokens,
        )


PROMPT_DEFINITIONS = {
    "ERROR": PromptDefinition(error_system_prompt, error_user_prompt, SimpleError),
    "PRESENT": PromptDefinition(present_rf_system_prompt, present_rf_user_prompt, RefactoringSteps),
    "SUGGESTED": PromptDefinition(
        suggested_rf_system_prompt,
        suggested_rf_user_prompt,
        SuggestedRefactoringsWithHints,
    ),
    "STEP_ERROR": PromptDefinition(
        step_based_error_system_prompt,
        step_based_error_user_prompt,
        SimpleError,
    ),
}

class StructuredOutputClient:
    """Render prompts and request model responses."""

    def __init__(self, client, config: LLMConfig):
        self.client = client
        self.config = config
        self.prompt_definitions = PROMPT_DEFINITIONS

    def request_structured_response(self, prompt_type: str, prompt_data: dict, temperature: float = 0.0, max_tokens: int | None = None, **kwargs) -> BaseModel:
        """Send a named prompt and return its parsed response."""

        definition = self.prompt_definitions.get(prompt_type)
        if definition is None:
            raise ValueError(f"Unknown prompt_type: {prompt_type}")

        prompt_template_values = dict(prompt_data)
        prompt_template_values["fields"] = describe_model_fields(definition.response_model)

        token_budget = max_tokens if max_tokens is not None else self.config.max_tokens

        completion_arguments = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": definition.system_prompt},
                {"role": "user", "content": definition.user_prompt_template.format(**prompt_template_values)},
            ],
            "response_model": definition.response_model,
            "temperature": temperature,
            "max_tokens": token_budget,
            **kwargs
        }

        model_response = self.client.chat.completions.create(**completion_arguments)
        # print(response)
        return model_response

def create_llm_client(config: LLMConfig):
    """Create the LLM client used by the application."""

    client = instructor.from_mistral(
        Mistral(api_key=config.api_key),
        mode=instructor.Mode.MISTRAL_STRUCTURED_OUTPUTS,
    )
    return StructuredOutputClient(client, config)


def describe_model_fields(model: Type[BaseModel], indent: int = 0) -> str:
    """Describe a response model's fields for a prompt."""

    lines = []
    prefix = "  " * indent
    for field_name, field in model.model_fields.items():
        field_type = field.annotation
        description = field.description

        origin = get_origin(field_type)
        args = get_args(field_type)

        # Case 1: Nested BaseModel
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            lines.append(f"{prefix}- {field_name}: (object) {description}")
            lines.append(describe_model_fields(field_type, indent + 1))

        # Case 2: List of BaseModel
        elif origin is list and args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
            lines.append(f"{prefix}- {field_name}: (list of objects) {description}")
            lines.append("     Each element should include:")
            lines.append(describe_model_fields(args[0], indent + 1))

        # Case 3: Simple field
        else:
            lines.append(f"{prefix}- {field_name}: {description}")

    return "\n".join(lines)


# Compatibility aliases for the excluded run_notequiv_feedback.py script.
LLMClientWrapper = StructuredOutputClient
get_client_wrapper = create_llm_client

