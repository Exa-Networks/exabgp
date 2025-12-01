"""Peer context for message handlers.

PeerContext provides shared state for all handlers in a peer session,
enabling isolated unit testing without coupling to the Peer class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability import Negotiated
    from exabgp.reactor.protocol import Protocol


@dataclass
class PeerContext:
    """Shared context for all handlers in a peer session.

    Provides access to protocol, negotiated capabilities, and peer configuration
    without coupling handlers to the Peer class.
    """

    proto: Protocol
    neighbor: Neighbor
    negotiated: Negotiated
    refresh_enhanced: bool
    routes_per_iteration: int
    peer_id: str
