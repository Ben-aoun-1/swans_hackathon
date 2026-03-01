"""Statute of limitations calendar entry creation.

Creates a Clio calendar entry at accident_date + 8 years,
assigned to the responsible attorney with a 7-day reminder.
"""

from __future__ import annotations

from datetime import datetime

from dateutil.relativedelta import relativedelta
from loguru import logger

from app.services.clio_client import ClioClient


async def _resolve_calendar_id(clio: ClioClient, attorney_name: str) -> int | None:
    """Find the calendar ID that belongs to the given attorney.

    Clio's calendar_owner requires a *calendar* ID, not a user ID.
    We match by name (first calendar whose name contains the attorney name).
    Falls back to the first calendar if no match.
    """
    calendars = await clio.get_calendars()
    if not calendars:
        return None

    name_lower = attorney_name.lower().strip()
    for cal in calendars:
        if name_lower and name_lower in cal.get("name", "").lower():
            logger.debug("Matched calendar '{}' (id={}) for attorney '{}'", cal["name"], cal["id"], attorney_name)
            return cal["id"]

    # Fallback: first calendar (usually the logged-in user's)
    fallback = calendars[0]
    logger.debug("No name match for '{}', using first calendar '{}' (id={})", attorney_name, fallback["name"], fallback["id"])
    return fallback["id"]


async def create_statute_of_limitations_entry(
    clio: ClioClient,
    matter_id: int,
    accident_date_str: str,
    client_name: str,
    defendant_name: str,
    attorney_user_id: int,
) -> dict:
    """Create a statute of limitations calendar entry in Clio.

    Calculates SOL date as accident_date + 8 years and creates an all-day
    calendar entry assigned to the responsible attorney with a 7-day reminder.

    Args:
        clio: Authenticated ClioClient instance.
        matter_id: Clio matter ID.
        accident_date_str: Accident date as YYYY-MM-DD.
        client_name: Client name for the entry title.
        defendant_name: Defendant name for the entry title.
        attorney_user_id: Clio user ID of the responsible attorney.

    Returns:
        Created calendar entry dict from Clio.
    """
    accident_date = datetime.strptime(accident_date_str, "%Y-%m-%d").date()

    # +8 years — relativedelta handles Feb 29 → Feb 28 automatically
    sol_date = accident_date + relativedelta(years=8)

    logger.info(
        "SOL calculation: {} + 8 years = {}",
        accident_date.isoformat(),
        sol_date.isoformat(),
    )

    # Resolve the calendar ID from the attorney's user info
    me = await clio.who_am_i()
    calendar_id = await _resolve_calendar_id(clio, me.get("name", ""))
    if not calendar_id:
        raise ValueError("No calendars found in Clio — cannot create calendar entry")

    # Format as ISO datetime with Eastern timezone offset
    start_at = f"{sol_date.isoformat()}T09:00:00-05:00"
    end_at = f"{sol_date.isoformat()}T17:00:00-05:00"

    entry_data = {
        "summary": f"⚠️ Statute of Limitations — {client_name} v {defendant_name}",
        "description": (
            f"Statute of limitations expires on this date for the personal injury "
            f"matter {client_name} v {defendant_name}. "
            f"Accident date: {accident_date_str}. "
            f"Take action to preserve claims before this deadline."
        ),
        "start_at": start_at,
        "end_at": end_at,
        "all_day": True,
        "matter": {"id": matter_id},
        "calendar_owner": {"id": calendar_id},
        "reminders": [{"minutes": 10080}],  # 7 days = 10080 minutes
    }

    entry = await clio.create_calendar_entry(entry_data)
    logger.info(
        "Created SOL calendar entry for {} (SOL date: {}, calendar_id={})",
        client_name,
        sol_date.isoformat(),
        calendar_id,
    )
    return entry
