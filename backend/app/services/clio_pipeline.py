"""Clio pipeline orchestration.

Coordinates the full post-approval flow:
1. Authenticate & get attorney info
2. Map custom field IDs
3. Find or create contact for the plaintiff
4. Find or create the matter (or use existing matter_id)
5. Update matter custom fields with verified extraction data
6. Change matter stage → "Data Verified"
7. Generate retainer agreement from Clio template
8. Create statute of limitations calendar entry
9. Download retainer document
10. Send personalized email to client
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from app.config import settings
from app.models.clio import PipelineResult, PipelineStep
from app.models.email import EmailData
from app.models.extraction import ExtractionResult, FieldExtraction, PartyInfo
from app.services.calendar import create_statute_of_limitations_entry
from app.services.clio_client import ClioAPIError, ClioClient
from app.services.document_gen import (
    download_retainer_pdf,
    generate_retainer,
    generate_retainer_locally,
)
from app.services.email_sender import get_booking_link, send_client_email


def _find_party_by_role(
    extraction: ExtractionResult,
    role: str,
) -> PartyInfo | None:
    """Find the first party matching the given role."""
    for party in extraction.parties:
        if party.role.value == role:
            return party
    return None


def _party_name(party: PartyInfo) -> str:
    """Get the display name for a party."""
    return party.full_name.value or "Unknown"


def _party_vehicle_str(party: PartyInfo) -> str:
    """Build 'Year Make Model' string for a party's vehicle."""
    parts = [p for p in (party.vehicle_year, party.vehicle_make, party.vehicle_model) if p]
    return " ".join(parts) if parts else ""


def _split_name(full_name: str) -> tuple[str, str]:
    """Split 'LAST, FIRST' into (first_name, last_name).

    Also handles 'FIRST LAST' format as fallback.
    """
    if "," in full_name:
        last, first = full_name.split(",", 1)
        return first.strip(), last.strip()
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return full_name.strip(), ""


def _format_accident_date(date_str: str | None) -> str:
    """Format YYYY-MM-DD as a nice date like 'March 15, 2024'."""
    if not date_str:
        return "the date of your accident"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y").replace(" 0", " ")
    except ValueError:
        return date_str


def _build_custom_field_values(
    extraction: ExtractionResult,
    field_map: dict[str, int],
    plaintiff: PartyInfo | None,
    defendant: PartyInfo | None,
    sol_date_str: str | None,
) -> list[dict]:
    """Build the custom_field_values array for the Clio PATCH.

    Maps extraction data to Clio custom field IDs. Skips fields
    that aren't found in the field map.
    """
    values: list[dict] = []

    def _add(field_name: str, value: str | None) -> None:
        if field_name in field_map and value:
            values.append({"custom_field": {"id": field_map[field_name]}, "value": value})

    # Top-level accident fields
    _add("Accident Date", extraction.accident_date)
    _add("Accident Location", extraction.accident_location)
    _add("Accident Description", extraction.accident_description)
    _add("Police Report Number", extraction.report_number)
    _add("Weather Conditions", extraction.weather_conditions)

    # Reporting officer
    officer_str = extraction.reporting_officer_name or ""
    if extraction.reporting_officer_badge:
        officer_str += f" (Badge #{extraction.reporting_officer_badge})"
    _add("Reporting Officer", officer_str.strip() or None)

    # Plaintiff fields
    if plaintiff:
        _add("Plaintiff Name", _party_name(plaintiff))
        _add("Plaintiff Address", plaintiff.address)
        _add("Plaintiff DOB", plaintiff.date_of_birth)
        _add("Plaintiff Phone", plaintiff.phone)
        _add("Plaintiff Vehicle", _party_vehicle_str(plaintiff))
        _add("Injuries Reported", plaintiff.injuries.value)

    # Defendant fields
    if defendant:
        _add("Defendant Name", _party_name(defendant))
        _add("Defendant Address", defendant.address)
        _add("Defendant Insurance", defendant.insurance_company.value)
        _add("Defendant Policy Number", defendant.insurance_policy_number.value)
        _add("Defendant Vehicle", _party_vehicle_str(defendant))

    # Statute of limitations date
    _add("Statute of Limitations Date", sol_date_str)

    return values


