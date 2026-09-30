"""A real Negotiated for tests which only need to say what a session agreed.

The tests used to hand the decoders a Mock shaped like a Negotiated. The compiled build
(plan/wip-mypyc.md) checks the declared type of every argument, and refuses a Mock where
`negotiated: Negotiated` is declared, so the session is built for real: a Neighbor with the
AS numbers and addresses asked for, and a Negotiated over it whose negotiated fields are
set to what the test says was agreed, without running an OPEN exchange.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv4

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)


def neighbor(
    *,
    local_as: int = 65000,
    peer_as: int = 65000,
    local_address: str | None = '127.0.0.1',
    peer_address: str = '127.0.0.2',
    router_id: str = '127.0.0.1',
) -> Neighbor:
    """A configured neighbor, iBGP by default."""
    from exabgp.bgp.message.open.routerid import RouterID

    configured = Neighbor()
    configured.session.local_as = ASN(local_as)
    configured.session.peer_as = ASN(peer_as)
    configured.session.local_address = IP.NoNextHop if local_address is None else IP.from_string(local_address)
    configured.session.peer_address = IPv4.from_string(peer_address)
    configured.session.router_id = RouterID(router_id)
    return configured


def negotiated(
    families: Iterable[FamilyTuple] = (IPV4_UNICAST,),
    *,
    asn4: bool = False,
    addpath_send: Iterable[FamilyTuple] = (),
    addpath_receive: Iterable[FamilyTuple] = (),
    msg_size: int = 4096,
    direction: Direction = Direction.IN,
    session: Neighbor | None = None,
    **fields: Any,
) -> Negotiated:
    """A Negotiated as if the OPEN exchange had agreed on these, over a real neighbor.

    `fields` sets any other negotiated attribute by name (aigp, local_as, peer_as, ...).
    """
    if session is None:
        # the AS numbers of the session are the neighbor's, so both say the same thing
        session = neighbor(
            local_as=int(fields.pop('local_as', 65000)),
            peer_as=int(fields.pop('peer_as', 65000)),
        )
    agreed = Negotiated.make_negotiated(session, direction)
    agreed.families = list(families)
    agreed.asn4 = asn4
    agreed.msg_size = msg_size
    agreed.local_as = agreed.neighbor.session.local_as
    agreed.peer_as = agreed.neighbor.session.peer_as
    for family in addpath_send:
        agreed.addpath._send[family] = True
    for family in addpath_receive:
        agreed.addpath._receive[family] = True
    for name, value in fields.items():
        # only what Negotiated has: a misspelt name must fail here, not pass silently
        assert hasattr(agreed, name), f'Negotiated has no {name}'
        setattr(agreed, name, value)
    return agreed


def open_message(capabilities: Iterable[Any] = (), *, asn: int = 65000, router_id: str = '127.0.0.1') -> Any:
    """An OPEN carrying these Capability instances, for a test which sets sent_open or received_open."""
    from exabgp.bgp.message.open import Capabilities, HoldTime, Open, RouterID, Version

    held = Capabilities()
    for capability in capabilities:
        held[capability.code()] = capability
    return Open.make_open(Version(4), ASN(asn), HoldTime(180), RouterID(router_id), held)
