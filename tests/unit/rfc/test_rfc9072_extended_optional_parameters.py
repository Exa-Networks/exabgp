"""RFC 9072: Optional Parameters longer than 255 octets in an OPEN.

The extended encoding is announced by the octet after the Optional Parameters Length, the
"Non-Ext OP Type", being 255. The length octet before it SHOULD be 255 too, but "MUST be
ignored on receipt once the use of the extended format is determined positively by
inspection of the Non-Extended Optional Parameters Type", and section 3 has a length other
than 255 followed by type 255 decoded with the extended encoding.

One finding, now a regression test: the extended encoding was recognised only when the
length octet was 255. A peer which put any other non-zero value there had its OPEN read
as an Optional Parameter of type 255, and refused as Unsupported Optional Parameters.

`Capabilities.unpack` takes the Optional Parameters block from its length octet on.

The ledger entries these prove are in qa/rfc/rfc9072.toml.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Notify
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.protocol.family import AFI, SAFI

EXTENDED = 255
CAPABILITIES = 2
ROUTE_REFRESH = 2
# a capability code IANA has not assigned, which a speaker ignores (RFC 5492 4)
UNASSIGNED = 200
UNSUPPORTED_OPTIONAL_PARAMETER = (2, 4)

# a Route Refresh capability, code 2 and no value, the smallest there is
CAPABILITY = bytes([ROUTE_REFRESH, 0])


def extended(non_ext_length: int, parameters: bytes) -> bytes:
    """The Optional Parameters of RFC 9072 Figure 1, with this Non-Ext OP Len."""
    return bytes([non_ext_length, EXTENDED]) + pack('!H', len(parameters)) + parameters


def extended_parameter(kind: int, value: bytes) -> bytes:
    """One parameter of RFC 9072 Figure 2, with its two octet length."""
    return bytes([kind]) + pack('!H', len(value)) + value


def standard(*parameters: bytes) -> bytes:
    block = b''.join(parameters)
    return bytes([len(block)]) + block


def standard_parameter(kind: int, value: bytes) -> bytes:
    return bytes([kind, len(value)]) + value


def many_families() -> Capabilities:
    """Capabilities which take more than 255 octets: one Multiprotocol TLV per SAFI."""
    families = MultiProtocol()
    for safi in range(1, 60):
        families.append((AFI.ipv4, SAFI(safi)))
    capabilities = Capabilities()
    capabilities[Capability.CODE.MULTIPROTOCOL] = families
    return capabilities


# --------------------------------------------------------------------- detection on receipt


@pytest.mark.rfc('rfc9072#2-non-ext-op-type-decides-the-encoding')
@pytest.mark.rfc('rfc9072#3-type-255-after-another-length-is-extended')
@pytest.mark.parametrize('non_ext_length', [EXTENDED, 1, 7, 254], ids=lambda length: f'non-ext-len-{length}')
def test_a_first_type_of_255_is_the_extended_encoding_whatever_the_length_octet(non_ext_length: int) -> None:
    parameters = extended(non_ext_length, extended_parameter(CAPABILITIES, CAPABILITY))
    assert Capabilities.unpack(parameters).announced(Capability.CODE.ROUTE_REFRESH)


@pytest.mark.rfc('rfc9072#2-non-ext-op-type-decides-the-encoding', polarity='negative')
def test_a_length_of_255_with_another_first_type_is_the_rfc_4271_encoding() -> None:
    """A length octet of 255 alone says nothing: the first parameter is an ordinary one."""
    # 253 octets of capabilities fill one parameter: an unknown one of a single octet, then
    # Route Refresh again and again
    capabilities = bytes([UNASSIGNED, 1, 0]) + CAPABILITY * 125
    parameters = standard(standard_parameter(CAPABILITIES, capabilities))
    assert parameters[0] == EXTENDED and parameters[1] == CAPABILITIES
    assert Capabilities.unpack(parameters).announced(Capability.CODE.ROUTE_REFRESH)


@pytest.mark.rfc('rfc9072#2-accept-extended-encoding-of-short-parameters')
def test_the_extended_encoding_of_a_few_octets_is_accepted() -> None:
    parameters = extended(EXTENDED, extended_parameter(CAPABILITIES, CAPABILITY))
    assert len(parameters) < 255
    assert Capabilities.unpack(parameters).announced(Capability.CODE.ROUTE_REFRESH)


@pytest.mark.rfc('rfc9072#2-accept-extended-encoding-of-short-parameters', polarity='negative')
def test_an_extended_length_beyond_the_parameters_is_refused() -> None:
    """Accepting the encoding is not accepting a length which overruns what was sent."""
    parameters = extended(EXTENDED, extended_parameter(CAPABILITIES, CAPABILITY))[:-1]
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(parameters)
    assert caught.value.code == 2


@pytest.mark.rfc('rfc9072#3-type-255-elsewhere-is-unrecognised')
@pytest.mark.parametrize(
    'parameters',
    [
        standard(standard_parameter(CAPABILITIES, CAPABILITY), standard_parameter(EXTENDED, b'')),
        extended(EXTENDED, extended_parameter(CAPABILITIES, CAPABILITY) + extended_parameter(EXTENDED, b'')),
    ],
    ids=['standard', 'extended'],
)
def test_type_255_anywhere_else_is_an_unsupported_optional_parameter(parameters: bytes) -> None:
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(parameters)
    assert (caught.value.code, caught.value.subcode) == UNSUPPORTED_OPTIONAL_PARAMETER


@pytest.mark.rfc('rfc9072#3-type-255-elsewhere-is-unrecognised', polarity='negative')
def test_type_255_as_the_non_ext_op_type_is_not_a_parameter() -> None:
    parameters = extended(EXTENDED, extended_parameter(CAPABILITIES, CAPABILITY))
    assert Capabilities.unpack(parameters).announced(Capability.CODE.ROUTE_REFRESH)


@pytest.mark.rfc('rfc9072#2-non-ext-op-len-not-zero', polarity='negative')
def test_a_length_of_zero_is_no_optional_parameters_even_before_type_255() -> None:
    """A peer which sets the length octet to 0 has sent no Optional Parameters: the octet
    after it is only inspected when the length is non-zero."""
    assert not Capabilities.unpack(bytes([0]) + extended(EXTENDED, extended_parameter(CAPABILITIES, CAPABILITY)))


# ------------------------------------------------------------------------ what we send


@pytest.mark.rfc('rfc9072#2-encode-extended-beyond-255')
@pytest.mark.rfc('rfc9072#2-non-ext-op-type-255-on-transmission')
@pytest.mark.rfc('rfc9072#2-non-ext-op-len-not-zero')
def test_more_than_255_octets_go_out_in_the_extended_encoding() -> None:
    packed = many_families().pack_capabilities()
    assert len(packed) > 255
    assert packed[0] == EXTENDED and packed[1] == EXTENDED
    assert int.from_bytes(packed[2:4], 'big') == len(packed) - 4
    assert len(Capabilities.unpack(packed)[Capability.CODE.MULTIPROTOCOL]) == 59


@pytest.mark.rfc('rfc9072#2-encode-extended-beyond-255', polarity='negative')
def test_255_octets_or_fewer_go_out_in_the_rfc_4271_encoding() -> None:
    capabilities = Capabilities()
    families = MultiProtocol()
    families.append((AFI.ipv4, SAFI.unicast))
    capabilities[Capability.CODE.MULTIPROTOCOL] = families
    packed = capabilities.pack_capabilities()
    assert packed[0] == len(packed) - 1 and packed[1] == CAPABILITIES
