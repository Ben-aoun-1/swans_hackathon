from pydantic import BaseModel
from typing import Literal


class PartyInfo(BaseModel):
    """Information about a party involved in the accident."""

    role: Literal["plaintiff", "defendant", "witness", "other"]
    full_name: str | None = None
    address: str | None = None
    date_of_birth: str | None = None  # YYYY-MM-DD
    phone: str | None = None
    driver_license: str | None = None
    vehicle_year: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    insurance_company: str | None = None
    insurance_policy_number: str | None = None
    injuries: str | None = None
    citation_issued: str | None = None


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
    confidence_notes: str | None = None
