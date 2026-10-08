"""draft-abraitis-bgp-version-capability-18, the Software Version capability.

The ledger these tests are joined to is qa/rfc/draft-abraitis-bgp-version-capability-18.toml.

Revision 00 put a length octet in front of the version.  Revisions 15 to 18 do not: the
Capability Value is the string, and its length is the Capability Length.  We sent the old
layout and read the first octet of every value as a length, so a peer sending the current
one (FRR does by default) had its OPEN refused with 2/0, whether or not we had enabled the
capability ourselves.  Software.unpack_capability now reads both, as FRR does.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.capabilities import Parameter
from exabgp.bgp.message.open.capability.software import Software
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB
from exabgp.version import version

SOFTWARE_VERSION = Capability.CODE.SOFTWARE_VERSION
EXTENDED = 255

# What FRR 10 sends with `neighbor X capability software-version`.
FRR_VERSION = b'FRRouting/10.2.1'


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(capability: str) -> Neighbor:
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65002;
    {capability}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    (neighbor,) = configuration.neighbors.values()
    return neighbor


def received(value: bytes) -> Capabilities:
    """Decode a Software Version capability a peer sent, in one Capabilities parameter."""
    tlv = bytes([int(SOFTWARE_VERSION), len(value)]) + value
    parameter = bytes([int(Parameter.CAPABILITIES), len(tlv)]) + tlv
    return Capabilities.unpack(bytes([len(parameter)]) + parameter)


def version_of(capabilities: Capabilities) -> str | None:
    capability = capabilities.get(SOFTWARE_VERSION)
    return capability.software_version if isinstance(capability, Software) else None


def our_value() -> bytes:
    (value,) = Software().extract_capability_bytes()
    return value


# ==============================================================================
# What we send
# ==============================================================================


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-configuration-option-default-disabled')
@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#4-explicitly-configured')
def test_a_neighbour_which_did_not_enable_it_does_not_announce_it() -> None:
    capabilities = Capabilities().new(neighbour(''), False)
    assert not capabilities.announced(SOFTWARE_VERSION)


@pytest.mark.rfc(
    'draft-abraitis-bgp-version-capability-18#3-configuration-option-default-disabled', polarity='negative'
)
@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#4-explicitly-configured', polarity='negative')
def test_a_neighbour_which_enabled_it_announces_it() -> None:
    capabilities = Capabilities().new(neighbour('capability { software-version enable; }'), False)
    assert capabilities.announced(SOFTWARE_VERSION)


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-version-utf-8')
def test_the_value_is_the_version_string_with_no_length_octet() -> None:
    value = our_value()

    assert value == Software().software_version.encode('utf-8')
    assert value.startswith(b'ExaBGP/'), f'the value starts with {value[:1]!r}, not the product name'


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-length-greater-than-zero')
def test_we_never_send_an_empty_value() -> None:
    assert len(our_value()) > 0


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-length-no-greater-than-64')
def test_a_long_version_is_cut_to_64_octets_on_a_character_boundary() -> None:
    software = Software()
    software.software_version = 'é' * 40

    (value,) = software.extract_capability_bytes()

    assert len(value) <= Software.SOFTWARE_VERSION_MAX_LEN
    assert value.decode('utf-8') == 'é' * 32


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-identifier-limited')
@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-no-advertising-in-identifier')
@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-product-version-is-a-version')
def test_our_identifier_is_the_product_and_its_version_alone() -> None:
    assert Software().software_version == f'ExaBGP/{version}'


# ==============================================================================
# What we receive
# ==============================================================================


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-version-utf-8')
def test_the_current_encoding_is_read_whole() -> None:
    assert version_of(received(FRR_VERSION)) == FRR_VERSION.decode()


def test_the_encoding_of_revision_00_is_still_read() -> None:
    """A length octet which accounts for the rest of the value is the old layout.

    ExaBGP up to this one, and FRR with `software-version old`, send it.
    """
    assert version_of(received(bytes([len(FRR_VERSION)]) + FRR_VERSION)) == FRR_VERSION.decode()


def test_a_version_whose_first_character_is_not_its_length_is_not_cut() -> None:
    """The first octet of 'FRRouting/10.2.1' is 0x46, which was taken as a length of 70."""
    assert FRR_VERSION[0] != len(FRR_VERSION) - 1
    assert version_of(received(FRR_VERSION)) == FRR_VERSION.decode()


def test_what_we_send_is_what_we_read() -> None:
    assert version_of(received(our_value())) == Software().software_version


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-length-greater-than-zero', polarity='negative')
def test_a_zero_length_capability_is_ignored_not_refused() -> None:
    capabilities = received(b'')

    assert version_of(capabilities) is None
    assert capabilities[SOFTWARE_VERSION].extract_capability_bytes() == []


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3-version-utf-8', polarity='negative')
@pytest.mark.parametrize('value', [b'\xff\xfe\xfd\xfc', b'\x04\xff\xfe\xfd\xfc', b'FRR/\xc3'])
def test_invalid_utf_8_is_not_interpreted(value: bytes) -> None:
    capabilities = received(value)

    assert version_of(capabilities) is None
    assert 'software' not in capabilities[SOFTWARE_VERSION].json()


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#3.1-extended-optional-parameters')
def test_the_capability_is_read_from_extended_optional_parameters() -> None:
    """RFC 9072 Figure 1 and 2: type 255 after the length octet, then two octet lengths."""
    tlv = bytes([int(SOFTWARE_VERSION), len(FRR_VERSION)]) + FRR_VERSION
    parameter = bytes([int(Parameter.CAPABILITIES)]) + pack('!H', len(tlv)) + tlv
    parameters = bytes([EXTENDED, EXTENDED]) + pack('!H', len(parameter)) + parameter

    assert version_of(Capabilities.unpack(parameters)) == FRR_VERSION.decode()


@pytest.mark.rfc('draft-abraitis-bgp-version-capability-18#4-only-for-display')
def test_the_version_is_only_displayed() -> None:
    """Nothing reads the decoded version but its str() and json(): no negotiation does."""
    capability = received(FRR_VERSION)[SOFTWARE_VERSION]

    assert FRR_VERSION.decode() in str(capability)
    assert FRR_VERSION.decode() in capability.json()
