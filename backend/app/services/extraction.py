"""Claude AI extraction service — PDF to structured JSON.

Converts police report PDFs into page images via PyMuPDF, sends them
to Claude Sonnet 4.6's vision API, and parses the structured JSON response
into a validated ExtractionResult with per-field confidence metadata.
"""

import base64
import json

import anthropic
import fitz  # PyMuPDF
from loguru import logger

from app.config import settings
from app.models.extraction import ExtractionResult, FieldExtraction
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


def _compute_metadata_stats(result: ExtractionResult, total_pages: int) -> None:
    """Post-process the extraction result to compute metadata statistics."""
    meta = result.extraction_metadata
    meta.total_pages = total_pages

    extracted = 0
    inferred = 0
    not_found = 0
    low_confidence: list[str] = []

    # Count top-level fields
    for field_name in (
        "report_number", "accident_date", "accident_time", "accident_location",
        "accident_description", "weather_conditions", "road_conditions",
        "reporting_officer_name", "reporting_officer_badge",
    ):
        if getattr(result, field_name) is not None:
            extracted += 1
        else:
            not_found += 1

    if result.number_of_vehicles is not None:
        extracted += 1
    else:
        not_found += 1

    # Count party-level FieldExtraction fields
    fe_fields = ("role", "full_name", "vehicle_color", "insurance_company", "insurance_policy_number", "injuries")

    for i, party in enumerate(result.parties):
        party_label = (
            party.full_name.value
            if party.full_name.value
            else f"party_{i + 1}"
        )

        for field_name in fe_fields:
            fe: FieldExtraction = getattr(party, field_name)  # type: ignore[type-arg]
            if fe.source == "not_found":
                not_found += 1
            elif fe.source == "inferred":
                inferred += 1
                extracted += 1
            else:
                if fe.value is not None:
                    extracted += 1
                else:
                    not_found += 1

            if fe.confidence == "low":
                low_confidence.append(f"{party_label}.{field_name}")
            elif fe.confidence == "medium":
                low_confidence.append(f"{party_label}.{field_name}")

        # Count plain string fields on party
        for field_name in ("address", "date_of_birth", "phone", "driver_license",
                           "vehicle_year", "vehicle_make", "vehicle_model", "citation_issued"):
            if getattr(party, field_name) is not None:
                extracted += 1
            else:
                not_found += 1

    meta.fields_extracted = extracted
    meta.fields_inferred = inferred
    meta.fields_not_found = not_found
    meta.low_confidence_fields = low_confidence


async def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Extract structured data from a police report PDF using Claude vision.

    1. Converts each PDF page to a PNG at 2x resolution
    2. Sends all pages + extraction prompt to Claude in a single message
    3. Parses and validates the JSON response into ExtractionResult
    4. Computes extraction metadata statistics
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
            max_tokens=8192,  # Increased for richer structured output
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

    # Step 6: Post-process metadata stats
    _compute_metadata_stats(result, total_pages=len(images))

    meta = result.extraction_metadata
    logger.info(
        "Extraction complete — report #{}, {} parties, form_type={}",
        result.report_number,
        len(result.parties),
        meta.form_type,
    )
    logger.info(
        "Metadata: {} extracted, {} inferred, {} not_found, {} low-confidence",
        meta.fields_extracted,
        meta.fields_inferred,
        meta.fields_not_found,
        len(meta.low_confidence_fields),
    )

    if meta.form_type and "MV-104" in (meta.form_type or ""):
        logger.info("Detected MV-104 form type")

    return result
