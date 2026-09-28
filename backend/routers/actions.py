"""Routes for recording learner actions."""

from fastapi import APIRouter, HTTPException, Request

from backend.database import record_action_log
from backend.schemas import ActionLogRequest

router = APIRouter()


@router.post("/log_action")
async def log_action(request_data: ActionLogRequest, request: Request):
    """Record a learner action and return a success response."""

    success = record_action_log(
        username=request_data.username,
        exercise=request_data.exercise,
        current_code=request_data.current_code,
        action=request_data.action,
        previous_code=request_data.previous_code,
        code_status=request_data.code_status,
        feedback=request_data.feedback,
        hint_tree=request_data.hint_tree,
        config=request.app.state.database_config,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to log action")
    return {"status": "ok"}