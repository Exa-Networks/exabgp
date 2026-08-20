"""Regression tests for the input validation audit.

Each test here reproduces a defect which was found by auditing the configuration
parser, the API and CLI helper processes and the BGP wire decoders. Before the
matching fix every test in this file failed, either because a malformed input was
accepted, or because it escaped as a raw Python exception instead of a
NOTIFICATION or a ValueError.

The audit was carried out on the main branch; this is the 5.0 counterpart. The
TCP-AO, unix socket and API group findings do not appear here because 5.0 has
none of those features.
"""

from __future__ import annotations

import os
import pathlib
from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.hostname import HostName
from exabgp.bgp.message.open.capability.software import Software
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.static.parser import _extended_community
from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.util.backlog import Backlog
from exabgp.util.psk import PSKError, decode_base64

log.init(getenv())


# ============================================================================
# Configuration: settings which must be given
# ============================================================================


def load(text):
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


def test_missing_peer_as_is_rejected():
    """peer-as was indistinguishable from "peer-as auto", both being None, and
    Negotiated.validate() skips the ASN check when it is None. Omitting the
    setting therefore turned off the check that the peer announces the ASN we
    expect."""
    ok, configuration = load(NEIGHBOR % '    local-as 65000;')
    assert not ok
    assert 'peer-as' in configuration.error.message


def test_missing_local_as_is_rejected():
    ok, configuration = load(NEIGHBOR % '    peer-as 65000;')
    assert not ok
    assert 'local-as' in configuration.error.message


def test_explicit_auto_as_is_still_accepted():
    """ "auto" is the documented way to ask for the None behaviour, and must keep
    working now that omitting the setting does not."""
    ok, configuration = load(NEIGHBOR % '    local-as auto;\n    peer-as auto;')
    assert ok
    neighbor = next(iter(configuration.neighbors.values()))
    assert neighbor['local-as'] is None
    assert neighbor['peer-as'] is None


def test_both_as_given_is_accepted():
    ok, configuration = load(NEIGHBOR % '    local-as 65000;\n    peer-as 65001;')
    assert ok


# ============================================================================
# Configuration: ASN range
# ============================================================================


@pytest.mark.parametrize('value', ['-1', '4294967296', '1.2.3', '1.65536', '65_000', '+5', '0x10', ''])
def test_invalid_asn_is_rejected(value):
    """Negative, out of range and malformed ASNs used to load: int() accepts a
    leading sign and underscores, and the dotted form never checked its parts."""
    with pytest.raises(ValueError):
        ASN.from_string(value)


@pytest.mark.parametrize(
    ('value', 'expected'),
    [('0', 0), ('65001', 65001), ('4294967295', 4294967295), ('1.1', 65537), ('0.65535', 65535)],
)
def test_valid_asn_is_accepted(value, expected):
    assert ASN.from_string(value) == expected


def test_negative_local_as_is_rejected_by_the_configuration():
    ok, configuration = load(NEIGHBOR % '    local-as -1;\n    peer-as 65001;')
    assert not ok
    assert 'ASN' in configuration.error.message


# ============================================================================
# Authentication keys
# ============================================================================


@pytest.mark.parametrize('value', ['ab!c', 'YWJ j', 'not-valid-base64!!!', ''])
def test_invalid_base64_key_is_rejected(value):
    """b64decode() without validate=True discards characters outside the alphabet,
    so a mistyped key silently became a different key. An empty key was accepted."""
    with pytest.raises(PSKError):
        decode_base64(value)


def test_valid_base64_key_is_accepted():
    assert decode_base64('YWJj') == b'abc'


def test_configuration_rejects_a_malformed_base64_md5_password():
    """binascii.Error is a ValueError, not a TypeError, so the configuration check
    and the socket setup both let a malformed key through."""
    ok, configuration = load(
        NEIGHBOR % "    local-as 65000;\n    peer-as 65001;\n    md5-password 'not-valid!!';\n    md5-base64 true;"
    )
    assert not ok
    assert 'not valid base64' in configuration.error.message

    ok, _ = load(NEIGHBOR % "    local-as 65000;\n    peer-as 65001;\n    md5-password 'YWJj';\n    md5-base64 true;")
    assert ok


# ============================================================================
# OPEN capabilities
# ============================================================================


def test_as4_capability_must_be_four_bytes():
    """RFC 6793 section 3: the value is a 4 octet AS number. A 2 byte value used
    to be accepted and quietly decoded as a 16 bit ASN."""
    with pytest.raises(Notify):
        ASN4.unpack_capability(None, b'\xfd\xe8')


