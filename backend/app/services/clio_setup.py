"""Self-configuring Clio Setup Agent.

Inspects the connected Clio account and ensures all required configuration
(practice area, matter stages, custom fields, document template) exists.
Creates anything missing so the pipeline can run without manual Clio setup.
"""

from __future__ import annotations

from pydantic import BaseModel
from loguru import logger

from app.services.clio_client import ClioAPIError, ClioClient


# ── Data definitions ─────────────────────────────────────────────────────

PRACTICE_AREA_NAME = "Personal Injury"

REQUIRED_STAGES = ["New Lead", "Report Received", "Data Verified", "Retainer Sent"]

# (field_name, clio_field_type)
REQUIRED_CUSTOM_FIELDS: list[tuple[str, str]] = [
    ("Accident Date", "date"),
    ("Accident Location", "text_line"),
    ("Accident Description", "text_area"),
    ("Police Report Number", "text_line"),
    ("Plaintiff Name", "text_line"),
    ("Plaintiff Address", "text_area"),
    ("Plaintiff DOB", "date"),
    ("Plaintiff Phone", "text_line"),
    ("Defendant Name", "text_line"),
    ("Defendant Address", "text_area"),
    ("Defendant Insurance", "text_line"),
    ("Defendant Policy Number", "text_line"),
    ("Defendant Vehicle", "text_line"),
    ("Plaintiff Vehicle", "text_line"),
    ("Injuries Reported", "text_area"),
    ("Weather Conditions", "text_line"),
    ("Reporting Officer", "text_line"),
    ("Statute of Limitations Date", "date"),
]

RETAINER_TEMPLATE_NAME = "retainer"


# ── Models ───────────────────────────────────────────────────────────────

class SetupStep(BaseModel):
    name: str
    status: str = "pending"  # pending | success | error | skipped
    detail: str | None = None


class SetupResult(BaseModel):
    ready: bool = False
    steps: list[SetupStep] = []
    attorney_name: str | None = None
    attorney_id: int | None = None
    practice_area_id: int | None = None
    missing_items: list[str] = []


# ── Check-only (non-destructive) ─────────────────────────────────────────

async def check_clio_setup(clio: ClioClient) -> SetupResult:
    """Check whether the Clio account has all required configuration.

    Does NOT create or modify anything - read-only inspection.
    """
    result = SetupResult()

    # 1. Verify authentication
    step = SetupStep(name="authenticate")
    try:
        me = await clio.who_am_i()
        result.attorney_name = me.get("name")
        result.attorney_id = me.get("id")
        step.status = "success"
        step.detail = me.get("name")
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
        result.steps.append(step)
        return result
    result.steps.append(step)

    # 2. Check practice area
    step = SetupStep(name="practice_area")
    try:
        practice_areas = await clio.get_practice_areas()
        pa = _find_by_name(practice_areas, PRACTICE_AREA_NAME)
        if pa:
            result.practice_area_id = pa["id"]
            step.status = "success"
            step.detail = f"{PRACTICE_AREA_NAME} (id={pa['id']})"
        else:
            step.status = "error"
            step.detail = f"'{PRACTICE_AREA_NAME}' not found"
            result.missing_items.append(f"Practice area: {PRACTICE_AREA_NAME}")
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
    result.steps.append(step)

    # 3. Check matter stages
    step = SetupStep(name="matter_stages")
    try:
        stages = await clio.get_matter_stages(practice_area_id=result.practice_area_id)
        stage_names = {s.get("name", "").lower() for s in stages}
        missing_stages = [s for s in REQUIRED_STAGES if s.lower() not in stage_names]
        if not missing_stages:
            step.status = "success"
            step.detail = f"All {len(REQUIRED_STAGES)} stages present"
        else:
            step.status = "error"
            step.detail = f"Missing: {', '.join(missing_stages)}"
            for ms in missing_stages:
                result.missing_items.append(f"Stage: {ms}")
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
    result.steps.append(step)

    # 4. Check custom fields
    step = SetupStep(name="custom_fields")
    try:
        fields = await clio.get_custom_fields()
        field_names = {f.get("name", "").lower() for f in fields}
        missing_fields = [
            name for name, _ in REQUIRED_CUSTOM_FIELDS
            if name.lower() not in field_names
        ]
        if not missing_fields:
            step.status = "success"
            step.detail = f"All {len(REQUIRED_CUSTOM_FIELDS)} fields present"
        else:
            step.status = "error"
            step.detail = f"{len(missing_fields)} missing"
            for mf in missing_fields:
                result.missing_items.append(f"Custom field: {mf}")
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
    result.steps.append(step)

    # 5. Check document template
    step = SetupStep(name="document_template")
    try:
        tmpl = await clio.find_template_by_name(RETAINER_TEMPLATE_NAME)
        if tmpl:
            step.status = "success"
            step.detail = tmpl.get("name") or tmpl.get("filename")
        else:
            step.status = "skipped"
            step.detail = "No retainer template found (local fallback available)"
    except Exception as e:
        step.status = "skipped"
        step.detail = f"Could not check templates: {str(e)[:100]}"
    result.steps.append(step)

    result.ready = len(result.missing_items) == 0
    return result


