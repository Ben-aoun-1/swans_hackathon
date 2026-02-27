from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AI Extraction
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model ID for extraction",
    )

    # Clio Manage — OAuth 2.0
    clio_client_id: str = Field(default="", description="Clio OAuth client ID")
    clio_client_secret: str = Field(default="", description="Clio OAuth client secret")
    clio_redirect_uri: str = Field(
        default="http://localhost:8000/api/clio/callback",
        description="Clio OAuth redirect URI",
    )
    clio_access_token: str = Field(default="", description="Clio access token")
    clio_refresh_token: str = Field(default="", description="Clio refresh token")
    clio_base_url: str = Field(
        default="https://app.clio.com",
        description="Clio API base URL",
    )

    # Email — SMTP
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: str = Field(default="", description="SMTP username")
    smtp_password: str = Field(default="", description="SMTP password")
    from_email: str = Field(default="", description="Sender email address")

    # Booking Links
    in_office_booking_url: str = Field(
        default="https://calendly.com/richards-law/in-office",
        description="In-office booking URL (March-August)",
    )
    virtual_booking_url: str = Field(
        default="https://calendly.com/richards-law/virtual",
        description="Virtual booking URL (September-February)",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
