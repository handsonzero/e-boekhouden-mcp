import pytest
from pydantic import ValidationError

from eboekhouden_mcp.config import ENV_FILE, Settings


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.e-boekhouden.nl",
        "https://evil.example",
        "https://api.e-boekhouden.nl.evil.example",
        "https://evil-e-boekhouden.nl",
        "https://api.e-boekhouden.nl@evil.example",
    ],
)
def test_base_url_must_be_e_boekhouden_over_https(base_url: str) -> None:
    with pytest.raises(ValidationError, match="base_url"):
        Settings(api_token="t", base_url=base_url, _env_file=None)  # pyright: ignore[reportCallIssue]


def test_api_token_is_not_shown_in_errors() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(api_token="secret-api-token", source="x" * 11, _env_file=None)  # pyright: ignore[reportCallIssue]
    assert "secret-api-token" not in str(error.value)


def test_env_file_is_next_to_pyproject() -> None:
    assert ENV_FILE.is_absolute()
    assert (ENV_FILE.parent / "pyproject.toml").is_file()
