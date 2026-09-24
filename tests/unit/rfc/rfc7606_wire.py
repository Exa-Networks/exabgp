"""Wire building blocks shared by the RFC 7606 ledger tests.

Every test in this directory feeds real bytes to the real decoder and asserts on what came
back out.  Nothing here mocks a session: `Negotiated.make_negotiated` builds the object the
production path uses, so a test which passes here passes against the code a peer talks to.

The pieces are small on purpose.  RFC 7606 is about what happens to the REST of an UPDATE
when one attribute is wrong, so almost every test needs a well formed UPDATE with exactly
one thing changed, and the difference between the two has to be visible in the test body.
"""

from __future__ import annotations

from struct import pack

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI

# the attribute flag bytes a peer puts in front of a path attribute
WELL_KNOWN_TRANSITIVE = 0x40
OPTIONAL = 0x80
OPTIONAL_TRANSITIVE = 0xC0

# one real IPv4 prefix, 10.0.0.0/24, so an UPDATE announces a route rather than being an
# End-of-RIB.  The route is what treat-as-withdraw acts on; without it the three approaches
# RFC 7606 distinguishes all look the same from outside.
IPV4_PREFIX = bytes([24, 10, 0, 0])
OTHER_IPV4_PREFIX = bytes([24, 10, 0, 1])

# the local and peer AS of the sessions below.  Equal numbers make an IBGP session, which
# is what sections 7.5, 7.9 and 7.10 turn on.
LOCAL_AS = 65001
PEER_AS = 65002


def session(asn4: bool = True, peer_as: int = PEER_AS) -> Negotiated:
    """A negotiated session for IPv4 and IPv6 unicast, EBGP unless told otherwise."""
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(LOCAL_AS)
    negotiated.peer_as = ASN(peer_as)
    negotiated.asn4 = asn4
    negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]
    return negotiated


def internal_session(asn4: bool = True) -> Negotiated:
    """The same session with the peer inside our own AS, so Negotiated.is_ibgp is true."""
    return session(asn4=asn4, peer_as=LOCAL_AS)


def attribute(flag: int, code: int, value: bytes) -> bytes:
    """One path attribute in the short-length encoding: flag, type, length, value."""
    assert len(value) <= 0xFF, 'use extended_attribute for a value over 255 bytes'
    return bytes([flag, code, len(value)]) + value


def extended_attribute(flag: int, code: int, value: bytes) -> bytes:
    """One path attribute with the Extended Length bit set and a two byte length."""
    return bytes([flag | Attribute.Flag.EXTENDED_LENGTH, code, 0, len(value)]) + value


ORIGIN_IGP = attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, bytes([0]))
EMPTY_AS_PATH = attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.AS_PATH, b'')
NEXT_HOP = attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, bytes([10, 0, 0, 1]))

# the three well-known mandatory attributes an IPv4 announcement needs, so a test which is
# about a fourth attribute does not trip over RFC 7606 3 (d) by accident
MANDATORY = ORIGIN_IGP + EMPTY_AS_PATH + NEXT_HOP


def mp_reach_ipv6(next_hop_length: int = 16, mask: int = 64) -> bytes:
    """An MP_REACH_NLRI announcing one IPv6 prefix, with a next hop of the given size."""
    prefix = bytes([mask]) + bytes((mask + 7) // 8)
    payload = pack('!HB', AFI.ipv6, SAFI.unicast) + bytes([next_hop_length])
    payload += bytes(next_hop_length) + bytes([0]) + prefix
    return attribute(OPTIONAL, Attribute.CODE.MP_REACH_NLRI, payload)


def mp_unreach_ipv6(mask: int = 64) -> bytes:
    """An MP_UNREACH_NLRI withdrawing one IPv6 prefix."""
    prefix = bytes([mask]) + bytes((mask + 7) // 8)
    payload = pack('!HB', AFI.ipv6, SAFI.unicast) + prefix
    return attribute(OPTIONAL, Attribute.CODE.MP_UNREACH_NLRI, payload)


def update(attributes: bytes, nlri: bytes = IPV4_PREFIX, withdrawn: bytes = b'') -> bytes:
    """An UPDATE payload, the bytes which follow the nineteen byte BGP header."""
    return pack('!H', len(withdrawn)) + withdrawn + pack('!H', len(attributes)) + attributes + nlri


def parse(payload: bytes, negotiated: Negotiated) -> UpdateCollection:
    """Decode an UPDATE the way the reactor does, and narrow the result to an UPDATE.

    `Message.unpack_message` is typed as returning a `Message` because it is the registry
    entry point; everything this directory sends is an UPDATE, and the assertion says so
    rather than hiding it behind a cast.
    """
    message = Update.unpack_message(payload, negotiated)
    assert isinstance(message, Update), f'expected an UPDATE, got {type(message).__name__}'
    return message.parse(negotiated)


def announced(parsed: UpdateCollection) -> list[str]:
    """The prefixes the UPDATE advertised, after RFC 7606 has had its say.

    Never `parsed.nlris`: that property is the union of announces and withdraws, so under
    treat-as-withdraw it still holds the route and an assertion against it cannot tell the
    two apart.
    """
    return [str(routed.nlri) for routed in parsed.announces]


def withdrawn_routes(parsed: UpdateCollection) -> list[str]:
    """The prefixes the UPDATE withdrew, whether the peer asked for it or RFC 7606 did."""
    return [str(nlri) for nlri in parsed.withdraws]
