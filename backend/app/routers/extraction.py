from fastapi import APIRouter, HTTPException, UploadFile, File
from loguru import logger

from app.models.extraction import ExtractionResult
from app.services.extraction import extract_from_pdf

router = APIRouter(prefix="/api", tags=["extraction"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/extract", response_model=ExtractionResult)
async def extract_pdf(file: UploadFile = File(...)):
    """Upload a police report PDF and extract structured data via Claude AI."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf.",
        )

    # Read file bytes
    pdf_bytes = await file.read()

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(pdf_bytes)} bytes). Maximum is {MAX_FILE_SIZE} bytes.",
        )

    logger.info("Received PDF: {} ({} bytes)", file.filename, len(pdf_bytes))

    # Run extraction
    try:
        result = await extract_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Extraction failed unexpectedly")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {type(e).__name__}: {e}",
        )

    return result
