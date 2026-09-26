from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.routers.exercises import get_exercise_or_404
from backend.schemas import DiagnoseRequest, HintRequest
from backend.services.feedback import (
    build_code_prompt_context,
    build_hint_tree,
    generate_notequiv_feedback,
)

router = APIRouter()


@router.post("/hint_tree")
async def get_hint_tree(data: HintRequest, request: Request):
    exercise = get_exercise_or_404(data.exercise_id, request.app.state.exercises)

    try:
        prompt_data = build_code_prompt_context(data, exercise)
        prompt_data["hint_group"] = data.hint_group
        suggested = request.app.state.client_wrapper.call("SUGGESTED", prompt_data)

        tree = build_hint_tree([suggestion.model_dump() for suggestion in suggested.suggestions])
        return {
            "status": "correct",
            "hint_tree": tree,
            "suggestions": suggested.suggestions,
        }
    except Exception as error:
        return JSONResponse(status_code=500, content={"error": str(error)})


@router.post("/correct_feedback")
async def get_correct_feedback(data: DiagnoseRequest, request: Request):
    exercise = get_exercise_or_404(data.exercise_id, request.app.state.exercises)

    try:
        prompt_data = build_code_prompt_context(data, exercise)
        present = request.app.state.client_wrapper.call("PRESENT", prompt_data)
        return {
            "present_refactorings": present.present_refactorings,
            "refactor_steps": present.steps,
            "general_feedback": present.general_feedback,
        }
    except Exception as error:
        return {"error": str(error)}


@router.post("/notequiv_feedback")
async def get_notequiv_feedback(data: DiagnoseRequest, request: Request):
    exercise = get_exercise_or_404(data.exercise_id, request.app.state.exercises)

    try:
        return generate_notequiv_feedback(data, exercise, request.app.state.client_wrapper)
    except Exception as error:
        return {"error": str(error)}