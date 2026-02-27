from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["review"])


@router.post("/approve")
async def approve_extraction():
    """Push verified extraction data through the Clio pipeline."""
    # TODO: Accept verified ExtractionResult, push to Clio pipeline
    return {"status": "not_implemented"}
