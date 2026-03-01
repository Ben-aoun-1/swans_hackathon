"""Review & approval endpoint.

Receives the verified extraction data from the frontend review UI
and triggers the full Clio pipeline.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel

from app.models.extraction import ExtractionResult
from app.services.clio_pipeline import run_pipeline
from app.services.token_store import get_session_id, get_tokens

router = APIRouter(prefix="/api", tags=["review"])


class ApproveRequest(BaseModel):
    """Request body for the approve endpoint."""

    extraction: ExtractionResult
    matter_id: int | None = None  # Optional: use existing matter
    pdf_base64: str | None = None  # Original police report PDF for upload to Clio
    upload_timestamp: float | None = None  # Unix epoch ms when user uploaded the PDF


@router.post("/approve")
async def approve_extraction(req: ApproveRequest, request: Request, response: Response):
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

    # Get per-session Clio tokens
    session_id = get_session_id(request, response)
    tokens = get_tokens(session_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="Not connected to Clio — go to Settings to connect your account")

    # Decode the original PDF if provided
    pdf_bytes: bytes | None = None
    if req.pdf_base64:
        try:
            pdf_bytes = base64.b64decode(req.pdf_base64)
            logger.info("Decoded police report PDF: {} bytes", len(pdf_bytes))
        except Exception as e:
            logger.warning("Failed to decode pdf_base64: {}", e)

    try:
        result = await run_pipeline(
            req.extraction,
            matter_id=req.matter_id,
            pdf_bytes=pdf_bytes,
            upload_timestamp=req.upload_timestamp,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            session_id=session_id,
        )
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
