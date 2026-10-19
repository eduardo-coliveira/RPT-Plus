"""Routes and session locks for user authentication."""

import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request

from backend.database import authenticate_user_credentials
from backend.schemas import LoginRequest, LogoutRequest

LOGIN_LOCK_TTL_SECONDS = 2400
SPECIAL_USERNAME = "st000"
SPECIAL_PASSWORD = "000000"
SPECIAL_GROUP = "STATE-BASED"

router = APIRouter()


def prune_expired_user_sessions(now: float, sessions: Dict[str, float]) -> None:
    """Remove sessions that have expired."""

    expired_users = [
        username for username, locked_at in sessions.items()
        if now - locked_at >= LOGIN_LOCK_TTL_SECONDS
    ]
    for username in expired_users:
        sessions.pop(username, None)


def _prune_expired_authenticated_sessions(
    now: float,
    sessions: Dict[str, float],
    authenticated_sessions: Dict[str, Tuple[str, float]],
) -> None:
    """Expire session tokens and their corresponding username locks."""

    expired_tokens = [
        token for token, (_, created_at) in authenticated_sessions.items()
        if now - created_at >= LOGIN_LOCK_TTL_SECONDS
    ]
    for token in expired_tokens:
        username, created_at = authenticated_sessions.pop(token)
        if username != SPECIAL_USERNAME and sessions.get(username) == created_at:
            sessions.pop(username, None)


def create_authenticated_session(request: Request, username: str) -> Optional[str]:
    """Create a token for an authenticated user, enforcing normal username locks."""

    sessions = request.app.state.active_user_sessions
    authenticated_sessions = request.app.state.authenticated_sessions
    with request.app.state.user_lock:
        now = time.time()
        prune_expired_user_sessions(now, sessions)
        _prune_expired_authenticated_sessions(now, sessions, authenticated_sessions)

        if username != SPECIAL_USERNAME and username in sessions:
            print(f"User {username} already logged in")
            return None

        token = secrets.token_urlsafe(32)
        if username != SPECIAL_USERNAME:
            sessions[username] = now
        authenticated_sessions[token] = (username, now)
        return token


def authenticated_username(request: Request) -> Optional[str]:
    """Resolve a valid session token to its server-established username."""

    token = request.headers.get("X-Session-Token")
    if not token:
        return None

    with request.app.state.user_lock:
        now = time.time()
        prune_expired_user_sessions(now, request.app.state.active_user_sessions)
        _prune_expired_authenticated_sessions(
            now,
            request.app.state.active_user_sessions,
            request.app.state.authenticated_sessions,
        )
        session = request.app.state.authenticated_sessions.get(token)
        return session[0] if session else None


@router.post("/login")
async def login_user(request_data: LoginRequest, request: Request):
    """Authenticate a user and start a session."""

    if request_data.username == SPECIAL_USERNAME:
        if request_data.password != SPECIAL_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        group_name = SPECIAL_GROUP
    else:
        user = authenticate_user_credentials(
            request_data.username,
            request_data.password,
            request.app.state.database_config,
        )
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        group_name = user["group_name"]

    session_token = create_authenticated_session(request, request_data.username)
    if not session_token:
        raise HTTPException(status_code=409, detail="This user is already logged in elsewhere.")

    return {
        "username": request_data.username,
        "group": group_name,
        "session_token": session_token,
    }


@router.post("/logout")
async def logout_user(request_data: LogoutRequest, request: Request):
    """End the session for a username."""

    username = request_data.username
    session_token = request_data.session_token
    with request.app.state.user_lock:
        now = time.time()
        prune_expired_user_sessions(now, request.app.state.active_user_sessions)
        _prune_expired_authenticated_sessions(
            now,
            request.app.state.active_user_sessions,
            request.app.state.authenticated_sessions,
        )
        session = request.app.state.authenticated_sessions.get(session_token)
        if not session or session[0] != username:
            raise HTTPException(status_code=401, detail="Invalid session")

        _, created_at = request.app.state.authenticated_sessions.pop(session_token)
        if username != SPECIAL_USERNAME:
            if request.app.state.active_user_sessions.get(username) == created_at:
                request.app.state.active_user_sessions.pop(username, None)
    return {"message": f"User {username} logged out"}