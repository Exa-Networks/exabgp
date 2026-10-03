"""settings.py

Settings dataclass for programmatic Configuration construction.

This module provides ConfigurationSettings which enables creating complete
BGP configuration without parsing config files.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.neighbor.settings import NeighborSettings


class Encoder(StrEnum):
    """How exabgp writes to an API program."""

    TEXT = 'text'
    JSON = 'json'


class OnExit(StrEnum):
    """What happens to the routes an API program announced when it exits."""

    WITHDRAW = 'withdraw'
    KEEP = 'keep'


@dataclass
class ProcessSettings:
    """One `process` section: an API program exabgp runs and talks to."""

    run: list[str]
    encoder: Encoder = Encoder.TEXT
    respawn: bool = True
    # unset, the API version of the program decides: see Processes._queue_exit
    on_exit: OnExit | None = None

    def to_dict(self) -> dict[str, Any]:
        """The form the reactor takes a process in, the keys being the configuration keywords."""
        process: dict[str, Any] = {
            'run': list(self.run),
            'encoder': str(self.encoder),
            'respawn': self.respawn,
        }
        if self.on_exit is not None:
            process['on-exit'] = str(self.on_exit)
        return process

    @classmethod
    def from_dict(cls, process: dict[str, Any]) -> ProcessSettings:
        """The inverse of to_dict: a process given to Configuration.from_settings as the reactor takes it."""
        return cls(
            run=list(process['run']),
            encoder=Encoder(process.get('encoder', Encoder.TEXT)),
            respawn=process.get('respawn', True),
            on_exit=OnExit(process['on-exit']) if 'on-exit' in process else None,
        )


@dataclass
class ConfigurationSettings:
    """Settings for programmatic Configuration creation.

    Enables creating complete BGP configuration without parsing config files.
    Useful for testing, API-driven creation, and programmatic configuration.

    Attributes:
        neighbors: List of NeighborSettings to create neighbors from
        processes: the process sections by name, ProcessSettings or the dict the reactor takes
    """

    neighbors: list['NeighborSettings'] = field(default_factory=list)
    processes: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> str:
        """Validate all settings including nested neighbors.

        Returns:
            Empty string if valid, error message if invalid.
        """
        for i, neighbor_settings in enumerate(self.neighbors):
            error = neighbor_settings.validate()
            if error:
                return f'neighbor[{i}]: {error}'
        return ''
