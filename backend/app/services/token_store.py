"""Per-session Clio token store.

Maps browser session IDs to Clio OAuth tokens so multiple users
can connect their own Clio accounts simultaneously.
Tokens live in memory only - a server restart clears everything.
"""

from __future__ import annotations

import uuid
from fastapi import Request, Response
from loguru import logger

# session_id -> {"access_token": ..., "refresh_token": ...}
_store: dict[str, dict[str, str]] = {}


def get_session_id(request: Request, response: Response) -> str:
    """Get or create a session ID from the cookie."""
    session_id = request.cookies.get("sid")
    if not session_id:
        session_id = uuid.uuid4().hex
        response.set_cookie(
            "sid",
            session_id,
            httponly=True,
            samesite="lax",
            max_age=86400,
        )
    return session_id


def get_tokens(session_id: str) -> dict[str, str] | None:
    """Get the Clio tokens for a session, or None if not connected."""
    return _store.get(session_id)


def set_tokens(session_id: str, access_token: str, refresh_token: str) -> None:
    """Store Clio tokens for a session."""
    _store[session_id] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
    logger.info("Stored tokens for session {}", session_id[:8])


def update_tokens(session_id: str, access_token: str, refresh_token: str) -> None:
    """Update tokens after a refresh (called by ClioClient)."""
    if session_id in _store:
        _store[session_id] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }


def clear_tokens(session_id: str) -> None:
    """Remove tokens for a session (disconnect)."""
    _store.pop(session_id, None)
    logger.info("Cleared tokens for session {}", session_id[:8])