# ── Full setup (creates missing items) ───────────────────────────────────

async def setup_clio_account(clio: ClioClient) -> SetupResult:
    """Inspect the Clio account and create any missing configuration.

    Steps:
    1. Authenticate + verify attorney
    2. Ensure practice area exists
    3. Ensure all matter stages exist
    4. Ensure all custom fields exist
    5. Check document template (informational only)
    """
    result = SetupResult()

    # ── Step 1: Authenticate ──
    step = SetupStep(name="authenticate")
    try:
        me = await clio.who_am_i()
        result.attorney_name = me.get("name")
        result.attorney_id = me.get("id")
        step.status = "success"
        step.detail = me.get("name")
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
        result.steps.append(step)
        return result
    result.steps.append(step)

    # ── Step 2: Practice Area ──
    step = SetupStep(name="practice_area")
    try:
        practice_areas = await clio.get_practice_areas()
        pa = _find_by_name(practice_areas, PRACTICE_AREA_NAME)
        if pa:
            result.practice_area_id = pa["id"]
            step.status = "success"
            step.detail = f"Found '{PRACTICE_AREA_NAME}' (id={pa['id']})"
        else:
            pa = await clio.create_practice_area(PRACTICE_AREA_NAME)
            result.practice_area_id = pa["id"]
            step.status = "success"
            step.detail = f"Created '{PRACTICE_AREA_NAME}' (id={pa['id']})"
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
        result.missing_items.append(f"Practice area: {PRACTICE_AREA_NAME}")
    result.steps.append(step)

    # ── Step 3: Matter Stages ──
    step = SetupStep(name="matter_stages")
    try:
        stages = await clio.get_matter_stages(practice_area_id=result.practice_area_id)
        existing = {s.get("name", "").lower(): s for s in stages}
        created = []
        found = []
        for i, stage_name in enumerate(REQUIRED_STAGES):
            if stage_name.lower() in existing:
                found.append(stage_name)
            else:
                try:
                    await clio.create_matter_stage(
                        stage_name,
                        result.practice_area_id,
                        order=i + 1,
                    )
                    created.append(stage_name)
                except ClioAPIError as e:
                    logger.warning("Could not create stage '{}': {}", stage_name, e)
                    result.missing_items.append(f"Stage: {stage_name}")

        parts = []
        if found:
            parts.append(f"{len(found)} found")
        if created:
            parts.append(f"{len(created)} created")
        step.status = "success" if not result.missing_items else "error"
        step.detail = ", ".join(parts) if parts else "None processed"
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
    result.steps.append(step)

    # ── Step 4: Custom Fields ──
    step = SetupStep(name="custom_fields")
    try:
        fields = await clio.get_custom_fields()
        existing_fields = {f.get("name", "").lower(): f for f in fields}
        created_count = 0
        found_count = 0
        for field_name, field_type in REQUIRED_CUSTOM_FIELDS:
            if field_name.lower() in existing_fields:
                found_count += 1
            else:
                try:
                    await clio.create_custom_field(field_name, field_type)
                    created_count += 1
                except ClioAPIError as e:
                    logger.warning("Could not create custom field '{}': {}", field_name, e)
                    result.missing_items.append(f"Custom field: {field_name}")

        # Invalidate cached field map so pipeline picks up new fields
        clio._field_id_map = None

        parts = []
        if found_count:
            parts.append(f"{found_count} found")
        if created_count:
            parts.append(f"{created_count} created")
        step.status = "success" if not any("Custom field" in m for m in result.missing_items) else "error"
        step.detail = ", ".join(parts) if parts else "None processed"
    except Exception as e:
        step.status = "error"
        step.detail = str(e)[:200]
    result.steps.append(step)

    # ── Step 5: Document Template (informational) ──
    step = SetupStep(name="document_template")
    try:
        tmpl = await clio.find_template_by_name(RETAINER_TEMPLATE_NAME)
        if tmpl:
            step.status = "success"
            step.detail = tmpl.get("name") or tmpl.get("filename")
        else:
            step.status = "skipped"
            step.detail = "No retainer template - local fallback will be used"
    except Exception as e:
        step.status = "skipped"
        step.detail = f"Could not check templates: {str(e)[:100]}"
    result.steps.append(step)

    result.ready = len(result.missing_items) == 0
    return result


# ── Helpers ──────────────────────────────────────────────────────────────

def _find_by_name(items: list[dict], name: str) -> dict | None:
    """Case-insensitive name match in a list of Clio records."""
    name_lower = name.lower()
    for item in items:
        if item.get("name", "").lower() == name_lower:
            return item
    return None
