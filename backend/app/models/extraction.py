from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, computed_field

T = TypeVar("T")


class FieldExtraction(BaseModel, Generic[T]):
    """A single extracted field with confidence metadata."""

    value: T | None = None
    confidence: Literal["high", "medium", "low"] = "high"
    source: Literal["explicit", "inferred", "not_found"] = "explicit"
    note: str | None = None  # Only populated when confidence is medium/low


class OccupantInfo(BaseModel):
    """An occupant (non-driver) associated with a vehicle."""

    full_name: str | None = None
    vehicle_number: int | None = None
    role: Literal["driver", "passenger", "pedestrian", "other"] = "passenger"
    injuries: str | None = None


class PartyInfo(BaseModel):
    """Information about a party involved in the accident."""

    # Fields with confidence tracking (ambiguous on police reports)
    role: FieldExtraction[Literal["plaintiff", "defendant", "witness", "other"]]
    full_name: FieldExtraction[str]
    vehicle_color: FieldExtraction[str] = FieldExtraction(source="not_found")
    insurance_company: FieldExtraction[str] = FieldExtraction(source="not_found")
    insurance_policy_number: FieldExtraction[str] = FieldExtraction(source="not_found")
    injuries: FieldExtraction[str] = FieldExtraction(source="not_found")

    # Plain fields (either present or not — no ambiguity)
    address: str | None = None
    date_of_birth: str | None = None  # YYYY-MM-DD
    phone: str | None = None
    driver_license: str | None = None
    vehicle_year: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    citation_issued: str | None = None

    # Vehicle section mapping
    vehicle_number: int | None = None  # Which vehicle section (1, 2, 3) on the form

    # Occupants associated with this party's vehicle
    occupants: list[OccupantInfo] = []


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process and quality."""

    form_type: str | None = None  # e.g. "MV-104", "MV-104A", "unknown"
    total_pages: int = 0
    fields_extracted: int = 0
    fields_inferred: int = 0
    fields_not_found: int = 0
    low_confidence_fields: list[str] = []  # Field names for the review UI to highlight
    is_amended: bool = False
    review_date: str | None = None  # Supervisor review date if visible
    filing_info: str | None = None  # e.g. "Index No. 500055/2023, filed 06/20/2023"


class ExtractionResult(BaseModel):
    """Structured data extracted from a police/accident report PDF."""

    report_number: str | None = None
    accident_date: str | None = None  # YYYY-MM-DD
    accident_time: str | None = None  # HH:MM
    accident_location: str | None = None
    accident_description: str | None = None
    weather_conditions: str | None = None
    road_conditions: str | None = None
    number_of_vehicles: int | None = None
    reporting_officer_name: str | None = None
    reporting_officer_badge: str | None = None
    parties: list[PartyInfo] = []
    extraction_metadata: ExtractionMetadata = ExtractionMetadata()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_notes(self) -> str | None:
        """Auto-generate a human-readable confidence summary for backward compatibility."""
        notes: list[str] = []
        meta = self.extraction_metadata

        if meta.low_confidence_fields:
            notes.append(
                f"Low confidence on: {', '.join(meta.low_confidence_fields)}."
            )

        if meta.fields_inferred > 0:
            notes.append(f"{meta.fields_inferred} field(s) were inferred from context.")

        # Collect per-field notes from parties
        for i, party in enumerate(self.parties, 1):
            for field_name in ("role", "full_name", "vehicle_color", "insurance_company", "insurance_policy_number", "injuries"):
                fe: FieldExtraction = getattr(party, field_name)  # type: ignore[type-arg]
                if fe.note:
                    party_label = fe.value if field_name == "full_name" and fe.value else f"Party {i}"
                    notes.append(f"{party_label} — {field_name}: {fe.note}")

        if meta.filing_info:
            notes.append(f"Filing info: {meta.filing_info}")

        if meta.is_amended:
            notes.append("This is an AMENDED report.")

        return " | ".join(notes) if notes else None
