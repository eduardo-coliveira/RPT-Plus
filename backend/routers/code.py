from fastapi import APIRouter, Request

from backend.routers.exercises import get_exercise_or_404
from backend.schemas import CodeRequest, DiagnoseRequest
from backend.services.diagnosis import (
    build_java_program,
    generate_test_code,
    interpret_diagnosis_result,
)
from backend.services.judge0 import submit_to_judge0

router = APIRouter()


@router.post("/run_code")
async def run_code(data: CodeRequest):
    try:
        result = submit_to_judge0(data.code)
        error_output = result.get("compile_output", "") or result.get("stderr", "")

        return {
            "language": "java",
            "version": "17.0.4",
            "run": {
                "code": result.get("exit_code", 1),
                "signal": None,
                "output": result.get("stdout", ""),
                "stderr": error_output,
            },
        }
    except Exception as error:
        return {"error": str(error)}


@router.post("/diagnose")
async def diagnose(data: DiagnoseRequest, request: Request):
    exercise = get_exercise_or_404(data.exercise_id, request.app.state.exercises)
    full_code = build_java_program(
        data.submitted_code,
        generate_test_code(exercise["call_method"], exercise["result_type"], exercise["tests"]),
    )

    try:
        result = submit_to_judge0(full_code)
        return interpret_diagnosis_result(result, exercise)
    except Exception as error:
        return {"status": "error", "message": str(error)}