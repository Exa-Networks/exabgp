"""capability.py

Typed capability configuration for BGP neighbors.

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from exabgp.protocol.family import FamilyTuple
from exabgp.util.enumeration import TriState

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.capability import CapabilityCode


# the capability codes of route refresh, RFC 2918, and enhanced route refresh, RFC 7313
ROUTE_REFRESH_CODE = 0x02
ENHANCED_ROUTE_REFRESH_CODE = 0x46
# the largest graceful restart time, in seconds. A module constant: in the compiled build a
# ClassVar on a dataclass is taken for a field, and its __init__ fails setting it
GRACEFUL_RESTART_MAX_TIME = 0xFFFF


@dataclass
class GracefulRestartConfig:
    """Graceful restart configuration.

    Attributes:
        state: TriState indicating enabled/disabled/unset
        time: Restart time in seconds (0-65535). Only meaningful when enabled.
    """

    state: TriState = TriState.UNSET
    time: int = 0

    def __post_init__(self) -> None:
        if self.time < 0 or self.time > GRACEFUL_RESTART_MAX_TIME:
            raise ValueError(f'graceful-restart time must be 0-{GRACEFUL_RESTART_MAX_TIME}, got {self.time}')

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
    paths_limit_per_family: dict[FamilyTuple, int] = field(default_factory=dict)
    route_refresh: TriState = TriState.FALSE  # advertise Route Refresh, RFC 2918
    enhanced_route_refresh: TriState = TriState.FALSE  # advertise Enhanced Route Refresh, RFC 7313
    nexthop: TriState = TriState.UNSET
    aigp: TriState = TriState.UNSET
    link_local_nexthop: TriState = TriState.UNSET
    link_local_prefer: bool = False  # Prefer link-local over global when both present
    multiple_labels: int = 0  # RFC 8277 2.1: the Count we send for each labelled family, 0 for none
    software_version: str | None = None
    # Codes the peer must advertise back, or be refused with (2, 7) (RFC 5492 3)
    required: frozenset[CapabilityCode] = frozenset()

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
            paths_limit_per_family=dict(self.paths_limit_per_family),
            route_refresh=self.route_refresh,
            enhanced_route_refresh=self.enhanced_route_refresh,
            nexthop=self.nexthop,
            aigp=self.aigp,
            link_local_nexthop=self.link_local_nexthop,
            link_local_prefer=self.link_local_prefer,
            multiple_labels=self.multiple_labels,
            software_version=self.software_version,
            required=self.required,
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
            and self.paths_limit_per_family == other.paths_limit_per_family
            and self.route_refresh == other.route_refresh
            and self.enhanced_route_refresh == other.enhanced_route_refresh
            and self.nexthop == other.nexthop
            and self.aigp == other.aigp
            and self.link_local_nexthop == other.link_local_nexthop
            and self.link_local_prefer == other.link_local_prefer
            and self.multiple_labels == other.multiple_labels
            and self.software_version == other.software_version
            and self.required == other.required
        )

    def route_refresh_statements(self) -> list[tuple[str, str]]:
        """The statements which configure route refresh: one when both capabilities agree, two otherwise."""
        normal = _capability_word(self.route_refresh, ROUTE_REFRESH_CODE in self.required)
        enhanced = _capability_word(self.enhanced_route_refresh, ENHANCED_ROUTE_REFRESH_CODE in self.required)
        if normal == enhanced:
            return [('route-refresh', normal)]
        return [('route-refresh-normal', normal), ('route-refresh-enhanced', enhanced)]


def _capability_word(advertised: TriState, required: bool) -> str:
    if not advertised.is_enabled():
        return 'disable'
    return 'require' if required else 'enable'
