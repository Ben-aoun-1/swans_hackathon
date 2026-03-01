"""End-to-end pipeline test: extraction → Clio pipeline.

Loads the Guillermo Reyes sample PDF, extracts data via Claude,
then runs the full Clio pipeline (contact → matter → custom fields →
stage → retainer → calendar → email).

Falls back to a mock ExtractionResult if extraction fails.
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


async def try_live_extraction() -> ExtractionResult | None:
    """Attempt to extract from the real PDF. Returns None on failure."""
    if not GUILLERMO_PDF.exists():
        print(f"  Sample PDF not found: {GUILLERMO_PDF}")
        return None

    try:
        from app.services.extraction import extract_from_pdf

        print(f"  Loading PDF ({GUILLERMO_PDF.stat().st_size:,} bytes)...")
        pdf_bytes = GUILLERMO_PDF.read_bytes()
        print("  Calling Claude extraction (this may take 30-60s)...")
        result = await extract_from_pdf(pdf_bytes)
        return result
    except Exception as e:
        print(f"  Extraction failed: {e}")
        return None


async def main():
    # ── Step 1: Get extraction data ──────────────────────────────
    print("=" * 70)
    print("STEP 1: EXTRACTION")
    print("=" * 70)

    extraction = await try_live_extraction()

    if extraction is None:
        print("  → Falling back to mock ExtractionResult")
        extraction = build_mock_extraction()
        source = "MOCK"
    else:
        source = "LIVE"

    # Print summary
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

    # ── Step 2: Run Clio pipeline ────────────────────────────────
    print("\n" + "=" * 70)
    print("STEP 2: CLIO PIPELINE")
    print("=" * 70)

    result = await run_pipeline(extraction)

    # ── Step 3: Print results ────────────────────────────────────
    print("\n" + "=" * 70)
    print("PIPELINE RESULTS")
    print("=" * 70)

    status_icon = {
        "success": "PASS",
        "error":   "FAIL",
        "skipped": "SKIP",
        "pending": "----",
        "running": "....",
    }

    print(f"\n  {'#':<4} {'Step':<25} {'Status':<8} {'Detail'}")
    print("  " + "-" * 80)
    for i, step in enumerate(result.steps, 1):
        icon = status_icon.get(step.status, "????")
        detail = (step.detail or "")[:60]
        print(f"  {i:<4} {step.name:<25} {icon:<8} {detail}")

    passed = sum(1 for s in result.steps if s.status == "success")
    failed = sum(1 for s in result.steps if s.status == "error")
    skipped = sum(1 for s in result.steps if s.status == "skipped")

    print("  " + "-" * 80)
    print(f"  Total: {len(result.steps)} steps — {passed} passed, {failed} failed, {skipped} skipped")
    print(f"\n  Overall success:  {result.success}")
    print(f"  Matter ID:        {result.matter_id}")
    print(f"  Matter URL:       {result.matter_url}")

    if result.success:
        print("\n  *** END-TO-END PIPELINE TEST PASSED ***")
    else:
        print("\n  *** PIPELINE HAD ERRORS — see details above ***")

    return 0 if result.success else 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
