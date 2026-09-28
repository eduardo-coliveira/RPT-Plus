"""Routes for running and diagnosing submitted code."""

from fastapi import APIRouter, Request

from backend.routers.exercises import find_exercise_or_404
from backend.schemas import CodeRequest, DiagnoseRequest
from backend.services.diagnosis import (
    build_java_execution_harness,
    build_java_test_runner_code,
    interpret_execution_result,
)
from backend.services.judge0 import submit_to_judge0

router = APIRouter()


@router.post("/run_code")
async def execute_code_submission(request_data: CodeRequest):
    """Run submitted code and return its output."""

    try:
        judge_result = submit_to_judge0(request_data.code)
        execution_error_output = judge_result.get("compile_output", "") or judge_result.get("stderr", "")

        return {
            "language": "java",
            "version": "17.0.4",
            "run": {
                "code": judge_result.get("exit_code", 1),
                "signal": None,
                "output": judge_result.get("stdout", ""),
                "stderr": execution_error_output,
            },
        }
    except Exception as error:
        return {"error": str(error)}


@router.post("/diagnose")
async def diagnose_code_submission(request_data: DiagnoseRequest, request: Request):
    """Run an exercise's tests and report the result."""

    exercise = find_exercise_or_404(request_data.exercise_id, request.app.state.exercises)
    full_code = build_java_execution_harness(
        request_data.submitted_code,
        build_java_test_runner_code(exercise["call_method"], exercise["result_type"], exercise["tests"]),
    )

    try:
        judge_result = submit_to_judge0(full_code)
        return interpret_execution_result(judge_result, exercise)
    except Exception as error:
        return {"status": "error", "message": str(error)}