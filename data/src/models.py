"""Validation models for the source data.

Validating at the edge means bad records are caught where they enter the
pipeline, not three transformations later when the error message no longer
tells you anything useful.

Replace this model with one that matches your team's data source.
"""

from datetime import datetime

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
        """The source sends a Unix timestamp; store a real datetime."""
        if isinstance(value, int):
            return datetime.fromtimestamp(value)
        return value

    model_config = {"populate_by_name": True}
