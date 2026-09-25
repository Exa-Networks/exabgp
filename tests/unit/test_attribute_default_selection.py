"""`with_default` chooses whether the defaults are synthesised, not whether anything is sent.

`Attributes.pack` builds the set of attribute codes it is going to encode from two sources:
the codes the collection actually holds, and the three codes it can synthesise when they are
absent (ORIGIN, AS_PATH and LOCAL_PREF).  `with_default` is about the second source only.

The union was written as `set(keys + list(default) if with_default else [])`, and a
conditional expression binds looser than `+` in Python, so the whole of `keys +
list(default)` was the true branch and `with_default=False` collapsed the set to nothing.
Every attribute the caller had put in the collection was silently dropped, so
`pack(negotiated, False)` returned `b''` whatever it was given.

The only caller which asked for it is `Update.messages`, for an UPDATE which carries nothing
but MP_UNREACH_NLRI of a unicast or multicast family.  RFC 4760 3 says such an UPDATE "is not
required to carry any other path attributes", and that pass wants no attribute field at all,
which is what the bug happened to give it.  So correcting the brackets alone would have
changed the wire: the withdrawn route's own attributes would start being encoded onto its
MP_UNREACH message, and the withdrawal would be sized against them, which is how a
withdrawal came to be dropped for the weight of an announcement it was not carrying.  That
pass therefore now says `b''` outright, and the last test here holds it.
"""

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attributes, MED
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

BGP_HEADER_SIZE = 19

MED_VALUE = 42


@pytest.fixture(autouse=True)
def quiet_codec_logging(monkeypatch):
    monkeypatch.setattr(log, 'debug', lambda *args: None)
    monkeypatch.setattr(log, 'critical', lambda *args: None)


def negotiated_session():
    """An EBGP session with the two unicast families these tests use."""
    negotiated = Negotiated({'capability': {'aigp': False}})
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]
    return negotiated


def one_med():
    """A collection holding a single attribute, and one which is never a default."""
    attributes = Attributes()
    attributes.add(MED(MED_VALUE))
    return attributes


def packed_codes(packed):
    """The attribute type codes of an encoded path attribute field, in the order they are in."""
    codes = []
    offset = 0
    while offset < len(packed):
        flag = packed[offset]
        code = packed[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = int.from_bytes(packed[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            length = packed[offset + 2]
            offset += 3
        codes.append(code)
        offset += length
    assert offset == len(packed), 'the encoded attribute field does not frame its own attributes'
    return codes


def attribute_field(message):
    """The Total Path Attribute field of one generated UPDATE, header and lengths removed."""
    body = message[BGP_HEADER_SIZE:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    start = 2 + withdrawn_length + 2
    length = int.from_bytes(body[2 + withdrawn_length : start], 'big')
    return body[start : start + length]


def withdrawn_ipv6(prefix):
    """One bare IPv6 unicast NLRI, which is all an MP_UNREACH_NLRI carries."""
    address, mask = prefix.split('/')
    ip = IP.create(address)
    nlri = INET(ip.afi, SAFI.unicast, Action.WITHDRAW)
    nlri.cidr = CIDR(ip.pack(), int(mask))
    return nlri


def test_without_the_defaults_the_attributes_held_are_still_packed():
    """The bug in one assertion: a collection holding a MED encoded to nothing at all."""
    negotiated = negotiated_session()

    packed = one_med().pack(negotiated, False)

    assert packed == MED(MED_VALUE).pack(negotiated)


def test_without_the_defaults_no_default_attribute_is_added():
    """The other half: the three synthesised codes stay out of it."""
    packed = one_med().pack(negotiated_session(), False)

    assert packed_codes(packed) == [Attribute.CODE.MED]


def test_with_the_defaults_the_defaults_join_the_attributes_held():
    """The union is a union: what is held, plus what an EBGP announcement must carry."""
    packed = one_med().pack(negotiated_session(), True)

    assert packed_codes(packed) == [Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH, Attribute.CODE.MED]


def test_an_mp_unreach_only_update_still_carries_nothing_but_the_mp_unreach():
    """The caller: RFC 4760 3, and the wire the corrected brackets must not have changed.

    Red without the `b''` at the call site, since the collection holds a MED which `pack` is
    now right to encode when it is asked for the attributes.
    """
    negotiated = negotiated_session()

    messages = list(Update([withdrawn_ipv6('2001:db8::/32')], one_med()).messages(negotiated))

    assert len(messages) == 1, 'one IPv6 withdrawal made {} messages'.format(len(messages))
    assert packed_codes(attribute_field(messages[0])) == [Attribute.CODE.MP_UNREACH_NLRI]
