"""RFC 5492, Capabilities Advertisement with BGP-4.

The ledger these tests are joined to is qa/rfc/rfc5492.toml.

This document exists because RFC 4271 says an OPEN with an Optional Parameter you do not
recognise ends the peering, which makes every new BGP feature a flag day. Almost all of
its weight is therefore in what a speaker must NOT do, and a parser which quietly
accepted everything would pass every positive test here. So each MUST that says "ignore
it" is paired with a case which must still be refused.

Everything drives Capabilities.unpack or Open.unpack_message on real wire bytes.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, Open
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.unknown import UnknownCapability
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.util.enumeration import TriState

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)

CAPABILITIES_PARAMETER = 2

# A code IANA has not assigned and exabgp has no decoder for. 222 sits in the private
# use range, which is where a peer's home-grown capability would be.
UNASSIGNED_CODE = 222

MULTIPROTOCOL_IPV4_UNICAST = pack('!HBB', AFI.ipv4, 0, SAFI.unicast)
MULTIPROTOCOL_IPV6_UNICAST = pack('!HBB', AFI.ipv6, 0, SAFI.unicast)


def parameter(capabilities: list[tuple[int, bytes]]) -> bytes:
    """One Capabilities Optional Parameter holding these <code, length, value> triples."""
    body = b''
    for code, value in capabilities:
        body += bytes([code, len(value)]) + value
    return bytes([CAPABILITIES_PARAMETER, len(body)]) + body


def optional_parameters(*parameters: bytes) -> bytes:
    """The Optional Parameters field of an OPEN: a length octet, then the parameters."""
    joined = b''.join(parameters)
    return bytes([len(joined)]) + joined


def open_message(*parameters: bytes) -> bytes:
    """A complete OPEN payload, as Open.unpack_message takes it."""
    return bytes([4]) + pack('!H', 65002) + pack('!H', 90) + bytes([192, 0, 2, 2]) + optional_parameters(*parameters)


def type_two_parameter_count(packed: bytes) -> int:
    """How many Capabilities Optional Parameters an Optional Parameters field holds."""
    count = 0
    offset = 1
    while offset < len(packed):
        assert packed[offset] == CAPABILITIES_PARAMETER, 'exabgp emitted a parameter which is not type 2'
        count += 1
        offset += 2 + packed[offset + 1]
    return count


def families_of(capabilities: Capabilities) -> list[FamilyTuple]:
    """The families a multiprotocol capability advertises, narrowed for the type checker."""
    advertised = capabilities[Capability.CODE.MULTIPROTOCOL]
    assert isinstance(advertised, MultiProtocol), 'the multiprotocol capability decoded to something else'
    return list(advertised)


def advertising_neighbour() -> Neighbor:
    """A neighbour with enough turned on that its OPEN carries several capabilities."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.capability.asn4 = TriState.TRUE
    neighbor.capability.route_refresh = True
    neighbor.add_family(IPV4_UNICAST)
    neighbor.add_family(IPV6_UNICAST)
    return neighbor


# =========================================================== 3, sending the parameter


@pytest.mark.rfc('rfc5492#3-open-may-carry-capabilities')
def test_our_open_takes_the_permission_and_carries_capabilities() -> None:
    packed = Capabilities().new(advertising_neighbour(), False).pack_capabilities()

    assert type_two_parameter_count(packed) >= 1, 'our OPEN carried no Capabilities Optional Parameter'


# =========================================================== 3, unknown capabilities


@pytest.mark.rfc('rfc5492#3-unknown-capability-must-be-ignored')
def test_a_capability_we_have_no_decoder_for_is_kept_as_unknown() -> None:
    """Ignored, in the sense that nothing acts on it: it decodes to the fallback class."""
    capabilities = Capabilities.unpack(optional_parameters(parameter([(UNASSIGNED_CODE, b'\x01\x02')])))

    assert UNASSIGNED_CODE in capabilities
    assert isinstance(capabilities[UNASSIGNED_CODE], UnknownCapability)


@pytest.mark.rfc('rfc5492#3-unknown-capability-must-be-ignored', polarity='negative')
def test_a_capability_we_do_understand_is_not_treated_as_unknown() -> None:
    """The half which finds bugs: answering UnknownCapability to everything also ignores."""
    capabilities = Capabilities.unpack(
        optional_parameters(parameter([(Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST)]))
    )

    assert families_of(capabilities) == [IPV4_UNICAST], 'a registered capability fell through to the unknown fallback'


@pytest.mark.rfc('rfc5492#3-no-notification-for-an-unknown-capability')
@pytest.mark.parametrize(
    'code', [UNASSIGNED_CODE, 0x04, 0x43, 0x7F], ids=['private', 'unassigned-4', 'dynamic', 'unassigned-127']
)
def test_an_unknown_capability_raises_nothing_and_ends_no_session(code: int) -> None:
    """Notify out of the parser is how a session dies, so raising nothing is the test."""
    message = open_message(parameter([(code, b'\x00\x01\x02\x03')]))

    decoded = Open.unpack_message(message, Negotiated.UNSET)

    assert code in decoded.capabilities


@pytest.mark.rfc('rfc5492#3-no-notification-for-an-unknown-capability', polarity='negative')
@pytest.mark.parametrize(
    'what,malformed',
    [
        (
            'a capability length past the end of its parameter',
            bytes([2, 4]) + bytes([UNASSIGNED_CODE, 10]) + b'\x00\x01',
        ),
        ('a capability header cut in half', bytes([2, 1]) + bytes([UNASSIGNED_CODE])),
    ],
    ids=['length-overrun', 'truncated-header'],
)
def test_a_capability_whose_length_disagrees_with_its_contents_is_still_refused(what: str, malformed: bytes) -> None:
    """Not raising for an unknown code must not become not raising for broken framing."""
    with pytest.raises(Notify):
        Capabilities.unpack(optional_parameters(malformed))


