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

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.configuration.configuration import Configuration
from exabgp.environment import getenv
from exabgp.logger import log

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
