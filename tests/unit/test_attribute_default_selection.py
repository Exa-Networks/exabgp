"""`with_default` chooses whether the defaults are synthesised, not whether anything is sent.

`AttributeCollection.pack_attribute` builds the set of attribute codes it is going to encode
from two sources: the codes the collection actually holds, and the three codes it can
synthesise when they are absent (ORIGIN, AS_PATH and LOCAL_PREF).  `with_default` is about
the second source only.

The union was written as `set(keys + list(default) if with_default else [])`, and a
conditional expression binds looser than `+` in Python, so the whole of `keys +
list(default)` was the true branch and `with_default=False` collapsed the set to nothing.
Every attribute the caller had put in the collection was silently dropped, so
`pack_attribute(negotiated, with_default=False)` returned `b''` whatever it was given.

The only caller which asked for it is `UpdateCollection.messages`, for an UPDATE which
carries nothing but MP_UNREACH_NLRI of a unicast or multicast family.  RFC 4760 3 says such
an UPDATE "is not required to carry any other path attributes", and that pass wants no
attribute field at all, which is what the bug happened to give it.  So correcting the
brackets alone would have changed the wire: the withdrawn route's own attributes would start
being encoded onto its MP_UNREACH message, and the withdrawal would be sized against them,
which is how a withdrawal came to be dropped for the weight of an announcement it was not
carrying.  That pass therefore now says `b''` outright, and the last test here holds it.
"""

from __future__ import annotations

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection, MED
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

CODE = Attribute.CODE

BGP_HEADER_SIZE = 19

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST = (AFI.ipv6, SAFI.unicast)

MED_VALUE = 42


def session() -> Negotiated:
    """An EBGP session with the two unicast families these tests use."""
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST, IPV6_UNICAST]
    return negotiated


def one_med() -> AttributeCollection:
    """A collection holding a single attribute, and one which is never a default."""
    attributes = AttributeCollection()
    attributes.add(MED.from_int(MED_VALUE))
    return attributes


def packed_codes(packed: bytes) -> list[int]:
    """The attribute type codes of an encoded path attribute field, in the order they are in."""
    codes: list[int] = []
    offset = 0
    while offset < len(packed):
        flag, code = packed[offset], packed[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            value_length = int.from_bytes(packed[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            value_length = packed[offset + 2]
            offset += 3
        codes.append(code)
        offset += value_length
    assert offset == len(packed), 'the encoded attribute field does not frame its own attributes'
    return codes


def attribute_field(message: bytes) -> bytes:
    """The Total Path Attribute field of one generated UPDATE, header and lengths removed."""
    body = message[BGP_HEADER_SIZE:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    start = 2 + withdrawn_length + 2
    length = int.from_bytes(body[2 + withdrawn_length : start], 'big')
    return bytes(body[start : start + length])


def withdrawn_ipv6(prefix: str, mask: int) -> NLRI:
    """One bare IPv6 unicast NLRI, which is all an MP_UNREACH_NLRI carries."""
    ip = IP.from_string(prefix)
    return INET.from_cidr(CIDR.create_cidr(ip.pack_ip(), mask), AFI.ipv6, SAFI.unicast)


def test_without_the_defaults_the_attributes_held_are_still_packed() -> None:
    """The bug in one assertion: a collection holding a MED encoded to nothing at all."""
    negotiated = session()

    packed = one_med().pack_attribute(negotiated, with_default=False)

    assert packed == MED.from_int(MED_VALUE).pack_attribute(negotiated)


def test_without_the_defaults_no_default_attribute_is_added() -> None:
    """The other half: the three synthesised codes stay out of it."""
    packed = one_med().pack_attribute(session(), with_default=False)

    assert packed_codes(packed) == [CODE.MED]


def test_with_the_defaults_the_defaults_join_the_attributes_held() -> None:
    """The union is a union: what is held, plus what an EBGP announcement must carry."""
    packed = one_med().pack_attribute(session(), with_default=True)

    assert packed_codes(packed) == [CODE.ORIGIN, CODE.AS_PATH, CODE.MED]


def test_an_mp_unreach_only_update_still_carries_nothing_but_the_mp_unreach() -> None:
    """The caller: RFC 4760 3, and the wire the corrected brackets must not have changed.

    Red without the `b''` at the call site, since the collection holds a MED which
    `pack_attribute` is now right to encode when it is asked for the attributes.
    """
    negotiated = session()
    collection = UpdateCollection([], [withdrawn_ipv6('2001:db8::', 32)], one_med())

    messages = list(collection.messages(negotiated))

    assert len(messages) == 1, f'one IPv6 withdrawal made {len(messages)} messages'
    assert packed_codes(attribute_field(messages[0])) == [CODE.MP_UNREACH_NLRI]
