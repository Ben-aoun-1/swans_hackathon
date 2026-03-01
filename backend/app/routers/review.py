"""Review & approval endpoint.

Receives the verified extraction data from the frontend review UI
and triggers the full Clio pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.models.extraction import ExtractionResult
from app.services.clio_pipeline import run_pipeline

router = APIRouter(prefix="/api", tags=["review"])


class ApproveRequest(BaseModel):
    """Request body for the approve endpoint."""

    extraction: ExtractionResult
    matter_id: int | None = None  # Optional: use existing matter


@router.post("/approve")
async def approve_extraction(req: ApproveRequest):
    """Push verified extraction data through the Clio pipeline.

    Receives the (potentially edited) extraction data from the review
    UI and orchestrates the full post-approval workflow: creating/updating
    the Clio matter, setting custom fields, generating the retainer,
    creating a calendar entry, and sending the client email.
    """
    logger.info(
        "Approve request received — report #{}, {} parties, matter_id={}",
        req.extraction.report_number,
        len(req.extraction.parties),
        req.matter_id,
    )

    try:
        result = await run_pipeline(req.extraction, matter_id=req.matter_id)
    except Exception as e:
        logger.error("Pipeline failed with unhandled exception: {}", e)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    if not result.success:
        failed = [s for s in result.steps if s.status == "error"]
        logger.warning(
            "Pipeline completed with errors: {}",
            [f"{s.name}: {s.detail}" for s in failed],
        )

    return result.model_dump()
