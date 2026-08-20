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
