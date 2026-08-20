"""Regression tests for the input validation audit.

Each test here reproduces a defect which was found by auditing the configuration
parser, the API and CLI helper processes and the BGP wire decoders. Before the
matching fix every test in this file failed, either because a malformed input was
accepted, or because it escaped as a raw Python exception instead of a
NOTIFICATION or a ValueError.
"""

from __future__ import annotations

from exabgp.bgp.message.open.asn import ASN
from exabgp.configuration.configuration import Configuration


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
