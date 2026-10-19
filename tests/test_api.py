import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend import app as api
from backend.routers import actions, auth, exercises, static
from backend.services import diagnosis, judge0
from backend.schemas import SimpleError, StepErrorFeedback, SuggestedRefactoringWithHints


def test_exercise_loader_works_from_a_different_working_directory(monkeypatch, tmp_path):
    expected_exercises = exercises.load_exercise_catalog()
    monkeypatch.chdir(tmp_path)

    assert exercises.load_exercise_catalog() == expected_exercises


def _stub_judge0(monkeypatch, result=None, error=None):
    judge0_response = Mock()
    judge0_response.raise_for_status.return_value = None
    judge0_response.json.return_value = result
    judge0_post = Mock(side_effect=error) if error is not None else Mock(return_value=judge0_response)
    monkeypatch.setattr(judge0.requests, "post", judge0_post)
    return judge0_post


def _first_exercise(client):
    return next(iter(client.app.state.exercises.values()))


def test_list_exercises_returns_ids_and_descriptions(client):
    response = client.get("/exercises")

    assert response.status_code == 200
    assert response.json() == [
        {"id": exercise.id, "description": exercise.description, "language": exercise.language}
        for exercise in client.app.state.exercises.values()
    ]


def test_python_exercise_alias_returns_same_summaries(client):
    response = client.get("/exercises_python")

    assert response.status_code == 200
    assert response.json() == client.get("/exercises").json()


def test_get_exercise_returns_known_exercise(client):
    exercise_id = next(iter(client.app.state.exercises))

    response = client.get(f"/exercise/{exercise_id}")

    assert response.status_code == 200
    assert response.json() == client.app.state.exercises[exercise_id].model_dump()


def test_list_exercises_filters_by_language(client):
    response = client.get("/exercises?language=csharp")

    assert response.status_code == 200
    assert response.json()
    assert {exercise["language"] for exercise in response.json()} == {"csharp"}


def test_get_exercise_returns_404_for_unknown_id(client):
    response = client.get("/exercise/unknown-test-exercise")

    assert response.status_code == 404
    assert response.json() == {"detail": "Exercise not found"}


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/diagnose", {"submitted_code": "code"}),
        ("/hint_tree", {"submitted_code": "code", "hint_group": "group-a"}),
        ("/correct_feedback", {"submitted_code": "code"}),
        ("/notequiv_feedback", {"submitted_code": "code"}),
    ],
)
def test_exercise_routes_return_same_404_for_unknown_id(client, path, payload):
    response = client.post(path, json={"exercise_id": "missing-exercise", **payload})

    assert response.status_code == 404
    assert response.json() == {"detail": "Exercise not found"}


