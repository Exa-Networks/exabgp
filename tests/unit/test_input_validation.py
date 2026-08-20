"""Regression tests for the input validation audit.

Each test here reproduces a defect which was found by auditing the configuration
parser, the API and CLI helper processes and the BGP wire decoders. Before the
matching fix every test in this file failed, either because a malformed input was
accepted, or because it escaped as a raw Python exception instead of a
NOTIFICATION or a ValueError.
"""

from __future__ import annotations

import platform
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.hostname import HostName
from exabgp.bgp.message.open.capability.software import Software
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.static.parser import _extended_community
from exabgp.util.psk import PSKError, decode_base64


# ============================================================================
# Configuration: mandatory schema fields
# ============================================================================


def load(text: str) -> tuple[bool, Configuration]:
    """Load a configuration from text, returning the outcome and the parser."""
    configuration = Configuration([text], text=True)
    return configuration.reload(), configuration


NEIGHBOR = """
neighbor 10.0.0.1 {
    router-id 1.2.3.4;
    local-address 10.0.0.2;
%s
}
"""


def test_missing_peer_as_is_rejected() -> None:
    """peer-as is mandatory: leaving it out used to load as ASN(0), which means
    "accept any peer ASN" and silently disabled the ASN check in negotiation."""
    ok, configuration = load(NEIGHBOR % '    local-as 65000;')
    assert not ok
    assert 'peer-as' in configuration.error.message


def test_missing_local_as_is_rejected() -> None:
    ok, configuration = load(NEIGHBOR % '    peer-as 65000;')
    assert not ok
    assert 'local-as' in configuration.error.message


def test_explicit_auto_as_is_still_accepted() -> None:
    """ "auto" is the documented way to ask for the ASN(0) behaviour, and must
    keep working now that omitting the leaf does not."""
    ok, configuration = load(NEIGHBOR % '    local-as auto;\n    peer-as auto;')
    assert ok
    neighbor = next(iter(configuration.neighbors.values()))
    assert neighbor.session.local_as == ASN(0)
    assert neighbor.session.peer_as == ASN(0)


def test_incomplete_tcp_ao_is_rejected() -> None:
    """A tcp-ao block without a password used to load and leave the session with
    no TCP-AO at all, silently unauthenticated."""
    ok, configuration = load(
        NEIGHBOR
        % '    local-as 65000;\n    peer-as 65001;\n    tcp-ao {\n        keyid 1;\n        algorithm hmac-sha-256;\n    }',
    )
    assert not ok
    assert 'password' in configuration.error.message


def test_complete_tcp_ao_is_accepted() -> None:
    ok, configuration = load(
        NEIGHBOR
        % '    local-as 65000;\n    peer-as 65001;\n    tcp-ao {\n        keyid 1;\n        algorithm hmac-sha-256;\n        password secret;\n    }',
    )
    assert ok


# ============================================================================
# Configuration: ASN range
# ============================================================================


@pytest.mark.parametrize('value', ['-1', '4294967296', '1.2.3', '1.65536', '65_000', '+5', '0x10', ''])
def test_invalid_asn_is_rejected(value: str) -> None:
    """Negative, out of range and malformed ASNs used to load: int() accepts a
    leading sign and underscores, and the dotted form never checked its parts."""
    with pytest.raises(ValueError):
        ASN.from_string(value)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [('0', 0), ('65001', 65001), ('4294967295', 4294967295), ('1.1', 65537), ('0.65535', 65535)],
)
def test_valid_asn_is_accepted(value: str, expected: int) -> None:
    assert ASN.from_string(value) == expected


def test_negative_local_as_is_rejected_by_the_configuration() -> None:
    ok, configuration = load(NEIGHBOR % '    local-as -1;\n    peer-as 65001;')
    assert not ok
    assert 'ASN' in configuration.error.message


# ============================================================================
# Authentication keys
# ============================================================================


@pytest.mark.parametrize('value', ['ab!c', 'YWJ j', 'not-valid-base64!!!', ''])
def test_invalid_base64_key_is_rejected(value: str) -> None:
    """b64decode() without validate=True discards characters outside the alphabet,
    so a mistyped key silently became a different key. An empty key was accepted."""
    with pytest.raises(PSKError):
        decode_base64(value)


def test_valid_base64_key_is_accepted() -> None:
    assert decode_base64('YWJj') == b'abc'


