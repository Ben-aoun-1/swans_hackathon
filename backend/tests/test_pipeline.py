"""End-to-end pipeline test with two-run idempotency check.

Run 1: Full pipeline — creates contact, matter, custom fields, stages,
       retainer, calendar, email, tasks, activity, communication, notes.
       Also tests: conflict check, priority scoring, AI email, speed-to-lead.
Run 2: Same extraction data, no matter_id — should find existing contact
       by email, find existing matter, detect duplicate report number,
       return duplicate_skipped=True.
"""

import asyncio
import sys
from pathlib import Path

# Add backend/ to path so `app` is importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.extraction import (
    ExtractionMetadata,
    ExtractionResult,
    FieldExtraction,
    OccupantInfo,
    PartyInfo,
)
from app.services.clio_pipeline import run_pipeline

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"
GUILLERMO_PDF = SAMPLES_DIR / "GUILLERMO_REYES_v_LIONEL_FRANCOIS_et_al_EXHIBIT_S__XX.pdf"


def build_mock_extraction() -> ExtractionResult:
    """Build a realistic mock ExtractionResult for testing."""
    plaintiff = PartyInfo(
        role=FieldExtraction(value="plaintiff", confidence="high", source="inferred",
                             note="Assigned plaintiff because this party sustained injuries and was legally stopped."),
        full_name=FieldExtraction(value="REYES, GUILLERMO", confidence="high", source="explicit"),
        address="123 Main St, Apt 4B, Queens, NY 11375",
        date_of_birth="1985-03-22",
        phone="718-555-0199",
        driver_license="S12345678",
        vehicle_year="2018",
        vehicle_make="TOYOTA",
        vehicle_model="CAMRY",
        vehicle_color=FieldExtraction(value="GRAY", confidence="high", source="explicit"),
        insurance_company=FieldExtraction(value="GEICO", confidence="high", source="explicit"),
        insurance_policy_number=FieldExtraction(value="POL-998877", confidence="high", source="explicit"),
        injuries=FieldExtraction(value="Neck pain, back pain, headache. Transported to Elmhurst Hospital.",
                                 confidence="high", source="explicit"),
        citation_issued=None,
        vehicle_number=1,
        occupants=[
            OccupantInfo(full_name="REYES, MARIA", vehicle_number=1, role="passenger", injuries="Shoulder pain"),
        ],
    )

    defendant = PartyInfo(
        role=FieldExtraction(value="defendant", confidence="medium", source="inferred",
                             note="Assigned defendant because narrative states this driver changed lanes and struck Vehicle 1. No citation issued."),
        full_name=FieldExtraction(value="FRANCOIS, LIONEL", confidence="high", source="explicit"),
        address="104-28 117 Street, Queens, NY 11419",
        date_of_birth="1955-05-09",
        phone=None,
        driver_license="403334776",
        vehicle_year="2011",
        vehicle_make="FORD",
        vehicle_model="VAN",
        vehicle_color=FieldExtraction(value=None, confidence="high", source="not_found"),
        insurance_company=FieldExtraction(value=None, confidence="medium", source="not_found",
                                          note="Insurance code 100 listed but carrier name not spelled out."),
        insurance_policy_number=FieldExtraction(value=None, confidence="high", source="not_found"),
        injuries=FieldExtraction(value="No injuries reported", confidence="high", source="explicit"),
        citation_issued=None,
        vehicle_number=2,
        occupants=[
            OccupantInfo(full_name="JEANBAPTISTE, YVONN", vehicle_number=2, role="passenger", injuries=None),
        ],
    )

    return ExtractionResult(
        report_number="2023-00123",
        accident_date="2023-06-15",
        accident_time="14:30",
        accident_location="Intersection of 5th Ave and 42nd St, New York, NY",
        accident_description=(
            "Vehicle 1 was traveling northbound on 5th Ave when Vehicle 2 ran a red light "
            "and struck Vehicle 1 on the driver side. Vehicle 1 driver and passenger reported "
            "injuries. EMS responded and transported Vehicle 1 driver to Elmhurst Hospital."
        ),
        weather_conditions="Clear",
        road_conditions="Dry",
        number_of_vehicles=2,
        reporting_officer_name="Officer Smith",
        reporting_officer_badge="4521",
        parties=[plaintiff, defendant],
        extraction_metadata=ExtractionMetadata(
            form_type="MV-104A",
            total_pages=2,
            is_amended=False,
        ),
    )


async def try_live_extraction() -> tuple[ExtractionResult | None, bytes | None]:
    """Attempt to extract from the real PDF. Returns (result, pdf_bytes) or (None, None)."""
    if not GUILLERMO_PDF.exists():
        print(f"  Sample PDF not found: {GUILLERMO_PDF}")
        return None, None

    try:
        from app.services.extraction import extract_from_pdf

        pdf_bytes = GUILLERMO_PDF.read_bytes()
        print(f"  Loading PDF ({len(pdf_bytes):,} bytes)...")
        print("  Calling Claude extraction (this may take 30-60s)...")
        result = await extract_from_pdf(pdf_bytes)
        return result, pdf_bytes
    except Exception as e:
        print(f"  Extraction failed: {e}")
        return None, None


