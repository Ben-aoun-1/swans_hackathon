"""Personalized client email sender.

Sends a warm email to the potential client with:
- Reference to their specific accident
- Retainer agreement PDF attached
- Seasonal booking link (March-Aug: in-office, Sep-Feb: virtual)
"""

from __future__ import annotations

from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from app.models.email import EmailData

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"


def get_booking_link(
    in_office_url: str,
    virtual_url: str,
    reference_date: datetime | None = None,
) -> tuple[str, str]:
    """Return (booking_url, booking_type) based on the current month.

    March–August → in-office
    September–February → virtual
    """
    date = reference_date or datetime.now()
    month = date.month

    if 3 <= month <= 8:
        return in_office_url, "in-office"
    else:
        return virtual_url, "virtual"


async def send_client_email(email_data: EmailData, smtp_config: dict) -> None:
    """Compose and send the personalized client email with retainer attachment.

    Args:
        email_data: All template variables and the retainer PDF bytes.
        smtp_config: Dict with keys: host, port, user, password, from_email.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

    template_vars = {
        "client_first_name": email_data.client_first_name,
        "accident_date_formatted": email_data.accident_date_formatted,
        "accident_location": email_data.accident_location,
        "accident_description_brief": email_data.accident_description_brief,
        "booking_link": email_data.booking_link,
        "booking_type": email_data.booking_type,
    }

    # Render HTML and plain text bodies
    html_template = env.get_template("client_email.html")
    html_body = html_template.render(**template_vars)

    text_template = env.get_template("client_email.txt")
    text_body = text_template.render(**template_vars)

    # Build MIME message
    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_config["from_email"]
    msg["To"] = email_data.to_email
    msg["Subject"] = "Richards & Law — Your Case Review and Next Steps"

    # HTML + plain text alternative
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    # Attach retainer PDF if available
    if email_data.retainer_pdf_bytes:
        pdf_part = MIMEApplication(email_data.retainer_pdf_bytes, _subtype="pdf")
        pdf_part.add_header(
            "Content-Disposition",
            "attachment",
            filename=email_data.retainer_pdf_filename,
        )
        msg.attach(pdf_part)
        logger.debug(
            "Attached retainer PDF ({} bytes) as '{}'",
            len(email_data.retainer_pdf_bytes),
            email_data.retainer_pdf_filename,
        )

    # Send via SMTP
    logger.info("Sending email to {} via {}:{}", email_data.to_email, smtp_config["host"], smtp_config["port"])
    await aiosmtplib.send(
        msg,
        hostname=smtp_config["host"],
        port=smtp_config["port"],
        username=smtp_config["user"],
        password=smtp_config["password"],
        use_tls=False,
        start_tls=True,
    )
    logger.info("Email sent successfully to {}", email_data.to_email)