async def run_pipeline(
    extraction: ExtractionResult,
    matter_id: int | None = None,
) -> PipelineResult:
    """Run the full Clio post-approval pipeline.

    Args:
        extraction: Verified extraction data from the review UI.
        matter_id: Optional existing Clio matter ID. If None, a new
            matter is created.

    Returns:
        PipelineResult with per-step status and the final matter_id.
    """
    steps: list[PipelineStep] = []
    result_matter_id: int | None = matter_id
    result_matter_url: str | None = None
    result_matter_display_number: str | None = None
    pi_practice_area_id: int | None = None  # Resolved in step 4, used in step 6

    plaintiff = _find_party_by_role(extraction, "plaintiff")
    defendant = _find_party_by_role(extraction, "defendant")
    plaintiff_name = _party_name(plaintiff) if plaintiff else "Unknown Client"
    defendant_name = _party_name(defendant) if defendant else "Unknown Defendant"

    async with ClioClient() as clio:

        # =================================================================
        # STEP 1: Verify Clio connection & get attorney info
        # =================================================================
        step = PipelineStep(name="authenticate", status="running")
        steps.append(step)
        attorney_id: int | None = None
        attorney_name: str | None = None

        try:
            me = await clio.who_am_i()
            attorney_id = me.get("id")
            attorney_name = me.get("name")
            step.status = "success"
            step.detail = f"Authenticated as {attorney_name} (id={attorney_id})"
            logger.info(step.detail)
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Auth failed: {}", e)
            return PipelineResult(success=False, steps=steps)

        # =================================================================
        # STEP 2: Build custom field ID map
        # =================================================================
        step = PipelineStep(name="map_custom_fields", status="running")
        steps.append(step)
        field_map: dict[str, int] = {}

        try:
            field_map = await clio.build_field_id_map()
            step.status = "success"
            step.detail = f"Mapped {len(field_map)} custom fields"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Field mapping failed: {}", e)
            # Non-fatal — continue without custom fields

        # =================================================================
        # STEP 3: Find or create contact (plaintiff)
        # =================================================================
        step = PipelineStep(name="create_contact", status="running")
        steps.append(step)
        contact_id: int | None = None

        try:
            if plaintiff and plaintiff.full_name.value:
                first_name, last_name = _split_name(plaintiff.full_name.value)

                # Check if contact already exists
                existing = await clio.find_contact_by_name(plaintiff.full_name.value)
                if existing:
                    contact_id = existing["id"]
                    step.status = "success"
                    step.detail = f"Found existing contact '{existing.get('name')}' (id={contact_id})"
                else:
                    contact = await clio.create_contact(
                        first_name=first_name,
                        last_name=last_name,
                        email="medaminebenaoun@gmail.com",
                        phone=plaintiff.phone,
                        address=plaintiff.address,
                    )
                    contact_id = contact["id"]
                    step.status = "success"
                    step.detail = f"Created contact '{contact.get('name')}' (id={contact_id})"
            else:
                step.status = "skipped"
                step.detail = "No plaintiff found in extraction data"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Contact creation failed: {}", e)

        # =================================================================
        # STEP 4: Create matter (if no matter_id provided)
        # =================================================================
        step = PipelineStep(name="create_matter", status="running")
        steps.append(step)

        try:
            if result_matter_id:
                step.status = "skipped"
                step.detail = f"Using existing matter {result_matter_id}"
            elif contact_id:
                description = f"{plaintiff_name} v {defendant_name} — Personal Injury"

                # Find the "Personal Injury" practice area so stages apply
                for pa in await clio.get_practice_areas():
                    if "personal injury" in pa.get("name", "").lower():
                        pi_practice_area_id = pa["id"]
                        break

                matter = await clio.create_matter(
                    client_id=contact_id,
                    description=description,
                    responsible_attorney_id=attorney_id,
                    practice_area_id=pi_practice_area_id,
                )
                result_matter_id = matter["id"]
                result_matter_display_number = matter.get("display_number")
                step.status = "success"
                step.detail = f"Created matter #{result_matter_display_number} (id={result_matter_id})"
            else:
                step.status = "error"
                step.detail = "Cannot create matter: no contact ID available"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Matter creation failed: {}", e)

        if not result_matter_id:
            return PipelineResult(success=False, steps=steps)

        result_matter_url = f"{settings.clio_base_url}/nc/#/matters/{result_matter_id}"

        # =================================================================
        # STEP 5: Update matter custom fields
        # =================================================================
        step = PipelineStep(name="update_custom_fields", status="running")
        steps.append(step)

        try:
            if field_map:
                # Calculate SOL date for the custom field
                sol_date_str: str | None = None
                if extraction.accident_date:
                    from dateutil.relativedelta import relativedelta

                    accident_dt = datetime.strptime(extraction.accident_date, "%Y-%m-%d").date()
                    sol_date = accident_dt + relativedelta(years=8)
                    sol_date_str = sol_date.isoformat()

                field_values = _build_custom_field_values(
                    extraction, field_map, plaintiff, defendant, sol_date_str
                )

                if field_values:
                    # Get current etag
                    matter_data = await clio.get_matter(result_matter_id)
                    etag = matter_data.get("etag", "")

                    updated = await clio.update_matter_custom_fields(
                        result_matter_id, etag, field_values
                    )
                    step.status = "success"
                    step.detail = f"Updated {len(field_values)} custom fields"
                else:
                    step.status = "skipped"
                    step.detail = "No field values to update"
            else:
                step.status = "skipped"
                step.detail = "No field map available"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Custom field update failed: {}", e)

        # =================================================================
        # STEP 6: Change matter stage → "Data Verified"
        # =================================================================
        step = PipelineStep(name="update_stage", status="running")
        steps.append(step)

        try:
            stage_id = await clio.get_stage_id_by_name("Data Verified", practice_area_id=pi_practice_area_id)
            if stage_id:
                matter_data = await clio.get_matter(result_matter_id)
                etag = matter_data.get("etag", "")
                await clio.update_matter_stage(result_matter_id, etag, stage_id)
                step.status = "success"
                step.detail = f"Stage changed to 'Data Verified' (id={stage_id})"
            else:
                step.status = "skipped"
                step.detail = "Stage 'Data Verified' not found in Clio"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Stage update failed: {}", e)

        # =================================================================
        # STEP 7: Generate retainer agreement from template
        # =================================================================
        step = PipelineStep(name="generate_retainer", status="running")
        steps.append(step)
        retainer_doc: dict | None = None
        retainer_bytes: bytes | None = None

        try:
            retainer_doc = await generate_retainer(clio, result_matter_id, plaintiff_name)
            step.detail = f"Clio doc '{retainer_doc.get('name')}' (id={retainer_doc.get('id')})"

            # Poll for version + download (async generation)
            retainer_bytes = await download_retainer_pdf(clio, retainer_doc["id"])
            if retainer_bytes:
                step.status = "success"
                step.detail += f", downloaded {len(retainer_bytes)} bytes"
            else:
                logger.info("Clio PDF not available — falling back to local generation")
                retainer_bytes = generate_retainer_locally(
                    extraction, result_matter_display_number, attorney_name
                )
                if retainer_bytes:
                    step.status = "success"
                    step.detail += f", local PDF generated ({len(retainer_bytes)} bytes)"
                else:
                    step.status = "success"
                    step.detail += " (PDF generation failed — email will be sent without attachment)"
        except ValueError as e:
            # Template not found in Clio — try local only
            logger.warning("Clio template not found, trying local generation: {}", e)
            retainer_bytes = generate_retainer_locally(
                extraction, result_matter_display_number, attorney_name
            )
            if retainer_bytes:
                step.status = "success"
                step.detail = f"Local PDF generated ({len(retainer_bytes)} bytes)"
            else:
                step.status = "skipped"
                step.detail = str(e)
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Retainer generation failed: {}", e)

        # =================================================================
        # STEP 8: Create statute of limitations calendar entry
        # =================================================================
        step = PipelineStep(name="create_calendar_entry", status="running")
        steps.append(step)

        try:
            if extraction.accident_date and attorney_id:
                await create_statute_of_limitations_entry(
                    clio,
                    result_matter_id,
                    extraction.accident_date,
                    plaintiff_name,
                    defendant_name,
                    attorney_id,
                )
                step.status = "success"
                step.detail = "SOL calendar entry created"
            else:
                step.status = "skipped"
                step.detail = "Missing accident_date or attorney_id"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Calendar entry failed: {}", e)

        # =================================================================
        # STEP 9: Send email
        # =================================================================
        step = PipelineStep(name="send_email", status="running")
        steps.append(step)

        # Check SMTP config first — skip gracefully if not configured
        if not settings.smtp_user or not settings.smtp_password:
            step.status = "skipped"
            step.detail = "SMTP not configured (SMTP_USER / SMTP_PASSWORD missing)"
        else:
            try:
                if retainer_bytes is None:
                    logger.warning("Sending email without retainer PDF attachment")

                booking_link, booking_type = get_booking_link(
                    settings.in_office_booking_url,
                    settings.virtual_booking_url,
                )

                # Build brief description (first sentence of accident_description)
                description_brief = extraction.accident_description or ""
                if "." in description_brief:
                    description_brief = description_brief.split(".")[0] + "."
                description_brief = description_brief.lower().strip()
                if not description_brief:
                    description_brief = "a motor vehicle accident"

                # Get client first name
                client_first = "there"
                if plaintiff and plaintiff.full_name.value:
                    client_first, _ = _split_name(plaintiff.full_name.value)

                email_data = EmailData(
                    to_email="medaminebenaoun@gmail.com",
                    client_first_name=client_first,
                    accident_date_formatted=_format_accident_date(extraction.accident_date),
                    accident_location=extraction.accident_location or "the accident location",
                    accident_description_brief=description_brief,
                    booking_link=booking_link,
                    booking_type=booking_type,
                    retainer_pdf_bytes=retainer_bytes,
                    retainer_pdf_filename=f"Retainer_Agreement_{plaintiff_name.replace(' ', '_')}.pdf",
                )

                smtp_config = {
                    "host": settings.smtp_host,
                    "port": settings.smtp_port,
                    "user": settings.smtp_user,
                    "password": settings.smtp_password,
                    "from_email": settings.from_email,
                }

                await send_client_email(email_data, smtp_config)
                attachment_note = " (with PDF)" if retainer_bytes else " (without attachment)"
                step.status = "success"
                step.detail = f"Email sent to {email_data.to_email}{attachment_note}"
            except Exception as e:
                step.status = "error"
                step.detail = str(e)
                logger.error("Email sending failed: {}", e)

    # =================================================================
    # Final result
    # =================================================================
    all_success = all(s.status in ("success", "skipped") for s in steps)
    logger.info(
        "Pipeline complete for matter {} — {} steps, success={}",
        result_matter_id,
        len(steps),
        all_success,
    )

    return PipelineResult(
        success=all_success,
        matter_id=result_matter_id,
        matter_url=result_matter_url,
        steps=steps,
    )
