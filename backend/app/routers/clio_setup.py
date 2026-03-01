"""Clio Setup API endpoints.

Provides check (read-only) and run (creates missing items) endpoints
for self-configuring the Clio account.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.config import settings
from app.services.clio_client import ClioClient
from app.services.clio_setup import SetupResult, check_clio_setup, setup_clio_account

router = APIRouter(prefix="/api/clio/setup", tags=["clio-setup"])


@router.get("/check", response_model=SetupResult)
async def check_setup():
    """Read-only check of Clio account configuration.

    Returns which items are present, missing, or errored without
    creating or modifying anything.
    """
    if not settings.clio_access_token:
        raise HTTPException(status_code=400, detail="Not connected to Clio")

    async with ClioClient() as clio:
        result = await check_clio_setup(clio)

    logger.info(
        "Setup check: ready={}, missing={}",
        result.ready,
        len(result.missing_items),
    )
    return result


@router.post("/run", response_model=SetupResult)
async def run_setup():
    """Configure the Clio account by creating any missing items.

    Creates practice areas, matter stages, and custom fields as needed.
    Document templates are informational only (cannot be created via API).
    """
    if not settings.clio_access_token:
        raise HTTPException(status_code=400, detail="Not connected to Clio")

    async with ClioClient() as clio:
        result = await setup_clio_account(clio)

    logger.info(
        "Setup run: ready={}, attorney={}, missing={}",
        result.ready,
        result.attorney_name,
        len(result.missing_items),
    )
    return result
