from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.notification import Notification
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.bgp.fsm import FSM


class ResponseEncoder(Protocol):
    """Protocol defining the interface for response encoders (Text and JSON)."""

    version: str

    def up(self, neighbor: 'Neighbor') -> str: ...

    def connected(self, neighbor: 'Neighbor') -> str: ...

    def down(self, neighbor: 'Neighbor', reason: str = '') -> str: ...

    def shutdown(self) -> str: ...

    def negotiated(self, neighbor: 'Neighbor', negotiated: 'Negotiated') -> str | None: ...

    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> str | None: ...

    def signal(self, neighbor: 'Neighbor', signal: int) -> str | None: ...

    def notification(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Notification',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...

    def packets(
        self,
        neighbor: 'Neighbor',
        direction: str,
        category: int,
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...

    def keepalive(
        self, neighbor: 'Neighbor', direction: str, header: bytes, body: bytes, negotiated: 'Negotiated'
    ) -> str: ...

    def open(
        self,
        neighbor: 'Neighbor',
        direction: str,
        sent_open: 'Open',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...

    def update(
        self,
        neighbor: 'Neighbor',
        direction: str,
        update: 'Update',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...

    def refresh(
        self,
        neighbor: 'Neighbor',
        direction: str,
        refresh: 'RouteRefresh',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...

    def operational(
        self,
        neighbor: 'Neighbor',
        direction: str,
        what: str,
        operational: 'OperationalFamily',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str: ...


class Response:
    from exabgp.reactor.api.response.text import Text
    from exabgp.reactor.api.response.json import JSON
