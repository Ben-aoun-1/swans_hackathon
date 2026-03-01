"""Retainer agreement document generation via Clio + local fallback.

Primary path: POST /api/v4/documents with a document_template.id (Clio API).
Fallback: Generate the retainer locally using python-docx to fill merge fields
in the template, then convert to PDF via LibreOffice headless. This handles
Clio free-trial limitations where document versions never materialize.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from docx import Document
from loguru import logger

from app.models.extraction import ExtractionResult, PartyInfo
from app.services.clio_client import ClioClient

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "retainer_agreement.docx"


async def generate_retainer(
    clio: ClioClient,
    matter_id: int,
    client_name: str,
) -> dict:
    """Trigger retainer agreement generation from a Clio document template.

    Finds the "Personal Injury Retainer Agreement" template and generates
    a document on the specified matter.

    Returns:
        Document metadata dict from Clio (may not have a version yet).

    Raises:
        ValueError: If the retainer template is not found in Clio.
    """
    template = await clio.find_template_by_name("Retainer")
    if not template:
        raise ValueError(
            "Retainer agreement template not found in Clio. "
            "Upload 'Personal Injury Retainer Agreement' template in "
            "Clio → Settings → Documents → Templates first."
        )

    template_id = template["id"]
    doc_name = f"Retainer Agreement - {client_name}"
    logger.info(
        "Generating retainer from template {} ('{}') for matter {}",
        template_id,
        template.get("name"),
        matter_id,
    )

    doc = await clio.generate_document_from_template(matter_id, template_id, doc_name)
    return doc


async def poll_for_document_version(
    clio: ClioClient,
    document_id: int,
    *,
    max_wait: int = 30,
    interval: int = 3,
) -> dict | None:
    """Poll until a document's latest_document_version becomes non-null.

    Clio generates the file asynchronously after the document record is
    created. This function polls the document metadata until the version
    materializes, meaning the file is ready for download.

    Returns:
        Document metadata dict with latest_document_version populated,
        or None if timed out.
    """
    elapsed = 0

    while elapsed < max_wait:
        resp = await clio._request(
            "GET",
            f"/api/v4/documents/{document_id}",
            params={"fields": "id,name,latest_document_version{id}"},
        )
        doc = resp.get("data", resp)
        version = (doc.get("latest_document_version") or {}).get("id")

        if version:
            logger.info(
                "Document {} version ready (version_id={}) after {}s",
                document_id,
                version,
                elapsed,
            )
            return doc

        logger.debug(
            "Document {} version not ready, waiting {}s… (elapsed {}s)",
            document_id,
            interval,
            elapsed,
        )
        await asyncio.sleep(interval)
        elapsed += interval

    logger.warning(
        "Document {} version not ready after {}s of polling",
        document_id,
        max_wait,
    )
    return None


async def download_retainer_pdf(clio: ClioClient, document_id: int) -> bytes | None:
    """Download a retainer document, polling until the version is ready.

    1. Polls until latest_document_version is non-null (up to 90s).
    2. Downloads the file bytes via the document version endpoint.

    Returns:
        Raw file bytes, or None if the version never materialized.
    """
    # Wait for the document version to be generated
    doc = await poll_for_document_version(clio, document_id)
    if not doc:
        logger.warning("Cannot download document {} — version never materialized", document_id)
        return None

    version_id = doc["latest_document_version"]["id"]
    logger.info("Downloading document {} via version {}", document_id, version_id)

    data = await clio.download_document(document_id)
    logger.info("Downloaded {} bytes", len(data))
    return data


# ─── Local fallback generation ──────────────────────────────────────────


def _party_vehicle_str(party: PartyInfo) -> str:
    """Build 'Year Make Model' string for a party's vehicle."""
    parts = [p for p in (party.vehicle_year, party.vehicle_make, party.vehicle_model) if p]
    return " ".join(parts) if parts else ""


def _replace_merge_fields(doc: Document, replacements: dict[str, str]) -> None:
    """Replace <<merge_field>> tags in all paragraphs.

    Handles the python-docx run-splitting problem: a single ``<<Tag>>``
    can span multiple runs. We concatenate all run texts in a paragraph,
    perform replacements on the full string, then write the result back
    into the first run and clear the rest.
    """
    for paragraph in doc.paragraphs:
        full_text = "".join(run.text for run in paragraph.runs)
        if "<<" not in full_text:
            continue

        new_text = full_text
        for tag, value in replacements.items():
            new_text = new_text.replace(tag, value)

        if new_text == full_text:
            continue

        # Write replaced text back: first run gets all text, rest cleared
        for i, run in enumerate(paragraph.runs):
            if i == 0:
                run.text = new_text
            else:
                run.text = ""


