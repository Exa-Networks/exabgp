"""settings.py

Settings dataclasses for deferred NLRI construction.

Each Settings class collects configuration values during parsing and validates
before creating the final NLRI object. This pattern enables:
1. Validation during assignment (catch errors early)
2. Final validation before NLRI creation
3. Immutable NLRI after construction

The Settings classes mirror the fields needed by each NLRI type's factory method.

Copyright (c) 2014-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher


@dataclass
class VPLSSettings:
    """Settings for VPLS NLRI construction.

    Collects all fields needed to create a VPLS NLRI, with validation
    during assignment and final validation before NLRI creation.

    Attributes:
        rd: Route Distinguisher
        endpoint: VPLS endpoint (VE ID), 0-65535
        base: Label base, 0-0xFFFFF (20 bits)
        offset: Label block offset
        size: Label block size
        nexthop: Next-hop IP address
        action: Route action (ANNOUNCE or WITHDRAW)
    """

    rd: RouteDistinguisher | None = None
    endpoint: int | None = None
    base: int | None = None
    offset: int | None = None
    size: int | None = None
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    action: Action = field(default=Action.UNSET)

    def set(self, name: str, value: Any) -> None:
        """Set a field with validation.

        Args:
            name: Field name ('rd', 'endpoint', 'base', 'offset', 'size', 'nexthop', 'action')
            value: Value to assign

        Raises:
            ValueError: If value is out of valid range for the field
        """
        if name == 'endpoint':
            if not isinstance(value, int) or value < 0 or value > 65535:
                raise ValueError(f'endpoint must be 0-65535, got {value}')
        elif name == 'base':
            if not isinstance(value, int) or value < 0 or value > 0xFFFFF:
                raise ValueError(f'base must be 0-1048575 (0xFFFFF), got {value}')
        elif name == 'offset':
            if not isinstance(value, int) or value < 0 or value > 65535:
                raise ValueError(f'offset must be 0-65535, got {value}')
        elif name == 'size':
            if not isinstance(value, int) or value < 0 or value > 65535:
                raise ValueError(f'size must be 0-65535, got {value}')
        setattr(self, name, value)

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.rd is None:
            return 'vpls nlri route-distinguisher missing'
        if self.endpoint is None:
            return 'vpls nlri endpoint missing'
        if self.base is None:
            return 'vpls nlri base missing'
        if self.offset is None:
            return 'vpls nlri offset missing'
        if self.size is None:
            return 'vpls nlri size missing'
        # Check size consistency (20-bit label space)
        if self.base > (0xFFFFF - self.size):
            return 'vpls nlri size inconsistency'
        return ''


@dataclass
class INETSettings:
    """Settings for INET/Label/IPVPN NLRI construction.

    Collects all fields needed to create INET-family NLRI, with validation
    during assignment and final validation before NLRI creation.

    This single Settings class handles:
    - INET (base class) - unicast/multicast routes
    - Label (subclass) - MPLS labeled routes (adds labels)
    - IPVPN (subclass) - VPN routes (adds labels + rd)

    Attributes:
        cidr: CIDR prefix (required)
        afi: Address Family Identifier (required)
        safi: Subsequent Address Family Identifier (required)
        action: Route action (ANNOUNCE or WITHDRAW)
        nexthop: Next-hop IP address
        path_info: ADD-PATH path identifier
        labels: MPLS label stack (for Label/IPVPN)
        rd: Route Distinguisher (for IPVPN)
    """

    cidr: 'CIDR | None' = None
    afi: AFI | None = None
    safi: SAFI | None = None
    action: Action = field(default=Action.UNSET)
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    path_info: PathInfo = field(default_factory=lambda: PathInfo.DISABLED)
    labels: 'Labels | None' = None
    rd: 'RouteDistinguisher | None' = None

    def set(self, name: str, value: Any) -> None:
        """Set a field with validation.

        Args:
            name: Field name
            value: Value to assign

        Raises:
            ValueError: If value is invalid for the field
        """
        setattr(self, name, value)

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.cidr is None:
            return 'inet nlri prefix/cidr missing'
        if self.afi is None:
            return 'inet nlri afi missing'
        if self.safi is None:
            return 'inet nlri safi missing'
        return ''


@dataclass
class FlowSettings:
    """Settings for FlowSpec NLRI construction.

    Collects all fields needed to create Flow NLRI, with validation
    during assignment and final validation before NLRI creation.

    Attributes:
        afi: Address Family Identifier (required)
        safi: Subsequent Address Family Identifier (required)
        action: Route action (ANNOUNCE or WITHDRAW)
        nexthop: Next-hop IP address
        rules: FlowSpec rules dict (keyed by rule type ID)
        rd: Route Distinguisher (for flow_vpn)
    """

    afi: AFI | None = None
    safi: SAFI | None = None
    action: Action = field(default=Action.UNSET)
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    rules: dict[int, list[Any]] = field(default_factory=dict)  # dict[int, list[FlowRule]]
    rd: 'RouteDistinguisher | None' = None

    def set(self, name: str, value: Any) -> None:
        """Set a field with validation.

        Args:
            name: Field name
            value: Value to assign

        Raises:
            ValueError: If value is invalid for the field
        """
        setattr(self, name, value)

    def add_rule(self, rule: Any) -> None:
        """Add a FlowSpec rule.

        Args:
            rule: FlowRule object with an ID attribute

        Raises:
            ValueError: If the rule is a prefix of another family than the route or its prefixes
        """
        from exabgp.bgp.message.update.nlri.flow import prefix_family_conflict

        conflict = prefix_family_conflict(self.rules, rule, self.afi)
        if conflict:
            raise ValueError(conflict)
        rule_id = rule.ID
        self.rules.setdefault(rule_id, []).append(rule)

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.afi is None:
            return 'flow nlri afi missing'
        if self.safi is None:
            return 'flow nlri safi missing'
        return ''


@dataclass
class RTCSettings:
    """Settings for RTC NLRI construction (RFC 4684 route target membership).

    Either `default`, the zero-length prefix asking for every VPN route, or both `origin_as`
    and `route_target`, a full 96 bit prefix. The shorter prefixes of section 4 are decoded but
    not configurable.

    Attributes:
        origin_as: AS originating the membership
        route_target: Route target the membership is for
        default: True for the default route target
        nexthop: Next-hop IP address
        action: Route action (ANNOUNCE or WITHDRAW)
    """

    origin_as: ASN | None = None
    route_target: RouteTarget | None = None
    default: bool = False
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    action: Action = field(default=Action.UNSET)

    def set(self, name: str, value: Any) -> None:
        """Set a field ('origin_as', 'route_target', 'default', 'nexthop', 'action')."""
        setattr(self, name, value)

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.default:
            if self.origin_as is not None or self.route_target is not None:
                return 'rtc default is the zero-length prefix and takes no origin-as or route-target'
            return ''
        if self.origin_as is None:
            return 'rtc origin-as missing (or use default)'
        if self.route_target is None:
            return 'rtc route-target missing (or use default)'
        return ''
