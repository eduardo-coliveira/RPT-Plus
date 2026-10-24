"""Send supported source languages to Judge0."""

import time

import requests

JUDGE0_URL = "https://ce.judge0.com/submissions"
LANGUAGE_CONFIGS = {
    "java": {"language_id": 62, "name": "java", "version": "13.0.1"},
    "csharp": {"language_id": 51, "name": "csharp", "version": "6.6.0.161"},
}
# (connect, read) seconds; the read timeout covers Judge0 compiling and running the code.
REQUEST_TIMEOUT_SECONDS = (5, 20)
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# One session keeps the HTTPS connection to Judge0 open between submissions.
session = requests.Session()


class Judge0TimeoutError(Exception):
    """Judge0 did not answer in time."""


class Judge0UnavailableError(Exception):
    """Judge0 could not be reached or kept failing."""


def submit_to_judge0(source_code: str, language: str = "java"):
    """Submit source code using its configured Judge0 language."""

    language_config = LANGUAGE_CONFIGS.get(language)
    if language_config is None:
        raise ValueError(f"Unsupported language: {language}")

    payload = {
        "language_id": language_config["language_id"],
        "source_code": source_code,
        "stdin": "",
        "expected_output": None,
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == MAX_ATTEMPTS
        try:
            response = session.post(
                f"{JUDGE0_URL}?wait=true",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout as error:
            if is_last_attempt:
                raise Judge0TimeoutError("Judge0 timed out") from error
        except requests.ConnectionError as error:
            if is_last_attempt:
                raise Judge0UnavailableError("Judge0 could not be reached") from error
        else:
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response.json()
            if is_last_attempt:
                raise Judge0UnavailableError(f"Judge0 returned status {response.status_code}")
        time.sleep(RETRY_DELAY_SECONDS)
