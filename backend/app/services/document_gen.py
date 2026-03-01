"""Retainer agreement document generation via Clio.

Since Automated Workflows are NOT available on the free trial,
we use the Clio API directly: POST /api/v4/documents with a document_template.id.

Document generation is async — the document record is created immediately
but the actual file (document version) takes a few seconds to materialize.
We poll until latest_document_version is non-null before downloading.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.services.clio_client import ClioClient


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
    max_wait: int = 90,
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
