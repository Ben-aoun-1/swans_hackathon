from pydantic import BaseModel


class EmailData(BaseModel):
    """Data needed to compose and send the client email."""

    to_email: str
    client_first_name: str
    accident_date_formatted: str  # e.g. "March 15, 2024"
    accident_location: str
    accident_description_brief: str  # One sentence
    booking_link: str
    booking_type: str  # "in-office" or "virtual"
    retainer_pdf_bytes: bytes | None = None
    retainer_pdf_filename: str = "Retainer_Agreement.pdf"

    model_config = {"arbitrary_types_allowed": True}