def test_session_rejects_a_malformed_base64_md5_password() -> None:
    """binascii.Error is a ValueError, not a TypeError: the runtime path in tcp.py
    only caught TypeError, so a bad key escaped instead of raising MD5Error."""
    from exabgp.bgp.neighbor.session import Session

    assert Session(md5_password='', md5_base64=True).validate_md5() == ''
    assert 'not valid base64' in Session(md5_password='====', md5_base64=True).validate_md5()
    assert 'not valid base64' in Session(md5_password='not-valid!!', md5_base64=True).validate_md5()
    assert Session(md5_password='YWJj', md5_base64=True).validate_md5() == ''


@pytest.mark.skipif(platform.system() != 'Linux', reason='TCP_MD5SIG is only set on Linux')
def test_tcp_md5_runtime_rejects_a_malformed_base64_key() -> None:
    import socket

    from exabgp.reactor.network.error import MD5Error
    from exabgp.reactor.network.tcp import md5

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(MD5Error):
            md5(sock, '127.0.0.1', 179, 'not-valid!!', True)


# ============================================================================
# OPEN capabilities
# ============================================================================


def test_as4_capability_must_be_four_bytes() -> None:
    """RFC 6793 section 3: the value is a 4 octet AS number. A 2 byte value used
    to be accepted and quietly decoded as a 16 bit ASN."""
    with pytest.raises(Notify):
        ASN4.unpack_capability(None, b'\xfd\xe8', None)


def test_as4_capability_accepts_four_bytes() -> None:
    assert ASN4.unpack_capability(None, b'\x00\x00\xfd\xe8', None) == 65000


def test_hostname_capability_rejects_invalid_utf8() -> None:
    """Invalid UTF-8 used to escape as UnicodeDecodeError."""
    with pytest.raises(Notify):
        HostName.unpack_capability(HostName(), b'\x04\xff\xfe\xfd\xfc\x00', None)


def test_software_capability_rejects_invalid_utf8() -> None:
    with pytest.raises(Notify):
        Software.unpack_capability(Software(), b'\x04\xff\xfe\xfd\xfc', None)


# ============================================================================
# AIGP attribute
# ============================================================================


def test_aigp_rejects_trailing_bytes() -> None:
    """13 bytes used to build an AIGP holding only the first 11: the trailing
    bytes were dropped and the attribute re-advertised as if well formed."""
    with pytest.raises(ValueError):
        AIGP.from_packet(b'\x01\x00\x0b' + pack('!Q', 5) + b'\xaa\xbb')


def test_aigp_accepts_an_exact_tlv() -> None:
    assert AIGP.from_packet(b'\x01\x00\x0b' + pack('!Q', 5)).aigp == 5


def test_aigp_ignores_unknown_trailing_tlvs() -> None:
    """RFC 7311: unknown TLVs are ignored, but they must still be well formed."""
    assert AIGP.from_packet(b'\x01\x00\x0b' + pack('!Q', 5) + b'\x02\x00\x05\x00\x00').aigp == 5


def test_aigp_requires_an_aigp_tlv() -> None:
    with pytest.raises(ValueError):
        AIGP.from_packet(b'\x02\x00\x05\x00\x00')


# ============================================================================
# Extended communities
# ============================================================================


def test_extended_community_rejects_a_short_ip() -> None:
    """target:1.2.3:100 used to raise IndexError out of the configuration parser."""
    with pytest.raises(ValueError):
        _extended_community('target:1.2.3:100')


@pytest.mark.parametrize('value', ['target:1.2.3.4.5:100', 'target:1.2.3.256:100', 'target:1.2.3.x:100'])
def test_extended_community_rejects_malformed_ips(value: str) -> None:
    with pytest.raises(ValueError):
        _extended_community(value)


@pytest.mark.parametrize('value', ['target:65000:100', 'target:1.2.3.4:100'])
def test_extended_community_accepts_valid_values(value: str) -> None:
    assert str(_extended_community(value)) == value


def test_data_check_extended_community_does_not_raise() -> None:
    """data_check.extendedcommunity() compared an int to a str and raised TypeError."""
    from exabgp.data import check as data_check

    assert data_check.extendedcommunity('target:65000:1.2.3.4') is True
    assert data_check.extendedcommunity('target:not-a-number:1.2.3.4') is False
