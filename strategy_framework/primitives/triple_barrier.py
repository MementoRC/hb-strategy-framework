"""TripleBarrierConfig — stop-loss, take-profit, and time-limit configuration."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class TripleBarrierConfig(BaseModel):
    """Immutable barrier configuration for executor position management.

    All percentage values are fractions (0.03 = 3%).
    A value of 0 means the barrier is disabled.
    """

    model_config = ConfigDict(frozen=True)

    stop_loss: Decimal = Decimal("0")
    take_profit: Decimal = Decimal("0")
    time_limit_s: int = 0

    @field_validator("stop_loss", "take_profit", mode="before")
    @classmethod
    def _validate_non_negative_decimal(cls, v: object) -> Decimal:
        val = Decimal(str(v))
        if val < 0:
            msg = "Barrier values must be non-negative"
            raise ValueError(msg)
        return val

    @field_validator("time_limit_s", mode="before")
    @classmethod
    def _validate_non_negative_time(cls, v: object) -> int:
        val = int(v)  # type: ignore[arg-type]
        if val < 0:
            msg = "time_limit_s must be non-negative"
            raise ValueError(msg)
        return val

    @property
    def has_stop_loss(self) -> bool:
        return self.stop_loss > 0

    @property
    def has_take_profit(self) -> bool:
        return self.take_profit > 0

    @property
    def has_time_limit(self) -> bool:
        return self.time_limit_s > 0

    def scale(self, factor: Decimal) -> TripleBarrierConfig:
        """Return a new config with percentage barriers scaled by factor.

        Time limit is NOT scaled (it's absolute, not relative to price).
        """
        return TripleBarrierConfig(
            stop_loss=self.stop_loss * factor,
            take_profit=self.take_profit * factor,
            time_limit_s=self.time_limit_s,
        )
