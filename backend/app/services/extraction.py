"""Claude AI extraction service — PDF to structured JSON.

Converts police report PDFs into page images via PyMuPDF, sends them
to Claude Sonnet 4.6's vision API, and parses the structured JSON response
into a validated ExtractionResult.
"""

import base64
import json

import anthropic
import fitz  # PyMuPDF
from loguru import logger

from app.config import settings
from app.models.extraction import ExtractionResult
from app.prompts.extraction_prompt import EXTRACTION_PROMPT


def pdf_to_images(pdf_bytes: bytes) -> list[tuple[bytes, str]]:
    """Convert PDF pages to a list of (png_bytes, media_type) tuples.

    Renders each page at 2x resolution for better readability by the vision model.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[tuple[bytes, str]] = []

    for page_num, page in enumerate(doc):
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for sharper images
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append((img_bytes, "image/png"))
        logger.debug(
            "Rendered page {}/{} — {}x{} px, {} bytes",
            page_num + 1,
            len(doc),
            pix.width,
            pix.height,
            len(img_bytes),
        )

    doc.close()
    logger.info("Converted PDF to {} page image(s)", len(images))
    return images


def _parse_json_response(raw_text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown code fences."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    return json.loads(text.strip())


async def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Extract structured data from a police report PDF using Claude vision.

    1. Converts each PDF page to a PNG at 2x resolution
    2. Sends all pages + extraction prompt to Claude in a single message
    3. Parses and validates the JSON response into ExtractionResult
    """
    logger.info("Starting PDF extraction ({} bytes)", len(pdf_bytes))

    # Step 1: Convert PDF to images
    images = pdf_to_images(pdf_bytes)
    if not images:
        raise ValueError("PDF contains no pages")

    # Step 2: Build the Claude API message content
    content: list[dict] = []
    for img_bytes, media_type in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(img_bytes).decode(),
            },
        })

    content.append({
        "type": "text",
        "text": EXTRACTION_PROMPT,
    })

    # Step 3: Call Claude API
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = settings.anthropic_model

    logger.info("Sending {} page(s) to Claude (model: {})", len(images), model)

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APITimeoutError:
        logger.error("Claude API request timed out")
        raise
    except anthropic.APIError as e:
        logger.error("Claude API error: {}", e)
        raise

    raw_text = response.content[0].text
    logger.debug("Claude response length: {} chars", len(raw_text))
    logger.debug(
        "Token usage — input: {}, output: {}",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    # Step 4: Parse JSON response
    try:
        data = _parse_json_response(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: {}", e)
        logger.debug("Raw response:\n{}", raw_text[:2000])
        raise ValueError(f"Claude returned invalid JSON: {e}") from e

    # Step 5: Validate with Pydantic
    try:
        result = ExtractionResult.model_validate(data)
    except Exception as e:
        logger.error("Pydantic validation failed: {}", e)
        raise ValueError(f"Extracted data failed validation: {e}") from e

    logger.info(
        "Extraction complete — report #{}, {} parties found",
        result.report_number,
        len(result.parties),
    )
    return result
