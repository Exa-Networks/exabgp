"""The contract every BGP message class keeps.

A message is its bytes.  Each class stores the body it was built from, derives every
field from it, and is built from fields by one `make_<name>` factory.  The base class
owns the framing, equality and the length rules; a subclass says what its body is and
nothing else.  `.claude/exabgp/BGP_MESSAGE_INTERFACE.md` is the spec this test enforces.

The classes are found by walking `Message.__subclasses__()`, so a message added next year
is held to the contract the day it is written, without anyone remembering to list it here.
Only the samples, which need real field values, are listed by hand, and
`test_every_class_has_a_sample` fails when one is missing.
"""

from __future__ import annotations

import inspect
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import KeepAlive, Message, Notification, Open, Update
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.version import Version
from exabgp.bgp.message.operational import Advisory, Operational, Query, Response, UnknownOperational
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.eor import EOR
from exabgp.protocol.family import AFI, SAFI

# route 10.0.0.0/24 next-hop 1.2.3.4, from `exabgp encode`
UPDATE_BODY = bytes.fromhex('00000015400101004002004003040102030440050400000064180a0000')

# the message codes RFC 4271 4.1 and its successors put on the wire
WIRE_CODES = frozenset(range(1, 7))


def negotiated() -> Negotiated:
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.IN)


def classes(root: type[Message] = Message) -> list[type[Message]]:
    """Every subclass of `root`, however deep, in a stable order."""
    found: list[type[Message]] = []
    pending = list(root.__subclasses__())
    while pending:
        klass = pending.pop(0)
        if klass in found:
            continue
        found.append(klass)
        pending.extend(klass.__subclasses__())
    return sorted(found, key=lambda klass: klass.__qualname__)


def samples() -> list[Message]:
    router_id = RouterID('192.0.2.1')
    return [
        KeepAlive.make_keepalive(),
        RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.REQUEST),
        Notification.make_notification(6, 2, b'\x05bye!'),
        Open.make_open(Version(4), ASN(65000), HoldTime(180), router_id, Capabilities()),
        Update(UPDATE_BODY),
        EOR.make_eor(AFI.ipv4, SAFI.unicast),
        EOR.make_eor(AFI.ipv6, SAFI.unicast),
        Advisory.ADM.make_advisory(AFI.ipv4, SAFI.unicast, 'demand'),
        Advisory.ASM.make_advisory(AFI.ipv4, SAFI.unicast, 'static'),
        Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, 7),
        Query.APCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, 7),
        Query.LPCQ.make_query(AFI.ipv4, SAFI.unicast, router_id, 7),
        Response.RPCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, 7, 10),
        Response.APCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, 7, 10),
        Response.LPCP.make_counter(AFI.ipv4, SAFI.unicast, router_id, 7, 10),
        UnknownOperational.make_unknown(Operational.SUBTYPE.MUD, b'\x01\x02'),
    ]


SAMPLES = samples()
IDS = [f'{type(sample).__qualname__}-{index}' for index, sample in enumerate(SAMPLES)]


# the Not Satisfied replies of the draft share one type, 0xFFFF, and say which error they are
# in their payload, so no decoder is registered for them: a peer's arrives as UnknownOperational
UNDECODED = {'NS.Malformed', 'NS.Unsupported', 'NS.Maximum', 'NS.Prohibited', 'NS.Busy', 'NS.NotFound'}


def abstract(klass: type[Message]) -> bool:
    """A class of the operational tree which is the layout of a group, and never sent: no NAME."""
    return issubclass(klass, Operational) and not klass.NAME


def test_every_class_has_a_sample() -> None:
    sampled = {type(sample).__qualname__ for sample in SAMPLES}
    missing = [
        klass.__qualname__
        for klass in classes()
        if klass.__qualname__ not in sampled | UNDECODED and not abstract(klass)
    ]
    assert missing == []


@pytest.mark.parametrize('klass', classes(), ids=lambda klass: klass.__qualname__)
def test_every_message_is_a_wire_message(klass: type[Message]) -> None:
    # the reactor's "nothing was read" is None, not a message with an internal code
    assert klass.ID in WIRE_CODES