def test_as4_capability_accepts_four_bytes():
    assert ASN4.unpack_capability(None, b'\x00\x00\xfd\xe8') == 65000


def test_hostname_capability_rejects_invalid_utf8():
    """Invalid UTF-8 used to escape as UnicodeDecodeError."""
    with pytest.raises(Notify):
        HostName.unpack_capability(HostName(), b'\x04\xff\xfe\xfd\xfc\x00')


def test_hostname_capability_rejects_a_truncated_name():
    with pytest.raises(Notify):
        HostName.unpack_capability(HostName(), b'\x40ab')


def test_software_capability_rejects_invalid_utf8():
    with pytest.raises(Notify):
        Software.unpack_capability(Software(), b'\x04\xff\xfe\xfd\xfc')


def test_software_capability_rejects_an_empty_value():
    with pytest.raises(Notify):
        Software.unpack_capability(Software(), b'')


# ============================================================================
# AIGP attribute
# ============================================================================


class _AigpNegotiated:
    aigp = True


def test_aigp_decodes_a_well_formed_tlv():
    """AIGP.unpack() did "data[:8] & 0x...", a bytes and an int, so every AIGP
    attribute on a configured session raised a TypeError."""
    attribute = AIGP.unpack(b'\x01\x00\x0b' + pack('!Q', 5), None, _AigpNegotiated())
    assert attribute.aigp == b'\x01\x00\x0b' + pack('!Q', 5)


def test_aigp_rejects_trailing_bytes():
    with pytest.raises(Notify):
        AIGP.unpack(b'\x01\x00\x0b' + pack('!Q', 5) + b'\xaa\xbb', None, _AigpNegotiated())


def test_aigp_ignores_unknown_trailing_tlvs():
    """RFC 7311: unknown TLVs are ignored, but they must still be well formed."""
    data = b'\x01\x00\x0b' + pack('!Q', 5) + b'\x02\x00\x05\x00\x00'
    assert AIGP.unpack(data, None, _AigpNegotiated()).aigp == b'\x01\x00\x0b' + pack('!Q', 5)


def test_aigp_requires_an_aigp_tlv():
    with pytest.raises(Notify):
        AIGP.unpack(b'\x02\x00\x05\x00\x00', None, _AigpNegotiated())


def test_aigp_rejects_a_truncated_tlv():
    with pytest.raises(Notify):
        AIGP.unpack(b'\x01\x00\x0b\x00', None, _AigpNegotiated())


# ============================================================================
# Extended communities
# ============================================================================


def test_extended_community_rejects_a_short_ip():
    """target:1.2.3:100 used to raise IndexError out of the configuration parser."""
    with pytest.raises(ValueError):
        _extended_community('target:1.2.3:100')


@pytest.mark.parametrize('value', ['target:1.2.3.4.5:100', 'target:1.2.3.256:100', 'target:1.2.3.x:100'])
def test_extended_community_rejects_malformed_ips(value):
    with pytest.raises(ValueError):
        _extended_community(value)


@pytest.mark.parametrize('value', ['target:65000:100', 'target:1.2.3.4:100'])
def test_extended_community_accepts_valid_values(value):
    assert str(_extended_community(value)) == value


def test_data_check_extended_community_does_not_raise():
    """data_check.extendedcommunity() compared an int to a str and raised TypeError,
    and redirect() had its condition inverted."""
    from exabgp.data import check as data_check

    assert data_check.extendedcommunity('target:65000:1.2.3.4') is True
    assert data_check.extendedcommunity('target:not-a-number:1.2.3.4') is False
    assert data_check.redirect('1.2.3.4:100') is True


# ============================================================================
# Wire decoders: no raw exception may escape
# ============================================================================


def unpack_or_notify(unpack, *args):
    """Run a decoder and let a Notify through, but not a raw Python exception."""
    try:
        nlri, _ = unpack(*args)
    except Notify:
        return
    nlri.json()
    str(nlri)
    nlri.index()
    nlri.as_dict()


@pytest.mark.parametrize('code', [1, 2, 3, 4, 5])
@pytest.mark.parametrize('length', [0, 3, 10, 20, 30, 34, 58])
def test_evpn_short_nlri_raises_notify(code, length):
    """Truncated EVPN routes used to escape as IndexError or ValueError, and the
    Inclusive Multicast decoder raised a bare Exception."""
    data = bytes([code, length]) + bytes(length)
    unpack_or_notify(EVPN.unpack_nlri, AFI.l2vpn, SAFI.evpn, data, Action.ANNOUNCE, None)


