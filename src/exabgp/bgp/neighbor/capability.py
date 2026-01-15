"""capability.py

Typed capability configuration for BGP neighbors.

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from exabgp.util.enumeration import TriState


@dataclass
class GracefulRestartConfig:
    """Graceful restart configuration.

    Attributes:
        state: TriState indicating enabled/disabled/unset
        time: Restart time in seconds (0-65535). Only meaningful when enabled.
    """

    MAX_TIME: ClassVar[int] = 0xFFFF  # Maximum restart time (65535 seconds)

    state: TriState = TriState.UNSET
    time: int = 0

    def __post_init__(self) -> None:
        if self.time < 0 or self.time > self.MAX_TIME:
            raise ValueError(f'graceful-restart time must be 0-{self.MAX_TIME}, got {self.time}')

    @classmethod
    def disabled(cls) -> 'GracefulRestartConfig':
        """Create a disabled graceful restart config."""
        return cls(state=TriState.FALSE, time=0)

    @classmethod
    def with_time(cls, time: int) -> 'GracefulRestartConfig':
        """Create an enabled graceful restart config with specified time."""
        return cls(state=TriState.TRUE, time=time)

    def is_enabled(self) -> bool:
        """Check if graceful restart is enabled."""
        return self.state == TriState.TRUE

    def is_disabled(self) -> bool:
        """Check if graceful restart is explicitly disabled."""
        return self.state == TriState.FALSE

    def is_unset(self) -> bool:
        """Check if graceful restart state is not yet determined."""
        return self.state == TriState.UNSET

    def __bool__(self) -> bool:
        """Allow truthiness check: if graceful_restart: ..."""
        return self.state == TriState.TRUE

    def __int__(self) -> int:
        """Allow int conversion for backward compatibility."""
        return self.time if self.state == TriState.TRUE else 0


@dataclass
class NeighborCapability:
    """Typed BGP capability configuration for a neighbor.

    Replaces the old dict-based Neighbor.Capability with proper types.
    """

    asn4: TriState = TriState.TRUE
    extended_message: TriState = TriState.TRUE
    graceful_restart: GracefulRestartConfig = field(default_factory=GracefulRestartConfig.disabled)
    multi_session: TriState = TriState.FALSE
    operational: TriState = TriState.FALSE
    add_path: int = 0  # 0=disabled, 1=receive, 2=send, 3=send/receive
    route_refresh: int = 0  # REFRESH enum: ABSENT=1, NORMAL=2, ENHANCED=4
    nexthop: TriState = TriState.UNSET
    aigp: TriState = TriState.UNSET
    link_local_nexthop: TriState = TriState.UNSET
    software_version: str | None = None

    def copy(self) -> 'NeighborCapability':
        """Create a copy of this capability configuration."""
        return NeighborCapability(
            asn4=self.asn4,
            extended_message=self.extended_message,
            graceful_restart=GracefulRestartConfig(
                state=self.graceful_restart.state,
                time=self.graceful_restart.time,
            ),
            multi_session=self.multi_session,
            operational=self.operational,
            add_path=self.add_path,
            route_refresh=self.route_refresh,
            nexthop=self.nexthop,
            aigp=self.aigp,
            link_local_nexthop=self.link_local_nexthop,
            software_version=self.software_version,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NeighborCapability):
            return False
        return (
            self.asn4 == other.asn4
            and self.extended_message == other.extended_message
            and self.graceful_restart.state == other.graceful_restart.state
            and self.graceful_restart.time == other.graceful_restart.time
            and self.multi_session == other.multi_session
            and self.operational == other.operational
            and self.add_path == other.add_path
            and self.route_refresh == other.route_refresh
            and self.nexthop == other.nexthop
            and self.aigp == other.aigp
            and self.link_local_nexthop == other.link_local_nexthop
            and self.software_version == other.software_version
        )
