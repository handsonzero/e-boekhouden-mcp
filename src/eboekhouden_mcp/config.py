import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DOMAIN = "e-boekhouden.nl"
# Not the working directory, so a `.env` in an untrusted checkout cannot change settings.
ENV_FILE = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "eboekhouden-mcp" / ".env"
)


class Settings(BaseSettings):
    """Configuration, read from `EB_*` environment variables (or `ENV_FILE`)."""

    model_config = SettingsConfigDict(env_prefix="EB_", env_file=ENV_FILE, extra="ignore")

    api_token: SecretStr = Field(
        description="API token from Beheer > Inrichting > Koppelingen > API."
    )
    source: str = Field(
        default="MCP",
        pattern=r"^[\w ]{1,10}$",
        description="Code identifying this integration to e-boekhouden.",
    )
    allow_writes: bool = Field(
        default=False,
        description="Expose create/update/delete tools in addition to read-only tools.",
    )
    base_url: str = "https://api.e-boekhouden.nl"
    timeout: float = Field(default=30.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        """The API token is sent to this URL, so only allow HTTPS to e-boekhouden itself."""
        url = urlsplit(value)
        host = url.hostname or ""
        if url.scheme != "https" or not (host == API_DOMAIN or host.endswith(f".{API_DOMAIN}")):
            raise ValueError(f"must be an https:// URL on {API_DOMAIN}")
        return value
