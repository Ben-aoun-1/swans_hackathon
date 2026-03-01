from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ClioCustomFieldValue(BaseModel):
    """A single custom field value to set on a Clio matter."""

    custom_field_id: int
    value: str


class ClioMatter(BaseModel):
    """Clio matter reference."""

    id: int
    etag: str | None = None
    display_number: str | None = None
    description: str | None = None
    status: str | None = None


class ClioCalendarEntry(BaseModel):
    """Data needed to create a statute of limitations calendar entry."""

    summary: str
    description: str
    start_at: str  # ISO datetime
    end_at: str  # ISO datetime
    all_day: bool = True
    matter_id: int
    attorney_user_id: int


class PipelineStep(BaseModel):
    """Status of a single step in the Clio pipeline."""

    name: str
    status: Literal["pending", "running", "success", "error", "skipped"] = "pending"
    detail: str | None = None


class PipelineResult(BaseModel):
    """Result of the full post-approval Clio pipeline."""

    success: bool
    matter_id: int | None = None
    matter_url: str | None = None
    steps: list[PipelineStep] = []
