"""Peer context for message handlers.

PeerContext provides shared state for all handlers in a peer session,
enabling isolated unit testing without coupling to the Peer class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability import Negotiated
    from exabgp.reactor.peer.peer import Stats
    from exabgp.reactor.protocol import Protocol


class PeerContext:
    """Shared context for all handlers in a peer session.

    Provides access to protocol, negotiated capabilities, and peer configuration
    without coupling handlers to the Peer class.

    Not a dataclass: compiled, a dataclass resolves its field types at import, and
    these types are only imported for the type checker.
    """

    def __init__(
        self,
        proto: Protocol,
        neighbor: Neighbor,
        negotiated: Negotiated,
        refresh_enhanced: bool,
        routes_per_iteration: int,
        peer_id: str,
        stats: Stats,
    ) -> None:
        self.proto = proto
        self.neighbor = neighbor
        self.negotiated = negotiated
        self.refresh_enhanced = refresh_enhanced
        self.routes_per_iteration = routes_per_iteration
        self.peer_id = peer_id
        self.stats = stats

    def __repr__(self) -> str:
        return (
            f'PeerContext(proto={self.proto!r}, neighbor={self.neighbor!r}, negotiated={self.negotiated!r}, '
            f'refresh_enhanced={self.refresh_enhanced!r}, routes_per_iteration={self.routes_per_iteration!r}, '
            f'peer_id={self.peer_id!r}, stats={self.stats!r})'
        )
