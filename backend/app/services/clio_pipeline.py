"""Clio pipeline orchestration.

Coordinates the full post-approval flow:
1.   Authenticate & get attorney info
2.   Map custom field IDs
3.   Conflict of interest check (search defendant as existing client)
4.   Find or create contact (email -> name -> create, then enrich)
5.   Find or create matter (search by contact -> create)
5.5  Duplicate report check (skip if same report already processed)
6.   Update matter custom fields
7.   Progressive stage advancement (New Lead -> Report Received -> Data Verified)
8.   Generate retainer agreement from Clio template
9.   Create statute of limitations calendar entry
10.  AI-personalized email paragraph (Claude Haiku)
11.  Send personalized email to client
12.  Upload police report PDF to Clio matter
13.  Upload retainer PDF to Clio matter
14.  Auto-generated task list on the matter
15.  Log intake activity on the matter
16.  Log client email as communication
17.  Case priority scoring
18.  Matter notes / audit trail
19.  Stage -> "Retainer Sent"
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import anthropic
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

# Email used for contacts created by this pipeline
PIPELINE_EMAIL = "medaminebenaoun@gmail.com"

# Stage progression order
STAGE_SEQUENCE = ["New Lead", "Report Received", "Data Verified"]


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
    """Build the custom_field_values array for the Clio PATCH."""
    values: list[dict] = []

    def _add(field_name: str, value: str | None) -> None:
        if field_name in field_map and value:
            values.append({"custom_field": {"id": field_map[field_name]}, "value": value})

    _add("Accident Date", extraction.accident_date)
    _add("Accident Location", extraction.accident_location)
    _add("Accident Description", extraction.accident_description)
    _add("Police Report Number", extraction.report_number)
    _add("Weather Conditions", extraction.weather_conditions)

    officer_str = extraction.reporting_officer_name or ""
    if extraction.reporting_officer_badge:
        officer_str += f" (Badge #{extraction.reporting_officer_badge})"
    _add("Reporting Officer", officer_str.strip() or None)

    if plaintiff:
        _add("Plaintiff Name", _party_name(plaintiff))
        _add("Plaintiff Address", plaintiff.address)
        _add("Plaintiff DOB", plaintiff.date_of_birth)
        _add("Plaintiff Phone", plaintiff.phone)
        _add("Plaintiff Vehicle", _party_vehicle_str(plaintiff))
        _add("Injuries Reported", plaintiff.injuries.value)

    if defendant:
        _add("Defendant Name", _party_name(defendant))
        _add("Defendant Address", defendant.address)
        _add("Defendant Insurance", defendant.insurance_company.value)
        _add("Defendant Policy Number", defendant.insurance_policy_number.value)
        _add("Defendant Vehicle", _party_vehicle_str(defendant))

    _add("Statute of Limitations Date", sol_date_str)

    return values


# ─── Case Priority Scoring ──────────────────────────────────────────────

def _compute_priority_score(
    extraction: ExtractionResult,
    plaintiff: PartyInfo | None,
    sol_date_str: str | None,
) -> tuple[int, list[str]]:
    """Score the case 1-10 based on injury severity, insurance, SOL urgency.

    Returns (score, list of reasoning strings).
    """
    score = 5  # baseline
    reasons: list[str] = []

    # Injury severity keywords
    if plaintiff and plaintiff.injuries.value:
        injuries_lower = plaintiff.injuries.value.lower()
        severe_keywords = ["hospital", "surgery", "fracture", "broken", "concussion", "unconscious", "icu", "ambulance", "transported", "emergency"]
        moderate_keywords = ["pain", "sprain", "strain", "whiplash", "headache", "laceration", "contusion"]

        severe_hits = [kw for kw in severe_keywords if kw in injuries_lower]
        moderate_hits = [kw for kw in moderate_keywords if kw in injuries_lower]

        if severe_hits:
            score += 2
            reasons.append(f"Severe injury indicators: {', '.join(severe_hits)}")
        if moderate_hits:
            score += 1
            reasons.append(f"Moderate injury indicators: {', '.join(moderate_hits)}")
        if not severe_hits and not moderate_hits:
            reasons.append("No significant injury keywords detected")
    else:
        score -= 1
        reasons.append("No injury data available")

    # Insurance availability (defendant)
    defendant = None
    for party in extraction.parties:
        if party.role.value == "defendant":
            defendant = party
            break

    if defendant and defendant.insurance_company.value:
        score += 1
        reasons.append(f"Defendant insured: {defendant.insurance_company.value}")
    else:
        score -= 1
        reasons.append("No defendant insurance identified")

    # SOL urgency
    if sol_date_str:
        try:
            sol_date = datetime.strptime(sol_date_str, "%Y-%m-%d").date()
            days_remaining = (sol_date - datetime.now().date()).days
            if days_remaining < 365:
                score += 2
                reasons.append(f"SOL urgent: {days_remaining} days remaining")
            elif days_remaining < 365 * 3:
                score += 1
                reasons.append(f"SOL approaching: {days_remaining} days remaining")
            else:
                reasons.append(f"SOL comfortable: {days_remaining} days remaining")
        except ValueError:
            pass

    # Multiple vehicles / witnesses
    if extraction.number_of_vehicles and extraction.number_of_vehicles > 2:
        score += 1
        reasons.append(f"Multi-vehicle accident ({extraction.number_of_vehicles} vehicles)")

    witness_count = sum(1 for p in extraction.parties if p.role.value == "witness")
    if witness_count > 0:
        score += 1
        reasons.append(f"{witness_count} witness(es) available")

    # Clamp to 1-10
    score = max(1, min(10, score))
    return score, reasons


# ─── AI Email Personalization ────────────────────────────────────────────

async def _generate_ai_paragraph(
    client_first_name: str,
    accident_date: str | None,
    accident_location: str | None,
    accident_description: str | None,
    injuries: str | None,
) -> str | None:
    """Call Claude Haiku to generate a warm, empathetic paragraph for the client email."""
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        prompt = (
            f"Write a single short paragraph (3-4 sentences) for a personal injury law firm email "
            f"to a potential client named {client_first_name}. Be warm, empathetic, and professional. "
            f"Reference these specific details naturally:\n"
            f"- Accident date: {accident_date or 'recent'}\n"
            f"- Location: {accident_location or 'not specified'}\n"
            f"- What happened: {accident_description or 'a motor vehicle accident'}\n"
            f"- Injuries: {injuries or 'reported injuries'}\n\n"
            f"Do NOT use legal jargon. Do NOT make promises about case outcomes. "
            f"Do NOT mention money or compensation. Just show genuine care and reassurance "
            f"that the firm is here to help them through this difficult time. "
            f"Write ONLY the paragraph, no greeting or sign-off."
        )

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        paragraph = response.content[0].text.strip()
        logger.info("Generated AI paragraph ({} chars)", len(paragraph))
        return paragraph

    except Exception as e:
        logger.warning("AI paragraph generation failed (non-fatal): {}", e)
        return None


# ─── Audit Trail Note Builder ────────────────────────────────────────────

def _build_audit_note(
    steps: list[PipelineStep],
    extraction: ExtractionResult,
    plaintiff_name: str,
    defendant_name: str,
    priority_score: int | None,
    priority_reasons: list[str],
    conflict_warning: str | None,
    speed_seconds: float | None,
) -> str:
    """Build a professional audit trail note for the Clio matter."""
    lines: list[str] = []
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    lines.append("Automated Intake Processing Complete")
    lines.append(f"Date: {now}")
    if speed_seconds is not None:
        lines.append(f"Processing Time: {speed_seconds:.0f} seconds")
    lines.append("")

    # Case summary
    lines.append(f"Report #: {extraction.report_number or 'N/A'}")
    lines.append(f"Accident Date: {extraction.accident_date or 'N/A'}")
    lines.append(f"Location: {extraction.accident_location or 'N/A'}")
    lines.append(f"Plaintiff: {plaintiff_name}")
    lines.append(f"Defendant: {defendant_name}")
    lines.append(f"Parties Involved: {len(extraction.parties)}")
    if extraction.weather_conditions:
        lines.append(f"Weather: {extraction.weather_conditions}")
    lines.append("")

    # Priority score
    if priority_score is not None:
        lines.append(f"Case Priority: {priority_score}/10")
        for reason in priority_reasons:
            lines.append(f"  - {reason}")
        lines.append("")

    # Conflict check
    if conflict_warning:
        lines.append(f"CONFLICT NOTICE: {conflict_warning}")
        lines.append("")

    # Actions completed (clean summary, no technical codes)
    completed = [s.name.replace("_", " ").title() for s in steps if s.status == "success"]
    if completed:
        lines.append("Actions Completed:")
        for action in completed:
            lines.append(f"  - {action}")
        lines.append("")

    # Confidence notes (useful for attorneys)
    if extraction.confidence_notes:
        lines.append(f"AI Extraction Notes: {extraction.confidence_notes}")

    return "\n".join(lines)


async def run_pipeline(
    extraction: ExtractionResult,
    matter_id: int | None = None,
    pdf_bytes: bytes | None = None,
) -> PipelineResult:
    """Run the full Clio post-approval pipeline.

    Args:
        extraction: Verified extraction data from the review UI.
        matter_id: Optional existing Clio matter ID.
        pdf_bytes: Original police report PDF bytes (for upload to Clio).

    Returns:
        PipelineResult with per-step status, priority score, speed-to-lead.
    """
    pipeline_start = time.monotonic()
    steps: list[PipelineStep] = []
    result_matter_id: int | None = matter_id
    result_matter_url: str | None = None
    result_matter_display_number: str | None = None
    pi_practice_area_id: int | None = None
    stage_name_to_id: dict[str, int] = {}
    conflict_warning: str | None = None
    priority_score: int | None = None
    priority_reasons: list[str] = []
    speed_to_lead: float | None = None
    ai_paragraph: str | None = None

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

        # =================================================================
        # STEP 3: Conflict of Interest Check
        # Search for defendant as an existing client in Clio
        # =================================================================
        step = PipelineStep(name="conflict_check", status="running")
        steps.append(step)

        try:
            if defendant and defendant.full_name.value:
                existing_defendant = await clio.find_contact_by_name(defendant.full_name.value)
                if existing_defendant:
                    # Check if this contact is a client on any open matter
                    def_matters = await clio.find_matters_by_contact(existing_defendant["id"])
                    if def_matters:
                        conflict_warning = (
                            f"POTENTIAL CONFLICT: Defendant '{defendant.full_name.value}' "
                            f"exists as a client on {len(def_matters)} open matter(s) in Clio. "
                            f"Contact ID: {existing_defendant['id']}. "
                            f"Matter(s): {', '.join(str(m['id']) for m in def_matters)}. "
                            f"Review before proceeding."
                        )
                        step.status = "success"
                        step.detail = f"CONFLICT: defendant is existing client on {len(def_matters)} matter(s)"
                        logger.warning(conflict_warning)
                    else:
                        step.status = "success"
                        step.detail = f"Defendant '{defendant.full_name.value}' exists as contact but has no open matters"
                else:
                    step.status = "success"
                    step.detail = "No conflict — defendant not found in Clio"
            else:
                step.status = "skipped"
                step.detail = "No defendant name available"
        except Exception as e:
            step.status = "success"
            step.detail = f"Conflict check inconclusive (non-fatal): {e}"
            logger.warning("Conflict check failed: {}", e)

        # =================================================================
        # STEP 4: Smart Contact Resolution + Enrichment
        # =================================================================
        step = PipelineStep(name="find_or_create_contact", status="running")
        steps.append(step)
        contact_id: int | None = None
        contact_source: str = ""

        try:
            if not (plaintiff and plaintiff.full_name.value):
                step.status = "skipped"
                step.detail = "No plaintiff found in extraction data"
            else:
                first_name, last_name = _split_name(plaintiff.full_name.value)

                existing = await clio.find_contact_by_email(PIPELINE_EMAIL)
                if existing:
                    contact_id = existing["id"]
                    contact_source = "email"
                    logger.info("Found contact by email: {} (id={})", existing.get("name"), contact_id)
                else:
                    existing = await clio.find_contact_by_name(plaintiff.full_name.value)
                    if existing:
                        contact_id = existing["id"]
                        contact_source = "name"
                        logger.info("Found contact by name: {} (id={})", existing.get("name"), contact_id)

                if contact_id:
                    try:
                        contact_detail = await clio.get_contact(contact_id)
                        etag = contact_detail.get("etag", "")
                        await clio.update_contact(
                            contact_id, etag,
                            phone=plaintiff.phone,
                            address=plaintiff.address,
                        )
                        step.status = "success"
                        step.detail = f"Found contact by {contact_source} (id={contact_id}), enriched"
                    except Exception as enrich_err:
                        logger.warning("Contact enrichment failed (non-fatal): {}", enrich_err)
                        step.status = "success"
                        step.detail = f"Found contact by {contact_source} (id={contact_id})"
                else:
                    contact = await clio.create_contact(
                        first_name=first_name,
                        last_name=last_name,
                        email=PIPELINE_EMAIL,
                        phone=plaintiff.phone,
                        address=plaintiff.address,
                    )
                    contact_id = contact["id"]
                    step.status = "success"
                    step.detail = f"Created contact '{contact.get('name')}' (id={contact_id})"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Contact resolution failed: {}", e)

        # =================================================================
        # STEP 5: Smart Matter Resolution
        # =================================================================
        step = PipelineStep(name="find_or_create_matter", status="running")
        steps.append(step)

        try:
            for pa in await clio.get_practice_areas():
                if "personal injury" in pa.get("name", "").lower():
                    pi_practice_area_id = pa["id"]
                    break

            if result_matter_id:
                matter_data = await clio.get_matter(result_matter_id)
                result_matter_display_number = matter_data.get("display_number")
                step.status = "success"
                step.detail = f"Using provided matter #{result_matter_display_number} (id={result_matter_id})"

            elif contact_id:
                existing_matters = await clio.find_matters_by_contact(contact_id)

                if existing_matters:
                    chosen = existing_matters[0]
                    for m in existing_matters:
                        ra = m.get("responsible_attorney") or {}
                        if "andrew" in ra.get("name", "").lower() and "richards" in ra.get("name", "").lower():
                            chosen = m
                            break

                    result_matter_id = chosen["id"]
                    result_matter_display_number = chosen.get("display_number")
                    step.status = "success"
                    step.detail = (
                        f"Found existing matter #{result_matter_display_number} "
                        f"(id={result_matter_id}) from {len(existing_matters)} open matter(s)"
                    )
                    logger.info(step.detail)
                else:
                    description = f"{plaintiff_name} v {defendant_name} — Personal Injury"
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
            logger.error("Matter resolution failed: {}", e)

        if not result_matter_id:
            return PipelineResult(success=False, steps=steps)

        result_matter_url = f"{settings.clio_base_url}/nc/#/matters/{result_matter_id}"

        # =================================================================
        # STEP 5.5: Duplicate Report Check
        # =================================================================
        step = PipelineStep(name="duplicate_check", status="running")
        steps.append(step)

        try:
            matter_data = await clio.get_matter(result_matter_id)
            existing_report_number: str | None = None

            for cfv in matter_data.get("custom_field_values", []):
                if cfv.get("field_name") == "Police Report Number":
                    existing_report_number = cfv.get("value")
                    break

            if existing_report_number and existing_report_number == extraction.report_number:
                step.status = "success"
                step.detail = f"Duplicate detected — report #{existing_report_number} already on matter"
                logger.info("Duplicate report detected, skipping remaining steps")
                return PipelineResult(
                    success=True,
                    matter_id=result_matter_id,
                    matter_url=result_matter_url,
                    steps=steps,
                    duplicate_skipped=True,
                )
            elif existing_report_number:
                step.status = "success"
                step.detail = f"Different report on matter (existing={existing_report_number}, new={extraction.report_number}) — overwriting"
                logger.warning(step.detail)
            else:
                step.status = "success"
                step.detail = "No existing report number — proceeding"
        except Exception as e:
            step.status = "success"
            step.detail = f"Could not check for duplicates (non-fatal): {e}"
            logger.warning("Duplicate check failed (non-fatal): {}", e)

        # =================================================================
        # STEP 6: Update matter custom fields
        # =================================================================
        step = PipelineStep(name="update_custom_fields", status="running")
        steps.append(step)
        sol_date_str: str | None = None

        try:
            if field_map:
                if extraction.accident_date:
                    from dateutil.relativedelta import relativedelta

                    accident_dt = datetime.strptime(extraction.accident_date, "%Y-%m-%d").date()
                    sol_date = accident_dt + relativedelta(years=8)
                    sol_date_str = sol_date.isoformat()

                field_values = _build_custom_field_values(
                    extraction, field_map, plaintiff, defendant, sol_date_str
                )

                if field_values:
                    matter_data = await clio.get_matter(result_matter_id)
                    etag = matter_data.get("etag", "")

                    await clio.update_matter_custom_fields(
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
        # STEP 7: Progressive Stage Advancement
        # =================================================================
        step = PipelineStep(name="update_stage", status="running")
        steps.append(step)

        try:
            all_stages = await clio.get_matter_stages(practice_area_id=pi_practice_area_id)
            stage_name_to_id = {s.get("name", ""): s["id"] for s in all_stages}
            logger.info("Stage map: {}", stage_name_to_id)

            matter_data = await clio.get_matter(result_matter_id)
            current_stage_name = (matter_data.get("matter_stage") or {}).get("name", "")
            logger.info("Current stage: '{}'", current_stage_name)

            target_stage = "Data Verified"
            if current_stage_name in STAGE_SEQUENCE:
                current_idx = STAGE_SEQUENCE.index(current_stage_name)
            else:
                current_idx = -1

            target_idx = STAGE_SEQUENCE.index(target_stage)

            if current_idx >= target_idx:
                step.status = "success"
                step.detail = f"Already at or past '{target_stage}' (current: '{current_stage_name}')"
            else:
                stages_advanced = []
                for stage_name in STAGE_SEQUENCE[current_idx + 1: target_idx + 1]:
                    sid = stage_name_to_id.get(stage_name)
                    if not sid:
                        logger.warning("Stage '{}' not found in Clio, skipping", stage_name)
                        continue

                    matter_data = await clio.get_matter(result_matter_id)
                    etag = matter_data.get("etag", "")
                    await clio.update_matter_stage(result_matter_id, etag, sid)
                    stages_advanced.append(stage_name)

                if stages_advanced:
                    step.status = "success"
                    step.detail = f"Advanced through: {' -> '.join(stages_advanced)}"
                else:
                    step.status = "skipped"
                    step.detail = "No matching stages found in Clio"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Stage update failed: {}", e)

        # =================================================================
        # STEP 8: Generate retainer agreement from template
        # =================================================================
        step = PipelineStep(name="generate_retainer", status="running")
        steps.append(step)
        retainer_bytes: bytes | None = None

        try:
            retainer_doc = await generate_retainer(clio, result_matter_id, plaintiff_name)
            step.detail = f"Clio doc '{retainer_doc.get('name')}' (id={retainer_doc.get('id')})"

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
                    step.detail += " (PDF generation failed — email sent without attachment)"
        except ValueError as e:
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
        # STEP 9: Create statute of limitations calendar entry
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
        # STEP 10: AI-Personalized Email Paragraph (Claude Haiku)
        # =================================================================
        step = PipelineStep(name="ai_email_personalization", status="running")
        steps.append(step)

        try:
            client_first = "there"
            if plaintiff and plaintiff.full_name.value:
                client_first, _ = _split_name(plaintiff.full_name.value)

            injuries_text = plaintiff.injuries.value if plaintiff else None

            ai_paragraph = await _generate_ai_paragraph(
                client_first_name=client_first,
                accident_date=extraction.accident_date,
                accident_location=extraction.accident_location,
                accident_description=extraction.accident_description,
                injuries=injuries_text,
            )

            if ai_paragraph:
                step.status = "success"
                step.detail = f"Generated personalized paragraph ({len(ai_paragraph)} chars)"
            else:
                step.status = "skipped"
                step.detail = "AI generation failed — using template without personalization"
        except Exception as e:
            step.status = "skipped"
            step.detail = f"AI generation failed (non-fatal): {e}"
            logger.warning("AI paragraph failed: {}", e)

        # =================================================================
        # STEP 11: Send email
        # =================================================================
        step = PipelineStep(name="send_email", status="running")
        steps.append(step)
        email_body_for_comm: str | None = None

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

                description_brief = extraction.accident_description or ""
                if "." in description_brief:
                    description_brief = description_brief.split(".")[0] + "."
                description_brief = description_brief.lower().strip()
                if not description_brief:
                    description_brief = "a motor vehicle accident"

                client_first = "there"
                if plaintiff and plaintiff.full_name.value:
                    client_first, _ = _split_name(plaintiff.full_name.value)

                email_data = EmailData(
                    to_email=PIPELINE_EMAIL,
                    client_first_name=client_first,
                    accident_date_formatted=_format_accident_date(extraction.accident_date),
                    accident_location=extraction.accident_location or "the accident location",
                    accident_description_brief=description_brief,
                    booking_link=booking_link,
                    booking_type=booking_type,
                    retainer_pdf_bytes=retainer_bytes,
                    retainer_pdf_filename=f"Retainer_Agreement_{plaintiff_name.replace(' ', '_')}.pdf",
                    ai_personal_paragraph=ai_paragraph,
                )

                # Save email body for communication logging
                email_body_for_comm = (
                    f"Dear {client_first},\n\n"
                    f"Thank you for reaching out to Richards & Law. We understand that the "
                    f"incident on {email_data.accident_date_formatted} near "
                    f"{email_data.accident_location} was a difficult experience.\n\n"
                )
                if ai_paragraph:
                    email_body_for_comm += f"{ai_paragraph}\n\n"
                email_body_for_comm += (
                    f"Attorney Andrew Richards has reviewed your case and we've prepared "
                    f"a retainer agreement for your review (attached as PDF).\n\n"
                    f"Book your consultation: {booking_link}\n\n"
                    f"Warm regards,\nThe Richards & Law Team"
                )

                smtp_config = {
                    "host": settings.smtp_host,
                    "port": settings.smtp_port,
                    "user": settings.smtp_user,
                    "password": settings.smtp_password,
                    "from_email": settings.from_email,
                }

                await send_client_email(email_data, smtp_config)

                # Record speed-to-lead at the moment email is sent
                speed_to_lead = time.monotonic() - pipeline_start

                attachment_note = " (with PDF)" if retainer_bytes else " (without attachment)"
                step.status = "success"
                step.detail = f"Email sent to {email_data.to_email}{attachment_note} [{speed_to_lead:.1f}s]"
            except Exception as e:
                step.status = "error"
                step.detail = str(e)
                logger.error("Email sending failed: {}", e)

        # =================================================================
        # STEP 12: Upload original police report PDF to Clio
        # =================================================================
        step = PipelineStep(name="upload_police_report", status="running")
        steps.append(step)

        try:
            if pdf_bytes:
                report_filename = f"Police_Report_{extraction.report_number or 'unknown'}.pdf"
                doc = await clio.upload_document(
                    result_matter_id, report_filename, pdf_bytes, "application/pdf"
                )
                if doc:
                    step.status = "success"
                    step.detail = f"Uploaded '{report_filename}' ({len(pdf_bytes):,} bytes, doc_id={doc.get('id')})"
                else:
                    step.status = "skipped"
                    step.detail = "Upload not supported or failed (non-fatal)"
            else:
                step.status = "skipped"
                step.detail = "No police report PDF provided"
        except Exception as e:
            step.status = "skipped"
            step.detail = f"Upload failed (non-fatal): {e}"
            logger.warning("Police report upload failed: {}", e)

        # =================================================================
        # STEP 13: Upload retainer PDF to Clio matter documents
        # =================================================================
        step = PipelineStep(name="upload_retainer_to_clio", status="running")
        steps.append(step)

        try:
            if retainer_bytes:
                filename = f"Retainer_Agreement_{plaintiff_name.replace(' ', '_')}.pdf"
                doc = await clio.upload_document(
                    result_matter_id, filename, retainer_bytes, "application/pdf"
                )
                if doc:
                    step.status = "success"
                    step.detail = f"Uploaded '{filename}' (doc_id={doc.get('id')})"
                else:
                    step.status = "skipped"
                    step.detail = "Upload not supported or failed (non-fatal)"
            else:
                step.status = "skipped"
                step.detail = "No retainer PDF available to upload"
        except Exception as e:
            step.status = "skipped"
            step.detail = f"Upload failed (non-fatal): {e}"
            logger.warning("Retainer upload failed: {}", e)

        # =================================================================
        # STEP 14: Auto-generated task list
        # =================================================================
        step = PipelineStep(name="create_tasks", status="running")
        steps.append(step)

        try:
            today = datetime.now().date()
            tasks_to_create = [
                ("Review signed retainer agreement", "Follow up with client to confirm retainer was received and review any questions.", 3, "High"),
                ("Schedule initial consultation", "Contact client to schedule their first consultation meeting.", 5, "High"),
                ("Request medical records", f"Request medical records for {plaintiff_name} related to injuries from the {extraction.accident_date or 'reported'} accident.", 7, "Normal"),
                ("File insurance claim", f"File insurance claim with defendant's carrier. Defendant: {defendant_name}.", 14, "Normal"),
                ("Order police report certified copy", f"Order certified copy of police report #{extraction.report_number or 'N/A'} from the precinct.", 10, "Normal"),
            ]

            created_count = 0
            for task_name, task_desc, days_offset, priority in tasks_to_create:
                due = (today + timedelta(days=days_offset)).isoformat()
                try:
                    await clio.create_task(
                        result_matter_id,
                        task_name,
                        task_desc,
                        due_date=due,
                        assignee_id=attorney_id,
                        priority=priority,
                    )
                    created_count += 1
                except Exception as task_err:
                    logger.warning("Failed to create task '{}': {}", task_name, task_err)

            if created_count > 0:
                step.status = "success"
                step.detail = f"Created {created_count}/{len(tasks_to_create)} follow-up tasks"
            else:
                step.status = "skipped"
                step.detail = "No tasks could be created"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Task creation failed: {}", e)

        # =================================================================
        # STEP 15: Log intake activity on the matter
        # =================================================================
        step = PipelineStep(name="log_activity", status="running")
        steps.append(step)

        try:
            if attorney_id:
                today_str = datetime.now().strftime("%Y-%m-%d")
                activity_note = (
                    f"Automated intake: police report #{extraction.report_number or 'N/A'} processed, "
                    f"data extracted and verified, retainer agreement generated, "
                    f"client emailed, calendar entry created. "
                    f"Case: {plaintiff_name} v {defendant_name}."
                )
                if speed_to_lead is not None:
                    activity_note += f" Speed-to-lead: {speed_to_lead:.1f}s."

                await clio.create_activity(
                    matter_id=result_matter_id,
                    user_id=attorney_id,
                    date=today_str,
                    note=activity_note,
                    quantity=0,
                    non_billable=True,
                )
                step.status = "success"
                step.detail = "Logged non-billable intake activity"
            else:
                step.status = "skipped"
                step.detail = "No attorney ID available"
        except Exception as e:
            step.status = "skipped"
            step.detail = f"Activity logging failed (non-fatal): {e}"
            logger.warning("Activity log failed: {}", e)

        # =================================================================
        # STEP 16: Log client email as communication
        # =================================================================
        step = PipelineStep(name="log_communication", status="running")
        steps.append(step)

        try:
            if email_body_for_comm:
                today_str = datetime.now().strftime("%Y-%m-%d")
                await clio.create_communication(
                    matter_id=result_matter_id,
                    subject="Richards & Law — Your Case Review and Next Steps",
                    body=email_body_for_comm,
                    contact_id=contact_id,
                    sender_id=attorney_id,
                    date=today_str,
                    comm_type="EmailCommunication",
                )
                step.status = "success"
                step.detail = "Client email logged as EmailCommunication"
            else:
                step.status = "skipped"
                step.detail = "No email was sent to log"
        except Exception as e:
            step.status = "skipped"
            step.detail = f"Communication logging failed (non-fatal): {e}"
            logger.warning("Communication log failed: {}", e)

        # =================================================================
        # STEP 17: Case Priority Scoring
        # =================================================================
        step = PipelineStep(name="priority_scoring", status="running")
        steps.append(step)

        try:
            priority_score, priority_reasons = _compute_priority_score(
                extraction, plaintiff, sol_date_str
            )
            step.status = "success"
            step.detail = f"Priority score: {priority_score}/10 ({len(priority_reasons)} factors)"
            logger.info("Case priority: {}/10 — {}", priority_score, "; ".join(priority_reasons))
        except Exception as e:
            step.status = "skipped"
            step.detail = f"Scoring failed (non-fatal): {e}"
            logger.warning("Priority scoring failed: {}", e)

        # =================================================================
        # STEP 18: Matter notes / audit trail
        # =================================================================
        step = PipelineStep(name="audit_trail_note", status="running")
        steps.append(step)

        try:
            audit_note = _build_audit_note(
                steps, extraction, plaintiff_name, defendant_name,
                priority_score, priority_reasons, conflict_warning,
                speed_to_lead,
            )

            subject = f"Automated Intake — {plaintiff_name} v {defendant_name}"
            if priority_score is not None:
                subject += f" [Priority: {priority_score}/10]"

            await clio.create_note(
                result_matter_id,
                subject=subject,
                detail=audit_note,
            )
            step.status = "success"
            step.detail = f"Audit trail note created ({len(audit_note)} chars)"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.error("Audit trail note failed: {}", e)

        # =================================================================
        # STEP 19: Stage -> "Retainer Sent"
        # =================================================================
        step = PipelineStep(name="stage_retainer_sent", status="running")
        steps.append(step)

        try:
            retainer_sent_id = stage_name_to_id.get("Retainer Sent")
            if not retainer_sent_id:
                all_stages = await clio.get_matter_stages(practice_area_id=pi_practice_area_id)
                for s in all_stages:
                    if "retainer sent" in s.get("name", "").lower():
                        retainer_sent_id = s["id"]
                        break

            if retainer_sent_id:
                matter_data = await clio.get_matter(result_matter_id)
                etag = matter_data.get("etag", "")
                await clio.update_matter_stage(result_matter_id, etag, retainer_sent_id)
                step.status = "success"
                step.detail = "Stage changed to 'Retainer Sent'"
            else:
                step.status = "skipped"
                step.detail = "Stage 'Retainer Sent' not found in Clio"
        except Exception as e:
            step.status = "error"
            step.detail = str(e)
            logger.warning("Retainer Sent stage update failed: {}", e)

    # =================================================================
    # Final result
    # =================================================================
    total_elapsed = time.monotonic() - pipeline_start
    all_success = all(s.status in ("success", "skipped") for s in steps)
    logger.info(
        "Pipeline complete for matter {} — {} steps, success={}, {:.1f}s total",
        result_matter_id,
        len(steps),
        all_success,
        total_elapsed,
    )

    return PipelineResult(
        success=all_success,
        matter_id=result_matter_id,
        matter_url=result_matter_url,
        steps=steps,
        speed_to_lead_seconds=speed_to_lead,
        priority_score=priority_score,
        conflict_warning=conflict_warning,
    )
