"""draft-mpmz-bess-mup-safi-05: a malformed MUP route is skipped, not a session reset.

The ledger these tests are joined to is qa/rfc/draft-mpmz-bess-mup-safi-05.toml.

Every route type of section 3.1 ends its encoding rules the same way: a malformed NLRI is
handled as "Treat-as-withdraw" and the speaker "MUST skip such NLRIs and continue
processing of rest of the Update message".  Skipping needs to know where the next NLRI
starts, which the outer MUP framing gives: Architecture Type, Route Type and a Length
octet.  So a body which is wrong inside an honest Length goes alone, and a Length which
runs past the attribute still resets the session, since nothing says where the next NLRI
would begin.

Each test puts a well formed route behind the malformed one, so a decoder which dropped
the whole attribute, or stopped at the first error, fails it.
"""

from __future__ import annotations

from collections.abc import Callable
from struct import pack

import pytest

from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from tests import negotiation

pytestmark = pytest.mark.timeout(10)

MUP_V4: FamilyTuple = (AFI.ipv4, SAFI.mup)
MUP_V6: FamilyTuple = (AFI.ipv6, SAFI.mup)

ARCHITECTURE_3GPP_5G = 1
ISD, DSD, T1ST, T2ST = 1, 2, 3, 4

RD = pack('!HHI', 0, 65000, 1)
NEXT_HOP = bytes([192, 0, 2, 1])
ADDRESS_BITS = {AFI.ipv4: 32, AFI.ipv6: 128}


def mup(code: int, body: bytes) -> bytes:
    """A MUP NLRI whose Length octet is honest, whatever the body holds."""
    return pack('!BHB', ARCHITECTURE_3GPP_5G, code, len(body)) + body


def isd(prefix_bits: int, prefix: bytes) -> bytes:
    return mup(ISD, RD + bytes([prefix_bits]) + prefix)


