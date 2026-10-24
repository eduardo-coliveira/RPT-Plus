"""Routes and session locks for user authentication."""

import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from backend.database import authenticate_user_credentials
from backend.schemas import LoginRequest, LogoutRequest

# A session expires after this long without an authenticated request.
SESSION_IDLE_TTL_SECONDS = 3600
SPECIAL_USERNAME = "st000"
SPECIAL_PASSWORD = "000000"
SPECIAL_GROUP = "STATE-BASED"

router = APIRouter()


@dataclass
class AuthSession:
    """A login session and the time it was last used."""

    username: str
    user_id: Optional[int]
    last_seen: float


def prune_expired_user_sessions(now: float, sessions: Dict[str, float]) -> None:
    """Remove username locks that have been idle for too long."""

    expired_users = [
        username for username, locked_at in sessions.items()
        if now - locked_at >= SESSION_IDLE_TTL_SECONDS
    ]
    for username in expired_users:
        sessions.pop(username, None)


def _release_username_lock(sessions: Dict[str, float], session: AuthSession) -> None:
    """Release a username lock if this session still owns it."""

    if session.username != SPECIAL_USERNAME and sessions.get(session.username) == session.last_seen:
        sessions.pop(session.username, None)


def _prune_expired_authenticated_sessions(
    now: float,
    sessions: Dict[str, float],
    authenticated_sessions: Dict[str, AuthSession],
) -> None:
    """Expire idle session tokens and their corresponding username locks."""

    expired_tokens = [
        token for token, session in authenticated_sessions.items()
        if now - session.last_seen >= SESSION_IDLE_TTL_SECONDS
    ]
    for token in expired_tokens:
        _release_username_lock(sessions, authenticated_sessions.pop(token))


def create_authenticated_session(
    request: Request,
    username: str,
    user_id: Optional[int] = None,
) -> Optional[str]:
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
        authenticated_sessions[token] = AuthSession(username, user_id, now)
        return token


def authenticated_session(request: Request) -> Optional[AuthSession]:
    """Resolve a valid session token to its session and renew its idle timer."""

    token = request.headers.get("X-Session-Token")
    if not token:
        return None

    with request.app.state.user_lock:
        sessions = request.app.state.active_user_sessions
        authenticated_sessions = request.app.state.authenticated_sessions
        now = time.time()
        prune_expired_user_sessions(now, sessions)
        _prune_expired_authenticated_sessions(now, sessions, authenticated_sessions)
        session = authenticated_sessions.get(token)
        if session is None:
            return None

        # The lock timestamp identifies the owning session, so both are renewed together.
        owns_lock = session.username != SPECIAL_USERNAME and sessions.get(session.username) == session.last_seen
        session.last_seen = now
        if owns_lock:
            sessions[session.username] = now
        return session


def authenticated_username(request: Request) -> Optional[str]:
    """Resolve a valid session token to its server-established username."""

    session = authenticated_session(request)
    return session.username if session else None


@router.post("/login")
async def login_user(request_data: LoginRequest, request: Request):
    """Authenticate a user and start a session."""

    if request_data.username == SPECIAL_USERNAME:
        if request_data.password != SPECIAL_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        group_name = SPECIAL_GROUP
        user_id = None
    else:
        user = authenticate_user_credentials(
            request_data.username,
            request_data.password,
            request.app.state.database_config,
        )
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        group_name = user["group_name"]
        user_id = user["id"]

    session_token = create_authenticated_session(request, request_data.username, user_id)
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
        if not session or session.username != username:
            raise HTTPException(status_code=401, detail="Invalid session")

        request.app.state.authenticated_sessions.pop(session_token)
        _release_username_lock(request.app.state.active_user_sessions, session)
    return {"message": f"User {username} logged out"}
