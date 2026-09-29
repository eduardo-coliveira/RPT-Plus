"""Send supported source languages to Judge0."""

import requests

JUDGE0_URL = "https://ce.judge0.com/submissions"
LANGUAGE_CONFIGS = {
    "java": {"language_id": 62, "name": "java", "version": "13.0.1"},
    "csharp": {"language_id": 51, "name": "csharp", "version": "6.6.0.161"},
}


def submit_to_judge0(source_code: str, language: str = "java"):
    """Submit source code using its configured Judge0 language."""

    language_config = LANGUAGE_CONFIGS.get(language)
    if language_config is None:
        raise ValueError(f"Unsupported language: {language}")

    response = requests.post(
        f"{JUDGE0_URL}?wait=true",
        json={
            "language_id": language_config["language_id"],
            "source_code": source_code,
            "stdin": "",
            "expected_output": None,
        },
    )
    response.raise_for_status()
    return response.json()