@pytest.mark.parametrize('klass', classes(), ids=lambda klass: klass.__qualname__)
def test_type_is_derived_from_the_id(klass: type[Message]) -> None:
    assert klass.TYPE == bytes([klass.ID])
    assert klass.LENGTH_MIN == Message.HEADER_LEN + klass.FIXED_SIZE


@pytest.mark.parametrize('declared', ['TYPE', 'LENGTH_MIN'])
def test_a_derived_field_can_not_be_declared(declared: str) -> None:
    with pytest.raises(TypeError):
        type('Declares', (KeepAlive,), {declared: b'\x04' if declared == 'TYPE' else 19})


@pytest.mark.parametrize('klass', classes(), ids=lambda klass: klass.__qualname__)
def test_framing_belongs_to_the_base(klass: type[Message]) -> None:
    assert 'pack_message' not in vars(klass)
    assert '_message' not in vars(klass)


@pytest.mark.parametrize('klass', classes(), ids=lambda klass: klass.__qualname__)
def test_equality_belongs_to_the_base(klass: type[Message]) -> None:
    assert '__eq__' not in vars(klass)
    assert '__ne__' not in vars(klass)
    assert '__hash__' not in vars(klass)


@pytest.mark.parametrize('klass', classes(), ids=lambda klass: klass.__qualname__)
def test_the_constructor_takes_the_body(klass: type[Message]) -> None:
    parameters = list(inspect.signature(klass.__init__).parameters)
    assert parameters == ['self', 'packed']


@pytest.mark.parametrize('sample', SAMPLES, ids=IDS)
def test_the_message_is_the_header_and_the_body(sample: Message) -> None:
    session = negotiated()
    wire = sample.pack_message(session)
    body = bytes(sample.pack_body(session))
    assert wire == Message.MARKER + (Message.HEADER_LEN + len(body)).to_bytes(2, 'big') + sample.TYPE + body


@pytest.mark.parametrize('sample', SAMPLES, ids=IDS)
def test_what_is_packed_unpacks_to_the_same_message(sample: Message) -> None:
    session = negotiated()
    wire = sample.pack_message(session)
    decoded = Message.unpack(wire[18], wire[Message.HEADER_LEN :], session)
    assert type(decoded) is type(sample)
    assert decoded == sample
    assert hash(decoded) == hash(sample)
    assert decoded.pack_message(session) == wire


@pytest.mark.parametrize('sample', SAMPLES, ids=IDS)
def test_the_length_is_within_the_bounds_of_the_class(sample: Message) -> None:
    length = len(sample.pack_message(negotiated()))
    assert sample.LENGTH_MIN <= length <= sample.LENGTH_MAX
    assert Message.length_valid(sample.ID, length)


@pytest.mark.parametrize(
    'code,length,valid',
    [
        (Message.CODE.OPEN, 28, False),
        (Message.CODE.OPEN, 29, True),
        (Message.CODE.UPDATE, 22, False),
        (Message.CODE.UPDATE, 23, True),
        (Message.CODE.NOTIFICATION, 20, False),
        (Message.CODE.NOTIFICATION, 21, True),
        (Message.CODE.KEEPALIVE, 19, True),
        (Message.CODE.KEEPALIVE, 20, False),
        (Message.CODE.ROUTE_REFRESH, 22, False),
        (Message.CODE.ROUTE_REFRESH, 23, True),
        (Message.CODE.ROUTE_REFRESH, 24, False),
        (Message.CODE.OPERATIONAL, 22, False),
        (Message.CODE.OPERATIONAL, 23, True),
        # a type nobody registered is refused by its type, not by its length
        (0xF0, 19, True),
        (0xF0, 18, False),
    ],
)
def test_length_rules(code: int, length: int, valid: bool) -> None:
    assert Message.length_valid(code, length) is valid


def test_messages_are_equal_by_their_bytes() -> None:
    assert KeepAlive.make_keepalive() == KeepAlive.make_keepalive()
    first = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.REQUEST)
    second = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.unicast, RouteRefresh.REQUEST)
    assert first != second
    assert len({first, second, RouteRefresh(bytes(first.pack_body(negotiated())))}) == 2


def test_messages_of_different_types_are_not_equal() -> None:
    assert Notification.make_notification(6, 2) != RouteRefresh(b'\x06\x02\x00\x00')
