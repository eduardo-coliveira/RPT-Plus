import requests

JUDGE0_URL = "https://ce.judge0.com/submissions"


def submit_to_judge0(source_code: str):
    response = requests.post(
        f"{JUDGE0_URL}?wait=true",
        json={
            "language_id": 62,
            "source_code": source_code,
            "stdin": "",
            "expected_output": None,
        },
    )
    response.raise_for_status()
    return response.json()