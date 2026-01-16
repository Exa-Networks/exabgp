"""settings.py

Settings dataclasses for deferred Neighbor/Session construction.

Each Settings class collects configuration values and validates before creating
the final object. This pattern enables:
1. Programmatic neighbor/session creation without config file parsing
2. Validation before object creation
3. Testing without config files
4. API-driven configuration

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.open.routerid import RouterID
    from exabgp.bgp.neighbor.capability import NeighborCapability
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IP
    from exabgp.rib.route import Route


@dataclass
class SessionSettings:
    """Settings for deferred Session construction.

    Collects all fields needed to create a Session, with validation
    before Session creation.

    Attributes:
        peer_address: BGP peer IP address (required)
        local_as: Local AS number (required)
        peer_as: Peer AS number (required)
        local_address: Local IP address (None = auto-discovery)
        router_id: BGP router ID (derived from local_address if IPv4)
        md5_password: TCP MD5 password
        md5_base64: Whether MD5 password is base64-encoded
        connect: TCP port to connect to (0 = default 179)
        listen: TCP port to listen on (0 = disabled)
        passive: Passive connection mode
        source_interface: Source interface for connection
        outgoing_ttl: TTL for outgoing packets
        incoming_ttl: TTL for incoming packets
    """

    # Required fields
    peer_address: 'IP | None' = None
    local_as: 'ASN | None' = None
    peer_as: 'ASN | None' = None

    # Optional fields with defaults
    local_address: 'IP | None' = None  # None = auto-discovery
    router_id: 'RouterID | None' = None
    md5_password: str = ''
    md5_base64: bool = False
    # TCP-AO (RFC 5925) - mutually exclusive with MD5
    tcp_ao_keyid: int | None = None
    tcp_ao_algorithm: str = ''
    tcp_ao_password: str = ''
    tcp_ao_base64: bool = False
    connect: int = 0
    listen: int = 0
    passive: bool = False
    source_interface: str = ''
    outgoing_ttl: int | None = None
    incoming_ttl: int | None = None

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        if self.peer_address is None:
            return 'session peer-address missing'
        if self.local_as is None:
            return 'session local-as missing'
        if self.peer_as is None:
            return 'session peer-as missing'
        # listen requires local_address (can't auto-discover when listening)
        if self.listen > 0 and self.local_address is None:
            return 'session local-address required when listen is set'
        return ''


def _default_session_settings() -> SessionSettings:
    """Factory for default SessionSettings (used by dataclass field)."""
    return SessionSettings()


def _default_capability() -> 'NeighborCapability':
    """Factory for default NeighborCapability (used by dataclass field)."""
    from exabgp.bgp.neighbor.capability import NeighborCapability

    return NeighborCapability()


@dataclass
class NeighborSettings:
    """Settings for deferred Neighbor construction.

    Collects all fields needed to create a Neighbor, with validation
    before Neighbor creation.

    Attributes:
        session: Session settings (connection config)
        description: Neighbor description
        hold_time: BGP hold time (0 or 3-65535)
        rate_limit: Rate limiting (0 = disabled)
        host_name: Hostname capability
        domain_name: Domain name capability
        group_updates: Group UPDATE messages
        auto_flush: Auto flush routes
        adj_rib_in: Maintain adjacency RIB in
        adj_rib_out: Maintain adjacency RIB out
        manual_eor: Manual end-of-RIB handling
        capability: BGP capabilities
        families: Address families to negotiate
        nexthops: Next-hop address families
        addpaths: ADD-PATH families
        routes: Routes to announce
        api: API configuration
    """

    # Session configuration
    session: SessionSettings = field(default_factory=_default_session_settings)

    # BGP policy (optional with defaults)
    description: str = ''
    hold_time: int = 180
    rate_limit: int = 0
    host_name: str = ''
    domain_name: str = ''
    group_updates: bool = True
    auto_flush: bool = True
    adj_rib_in: bool = True
    adj_rib_out: bool = True
    manual_eor: bool = False

    # Capability
    capability: 'NeighborCapability' = field(default_factory=_default_capability)

    # Families
    families: list[tuple['AFI', 'SAFI']] = field(default_factory=list)
    nexthops: list[tuple['AFI', 'SAFI', 'AFI']] = field(default_factory=list)
    addpaths: list[tuple['AFI', 'SAFI']] = field(default_factory=list)

    # Routes and API (optional)
    routes: list['Route'] = field(default_factory=list)
    api: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> str:
        """Validate all settings are present and consistent.

        Returns:
            Empty string if valid, error message if invalid.
        """
        # Validate nested session
        session_error = self.session.validate()
        if session_error:
            return session_error

        # Hold time must be 0 (disabled) or 3-65535
        if self.hold_time < 0 or self.hold_time > 65535:
            return 'neighbor hold-time must be 0-65535'
        if self.hold_time > 0 and self.hold_time < 3:
            return 'neighbor hold-time must be 0 (disabled) or >= 3'

        return ''