def _build_replacement_map(
    extraction: ExtractionResult,
    matter_display_number: str | None,
    attorney_name: str | None,
) -> dict[str, str]:
    """Build the tag → value replacement map from extraction data."""
    plaintiff: PartyInfo | None = None
    defendant: PartyInfo | None = None
    for party in extraction.parties:
        if party.role.value == "plaintiff" and not plaintiff:
            plaintiff = party
        elif party.role.value == "defendant" and not defendant:
            defendant = party

    # SOL date
    sol_date_str = ""
    if extraction.accident_date:
        try:
            accident_dt = datetime.strptime(extraction.accident_date, "%Y-%m-%d").date()
            sol_date = accident_dt + relativedelta(years=8)
            sol_date_str = sol_date.strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            sol_date_str = extraction.accident_date

    # Format accident date nicely
    accident_date_fmt = ""
    if extraction.accident_date:
        try:
            dt = datetime.strptime(extraction.accident_date, "%Y-%m-%d")
            accident_date_fmt = dt.strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            accident_date_fmt = extraction.accident_date

    today_fmt = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")

    replacements: dict[str, str] = {
        # Standard Clio fields
        "<<Today>>": today_fmt,
        "<<Firm.Address>>": "118-35 Queens Blvd Suite 400, Forest Hills, NY 11375",
        "<<Firm.Phone>>": "(718) 530-4040",
        "<<Matter.ResponsibleAttorney.Name>>": attorney_name or "Richards & Law",
        "<<Matter.DisplayNumber>>": matter_display_number or "N/A",
        "<<Matter.Client.Email>>": "medaminebenaoun@gmail.com",
        # Plaintiff / Client fields
        "<<Matter.CustomField.Plaintiff Name>>": (plaintiff.full_name.value or "N/A") if plaintiff else "N/A",
        "<<Matter.CustomField.Plaintiff Address>>": (plaintiff.address or "N/A") if plaintiff else "N/A",
        "<<Matter.CustomField.Plaintiff DOB>>": (plaintiff.date_of_birth or "N/A") if plaintiff else "N/A",
        "<<Matter.CustomField.Plaintiff Phone>>": (plaintiff.phone or "N/A") if plaintiff else "N/A",
        "<<Matter.CustomField.Plaintiff Vehicle>>": _party_vehicle_str(plaintiff) or "N/A" if plaintiff else "N/A",
        "<<Matter.CustomField.Injuries Reported>>": (plaintiff.injuries.value or "N/A") if plaintiff else "N/A",
        # Defendant fields
        "<<Matter.CustomField.Defendant Name>>": (defendant.full_name.value or "N/A") if defendant else "N/A",
        "<<Matter.CustomField.Defendant Address>>": (defendant.address or "N/A") if defendant else "N/A",
        "<<Matter.CustomField.Defendant Insurance>>": (defendant.insurance_company.value or "N/A") if defendant else "N/A",
        "<<Matter.CustomField.Defendant Policy Number>>": (defendant.insurance_policy_number.value or "N/A") if defendant else "N/A",
        "<<Matter.CustomField.Defendant Vehicle>>": _party_vehicle_str(defendant) or "N/A" if defendant else "N/A",
        # Accident fields
        "<<Matter.CustomField.Accident Date>>": accident_date_fmt or "N/A",
        "<<Matter.CustomField.Accident Location>>": extraction.accident_location or "N/A",
        "<<Matter.CustomField.Accident Description>>": extraction.accident_description or "N/A",
        "<<Matter.CustomField.Police Report Number>>": extraction.report_number or "N/A",
        # SOL
        "<<Matter.CustomField.Statute of Limitations Date>>": sol_date_str or "N/A",
    }

    return replacements


def generate_retainer_locally(
    extraction: ExtractionResult,
    matter_display_number: str | None = None,
    attorney_name: str | None = None,
) -> bytes | None:
    """Generate a retainer agreement PDF locally using python-docx + LibreOffice.

    Opens the template at ``templates/retainer_agreement.docx``, fills all
    ``<<merge_field>>`` tags with values from the extraction data, saves a
    temporary .docx, converts to PDF via LibreOffice headless, and returns
    the raw PDF bytes.

    Returns:
        PDF bytes, or None if generation fails.
    """
    if not TEMPLATE_PATH.exists():
        logger.error("Retainer template not found at {}", TEMPLATE_PATH)
        return None

    logger.info("Generating retainer locally from {}", TEMPLATE_PATH)

    replacements = _build_replacement_map(extraction, matter_display_number, attorney_name)

    # Open template and fill merge fields
    doc = Document(str(TEMPLATE_PATH))
    _replace_merge_fields(doc, replacements)

    # Save filled docx to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "retainer_filled.docx"
        doc.save(str(docx_path))
        logger.info("Saved filled docx to {}", docx_path)

        # Convert to PDF via LibreOffice headless
        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", tmpdir,
                    str(docx_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                logger.error("LibreOffice conversion failed: {}", result.stderr)
                return None

        except FileNotFoundError:
            logger.error("LibreOffice not installed — cannot convert docx to PDF")
            return None
        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out after 60s")
            return None

        pdf_path = Path(tmpdir) / "retainer_filled.pdf"
        if not pdf_path.exists():
            logger.error("PDF not found at {} after conversion", pdf_path)
            return None

        pdf_bytes = pdf_path.read_bytes()
        logger.info("Generated retainer PDF: {} bytes", len(pdf_bytes))
        return pdf_bytes
