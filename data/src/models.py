"""Validation models for the source data. Replace with your source's shape."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class Posting(BaseModel):
    """One job posting from the source API."""

    slug: str
    title: str
    company_name: str = Field(alias="company_name")
    location: str | None = None
    remote: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _epoch_to_datetime(cls, value: object) -> object:
        """Unix timestamp to a UTC datetime.

        Without the timezone, Python reads the number in whatever zone the
        machine is in, so your laptop and the container disagree about what
        `posted_at` means.
        """
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=UTC)
        return value

    model_config = {"populate_by_name": True}
