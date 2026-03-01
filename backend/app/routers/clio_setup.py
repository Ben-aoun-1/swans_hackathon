"""Clio Setup API endpoints.

Provides check (read-only) and run (creates missing items) endpoints
for self-configuring the Clio account.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger

from app.services.clio_client import ClioClient
from app.services.clio_setup import SetupResult, check_clio_setup, setup_clio_account
from app.services.token_store import get_session_id, get_tokens

router = APIRouter(prefix="/api/clio/setup", tags=["clio-setup"])


def _get_clio_client(request: Request, response: Response) -> ClioClient:
    """Build a ClioClient from the current session's tokens."""
    session_id = get_session_id(request, response)
    tokens = get_tokens(session_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="Not connected to Clio")
    return ClioClient(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", ""),
        session_id=session_id,
    )


@router.get("/check", response_model=SetupResult)
async def check_setup(request: Request, response: Response):
    """Read-only check of Clio account configuration.

    Returns which items are present, missing, or errored without
    creating or modifying anything.
    """
    clio = _get_clio_client(request, response)

    async with clio:
        result = await check_clio_setup(clio)

    logger.info(
        "Setup check: ready={}, missing={}",
        result.ready,
        len(result.missing_items),
    )
    return result


@router.post("/run", response_model=SetupResult)
async def run_setup(request: Request, response: Response):
    """Configure the Clio account by creating any missing items.

    Creates practice areas, matter stages, and custom fields as needed.
    Document templates are informational only (cannot be created via API).
    """
    clio = _get_clio_client(request, response)

    async with clio:
        result = await setup_clio_account(clio)

    logger.info(
        "Setup run: ready={}, attorney={}, missing={}",
        result.ready,
        result.attorney_name,
        len(result.missing_items),
    )
    return result
