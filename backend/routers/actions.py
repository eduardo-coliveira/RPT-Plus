from fastapi import APIRouter, HTTPException, Request

from backend.database import log_action_entry
from backend.schemas import ActionLogRequest

router = APIRouter()


@router.post("/log_action")
async def log_action(data: ActionLogRequest, request: Request):
    success = log_action_entry(
        username=data.username,
        exercise=data.exercise,
        current_code=data.current_code,
        action=data.action,
        previous_code=data.previous_code,
        code_status=data.code_status,
        feedback=data.feedback,
        hint_tree=data.hint_tree,
        config=request.app.state.database_config,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to log action")
    return {"status": "ok"}