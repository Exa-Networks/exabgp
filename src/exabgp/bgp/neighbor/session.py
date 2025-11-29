"""session.py

Created by Thomas Mangin on 2024-01-01.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.bgp.message.open.routerid import RouterID


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
        if self.md5_ip is None and not self.auto_discovery:
            self.md5_ip = self.local_address

    def connection_established(self, local: str) -> None:
        """Called after TCP connection to set auto-discovered values.

        Args:
            local: The local IP address as determined by the TCP connection.
        """
        from exabgp.bgp.message.open.routerid import RouterID

        if self.auto_discovery:
            self.local_address = IP.create(local)

        if self.router_id is None and self.local_address.afi == AFI.ipv4:
            self.router_id = RouterID(self.local_address.top())

        if self.md5_ip is None:
            self.md5_ip = self.local_address
