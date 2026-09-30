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


# The API processes a test listens as: the name a neighbor's api table lists for each event
# it asks to hear of, and under which the Processes of `reactor()` holds a `Told`.
PROCESS = 'told'


class Told:
    """An API encoder which records what it was asked to print, and prints nothing.

    `ResponseEncoder` is a typing.Protocol, so a compiled Processes holds this as it holds
    the JSON encoder. No process runs under its name, so Processes.write sends nothing.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)

        def record(*args: Any) -> str:
            self.calls.append((name, args))
            return ''

        return record

    def called(self, name: str) -> list[tuple[Any, ...]]:
        """The arguments of each call to the encoder method `name`, in order."""
        return [args for called, args in self.calls if called == name]

    def names(self) -> list[str]:
        """The encoder methods called, in order."""
        return [called for called, _ in self.calls]


def api_asks(configured: Neighbor, *events: str) -> Neighbor:
    """Give the neighbor the api table of the configuration, with PROCESS asking for `events`.

    The table is the one resolve.api builds: every event, most listing no process.
    """
    from exabgp.configuration.grammar.tree import resolve

    table = resolve.api({})
    for event in events:
        assert event in table, f'the api table has no {event}'
        table[event] = [PROCESS]
    configured.api = table
    return configured


def reactor() -> tuple[Any, Told]:
    """A real Reactor with a real Processes, and the Told which hears what the API is told."""
    from exabgp.reactor.api.processes import Processes
    from exabgp.reactor.loop import Reactor

    built = Reactor(None)
    built.processes = Processes()
    told = Told()
    built.processes._encoder[PROCESS] = told
    return built, told


def peer(configured: Neighbor | None = None) -> tuple[Any, Told]:
    """A real Peer over the neighbor (an api table asking for nothing if it has none)."""
    from exabgp.reactor.peer import Peer

    if configured is None:
        configured = neighbor()
    if not configured.api:
        api_asks(configured)
    built, told = reactor()
    return Peer(configured, built), told


def protocol(configured: Neighbor | None = None) -> tuple[Any, Told]:
    """A real Protocol of a real Peer, not connected, see `connect()`."""
    from exabgp.reactor.protocol import Protocol

    session, told = peer(configured)
    return Protocol(session), told


def connect(proto: Any) -> Any:
    """Connect the Protocol to one end of a socket pair, and return the other end, the peer.

    The connection is a real one: what the peer end sends is read by the production framing
    code, and what the Protocol writes can be received from the peer end.
    """
    import socket

    from exabgp.reactor.network.outgoing import Outgoing

    ours, theirs = socket.socketpair()
    ours.setblocking(False)
    # an Outgoing built with no options opens nothing: the socket is given to it
    connection = Outgoing(proto.neighbor.session.peer_address.afi, 'peer', 'local')
    connection.io = ours
    proto.connection = connection
    return theirs


def received(theirs: Any) -> bytes:
    """Everything the Protocol has written to the peer end so far."""
    theirs.setblocking(False)
    data = b''
    # bounded: a socket pair buffers far less than this, and each read takes at least a byte
    for _ in range(1024):
        try:
            chunk = theirs.recv(65536)
        except BlockingIOError:
            break
        if not chunk:
            break
        data += chunk
    return data


def messages(data: bytes) -> list[tuple[int, bytes]]:
    """Split what was received into (type, body) of each BGP message."""
    found = []
    # bounded: each message is at least a 19 octet header
    while data:
        assert len(data) >= 19, 'a partial message was received'
        length = int.from_bytes(data[16:18], 'big')
        found.append((data[18], data[19:length]))
        data = data[length:]
    return found


def context(configured: Neighbor | None = None, *, refresh_enhanced: bool = False) -> tuple[Any, Told]:
    """The PeerContext a message handler is given, over a real Protocol, Peer and Reactor.

    The negotiated capabilities are the Protocol's: set them on `ctx.negotiated`, which
    is the same object as `ctx.proto.negotiated`.
    """
    from exabgp.reactor.peer.context import PeerContext

    proto, told = protocol(configured)
    session = proto.peer
    built = PeerContext(proto, proto.neighbor, proto.negotiated, refresh_enhanced, 1, session.id(), session.stats)
    return built, told


def interpreted(module: Any) -> Any:
    """The module itself when it is interpreted, else an interpreted copy of its source.

    A module compiled with mypyc calls its own functions, the ones it imports, and the
    methods of compiled classes directly: a stub set on the module or on the class is never
    called by it. A test which must replace such a collaborator runs the module's source,
    the .py kept beside the extension, which looks each of them up at run time. The copy is
    a separate module: patch the copy, and call the copy.
    """
    import importlib.util
    from pathlib import Path

    location = Path(str(module.__file__))
    if location.suffix == '.py':
        return module
    source = location.parent / (module.__name__.rsplit('.', 1)[-1] + '.py')
    spec = importlib.util.spec_from_file_location(f'{module.__name__}_interpreted', source)
    assert spec is not None and spec.loader is not None, f'no source beside {location}'
    copy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copy)
    return copy


def disconnect(proto: Any, theirs: Any) -> None:
    """Close both ends of what `connect()` opened.

    A connection left to the garbage collector closes itself whenever it is collected, and
    logs it, in the middle of whichever test is running then.
    """
    theirs.close()
    if proto.connection is not None:
        proto.connection.close()
