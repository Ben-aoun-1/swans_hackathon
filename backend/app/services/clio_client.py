"""Clio Manage API v4 client wrapper.

Handles all HTTP communication with Clio including OAuth token refresh,
matters, contacts, custom fields, documents, and calendar entries.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.config import settings

TOKENS_FILE = Path(__file__).resolve().parent.parent.parent / ".clio_tokens.json"


class ClioAPIError(Exception):
    """Raised when Clio API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Clio API {status_code}: {detail}")


class ClioClient:
    """Async HTTP client for the Clio Manage API v4.

    Usage::

        async with ClioClient() as clio:
            me = await clio.who_am_i()
    """

    def __init__(self) -> None:
        self._access_token: str = settings.clio_access_token
        self._refresh_token: str = settings.clio_refresh_token
        self._base_url: str = settings.clio_base_url
        self._client_id: str = settings.clio_client_id
        self._client_secret: str = settings.clio_client_secret

        # Try to load tokens from backup file on disk
        self._load_tokens_from_file()

        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._build_headers(),
            timeout=30.0,
        )

        # In-memory cache for custom field ID mapping
        self._field_id_map: dict[str, int] | None = None

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-API-VERSION": "4.0.13",
        }

    def _load_tokens_from_file(self) -> None:
        """Load tokens from backup JSON file if they exist and in-memory ones are empty."""
        if self._access_token and self._refresh_token:
            return
        if TOKENS_FILE.exists():
            try:
                data = json.loads(TOKENS_FILE.read_text())
                if not self._access_token and data.get("access_token"):
                    self._access_token = data["access_token"]
                    settings.clio_access_token = data["access_token"]
                if not self._refresh_token and data.get("refresh_token"):
                    self._refresh_token = data["refresh_token"]
                    settings.clio_refresh_token = data["refresh_token"]
                logger.info("Loaded Clio tokens from {}", TOKENS_FILE)
            except Exception as e:
                logger.warning("Failed to load tokens file: {}", e)

    def _save_tokens_to_file(self) -> None:
        """Persist current tokens to disk."""
        try:
            TOKENS_FILE.write_text(
                json.dumps(
                    {
                        "access_token": self._access_token,
                        "refresh_token": self._refresh_token,
                    },
                    indent=2,
                )
            )
            logger.debug("Saved Clio tokens to {}", TOKENS_FILE)
        except Exception as e:
            logger.warning("Failed to save tokens file: {}", e)

    # -- Context manager ---------------------------------------------------

    async def __aenter__(self) -> ClioClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._http.aclose()

    # -- Token management --------------------------------------------------

    async def _refresh_access_token(self) -> None:
        """Refresh the OAuth access token using the refresh token."""
        logger.info("Refreshing Clio access token…")
        resp = await self._http.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if resp.status_code != 200:
            raise ClioAPIError(resp.status_code, f"Token refresh failed: {resp.text}")

        body = resp.json()
        self._access_token = body["access_token"]
        self._refresh_token = body["refresh_token"]

        # Update in-memory settings so other code paths see the new token
        settings.clio_access_token = self._access_token
        settings.clio_refresh_token = self._refresh_token

        # Update the httpx client headers
        self._http.headers["Authorization"] = f"Bearer {self._access_token}"

        # Persist to disk
        self._save_tokens_to_file()
        logger.info("Clio access token refreshed successfully")

    # -- Central request method --------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        raw_response: bool = False,
    ) -> Any:
        """Send a request to Clio with automatic 401 refresh and 429 backoff.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE).
            path: API path, e.g. ``/api/v4/matters/123``.
            json_body: JSON body for POST/PATCH.
            params: Query parameters.
            raw_response: If True, return raw bytes instead of JSON.

        Returns:
            Parsed JSON dict (or bytes if raw_response=True).
        """
        max_retries = 3
        backoff_seconds = [1, 2, 4]

        for attempt in range(max_retries + 1):
            logger.debug("Clio {} {} (attempt {})", method, path, attempt + 1)

            kwargs: dict[str, Any] = {"params": params}
            if json_body is not None:
                kwargs["json"] = json_body

            resp = await self._http.request(method, path, **kwargs)

            # 401 → refresh token and retry once
            if resp.status_code == 401 and attempt == 0:
                logger.warning("Got 401, refreshing token…")
                await self._refresh_access_token()
                continue

            # 429 → exponential backoff
            if resp.status_code == 429 and attempt < max_retries:
                wait = backoff_seconds[min(attempt, len(backoff_seconds) - 1)]
                logger.warning("Rate limited (429), waiting {}s…", wait)
                await asyncio.sleep(wait)
                continue

            # Success
            if 200 <= resp.status_code < 300:
                if raw_response:
                    return resp.content
                # Some endpoints return empty body (204)
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            # Unrecoverable error
            detail = resp.text[:500]
            logger.error("Clio API error {} on {} {}: {}", resp.status_code, method, path, detail)
            raise ClioAPIError(resp.status_code, detail)

        # Should not reach here, but just in case
        raise ClioAPIError(429, "Max retries exceeded on rate limit")

    # =====================================================================
    # Identity
    # =====================================================================

    async def who_am_i(self) -> dict:
        """Get the authenticated user's info."""
        resp = await self._request("GET", "/api/v4/users/who_am_i", params={"fields": "id,name,email"})
        return resp.get("data", resp)

    # =====================================================================
    # Contacts
    # =====================================================================

    async def create_contact(
        self,
        first_name: str,
        last_name: str,
        *,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
    ) -> dict:
        """Create a new contact in Clio."""
        data: dict[str, Any] = {
            "first_name": first_name,
            "last_name": last_name,
            "type": "Person",
        }

        if email:
            data["email_addresses"] = [{"name": "Work", "address": email, "default_email": True}]
        if phone:
            data["phone_numbers"] = [{"name": "Work", "number": phone, "default_phone_number": True}]
        if address:
            # Clio expects structured address, but we only have a string — use primary_address
            data["addresses"] = [{"name": "Work", "street": address}]

        resp = await self._request(
            "POST",
            "/api/v4/contacts",
            json_body={"data": data},
            params={"fields": "id,name,first_name,last_name,email_addresses{address}"},
        )
        contact = resp.get("data", resp)
        logger.info("Created Clio contact: {} (id={})", contact.get("name"), contact.get("id"))
        return contact

    async def find_contact_by_name(self, name: str) -> dict | None:
        """Search for a contact by name. Returns the first match or None."""
        resp = await self._request(
            "GET",
            "/api/v4/contacts",
            params={
                "query": name,
                "fields": "id,name,first_name,last_name,email_addresses{address}",
            },
        )
        contacts = resp.get("data", [])
        return contacts[0] if contacts else None

    # =====================================================================
    # Matters
    # =====================================================================

    async def create_matter(
        self,
        client_id: int,
        description: str,
        *,
        practice_area_id: int | None = None,
        responsible_attorney_id: int | None = None,
    ) -> dict:
        """Create a new matter in Clio."""
        data: dict[str, Any] = {
            "client": {"id": client_id},
            "description": description,
            "status": "open",
        }
        if practice_area_id:
            data["practice_area"] = {"id": practice_area_id}
        if responsible_attorney_id:
            data["responsible_attorney"] = {"id": responsible_attorney_id}

        resp = await self._request(
            "POST",
            "/api/v4/matters",
            json_body={"data": data},
            params={"fields": "id,etag,display_number,description,status"},
        )
        matter = resp.get("data", resp)
        logger.info("Created Clio matter: {} (id={})", matter.get("display_number"), matter.get("id"))
        return matter

    async def get_matter(self, matter_id: int) -> dict:
        """Get full matter details including custom fields and stage."""
        resp = await self._request(
            "GET",
            f"/api/v4/matters/{matter_id}",
            params={
                "fields": (
                    "id,etag,display_number,description,status,"
                    "client{id,name},"
                    "custom_field_values{id,field_name,value},"
                    "matter_stage{id,name}"
                ),
            },
        )
        return resp.get("data", resp)

    async def update_matter_custom_fields(
        self,
        matter_id: int,
        etag: str,
        field_values: list[dict],
    ) -> dict:
        """Update custom field values on a matter.

        Args:
            matter_id: Clio matter ID.
            etag: Current etag (required for PATCH).
            field_values: List of ``{"custom_field": {"id": X}, "value": "Y"}``.
        """
        resp = await self._request(
            "PATCH",
            f"/api/v4/matters/{matter_id}",
            json_body={"data": {"custom_field_values": field_values}},
            params={
                "fields": "id,etag,custom_field_values{id,field_name,value}",
                "if-match": etag,
            },
        )
        matter = resp.get("data", resp)
        logger.info("Updated {} custom fields on matter {}", len(field_values), matter_id)
        return matter

    async def update_matter_stage(
        self,
        matter_id: int,
        etag: str,
        stage_id: int,
    ) -> dict:
        """Change the matter's stage (e.g. to "Data Verified")."""
        resp = await self._request(
            "PATCH",
            f"/api/v4/matters/{matter_id}",
            json_body={"data": {"status": "open", "matter_stage": {"id": stage_id}}},
            params={
                "fields": "id,etag,matter_stage{id,name}",
                "if-match": etag,
            },
        )
        matter = resp.get("data", resp)
        stage_name = (matter.get("matter_stage") or {}).get("name", "unknown")
        logger.info("Matter {} stage changed to '{}'", matter_id, stage_name)
        return matter

    # =====================================================================
    # Custom Fields
    # =====================================================================

    async def get_custom_fields(self) -> list[dict]:
        """List all matter-level custom fields."""
        resp = await self._request(
            "GET",
            "/api/v4/custom_fields",
            params={"fields": "id,name,field_type,parent_type", "parent_type": "Matter"},
        )
        return resp.get("data", [])

    async def build_field_id_map(self) -> dict[str, int]:
        """Build and cache a mapping of custom field name → Clio field ID."""
        if self._field_id_map is not None:
            return self._field_id_map

        fields = await self.get_custom_fields()
        self._field_id_map = {f["name"]: f["id"] for f in fields}
        logger.info("Built field ID map with {} custom fields: {}", len(self._field_id_map), list(self._field_id_map.keys()))
        return self._field_id_map

    # =====================================================================
    # Practice Areas & Matter Stages
    # =====================================================================

    async def get_practice_areas(self) -> list[dict]:
        """List all practice areas."""
        resp = await self._request(
            "GET",
            "/api/v4/practice_areas",
            params={"fields": "id,name"},
        )
        return resp.get("data", [])

    async def get_matter_stages(self, practice_area_id: int | None = None) -> list[dict]:
        """List matter stages, optionally filtered by practice area."""
        params: dict[str, Any] = {"fields": "id,name,order"}
        if practice_area_id:
            params["practice_area_id"] = practice_area_id
        resp = await self._request("GET", "/api/v4/matter_stages", params=params)
        return resp.get("data", [])

    async def get_stage_id_by_name(
        self, name: str, practice_area_id: int | None = None
    ) -> int | None:
        """Find a matter stage ID by name (case-insensitive substring match)."""
        stages = await self.get_matter_stages(practice_area_id=practice_area_id)
        name_lower = name.lower()
        for stage in stages:
            if name_lower in stage.get("name", "").lower():
                return stage["id"]
        return None

    # =====================================================================
    # Calendar Entries
    # =====================================================================

    async def create_calendar_entry(self, data: dict) -> dict:
        """Create a calendar entry in Clio."""
        resp = await self._request(
            "POST",
            "/api/v4/calendar_entries",
            json_body={"data": data},
            params={"fields": "id,summary,start_at,end_at,all_day"},
        )
        entry = resp.get("data", resp)
        logger.info("Created calendar entry: {} (id={})", entry.get("summary"), entry.get("id"))
        return entry

    async def get_calendars(self) -> list[dict]:
        """List all calendars (used to resolve user → calendar_owner ID)."""
        resp = await self._request(
            "GET",
            "/api/v4/calendars",
            params={"fields": "id,name"},
        )
        return resp.get("data", [])

    # =====================================================================
    # Documents & Templates
    # =====================================================================

    async def generate_document_from_template(
        self,
        matter_id: int,
        template_id: int,
        name: str,
    ) -> dict:
        """Generate a document from a Clio document template."""
        resp = await self._request(
            "POST",
            "/api/v4/documents",
            json_body={
                "data": {
                    "name": name,
                    "parent": {"id": matter_id, "type": "Matter"},
                    "document_template": {"id": template_id},
                }
            },
            params={"fields": "id,name,content_type,created_at,latest_document_version{id}"},
        )
        doc = resp.get("data", resp)
        logger.info("Generated document '{}' (id={}) from template {}", doc.get("name"), doc.get("id"), template_id)
        return doc

    async def list_matter_documents(self, matter_id: int) -> list[dict]:
        """List all documents attached to a matter."""
        resp = await self._request(
            "GET",
            "/api/v4/documents",
            params={
                "matter_id": matter_id,
                "fields": "id,name,content_type,created_at,latest_document_version{id}",
            },
        )
        return resp.get("data", [])

    async def download_document(self, document_id: int) -> bytes:
        """Download a document's file content as raw bytes.

        Tries /documents/{id}/download first. On 404, fetches the document
        metadata to get the latest_document_version ID and retries with
        /document_versions/{version_id}/download.
        """
        try:
            return await self._request(
                "GET",
                f"/api/v4/documents/{document_id}/download",
                raw_response=True,
            )
        except ClioAPIError as e:
            if e.status_code != 404:
                raise
            logger.debug("Document download 404, trying via document_version…")

        # Fetch document metadata to get the version ID
        resp = await self._request(
            "GET",
            f"/api/v4/documents/{document_id}",
            params={"fields": "id,latest_document_version{id}"},
        )
        doc = resp.get("data", resp)
        version = (doc.get("latest_document_version") or {}).get("id")
        if not version:
            raise ClioAPIError(404, f"No document version found for document {document_id}")

        return await self._request(
            "GET",
            f"/api/v4/document_versions/{version}/download",
            raw_response=True,
        )

    async def get_document_templates(self) -> list[dict]:
        """List all document templates."""
        resp = await self._request(
            "GET",
            "/api/v4/document_templates",
            params={"fields": "id,filename"},
        )
        # Normalize: expose "filename" as "name" for consistent downstream usage
        templates = resp.get("data", [])
        for t in templates:
            if "filename" in t and "name" not in t:
                t["name"] = t["filename"]
        return templates

    async def find_template_by_name(self, name: str) -> dict | None:
        """Find a document template by name (case-insensitive substring match)."""
        templates = await self.get_document_templates()
        name_lower = name.lower()
        for tmpl in templates:
            if name_lower in tmpl.get("name", "").lower():
                return tmpl
        return None
