"""Routes for recording learner actions."""

from fastapi import APIRouter, HTTPException, Request

from backend.database import record_action_log
from backend.routers.auth import SPECIAL_USERNAME, authenticated_session
from backend.schemas import ActionLogRequest

router = APIRouter()


@router.post("/log_action")
async def log_action(request_data: ActionLogRequest, request: Request):
    """Record a learner action and return a success response."""

    session = authenticated_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="A valid login session is required")
    username = session.username
    if request_data.username != username:
        raise HTTPException(status_code=403, detail="Action username does not match the login session")
    if username == SPECIAL_USERNAME:
        return {"status": "ok"}

    success = record_action_log(
        user_id=session.user_id,
        exercise=request_data.exercise,
        current_code=request_data.current_code,
        action=request_data.action,
        previous_code=request_data.previous_code,
        code_status=request_data.code_status,
        feedback=request_data.feedback,
        hint_tree=request_data.hint_tree,
        last_correct_code=request_data.last_correct_code,
        config=request.app.state.database_config,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to log action")
    return {"status": "ok"}