def print_result(result, run_label: str) -> None:
    """Print pipeline result in a formatted table."""
    status_icon = {
        "success": "PASS",
        "error":   "FAIL",
        "skipped": "SKIP",
        "pending": "----",
        "running": "....",
    }

    print(f"\n  {'#':<4} {'Step':<30} {'Status':<8} {'Detail'}")
    print("  " + "-" * 90)
    for i, step in enumerate(result.steps, 1):
        icon = status_icon.get(step.status, "????")
        detail = (step.detail or "")[:70]
        print(f"  {i:<4} {step.name:<30} {icon:<8} {detail}")

    passed = sum(1 for s in result.steps if s.status == "success")
    failed = sum(1 for s in result.steps if s.status == "error")
    skipped = sum(1 for s in result.steps if s.status == "skipped")

    print("  " + "-" * 90)
    print(f"  Total: {len(result.steps)} steps — {passed} passed, {failed} failed, {skipped} skipped")
    print(f"\n  Overall success:    {result.success}")
    print(f"  Matter ID:          {result.matter_id}")
    print(f"  Matter URL:         {result.matter_url}")
    print(f"  Duplicate skipped:  {result.duplicate_skipped}")
    if result.speed_to_lead_seconds is not None:
        print(f"  Speed-to-lead:      {result.speed_to_lead_seconds:.1f}s")
    if result.priority_score is not None:
        print(f"  Priority score:     {result.priority_score}/10")
    if result.conflict_warning:
        print(f"  Conflict warning:   {result.conflict_warning[:80]}")


async def main():
    # ── Get extraction data ──────────────────────────────────────
    print("=" * 70)
    print("EXTRACTION")
    print("=" * 70)

    extraction, pdf_bytes = await try_live_extraction()

    if extraction is None:
        print("  -> Falling back to mock ExtractionResult")
        extraction = build_mock_extraction()
        pdf_bytes = GUILLERMO_PDF.read_bytes() if GUILLERMO_PDF.exists() else None
        source = "MOCK"
    else:
        source = "LIVE"

    plaintiff = next((p for p in extraction.parties if p.role.value == "plaintiff"), None)
    defendant = next((p for p in extraction.parties if p.role.value == "defendant"), None)

    print(f"\n  Source:           {source}")
    print(f"  Report #:         {extraction.report_number}")
    print(f"  Accident date:    {extraction.accident_date}")
    print(f"  Location:         {extraction.accident_location}")
    print(f"  Plaintiff:        {plaintiff.full_name.value if plaintiff else 'N/A'}")
    print(f"  Defendant:        {defendant.full_name.value if defendant else 'N/A'}")
    print(f"  Parties:          {len(extraction.parties)}")
    print(f"  Form type:        {extraction.extraction_metadata.form_type}")
    if pdf_bytes:
        print(f"  PDF size:         {len(pdf_bytes):,} bytes")

    # ── RUN 1: Full pipeline from scratch ────────────────────────
    print("\n" + "=" * 70)
    print("RUN 1: FULL PIPELINE (19 steps)")
    print("=" * 70)

    result1 = await run_pipeline(extraction, pdf_bytes=pdf_bytes)
    print_result(result1, "Run 1")

    if result1.success:
        print("\n  *** RUN 1 PASSED ***")
    else:
        print("\n  *** RUN 1 HAD ERRORS ***")

    # ── RUN 2: Idempotency test (no matter_id) ──────────────────
    print("\n" + "=" * 70)
    print("RUN 2: IDEMPOTENCY TEST (same data, no matter_id)")
    print("=" * 70)

    result2 = await run_pipeline(extraction, pdf_bytes=pdf_bytes)
    print_result(result2, "Run 2")

    if result2.duplicate_skipped:
        print("\n  *** RUN 2 CORRECTLY DETECTED DUPLICATE — SKIPPED ***")
    elif result2.success:
        print("\n  *** RUN 2 PASSED (but did NOT detect duplicate) ***")
    else:
        print("\n  *** RUN 2 HAD ERRORS ***")

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Run 1 success:           {result1.success}")
    print(f"  Run 1 matter_id:         {result1.matter_id}")
    print(f"  Run 1 speed-to-lead:     {result1.speed_to_lead_seconds:.1f}s" if result1.speed_to_lead_seconds else "  Run 1 speed-to-lead:     N/A")
    print(f"  Run 1 priority:          {result1.priority_score}/10" if result1.priority_score else "  Run 1 priority:          N/A")
    print(f"  Run 1 conflict:          {result1.conflict_warning or 'None'}")
    print(f"  Run 2 success:           {result2.success}")
    print(f"  Run 2 matter_id:         {result2.matter_id}")
    print(f"  Run 2 duplicate_skipped: {result2.duplicate_skipped}")
    print(f"  Same matter used:        {result1.matter_id == result2.matter_id}")

    all_pass = result1.success and result2.success and result2.duplicate_skipped
    if all_pass:
        print("\n  *** ALL TESTS PASSED ***")
    else:
        print("\n  *** SOME TESTS FAILED — see details above ***")

    return 0 if all_pass else 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
