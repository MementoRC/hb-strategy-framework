"""TrailingStop — activation price + trailing delta with string serialization."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class TrailingStop(BaseModel):
    """Immutable trailing stop configuration.

    When PnL exceeds activation_price_pct, a trailing stop is placed
    at trailing_delta_pct below the peak PnL.

    String format: "activation,delta" (e.g., "0.015,0.005").
    """

    model_config = ConfigDict(frozen=True)

    activation_price_pct: Decimal
    trailing_delta_pct: Decimal

    @field_validator("activation_price_pct", "trailing_delta_pct", mode="before")
    @classmethod
    def _validate_positive(cls, v: object) -> Decimal:
        val = Decimal(str(v))
        if val < 0:
            msg = "TrailingStop values must be non-negative"
            raise ValueError(msg)
        return val

    @classmethod
    def from_string(cls, s: str) -> TrailingStop:
        """Parse 'activation,delta' format."""
        parts = s.strip().split(",")
        if len(parts) != 2:
            msg = f"Expected format 'activation,delta', got '{s}'"
            raise ValueError(msg)
        return cls(
            activation_price_pct=Decimal(parts[0].strip()),
            trailing_delta_pct=Decimal(parts[1].strip()),
        )

    def to_string(self) -> str:
        """Serialize to 'activation,delta' format."""
        return f"{self.activation_price_pct},{self.trailing_delta_pct}"

    def scale(self, factor: Decimal) -> TrailingStop:
        """Return a new TrailingStop with both values scaled."""
        return TrailingStop(
            activation_price_pct=self.activation_price_pct * factor,
            trailing_delta_pct=self.trailing_delta_pct * factor,
        )
