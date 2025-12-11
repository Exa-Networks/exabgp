"""settings.py

Settings dataclass for programmatic Configuration construction.

This module provides ConfigurationSettings which enables creating complete
BGP configuration without parsing config files.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.neighbor.settings import NeighborSettings


@dataclass
class ConfigurationSettings:
    """Settings for programmatic Configuration creation.

    Enables creating complete BGP configuration without parsing config files.
    Useful for testing, API-driven creation, and programmatic configuration.

    Attributes:
        neighbors: List of NeighborSettings to create neighbors from
        processes: Process configuration dict
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
