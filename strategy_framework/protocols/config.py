"""ConfigProtocol — contracts for strategy configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConfigProtocol(Protocol):
    """Minimal contract for strategy configs."""

    @property
    def controller_id(self) -> str: ...

    @property
    def controller_name(self) -> str: ...

    @property
    def controller_type(self) -> str: ...


@runtime_checkable
class UpdatableConfigProtocol(ConfigProtocol, Protocol):
    """Config that supports live parameter updates."""

    def get_updatable_fields(self) -> list[str]: ...

    def update_from(self, other: object) -> None: ...
