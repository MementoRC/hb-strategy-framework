"""StrategyConfigBase — Pydantic v2 base for all strategy configurations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrategyConfigBase(BaseModel):
    """Base configuration for strategies.

    Subclasses define their fields. Fields listed in Meta.updatable
    can be changed at runtime via update_from().
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    controller_id: str
    controller_name: str = ""
    controller_type: str = "generic"

    class Meta:
        updatable: list[str] = []

    def get_updatable_fields(self) -> list[str]:
        """Return list of field names that can be updated at runtime."""
        return self.Meta.updatable

    def update_from(self, other: object) -> None:
        """Update only the updatable fields from another config instance."""
        for field_name in self.get_updatable_fields():
            if hasattr(other, field_name):
                setattr(self, field_name, getattr(other, field_name))
