"""session.py

Created by Thomas Mangin on 2024-01-01.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.bgp.message.open.routerid import RouterID
    from exabgp.bgp.neighbor.settings import SessionSettings

# MD5 password length constraint (RFC 2385)
MAX_MD5_PASSWORD_LENGTH = 80


@dataclass
class Session:
    """Connection/session-related configuration for a BGP neighbor.

    Encapsulates TCP connection parameters and auto-derivation logic.
    Uses IP.NoNextHop as sentinel for auto-discovery mode.
    """

    # Required - must be set during configuration
    peer_address: IP = field(default_factory=lambda: IP.NoNextHop)

    # With defaults (non-None where possible)
    local_address: IP = field(default_factory=lambda: IP.NoNextHop)  # NoNextHop = auto-discovery
    local_link_local: IP | None = None  # Link-local address for IPv6 (fe80::/10)
    local_as: ASN = field(default_factory=lambda: ASN(0))  # 0 = auto (mirror peer)
    peer_as: ASN = field(default_factory=lambda: ASN(0))  # 0 = auto
    router_id: 'RouterID | None' = None  # Derived from local_address if None and IPv4
    md5_password: str = ''
    md5_base64: bool = False
    md5_ip: IP | None = None  # Derived from local_address if None
    connect: int = 0  # 0 = use default (179)
    listen: int = 0  # 0 = disabled
    passive: bool = False
    source_interface: str = ''
    outgoing_ttl: int | None = None
    incoming_ttl: int | None = None

    @property
    def auto_discovery(self) -> bool:
        """True if local_address should be auto-discovered from TCP connection."""
        return self.local_address is IP.NoNextHop

    def infer(self) -> None:
        """Derive optional fields from required ones.

        Called after configuration parsing to set derived defaults.
        """
        from exabgp.bgp.message.open.routerid import RouterID

        if self.md5_ip is None and not self.auto_discovery:
            self.md5_ip = self.local_address

        # Derive router_id from local_address if IPv4 and not auto-discovery
        if not self.router_id and not self.auto_discovery and self.local_address.afi == AFI.ipv4:
            self.router_id = RouterID(self.local_address.top())

    def missing(self) -> str:
        """Check for missing required session fields.

        Returns:
            Name of missing field, or empty string if complete.
        """
        if self.listen > 0 and self.auto_discovery:
            return 'local-address'
        if self.peer_address is IP.NoNextHop:
            return 'peer-address'
        if self.auto_discovery and not self.router_id:
            return 'router-id'
        if self.peer_address.afi == AFI.ipv6 and not self.router_id:
            return 'router-id'
        return ''

    def validate_md5(self) -> str:
        """Validate MD5 password configuration.

        Returns:
            Error message if invalid, empty string if valid.
        """
        if not self.md5_password:
            return ''

        try:
            password = base64.b64decode(self.md5_password) if self.md5_base64 else self.md5_password
        except (TypeError, ValueError) as e:
            return f'Invalid base64 encoding of MD5 password ({e})'

        if len(password) > MAX_MD5_PASSWORD_LENGTH:
            return f'MD5 password must be no larger than {MAX_MD5_PASSWORD_LENGTH} characters'

        return ''

    def ip_self(self, afi: AFI) -> IP:
        """Get the local IP address for next-hop self.

        Args:
            afi: The address family of the route.

        Returns:
            The IP to use as next-hop self.

        Raises:
            TypeError: If address family mismatch prevents next-hop self.
        """
        if not self.auto_discovery and afi == self.local_address.afi:
            return self.local_address

        # attempting to not barf for next-hop self when the peer is IPv6
        if afi == AFI.ipv4 and self.router_id is not None:
            return self.router_id

        local_afi = self.local_address.afi if not self.auto_discovery else 'unknown'
        raise TypeError(
            f'use of "next-hop self": the route ({afi}) does not have the same family as the BGP tcp session ({local_afi})',
        )

    def ip_link_local(self) -> IP | None:
        """Get the local link-local IPv6 address if available.

        Returns:
            Link-local IP or None if not set.
        """
        return self.local_link_local

    def connection_established(self, local: str) -> None:
        """Called after TCP connection to set auto-discovered values.

        Args:
            local: The local IP address as determined by the TCP connection.
        """
        from exabgp.bgp.message.open.routerid import RouterID

        if self.auto_discovery:
            self.local_address = IP.from_string(local)

        if self.router_id is None and self.local_address.afi == AFI.ipv4:
            self.router_id = RouterID(self.local_address.top())

        if self.md5_ip is None:
            self.md5_ip = self.local_address

    @classmethod
    def from_settings(cls, settings: 'SessionSettings') -> 'Session':
        """Create Session from validated settings.

        This factory method enables programmatic Session creation without
        parsing config files. Useful for testing and API-driven creation.

        Args:
            settings: SessionSettings with required fields populated.

        Returns:
            Configured Session instance with infer() called.

        Raises:
            ValueError: If settings validation fails.
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        assert settings.peer_address is not None
        assert settings.local_as is not None
        assert settings.peer_as is not None

        session = cls(
            peer_address=settings.peer_address,
            local_address=settings.local_address if settings.local_address else IP.NoNextHop,
            local_as=settings.local_as,
            peer_as=settings.peer_as,
            router_id=settings.router_id,
            md5_password=settings.md5_password,
            md5_base64=settings.md5_base64,
            connect=settings.connect,
            listen=settings.listen,
            passive=settings.passive,
            source_interface=settings.source_interface,
            outgoing_ttl=settings.outgoing_ttl,
            incoming_ttl=settings.incoming_ttl,
        )
        session.infer()
        return session
