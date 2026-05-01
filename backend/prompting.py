from typing import Type, get_args, get_origin
from pydantic import BaseModel
# from openai import OpenAI
# Monkey patch mistralai to provide top-level Mistral import for instructor compatibility
import mistralai
from mistralai.client import Mistral as RealMistral
mistralai.Mistral = RealMistral
from mistralai import Mistral

import instructor
import os
from backend.prompts import *
from backend.schemas import *

class LLMClientWrapper:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.system_prompts: dict = {
            "ERROR": error_system_prompt,
            "PRESENT": present_rf_system_prompt,
            "SUGGESTED": suggested_rf_system_prompt,
        }
        self.user_prompt_templates: dict = {
            "ERROR": error_user_prompt,
            "PRESENT": present_rf_user_prompt,
            "SUGGESTED": suggested_rf_user_prompt,
        }
        self.response_models: dict = {
            "ERROR": SimpleError,
            "PRESENT": RefactoringSteps,
            "SUGGESTED": SuggestedRefactoringsWithHints,
        }

    def call(self, prompt_type: str, prompt_data: dict, temperature: float = 0.0, max_tokens=1600, **kwargs) -> BaseModel:
        # Prepare call arguments
        response_model = self.response_models.get(prompt_type)
        if not response_model:
            raise ValueError(f"Unknown prompt_type: {prompt_type}")
        prompt_data["fields"] = describe_model_fields(response_model)
        call_args = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompts.get(prompt_type)},
                {"role": "user", "content": self.user_prompt_templates.get(prompt_type).format(**prompt_data)},
            ],
            "response_model": response_model,
            "temperature": temperature,
            "max_tokens":max_tokens,
            **kwargs
        }

        response = self.client.chat.completions.create(**call_args)
        print(response)
        return response
    
def get_client_wrapper(model: str): 
    # if local: 
    #     client = instructor.from_openai(OpenAI(base_url='http://localhost:11434/v1',api_key='ollama' ),mode=instructor.Mode.JSON)
    # else:
        # client = instructor.from_openai(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")), mode=instructor.Mode.JSON)
    client = instructor.from_mistral(Mistral(api_key=os.environ.get("MISTRAL_API_KEY")), mode=instructor.Mode.MISTRAL_STRUCTURED_OUTPUTS)
    return LLMClientWrapper(client, model)


def describe_model_fields(model: Type[BaseModel], indent: int = 0) -> str:
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

