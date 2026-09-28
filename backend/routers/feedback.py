"""Routes for hints and refactoring feedback."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.routers.exercises import find_exercise_or_404
from backend.schemas import DiagnoseRequest, HintRequest
from backend.services.feedback import (
    build_prompt_context,
    build_hint_tree,
    generate_non_equivalence_feedback,
)

router = APIRouter()


@router.post("/hint_tree")
async def generate_hint_tree(request_data: HintRequest, request: Request):
    """Generate hints for the submitted code and exercise."""

    exercise = find_exercise_or_404(request_data.exercise_id, request.app.state.exercises)

    try:
        prompt_data = build_prompt_context(request_data, exercise)
        prompt_data["hint_group"] = request_data.hint_group
        suggested = request.app.state.client_wrapper.request_structured_response("SUGGESTED", prompt_data)

        tree = build_hint_tree([suggestion.model_dump() for suggestion in suggested.suggestions])
        return {
            "status": "correct",
            "hint_tree": tree,
            "suggestions": suggested.suggestions,
        }
    except Exception as error:
        return JSONResponse(status_code=500, content={"error": str(error)})


@router.post("/correct_feedback")
async def generate_refactoring_feedback(request_data: DiagnoseRequest, request: Request):
    """Generate refactoring feedback for submitted code."""

    exercise = find_exercise_or_404(request_data.exercise_id, request.app.state.exercises)

    try:
        prompt_data = build_prompt_context(request_data, exercise)
        present = request.app.state.client_wrapper.request_structured_response("PRESENT", prompt_data)
        return {
            "present_refactorings": present.present_refactorings,
            "refactor_steps": present.steps,
            "general_feedback": present.general_feedback,
        }
    except Exception as error:
        return {"error": str(error)}


@router.post("/notequiv_feedback")
async def generate_non_equivalence_feedback_response(request_data: DiagnoseRequest, request: Request):
    """Explain why a submission changed behavior."""

    exercise = find_exercise_or_404(request_data.exercise_id, request.app.state.exercises)

    try:
        return generate_non_equivalence_feedback(request_data, exercise, request.app.state.client_wrapper)
    except Exception as error:
        return {"error": str(error)}