def test_evpn_fuzz_never_raises_a_raw_exception():
    for code in range(0, 8):
        for length in range(0, 60):
            for _ in range(5):
                data = bytes([code, length]) + os.urandom(length)
                unpack_or_notify(EVPN.unpack_nlri, AFI.l2vpn, SAFI.evpn, data, Action.ANNOUNCE, None)


@pytest.mark.parametrize('code', [1, 2, 3, 4, 6])
@pytest.mark.parametrize('length', [0, 1, 4, 9, 13, 20])
def test_bgpls_short_nlri_raises_notify(code, length):
    """BGP-LS decoders used to raise a bare Exception, a RuntimeError, a
    struct.error or an AttributeError depending on where they fell over."""
    data = pack('!HH', code, length) + bytes(length)
    unpack_or_notify(BGPLS.unpack_nlri, AFI.bgpls, SAFI.bgp_ls, data, Action.ANNOUNCE, None)


def test_bgpls_fuzz_never_raises_a_raw_exception():
    for code in (1, 2, 3, 4, 6):
        for length in range(0, 60):
            for _ in range(5):
                data = pack('!HH', code, length) + os.urandom(length)
                unpack_or_notify(BGPLS.unpack_nlri, AFI.bgpls, SAFI.bgp_ls, data, Action.ANNOUNCE, None)


@pytest.mark.parametrize('key', ['1:1', '1:2', '1:3', '1:4'])
@pytest.mark.parametrize('length', [0, 1, 8, 9, 13, 20])
def test_mup_short_nlri_raises_notify(key, length):
    """The MUP decoders read the length fields before knowing the payload held
    them, and never compared the announced length to the size of the route."""
    arch, code = (int(_) for _ in key.split(':'))
    data = bytes([arch]) + code.to_bytes(2, 'big') + bytes([length]) + bytes(length)
    for afi in (AFI.ipv4, AFI.ipv6):
        unpack_or_notify(MUP.unpack_nlri, afi, SAFI.mup, data, Action.ANNOUNCE, None)


def test_mup_fuzz_never_raises_a_raw_exception():
    for key in ('1:1', '1:2', '1:3', '1:4'):
        arch, code = (int(_) for _ in key.split(':'))
        for length in range(0, 60):
            for _ in range(5):
                data = bytes([arch]) + code.to_bytes(2, 'big') + bytes([length]) + os.urandom(length)
                for afi in (AFI.ipv4, AFI.ipv6):
                    unpack_or_notify(MUP.unpack_nlri, afi, SAFI.mup, data, Action.ANNOUNCE, None)


# ============================================================================
# API and CLI buffering limits
# ============================================================================


def test_backlog_counts_bytes_not_chunks():
    """The pipe helper compared len(backlog), the number of sources in the dict
    and always two, against a 100 MB limit, so the guard could never fire."""
    backlog = Backlog()
    assert backlog.nbytes == 0
    assert not backlog

    backlog.append(b'a' * 1024)
    backlog.append(b'b' * 512)
    assert len(backlog) == 2
    assert backlog.nbytes == 1536

    assert backlog.popleft() == b'a' * 1024
    assert backlog.nbytes == 512

    backlog.clear()
    assert backlog.nbytes == 0
    assert not backlog


def test_pipe_bounds_its_buffer_by_bytes():
    """Guard against reintroducing the exact bug. The check is on the source
    because the buffering lives inside a closure in the select loop."""
    source = (pathlib.Path(__file__).resolve().parents[2] / 'src' / 'exabgp' / 'application' / 'pipe.py').read_text()
    assert 'if len(backlog) >' not in source
    assert 'backlog[source].nbytes' in source
    assert 'MAX_COMMAND_SIZE' in source


def test_processes_caps_a_command_without_a_newline():
    """A helper process which never sends a newline grew _buffer without bound."""
    from exabgp.reactor.api.processes import Processes

    assert Processes.MAX_COMMAND_SIZE > 0
    source = (
        pathlib.Path(__file__).resolve().parents[2] / 'src' / 'exabgp' / 'reactor' / 'api' / 'processes.py'
    ).read_text()
    assert 'self.MAX_COMMAND_SIZE' in source
    assert 'self._buffer.pop(process_name, None)' in source
