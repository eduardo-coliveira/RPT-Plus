import time
from threading import RLock
from typing import Dict

from fastapi import APIRouter, HTTPException, Request

from backend.database import authenticate_user
from backend.schemas import LoginRequest, LogoutRequest

LOGIN_LOCK_TTL_SECONDS = 2400

router = APIRouter()


def claim_user_session(username: str, sessions: Dict[str, float], user_lock) -> bool:
    with user_lock:
        now = time.time()
        prune_expired_user_sessions(now, sessions)
        if username in sessions:
            print(f"User {username} already logged in")
            return False
        sessions[username] = now
        print(f"Added user {username} to sessions: {sessions}")
        return True


def prune_expired_user_sessions(now: float, sessions: Dict[str, float]) -> None:
    expired_users = [
        username for username, locked_at in sessions.items()
        if now - locked_at >= LOGIN_LOCK_TTL_SECONDS
    ]
    for username in expired_users:
        sessions.pop(username, None)


@router.post("/login")
async def login(data: LoginRequest, request: Request):
    user = authenticate_user(
        data.username,
        data.password,
        request.app.state.database_config,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not claim_user_session(
        user["username"],
        request.app.state.active_user_sessions,
        request.app.state.user_lock,
    ):
        raise HTTPException(status_code=409, detail="This user is already logged in elsewhere.")

    return {"username": user["username"], "group": user["group_name"]}


@router.post("/logout")
async def logout(data: LogoutRequest, request: Request):
    username = data.username
    print(f"Logout request for user: {username}")
    with request.app.state.user_lock:
        request.app.state.active_user_sessions.pop(username, None)
    return {"message": f"User {username} logged out"}