def test_login_rejects_invalid_credentials(client, monkeypatch):
    monkeypatch.setattr(auth, "authenticate_user_credentials", lambda username, password, config: None)

    response = client.post("/login", json={"username": "learner", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_login_claims_session_and_rejects_duplicate_login(client, monkeypatch):
    monkeypatch.setattr(
        auth,
        "authenticate_user_credentials",
        lambda username, password, config: {"username": username, "group_name": "group-a"},
    )

    payload = {"username": "learner", "password": "correct"}
    first_response = client.post("/login", json=payload)
    duplicate_response = client.post("/login", json=payload)

    assert first_response.status_code == 200
    assert first_response.json()["username"] == "learner"
    assert first_response.json()["group"] == "group-a"
    assert first_response.json()["session_token"]
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "This user is already logged in elsewhere."}


def test_special_user_can_have_multiple_concurrent_sessions(client, monkeypatch):
    authenticator = Mock(side_effect=AssertionError("Special login must not query the database"))
    monkeypatch.setattr(auth, "authenticate_user_credentials", authenticator)
    payload = {"username": auth.SPECIAL_USERNAME, "password": auth.SPECIAL_PASSWORD}

    first_response = client.post("/login", json=payload)
    second_response = client.post("/login", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["username"] == auth.SPECIAL_USERNAME
    assert first_response.json()["group"] == "STATE-BASED"
    assert first_response.json()["session_token"] != second_response.json()["session_token"]
    assert client.app.state.active_user_sessions == {}
    assert len(client.app.state.authenticated_sessions) == 2
    authenticator.assert_not_called()


def test_special_user_rejects_incorrect_password(client, monkeypatch):
    authenticator = Mock(side_effect=AssertionError("Special login must not query the database"))
    monkeypatch.setattr(auth, "authenticate_user_credentials", authenticator)

    response = client.post("/login", json={"username": auth.SPECIAL_USERNAME, "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    authenticator.assert_not_called()


def test_prefixed_assets_are_served_as_static_files_not_html(client):
    assets_dir = Path(static.DIST_DIR) / "assets"
    asset = next((p for p in assets_dir.glob("*.js")), None) if assets_dir.is_dir() else None
    if asset is None:
        pytest.skip("Frontend is not built")

    prefixed = client.get(f"/rpt-plus/assets/{asset.name}")
    plain = client.get(f"/assets/{asset.name}")

    assert prefixed.status_code == 200
    assert "javascript" in prefixed.headers["content-type"]
    assert prefixed.content == plain.content


def test_prefixed_api_routes_match_unprefixed_routes(client, monkeypatch):
    log_entry = Mock(return_value=True)
    monkeypatch.setattr(actions, "record_action_log", log_entry)

    login_response = client.post("/rpt-plus/login", json={"username": "st000", "password": "000000"})
    token = login_response.json()["session_token"]
    action_response = client.post(
        "/rpt-plus/log_action",
        json={"username": "st000", "exercise": "0.isOvenReady", "current_code": "code", "action": "Diagnose"},
        headers={"X-Session-Token": token},
    )

    assert login_response.status_code == 200
    assert action_response.status_code == 200
    assert client.get("/rpt-plus/exercises").json() == client.get("/exercises").json()
    log_entry.assert_not_called()


def test_login_sessions_are_isolated_between_app_instances(client, monkeypatch):
    monkeypatch.setattr(
        auth,
        "authenticate_user_credentials",
        lambda username, password, config: {"username": username, "group_name": "group-a"},
    )
    second_app = api.create_app()

    with TestClient(second_app) as second_client:
        first_response = client.post("/login", json={"username": "learner", "password": "correct"})
        second_response = second_client.post("/login", json={"username": "learner", "password": "correct"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert client.app.state.active_user_sessions == {"learner": next(iter(client.app.state.active_user_sessions.values()))}
    assert second_app.state.active_user_sessions == {"learner": next(iter(second_app.state.active_user_sessions.values()))}


def test_logout_removes_only_the_matching_active_session(client):
    response = client.post("/login", json={"username": "st000", "password": "000000"})
    token = response.json()["session_token"]
    client.app.state.authenticated_sessions["other-token"] = ("st000", time.time())

    logout_response = client.post(
        "/logout",
        json={"username": "st000", "session_token": token},
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {"message": "User st000 logged out"}
    assert token not in client.app.state.authenticated_sessions
    assert "other-token" in client.app.state.authenticated_sessions


def test_log_action_returns_ok_when_database_write_succeeds(client, monkeypatch):
    log_entry = Mock(return_value=True)
    monkeypatch.setattr(actions, "record_action_log", log_entry)
    payload = {
        "username": "learner",
        "exercise": "0.isOvenReady",
        "current_code": "return true;",
        "action": "Diagnose",
        "previous_code": "return false;",
        "code_status": "correct",
        "feedback": "Looks good",
        "hint_tree": '{"Tree": []}',
    }
    created_at = time.time()
    client.app.state.active_user_sessions["learner"] = created_at
    client.app.state.authenticated_sessions["learner-token"] = ("learner", created_at)

    response = client.post(
        "/log_action",
        json=payload,
        headers={"X-Session-Token": "learner-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    log_entry.assert_called_once_with(**payload, config=client.app.state.database_config)


def test_log_action_returns_500_when_database_write_fails(client, monkeypatch):
    monkeypatch.setattr(actions, "record_action_log", Mock(return_value=False))
    created_at = time.time()
    client.app.state.active_user_sessions["learner"] = created_at
    client.app.state.authenticated_sessions["learner-token"] = ("learner", created_at)

    response = client.post(
        "/log_action",
        json={
            "username": "learner",
            "exercise": "0.isOvenReady",
            "current_code": "code",
            "action": "Diagnose",
        },
        headers={"X-Session-Token": "learner-token"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to log action"}


def test_special_user_action_is_not_logged(client, monkeypatch):
    log_entry = Mock()
    monkeypatch.setattr(actions, "record_action_log", log_entry)
    login_response = client.post("/login", json={"username": "st000", "password": "000000"})

    response = client.post(
        "/log_action",
        json={
            "username": "st000",
            "exercise": "0.isOvenReady",
            "current_code": "return true;",
            "action": "Diagnose",
        },
        headers={"X-Session-Token": login_response.json()["session_token"]},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    log_entry.assert_not_called()


def test_log_action_requires_a_valid_session_and_rejects_identity_spoofing(client, monkeypatch):
    log_entry = Mock(return_value=True)
    monkeypatch.setattr(actions, "record_action_log", log_entry)
    monkeypatch.setattr(
        auth,
        "authenticate_user_credentials",
        lambda username, password, config: {"username": username, "group_name": "group-a"},
    )
    missing_session_response = client.post(
        "/log_action",
        json={
            "username": "st000",
            "exercise": "0.isOvenReady",
            "current_code": "code",
            "action": "Diagnose",
        },
    )

    login_response = client.post("/login", json={"username": "learner", "password": "correct"})
    mismatch_response = client.post(
        "/log_action",
        json={
            "username": "st000",
            "exercise": "0.isOvenReady",
            "current_code": "code",
            "action": "Diagnose",
        },
        headers={"X-Session-Token": login_response.json()["session_token"]},
    )

    assert missing_session_response.status_code == 401
    assert mismatch_response.status_code == 403
    log_entry.assert_not_called()


def test_run_code_translates_mocked_judge0_response(client, monkeypatch):
    judge0_response = Mock()
    judge0_response.json.return_value = {
        "exit_code": 0,
        "stdout": "result\n",
        "stderr": "runtime output",
        "compile_output": "compiler output",
    }
    judge0_post = Mock(return_value=judge0_response)
    monkeypatch.setattr(judge0.requests, "post", judge0_post)

    response = client.post("/run_code", json={"code": "public class Main {}"})

    assert response.status_code == 200
    assert response.json() == {
        "language": "csharp",
        "version": "6.6.0.161",
        "run": {
            "code": 0,
            "signal": None,
            "output": "result\n",
            "stderr": "compiler output",
        },
    }
    judge0_post.assert_called_once_with(
        f"{judge0.JUDGE0_URL}?wait=true",
        json={
            "language_id": 51,
            "source_code": "public class Main {}",
            "stdin": "",
            "expected_output": None,
        },
    )


def test_correct_feedback_uses_stubbed_llm(client, monkeypatch):
    llm = Mock()
    llm.request_structured_response.return_value = SimpleNamespace(
        present_refactorings=False,
        steps=[],
        general_feedback="No structural changes were found.",
    )
    monkeypatch.setattr(client.app.state, "client_wrapper", llm)
    exercise_id = next(iter(client.app.state.exercises))

    response = client.post(
        "/correct_feedback",
        json={"exercise_id": exercise_id, "submitted_code": "public static void run() {}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "present_refactorings": False,
        "refactor_steps": [],
        "general_feedback": "No structural changes were found.",
    }
    llm.request_structured_response.assert_called_once()
    assert llm.request_structured_response.call_args.args[0] == "PRESENT"
    assert llm.request_structured_response.call_args.args[1] == {
        "submitted_code": "public static void run() {}",
        "previous_code": "",
        "method_explanation": client.app.state.exercises[exercise_id].description,
        "language": "C#",
    }


def test_diagnose_reports_compile_errors_from_judge0(client, monkeypatch):
    _stub_judge0(
        monkeypatch,
        {
            "status": {"id": 6},
            "compile_output": "cannot find symbol",
            "stderr": "runtime output",
        },
    )

    response = client.post(
        "/diagnose",
        json={"exercise_id": _first_exercise(client).id, "submitted_code": "public class Program {}"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "compile_error", "message": "cannot find symbol"}


def test_diagnose_reports_the_first_failing_test(client, monkeypatch):
    exercise = _first_exercise(client)
    _stub_judge0(
        monkeypatch,
        {
            "status": {"id": 3},
            "stdout": "TEST_RESULT:0|expected=false|actual=true",
        },
    )

    response = client.post(
        "/diagnose",
        json={"exercise_id": _first_exercise(client).id, "submitted_code": "public class Program {}"},
    )

    assert response.json() == {
        "status": "notequiv",
            "call": f'{exercise.call_method}({", ".join(map(str, exercise.tests[0].inputs))})',
        "expected": "false",
        "actual": "true",
        "reason": "Expected false, got true",
    }


def test_diagnose_accepts_all_matching_test_results_and_sends_generated_program(client, monkeypatch):
    exercise = _first_exercise(client)
    submitted_code = "public static bool isOvenReady(int temperature) { return true; }"
    stdout = "\n".join(
        f"TEST_RESULT:{index}|expected={test.expected}|actual={test.expected}"
        for index, test in enumerate(exercise.tests)
    )
    judge0_post = _stub_judge0(
        monkeypatch,
        {"status": {"id": 3}, "stdout": stdout},
    )

    response = client.post(
        "/diagnose",
        json={"exercise_id": exercise.id, "submitted_code": submitted_code},
    )

    assert response.json() == {"status": "correct"}
    judge0_post.assert_called_once_with(
        f"{judge0.JUDGE0_URL}?wait=true",
        json={
            "language_id": 51,
            "source_code": diagnosis.build_execution_harness(submitted_code, exercise),
            "stdin": "",
            "expected_output": None,
        },
    )


def test_run_code_supports_csharp_and_reports_runtime_metadata(client, monkeypatch):
    judge0_post = _stub_judge0(monkeypatch, {"exit_code": 0, "stdout": "ok", "stderr": ""})

    response = client.post("/run_code", json={"code": "public class Program {}", "language": "csharp"})

    assert response.json()["language"] == "csharp"
    assert response.json()["version"] == "6.6.0.161"
    assert judge0_post.call_args.kwargs["json"]["language_id"] == 51


def test_diagnose_builds_and_submits_csharp_harness(client, monkeypatch):
    exercise = next(item for item in client.app.state.exercises.values() if item.language == "csharp")
    judge0_post = _stub_judge0(monkeypatch, {"status": {"id": 3}, "stdout": "TEST_RESULT:0|expected=false|actual=false"})

    response = client.post(
        "/diagnose",
        json={"exercise_id": exercise.id, "submitted_code": exercise.start_method},
    )

    assert response.json() == {"status": "correct"}
    submitted = judge0_post.call_args.kwargs["json"]
    assert submitted["language_id"] == 51
    assert "public class Program" in submitted["source_code"]
    assert "public static void Main(string[] args)" in submitted["source_code"]
    assert "System.Console.WriteLine" in submitted["source_code"]


@pytest.mark.parametrize(
    "stdout",
    ["TEST_RESULT:invalid", "compiler produced no test output"],
    ids=["malformed-result", "missing-results"],
)
def test_diagnose_reports_unusable_test_output(client, monkeypatch, stdout):
    _stub_judge0(
        monkeypatch,
        {"status": {"id": 3}, "stdout": stdout, "stderr": "execution details"},
    )

    response = client.post(
        "/diagnose",
        json={"exercise_id": _first_exercise(client).id, "submitted_code": "public class Program {}"},
    )

    assert response.json() == {
        "status": "notequiv",
        "reason": "execution details",
        "expected": "N/A",
        "actual": "N/A",
    }


def test_diagnose_returns_error_when_judge0_request_fails(client, monkeypatch):
    _stub_judge0(monkeypatch, error=RuntimeError("Judge0 unavailable"))

    response = client.post(
        "/diagnose",
        json={"exercise_id": _first_exercise(client).id, "submitted_code": "public class Program {}"},
    )

    assert response.json() == {"status": "error", "message": "Judge0 unavailable"}


def test_hint_tree_passes_prompt_fields_to_llm_and_returns_tree(client, monkeypatch):
    exercise_id = _first_exercise(client).id
    suggestion = SuggestedRefactoringWithHints(
        title="Use a range check",
        suggestion="Express the boundaries directly.",
        reason="The condition is easier to scan.",
        target_code="if (temperature >= 150 && temperature <= 250)",
        refactored_code="return temperature >= 150 && temperature <= 250;",
        general_hint="Look at how the bounds are expressed.",
        targeted_hint="Can the condition be returned directly?",
    )
    llm = Mock()
    llm.request_structured_response.return_value = SimpleNamespace(suggestions=[suggestion])
    monkeypatch.setattr(client.app.state, "client_wrapper", llm)

    response = client.post(
        "/hint_tree",
        json={
            "exercise_id": exercise_id,
            "submitted_code": "public static bool isOvenReady(int temperature) {}",
            "previous_code": "previous version",
            "hint_group": "group-a",
            "code_diagnosis": "correct",
            "username": "learner",
        },
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "correct"
    hint_node = response_data["hint_tree"]["Tree"][2][0]["Tree"]
    assert hint_node[0] == "Look at how the bounds are expressed."
    assert hint_node[2][0]["Tree"][0] == "Can the condition be returned directly?"
    assert hint_node[5]["title"] == "Use a range check"
    llm.request_structured_response.assert_called_once_with(
        "SUGGESTED",
        {
            "submitted_code": "public static bool isOvenReady(int temperature) {}",
            "previous_code": "previous version",
            "method_explanation": client.app.state.exercises[exercise_id].description,
            "language": "C#",
            "hint_group": "group-a",
        },
    )


@pytest.mark.parametrize(
    ("hint_group", "prompt_type", "test_case_failure"),
    [
        ("STATE-BASED", "ERROR", "Expected false but got true."),
        ("STEP-BASED", "STEP_ERROR", "A test failed."),
    ],
)
def test_notequiv_feedback_selects_llm_prompt_and_failure_text(
    client, monkeypatch, hint_group, prompt_type, test_case_failure
):
    llm = Mock()
    if prompt_type == "STEP_ERROR":
        llm.request_structured_response.return_value = StepErrorFeedback(
            classification="Refactoring misconception",
            incorrect_code="if (condition1 && condition2) {}",
            previous_code="if (condition1) {} else {}",
            explanation="The else branch was lost.",
            failed_test="The false condition skips the required branch.",
            fix_suggestion="Preserve the else behavior when simplifying the conditions.",
        )
    else:
        llm.request_structured_response.return_value = SimpleError(
            classification="Refactoring misconception",
            incorrect_code="if (condition1 && condition2) {}",
            failed_test="The false condition skips the required branch.",
            fix_suggestion="Preserve the else behavior when simplifying the conditions.",
        )
    monkeypatch.setattr(client.app.state, "client_wrapper", llm)
    payload = {
        "exercise_id": _first_exercise(client).id,
        "submitted_code": "public static bool isOvenReady(int temperature) {}",
        "previous_code": "previous version",
        "hint_group": hint_group,
    }
    if hint_group == "STATE-BASED":
        payload["test_case_failure"] = test_case_failure

    response = client.post("/notequiv_feedback", json=payload)

    assert response.status_code == 200
    assert response.json()["classification"] == "Refactoring misconception"
    assert response.json()["incorrect_code"] == "if (condition1 && condition2) {}"
    assert ("explanation" in response.json()) == (prompt_type == "STEP_ERROR")
    llm.request_structured_response.assert_called_once_with(
        prompt_type,
        {
            "previous_code": "previous version",
            "submitted_code": "public static bool isOvenReady(int temperature) {}",
            "test_case_failure": test_case_failure,
            "method_explanation": _first_exercise(client).description,
            "language": "C#",
        },
    )


def test_hint_tree_returns_server_error_when_llm_fails(client, monkeypatch):
    llm = Mock()
    llm.request_structured_response.side_effect = RuntimeError("LLM unavailable")
    monkeypatch.setattr(client.app.state, "client_wrapper", llm)

    response = client.post(
        "/hint_tree",
        json={"exercise_id": _first_exercise(client).id, "submitted_code": "code", "hint_group": "group-a"},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "LLM unavailable"}