def address(afi: AFI) -> bytes:
    return bytes(range(1, ADDRESS_BITS[afi] // 8 + 1))


def t1st(
    afi: AFI, prefix_bits: int, endpoint_bits: int, source: bytes | None = b'', teid: int = 12345, prefix: int = 0
) -> bytes:
    """A Type 1 ST route; `source` None leaves the Source Address Length out, as -02 did."""
    prefix_octets = bytes([prefix]) * ((prefix_bits + 7) // 8)
    teid_qfi = pack('!IB', teid, 5)
    endpoint = bytes([endpoint_bits]) + bytes(endpoint_bits // 8)
    source_field = b'' if source is None else bytes([len(source) * 8]) + source
    return mup(T1ST, RD + bytes([prefix_bits]) + prefix_octets + teid_qfi + endpoint + source_field)


def t2st(afi: AFI, endpoint_bits: int, teid: int = 1) -> bytes:
    """A Type 2 ST route; the TEID is only written when the Endpoint Length has room for it."""
    teid_bits = max(endpoint_bits - ADDRESS_BITS[afi], 0)
    teid_octets = (teid_bits + 7) // 8
    value = teid.to_bytes(teid_octets, 'big') if teid_octets else b''
    return mup(T2ST, RD + bytes([endpoint_bits]) + address(afi) + value)


def session() -> Negotiated:
    return negotiation.negotiated([MUP_V4, MUP_V6])


def announced(family: FamilyTuple, *routes: bytes) -> list[NLRI]:
    afi, safi = family
    value = pack('!HB', int(afi), int(safi)) + bytes([len(NEXT_HOP)]) + NEXT_HOP + bytes([0]) + b''.join(routes)
    attribute = MPRNLRI.unpack_attribute(value, session())
    assert isinstance(attribute, MPRNLRI)
    return list(attribute)


def withdrawn(family: FamilyTuple, *routes: bytes) -> list[NLRI]:
    afi, safi = family
    attribute = MPURNLRI.unpack_attribute(pack('!HB', int(afi), int(safi)) + b''.join(routes), session())
    assert isinstance(attribute, MPURNLRI)
    return list(attribute)


def survivors(family: FamilyTuple, malformed: bytes, good: bytes) -> None:
    """Only the good route is left, announced or withdrawn, wherever the malformed one sits."""
    for decode in (announced, withdrawn):
        for routes in ((malformed, good), (good, malformed)):
            (route,) = decode(family, *routes)
            assert bytes(route.pack_nlri(Negotiated.UNSET)) == good


# ---------------------------------------------------------- the route types of section 3.1


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.1-isd-prefix-length-malformed-skip')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_an_isd_route_with_a_prefix_length_past_the_address_is_skipped(family: FamilyTuple) -> None:
    afi = family[0]
    too_long = ADDRESS_BITS[afi] + 1
    survivors(family, isd(too_long, bytes((too_long + 7) // 8)), isd(24, bytes([10, 0, 0])))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.1-isd-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_an_isd_route_with_a_prefix_of_the_full_address_is_kept(family: FamilyTuple) -> None:
    """The maximum is allowed: an off by one in the bound would skip a valid host route."""
    bits = ADDRESS_BITS[family[0]]
    route = isd(bits, address(family[0]))
    (decoded,) = announced(family, route)
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


def test_a_dsd_route_with_an_address_neither_4_nor_16_octets_is_skipped() -> None:
    survivors(MUP_V4, mup(DSD, RD + bytes([1, 2, 3])), mup(DSD, RD + bytes([10, 0, 0, 1])))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.2-dsd-address-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_dsd_route_with_the_address_of_the_other_afi_is_skipped(family: FamilyTuple) -> None:
    """Both sizes used to be accepted under either AFI, so an IPv6 address rode in an IPv4 route."""
    other = AFI.ipv6 if family[0] == AFI.ipv4 else AFI.ipv4
    survivors(family, mup(DSD, RD + address(other)), mup(DSD, RD + address(family[0])))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.2-dsd-address-length-malformed-skip')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_dsd_route_with_the_address_of_its_afi_is_kept(family: FamilyTuple) -> None:
    route = mup(DSD, RD + address(family[0]))
    (decoded,) = announced(family, route)
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3-t1st-prefix-length-malformed-skip')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t1st_route_with_a_prefix_length_past_the_address_is_skipped(family: FamilyTuple) -> None:
    afi = family[0]
    survivors(family, t1st(afi, ADDRESS_BITS[afi] + 1, 32), t1st(afi, 24, 32))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3-t1st-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t1st_route_with_a_prefix_of_the_full_address_is_kept(family: FamilyTuple) -> None:
    afi = family[0]
    route = t1st(afi, ADDRESS_BITS[afi], 128)
    (decoded,) = announced(family, route)
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


# ---------------------------------------------------------- 3.1.3.1, the 3gpp-5g part of a Type 1 ST route


def update(family: FamilyTuple, *routes: bytes) -> UpdateCollection:
    """An iBGP UPDATE announcing `routes`, decoded as one received from a peer."""
    afi, safi = family
    value = pack('!HB', int(afi), int(safi)) + bytes([len(NEXT_HOP)]) + NEXT_HOP + bytes([0]) + b''.join(routes)
    attributes = (
        bytes([0x40, 1, 1, 0])  # ORIGIN IGP
        + bytes([0x40, 2, 0])  # an empty AS_PATH, iBGP
        + bytes([0x90, 14])
        + pack('!H', len(value))
        + value
    )
    return UpdateCollection.unpack_message(pack('!H', 0) + pack('!H', len(attributes)) + attributes, session())


def withdrawn_key(family: FamilyTuple, malformed: bytes) -> None:
    """The malformed route is withdrawn by its key, and the good one beside it announced."""
    good = t1st(family[0], 24, 32, prefix=10)
    for routes in ((malformed, good), (good, malformed)):
        decoded = update(family, *routes)
        assert [bytes(routed.nlri.pack_nlri(Negotiated.UNSET)) for routed in decoded.announces] == [good]
        (withdraw,) = decoded.withdraws
        (expected,) = announced(family, t1st(family[0], 24, 32))
        # the key is RD, Prefix Length and Prefix: a withdrawal removes what it announced
        assert withdraw.index() == expected.index()
        assert str(withdraw).startswith('mup:t1st:'), str(withdraw)
        assert '"prefix_ip_len": 24' in withdraw.json()


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-teid-zero-malformed', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t1st_route_with_a_teid_of_zero_withdraws_its_key(family: FamilyTuple) -> None:
    withdrawn_key(family, t1st(family[0], 24, 32, teid=0))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-teid-zero-malformed')
def test_a_t1st_route_with_a_teid_of_one_is_announced() -> None:
    route = t1st(AFI.ipv4, 24, 32, teid=1)
    assert [bytes(r.nlri.pack_nlri(Negotiated.UNSET)) for r in update(MUP_V4, route).announces] == [route]


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-endpoint-length-malformed', polarity='negative')
@pytest.mark.parametrize('bits', [0, 40, 64])
def test_a_t1st_route_with_an_endpoint_neither_32_nor_128_bits_withdraws_its_key(bits: int) -> None:
    """It was skipped, which left the route the peer had announced before in place."""
    withdrawn_key(MUP_V4, t1st(AFI.ipv4, 24, bits))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-endpoint-length-malformed')
@pytest.mark.parametrize('bits', [32, 128])
def test_a_t1st_route_with_an_endpoint_of_32_or_128_bits_is_announced(bits: int) -> None:
    route = t1st(AFI.ipv4, 24, bits)
    assert [bytes(r.nlri.pack_nlri(Negotiated.UNSET)) for r in update(MUP_V4, route).announces] == [route]


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-source-length', polarity='negative')
@pytest.mark.parametrize('source', [bytes(1), bytes(5), bytes(8)])
def test_a_t1st_route_with_a_source_neither_0_32_nor_128_bits_withdraws_its_key(source: bytes) -> None:
    withdrawn_key(MUP_V4, t1st(AFI.ipv4, 24, 32, source=source))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-source-length')
@pytest.mark.parametrize('source', [b'', bytes([10, 0, 0, 1]), bytes(range(16))], ids=['none', 'ipv4', 'ipv6'])
def test_a_t1st_route_with_a_source_of_0_32_or_128_bits_is_announced(source: bytes) -> None:
    """A Source Address Length of 0 carries no source: it was refused, as not 32 or 128."""
    route = t1st(AFI.ipv4, 24, 32, source=source)
    (decoded,) = [routed.nlri for routed in update(MUP_V4, route).announces]
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route
    decoded.json()
    str(decoded)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-source-length')
def test_a_t1st_route_without_a_source_is_sent_with_a_source_length_of_zero() -> None:
    """Since -03 the octet is always there; -02 left it out when there was no source."""
    from exabgp.bgp.message.update.nlri.mup import Type1SessionTransformedRoute
    from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
    from exabgp.protocol.ip import IP

    route = Type1SessionTransformedRoute.make_t1st(
        rd=RouteDistinguisher(RD),
        prefix_ip_len=24,
        prefix_ip=IP.from_string('0.0.0.0'),
        teid=12345,
        qfi=5,
        endpoint_ip_len=32,
        endpoint_ip=IP.from_string('0.0.0.0'),
        source_ip_len=0,
        source_ip=b'',
        afi=AFI.ipv4,
    )
    assert bytes(route.pack_nlri(Negotiated.UNSET)) == t1st(AFI.ipv4, 24, 32)


def test_a_t1st_route_of_draft_02_without_a_source_length_is_read_as_one_of_zero() -> None:
    """Unmarked: the -02 encoding is no longer the draft's, but exabgp sent it until now.

    It is kept, and held as the -05 encoding, so the route compares, hashes and is sent
    again as the one a current peer would have written.
    """
    (decoded,) = announced(MUP_V4, t1st(AFI.ipv4, 24, 32, source=None))
    (current,) = announced(MUP_V4, t1st(AFI.ipv4, 24, 32))
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == t1st(AFI.ipv4, 24, 32)
    assert decoded == current and hash(decoded) == hash(current)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-architecture-encoding', polarity='negative')
@pytest.mark.parametrize('cut', [1, 4, 9], ids=['source', 'endpoint', 'teid'])
def test_a_t1st_route_whose_3gpp_5g_part_is_short_withdraws_its_key(cut: int) -> None:
    """The Length octet stays honest: the route is shorter, not overrunning the attribute."""
    route = t1st(AFI.ipv4, 24, 32, source=bytes([10, 0, 0, 1]))
    body = route[4 : len(route) - cut]
    withdrawn_key(MUP_V4, mup(T1ST, body))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-architecture-encoding', polarity='negative')
def test_a_t1st_route_with_octets_after_its_source_withdraws_its_key() -> None:
    route = t1st(AFI.ipv4, 24, 32, source=bytes([10, 0, 0, 1]))
    withdrawn_key(MUP_V4, mup(T1ST, route[4:] + bytes(1)))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-architecture-encoding')
def test_a_t1st_route_encoded_as_shown_is_announced() -> None:
    route = t1st(AFI.ipv4, 24, 32, source=bytes([10, 0, 0, 1]))
    assert [bytes(r.nlri.pack_nlri(Negotiated.UNSET)) for r in update(MUP_V4, route).announces] == [route]


def test_a_withdrawn_t1st_route_with_a_teid_of_zero_still_withdraws_its_key() -> None:
    """Unmarked: in MP_UNREACH_NLRI the malformed route was skipped, and its withdrawal lost."""
    (withdraw,) = withdrawn(MUP_V4, t1st(AFI.ipv4, 24, 32, teid=0))
    (expected,) = announced(MUP_V4, t1st(AFI.ipv4, 24, 32))
    assert withdraw.index() == expected.index()


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.4-t2st-endpoint-length-malformed-skip')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t2st_route_with_an_endpoint_longer_than_the_maximum_is_skipped(family: FamilyTuple) -> None:
    """64 for IPv4 and 160 for IPv6: the address and a TEID of up to 32 bits."""
    afi = family[0]
    maximum = ADDRESS_BITS[afi] + 32
    survivors(family, t2st(afi, maximum + 8), t2st(afi, ADDRESS_BITS[afi]))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.4.1-t2st-teid-zero-malformed', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
@pytest.mark.parametrize('teid_bits', [8, 32])
def test_a_t2st_route_with_a_teid_of_zero_is_skipped(family: FamilyTuple, teid_bits: int) -> None:
    """The TEID is part of a Type 2 ST route's key, so there is no other key to withdraw."""
    afi = family[0]
    endpoint_bits = ADDRESS_BITS[afi] + teid_bits
    survivors(family, t2st(afi, endpoint_bits, teid=0), t2st(afi, endpoint_bits, teid=1))


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.4.1-t2st-teid-zero-malformed')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t2st_route_without_a_teid_or_with_one_is_kept(family: FamilyTuple) -> None:
    """An Endpoint Length of the address alone carries no TEID, which is not a TEID of zero."""
    afi = family[0]
    for route in (t2st(afi, ADDRESS_BITS[afi]), t2st(afi, ADDRESS_BITS[afi] + 8, teid=1)):
        (decoded,) = announced(family, route)
        assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


# ---------------------------------------------------------- 3.1, the route types exabgp does not know


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1-other-route-types-ignored', polarity='negative')
@pytest.mark.parametrize('decode', [announced, withdrawn], ids=['mp-reach', 'mp-unreach'])
@pytest.mark.parametrize('architecture,code', [(ARCHITECTURE_3GPP_5G, 5), (2, ISD), (1, 0)])
def test_a_route_of_another_type_or_architecture_is_silently_ignored(
    decode: Callable[..., list[NLRI]], architecture: int, code: int
) -> None:
    """It used to reach the RIB and the API as a GenericMUP of raw octets."""
    good = isd(24, bytes([10, 0, 0]))
    other = pack('!BHB', architecture, code, len(RD) + 4) + RD + bytes(4)
    for routes in ((other, good), (good, other)):
        assert [bytes(route.pack_nlri(Negotiated.UNSET)) for route in decode(MUP_V4, *routes)] == [good]


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1-other-route-types-ignored')
@pytest.mark.parametrize('code', [ISD, DSD, T1ST, T2ST])
def test_the_four_route_types_of_3gpp_5g_are_kept(code: int) -> None:
    route = {
        ISD: isd(24, bytes([10, 0, 0])),
        DSD: mup(DSD, RD + address(AFI.ipv4)),
        T1ST: t1st(AFI.ipv4, 24, 32),
        T2ST: t2st(AFI.ipv4, 40, teid=1),
    }[code]
    (decoded,) = announced(MUP_V4, route)
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.4-t2st-endpoint-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('family', [MUP_V4, MUP_V6], ids=['ipv4', 'ipv6'])
def test_a_t2st_route_at_the_maximum_endpoint_length_is_kept(family: FamilyTuple) -> None:
    afi = family[0]
    route = t2st(afi, ADDRESS_BITS[afi] + 32)
    (decoded,) = announced(family, route)
    assert bytes(decoded.pack_nlri(Negotiated.UNSET)) == route


# ---------------------------------------------------------- what still resets the session


@pytest.mark.parametrize('decode', [announced, withdrawn], ids=['mp-reach', 'mp-unreach'])
def test_a_length_octet_past_the_attribute_still_resets_the_session(decode: Callable[..., list[NLRI]]) -> None:
    """Without an honest Length there is no next NLRI to continue from, so skipping is not on offer."""
    route = isd(24, bytes([10, 0, 0]))
    overrun = route[:3] + bytes([route[3] + 1]) + route[4:]
    with pytest.raises(Notify) as raised:
        decode(MUP_V4, overrun)
    assert not isinstance(raised.value, NLRIDiscard) or not raised.value.skip
    assert (raised.value.code, raised.value.subcode) == (3, 10)


# ---------------------------------------------------------- what exabgp is willing to send


def configured(line: str, afi_keyword: str = 'ipv4') -> str:
    """'' when the API accepts the route, the error otherwise."""
    from exabgp.configuration.configuration import Configuration

    configuration = Configuration([''], text=True)
    if configuration.partial(afi_keyword, line, 'announce'):
        return ''
    return str(configuration.error)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3.1-t1st-teid-zero-malformed')
def test_a_t1st_route_with_a_teid_of_zero_is_refused_by_the_configuration() -> None:
    assert configured('mup mup-t1st 10.0.1.0/24 rd 100:100 teid 1 qfi 9 endpoint 10.0.0.1 next-hop 10.0.0.1') == ''
    assert 'teid 0' in configured(
        'mup mup-t1st 10.0.1.0/24 rd 100:100 teid 0 qfi 9 endpoint 10.0.0.1 next-hop 10.0.0.1'
    )


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.4.1-t2st-teid-zero-malformed')
def test_a_t2st_route_with_a_teid_of_zero_is_refused_by_the_configuration() -> None:
    assert configured('mup mup-t2st 10.0.0.1 rd 100:100 teid 0/0 next-hop 10.0.0.1') == ''
    assert 'TEID 0/8' in configured('mup mup-t2st 10.0.0.1 rd 100:100 teid 0/8 next-hop 10.0.0.1')


# The prefix of an ISD or a T1ST route is a prefix of the AFI's family, at most 32 bits for
# IPv4 and 128 for IPv6: what a receiver treats as malformed, we refuse to send.  The
# configuration used to pack `mup-isd 10.0.1.0/255` as given, and refused a T1ST /33 only
# because the packing hit a negative count.

ISD_LINE = 'mup mup-isd {prefix} rd 100:100 next-hop {nexthop}'
T1ST_LINE = 'mup mup-t1st {prefix} rd 100:100 teid 1 qfi 9 endpoint {endpoint} next-hop {nexthop}'
IPV4_ROUTE = {'afi_keyword': 'ipv4', 'nexthop': '10.0.0.1', 'endpoint': '10.0.0.1'}
IPV6_ROUTE = {'afi_keyword': 'ipv6', 'nexthop': '2001:db8::1', 'endpoint': '2001:db8::1'}


def configured_mup(template: str, prefix: str, route: dict[str, str]) -> str:
    line = template.format(prefix=prefix, nexthop=route['nexthop'], endpoint=route['endpoint'])
    return configured(line, route['afi_keyword'])


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.1-isd-prefix-length-malformed-skip')
@pytest.mark.parametrize('prefix, route', [('10.0.1.1/32', IPV4_ROUTE), ('2001:db8::1/128', IPV6_ROUTE)])
def test_an_isd_route_of_the_full_address_is_accepted_by_the_configuration(prefix: str, route: dict[str, str]) -> None:
    assert configured_mup(ISD_LINE, prefix, route) == ''


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.1-isd-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize(
    'prefix, route',
    [('10.0.1.0/33', IPV4_ROUTE), ('10.0.1.0/255', IPV4_ROUTE), ('2001:db8::/129', IPV6_ROUTE)],
)
def test_an_isd_route_with_a_prefix_length_past_the_address_is_refused(prefix: str, route: dict[str, str]) -> None:
    assert 'prefix length' in configured_mup(ISD_LINE, prefix, route)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.1-isd-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('prefix, route', [('2001:db8::/32', IPV4_ROUTE), ('10.0.1.0/24', IPV6_ROUTE)])
def test_an_isd_route_with_a_prefix_of_the_other_family_is_refused(prefix: str, route: dict[str, str]) -> None:
    assert 'not an' in configured_mup(ISD_LINE, prefix, route)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3-t1st-prefix-length-malformed-skip')
@pytest.mark.parametrize('prefix, route', [('10.0.1.1/32', IPV4_ROUTE), ('2001:db8::1/128', IPV6_ROUTE)])
def test_a_t1st_route_of_the_full_address_is_accepted_by_the_configuration(prefix: str, route: dict[str, str]) -> None:
    assert configured_mup(T1ST_LINE, prefix, route) == ''


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3-t1st-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('prefix, route', [('10.0.1.0/33', IPV4_ROUTE), ('2001:db8::/129', IPV6_ROUTE)])
def test_a_t1st_route_with_a_prefix_length_past_the_address_is_refused(prefix: str, route: dict[str, str]) -> None:
    assert 'prefix length' in configured_mup(T1ST_LINE, prefix, route)


@pytest.mark.rfc('draft-mpmz-bess-mup-safi-05#3.1.3-t1st-prefix-length-malformed-skip', polarity='negative')
@pytest.mark.parametrize('prefix, route', [('2001:db8::/32', IPV4_ROUTE), ('10.0.1.0/24', IPV6_ROUTE)])
def test_a_t1st_route_with_a_prefix_of_the_other_family_is_refused(prefix: str, route: dict[str, str]) -> None:
    assert 'not an' in configured_mup(T1ST_LINE, prefix, route)


@pytest.mark.parametrize('factory', ['isd', 't1st'])
def test_the_factories_refuse_a_prefix_length_past_the_address(factory: str) -> None:
    """The configuration is the boundary; the factories hold us to it."""
    from exabgp.bgp.message.update.nlri.mup import InterworkSegmentDiscoveryRoute, Type1SessionTransformedRoute
    from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
    from exabgp.protocol.ip import IPv4

    rd = RouteDistinguisher.make_from_elements('100', 100)
    prefix = IPv4.from_string('10.0.1.0')
    with pytest.raises(AssertionError):
        if factory == 'isd':
            InterworkSegmentDiscoveryRoute.make_isd(rd=rd, prefix_ip_len=33, prefix_ip=prefix, afi=AFI.ipv4)
        else:
            Type1SessionTransformedRoute.make_t1st(
                rd=rd,
                prefix_ip_len=33,
                prefix_ip=prefix,
                teid=1,
                qfi=9,
                endpoint_ip_len=32,
                endpoint_ip=prefix,
                source_ip_len=0,
                source_ip=b'',
                afi=AFI.ipv4,
            )
