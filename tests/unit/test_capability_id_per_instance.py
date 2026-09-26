"""One peer's OPEN rewrote the capability variant every other session rendered.

`Capability.klass()` resolved the class registered for a wire capability code and then
assigned that code onto the class:

    kls.ID = what

Two capabilities are registered under two codes each, an RFC one and the code Cisco
actually put on the wire:

    RouteRefresh  0x02 (RFC 2918)  and  0x80
    MultiSession  0x44 (draft)     and  0x83

`register()` files both codes against the same class object, so `klass(0x02)` and
`klass(0x80)` answer the very same `RouteRefresh`.  `__str__` and `json()` then read
`self.ID` to decide which variant to report, and `self.ID` found the class attribute.
The code a capability carried was therefore process wide rather than per message: the
last OPEN parsed anywhere in the process decided what every already established session
reported.

Measured against HEAD: an RFC peer whose capability rendered
`{ "name": "route-refresh", "variant": "RFC" }` rendered
`{ "name": "route-refresh", "variant": "Cisco" }` after an unrelated second peer opened
with 0x80, with nothing about the first peer having changed.  That value is published to
every API client, is the thing an operator reads to tell a Cisco peering from an RFC one,
and the same flip reached the log line through `__str__`.

The fix records the received code on the instance in `Capability.unpack` and leaves the
class attribute alone.  The class attribute is still load-bearing: `Capability.register()`
reads `klass.ID` at import time to work out which code a class registers itself under, and
it must keep seeing the declared default.  Nothing else in the tree reads `ID` off a
capability class.

The ten singly registered capabilities were also written to on every OPEN, with their own
code, so no value changed there - but a plain `int` from the wire replaced the
`_CapabilityCode` the class was declared with, quietly losing the name that type carries.
This file pins that too.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import _CapabilityCode
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.refresh import RouteRefresh

OPEN_MESSAGE_ID = 1

# an OPEN body: version, ASN, hold time, router-id, then the optional parameters
OPEN_PREFIX = b'\x04' + b'\xff\xfe' + b'\x00\xb4'

MULTIPROTOCOL_IPV4_UNICAST = b'\x00\x01\x00\x01'


def open_body(router_id: bytes, capabilities: list[tuple[int, bytes]]) -> bytes:
    """Build a real OPEN body carrying `capabilities` as optional parameter type 2."""
    parameters = b''
    for code, value in capabilities:
        capability = bytes([code, len(value)]) + value
        parameters += bytes([2, len(capability)]) + capability
    return OPEN_PREFIX + router_id + bytes([len(parameters)]) + parameters


def parse_open(router_id: bytes, capabilities: list[tuple[int, bytes]]):
    """Parse an OPEN through the path the reactor uses."""
    return Message.unpack(OPEN_MESSAGE_ID, open_body(router_id, capabilities), Direction.IN, {'invalid': 'test'})


RFC_PEER = [
    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
    (Capability.CODE.ROUTE_REFRESH, b''),
    (Capability.CODE.MULTISESSION, b'\x00'),
]

CISCO_PEER = [
    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
    (Capability.CODE.ROUTE_REFRESH_CISCO, b''),
    (Capability.CODE.MULTISESSION_CISCO, b'\x00'),
]


def test_a_second_peer_does_not_rewrite_the_first_peers_variant() -> None:
    """The defect, end to end: two OPENs, and the first one's rendering must hold."""
    first = parse_open(b'\x0a\x00\x00\x01', RFC_PEER)
    before = {code: first.capabilities[code].json() for code in first.capabilities}
    before_text = {code: str(first.capabilities[code]) for code in first.capabilities}

    parse_open(b'\x0a\x00\x00\x02', CISCO_PEER)

    after = {code: first.capabilities[code].json() for code in first.capabilities}
    after_text = {code: str(first.capabilities[code]) for code in first.capabilities}

    assert after == before, 'a second peer rewrote what the first session reports'
    assert after_text == before_text, 'a second peer rewrote what the first session logs'


def test_the_rfc_peer_reports_the_rfc_variant() -> None:
    peer = parse_open(b'\x0a\x00\x00\x01', RFC_PEER)
    assert peer.capabilities[Capability.CODE.ROUTE_REFRESH].json() == ('{ "name": "route-refresh", "variant": "RFC" }')
    assert '"variant": "RFC"' in peer.capabilities[Capability.CODE.MULTISESSION].json()
    assert str(peer.capabilities[Capability.CODE.ROUTE_REFRESH]) == 'Route Refresh'


def test_the_cisco_peer_reports_the_cisco_variant() -> None:
    """The fix must not pin every peer to RFC: the Cisco codes still say Cisco."""
    peer = parse_open(b'\x0a\x00\x00\x02', CISCO_PEER)
    assert peer.capabilities[Capability.CODE.ROUTE_REFRESH_CISCO].json() == (
        '{ "name": "route-refresh", "variant": "Cisco" }'
    )
    assert '"variant": "Cisco"' in peer.capabilities[Capability.CODE.MULTISESSION_CISCO].json()
    assert str(peer.capabilities[Capability.CODE.ROUTE_REFRESH_CISCO]) == 'Cisco Route Refresh'


def test_both_variants_in_one_open_are_told_apart() -> None:
    """A peer announcing both codes, which happens, must not collapse into one answer."""
    peer = parse_open(
        b'\x0a\x00\x00\x03',
        [
            (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
            (Capability.CODE.ROUTE_REFRESH, b''),
            (Capability.CODE.ROUTE_REFRESH_CISCO, b''),
        ],
    )
    rfc = peer.capabilities[Capability.CODE.ROUTE_REFRESH]
    cisco = peer.capabilities[Capability.CODE.ROUTE_REFRESH_CISCO]
    assert '"variant": "RFC"' in rfc.json()
    assert '"variant": "Cisco"' in cisco.json()
    assert rfc != cisco


@pytest.mark.parametrize(
    'code',
    [
        Capability.CODE.ROUTE_REFRESH,
        Capability.CODE.ROUTE_REFRESH_CISCO,
        Capability.CODE.MULTISESSION,
        Capability.CODE.MULTISESSION_CISCO,
    ],
)
def test_unpacking_a_capability_leaves_the_class_default_alone(code: int) -> None:
    """`Capability.register()` reads `klass.ID` at import time; it must stay what it was."""
    Capability.unpack(code, {}, b'\x00')
    assert RouteRefresh.ID == Capability.CODE.ROUTE_REFRESH
    assert MultiSession.ID == Capability.CODE.MULTISESSION


def test_every_registered_capability_keeps_its_declared_code_type() -> None:
    """A wire code is a plain int; the class attributes are `_CapabilityCode`s.

    `klass()` is the resolver which used to write the code onto the class, so calling it
    for every registered code is the whole of the exposure, and it needs no payload.
    """
    for code in sorted(Capability.registered_capability):
        Capability.klass(int(code))  # int(): a capability code off the wire is a bare byte
    for klass in set(Capability.registered_capability.values()):
        assert isinstance(klass.ID, _CapabilityCode), f'{klass.__name__}.ID was overwritten with a bare int'


def test_the_received_code_is_on_the_instance() -> None:
    """What the fix actually does, stated once so a future reader sees the contract."""
    cisco = Capability.unpack(Capability.CODE.ROUTE_REFRESH_CISCO, {}, b'')
    assert cisco.ID == Capability.CODE.ROUTE_REFRESH_CISCO
    assert 'ID' in vars(cisco), 'the received code must live on the instance, not the class'
    assert RouteRefresh.ID == Capability.CODE.ROUTE_REFRESH