@pytest.mark.rfc('rfc5492#5-unsupported-capability-not-for-unknown-codes')
def test_an_open_carrying_an_unknown_capability_is_accepted_whole() -> None:
    """Section 5 restates the rule where subcode 7 is defined, so test the whole OPEN."""
    message = open_message(
        parameter(
            [
                (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
                (UNASSIGNED_CODE, b'\xde\xad\xbe\xef'),
            ]
        )
    )

    decoded = Open.unpack_message(message, Negotiated.UNSET)

    assert decoded.asn == ASN(65002), 'the OPEN did not survive the unknown capability'
    assert Capability.CODE.MULTIPROTOCOL in decoded.capabilities, 'the capability after the unknown one was lost'
    assert UNASSIGNED_CODE in decoded.capabilities


@pytest.mark.rfc('rfc5492#5-unsupported-capability-not-for-unknown-codes', polarity='negative')
def test_an_open_we_genuinely_cannot_parse_is_still_refused() -> None:
    """An OPEN carrying an Optional Parameter which is not Capabilities is a different thing."""
    unknown_parameter = bytes([9, 2]) + b'\x00\x00'

    with pytest.raises(Notify):
        Open.unpack_message(open_message(unknown_parameter), Negotiated.UNSET)


# =========================================================== 4, repeated capabilities


@pytest.mark.rfc('rfc5492#4-accept-repeated-identical-instances')
def test_a_capability_sent_twice_identically_is_accepted() -> None:
    """Additional instances do not change the meaning, so they must not change the outcome."""
    once = Capabilities.unpack(
        optional_parameters(parameter([(Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST)]))
    )
    twice = Capabilities.unpack(
        optional_parameters(
            parameter(
                [
                    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
                    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
                ]
            )
        )
    )

    assert families_of(twice) == families_of(once)
    assert families_of(twice) == [IPV4_UNICAST]


@pytest.mark.rfc('rfc5492#4-accept-repeated-identical-instances', polarity='negative')
def test_a_repeated_instance_which_is_malformed_is_not_accepted() -> None:
    """Tolerating repetition is not tolerating anything that comes after the first copy."""
    body = (
        bytes([Capability.CODE.MULTIPROTOCOL, 4])
        + MULTIPROTOCOL_IPV4_UNICAST
        + bytes([Capability.CODE.MULTIPROTOCOL, 4])
        + b'\x00\x01'
    )
    malformed = bytes([CAPABILITIES_PARAMETER, len(body)]) + body

    with pytest.raises(Notify):
        Capabilities.unpack(optional_parameters(malformed))


@pytest.mark.rfc('rfc5492#4-should-not-repeat-an-identical-capability')
def test_our_own_open_repeats_no_capability_triple() -> None:
    """Read the triples back off the wire bytes, not off the dict that produced them."""
    packed = Capabilities().new(advertising_neighbour(), False).pack_capabilities()

    seen: list[tuple[int, int, bytes]] = []
    offset = 1
    while offset < len(packed):
        end = offset + 2 + packed[offset + 1]
        body = packed[offset + 2 : end]
        position = 0
        while position < len(body):
            length = body[position + 1]
            seen.append((body[position], length, bytes(body[position + 2 : position + 2 + length])))
            position += 2 + length
        offset = end

    assert seen, 'our OPEN carried no capability at all, so this proves nothing'
    assert len(set(seen)) == len(seen), f'our OPEN repeats a capability triple: {seen}'


# =========================================================== 4, how many parameters


@pytest.mark.rfc('rfc5492#4-one-capabilities-parameter-per-open')
@pytest.mark.xfail(
    strict=True,
    reason='Capabilities.pack_capabilities wraps every capability TLV in its own type 2 parameter, so an OPEN carries one per capability',
)
def test_our_open_carries_a_single_capabilities_optional_parameter() -> None:
    packed = Capabilities().new(advertising_neighbour(), False).pack_capabilities()

    count = type_two_parameter_count(packed)
    assert count == 1, f'our OPEN carried {count} Capabilities Optional Parameters'


@pytest.mark.rfc('rfc5492#4-accept-multiple-capabilities-parameters')
def test_capabilities_split_across_two_parameters_are_all_read() -> None:
    """The set must be processed the same way however the peer chose to split it."""
    split = Capabilities.unpack(
        optional_parameters(
            parameter([(Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST)]),
            parameter(
                [
                    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV6_UNICAST),
                    (Capability.CODE.ROUTE_REFRESH, b''),
                ]
            ),
        )
    )
    together = Capabilities.unpack(
        optional_parameters(
            parameter(
                [
                    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST),
                    (Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV6_UNICAST),
                    (Capability.CODE.ROUTE_REFRESH, b''),
                ]
            )
        )
    )

    assert families_of(split) == [IPV4_UNICAST, IPV6_UNICAST]
    assert families_of(split) == families_of(together)
    assert Capability.CODE.ROUTE_REFRESH in split, 'the capability after the split was lost'


@pytest.mark.rfc('rfc5492#4-accept-multiple-capabilities-parameters', polarity='negative')
def test_a_second_parameter_which_overruns_the_field_is_refused() -> None:
    """Accepting several parameters must not mean trusting each one's length field."""
    good = parameter([(Capability.CODE.MULTIPROTOCOL, MULTIPROTOCOL_IPV4_UNICAST)])
    overrunning = bytes([CAPABILITIES_PARAMETER, 40]) + bytes([Capability.CODE.ROUTE_REFRESH, 0])

    with pytest.raises(Notify):
        Capabilities.unpack(optional_parameters(good, overrunning))
