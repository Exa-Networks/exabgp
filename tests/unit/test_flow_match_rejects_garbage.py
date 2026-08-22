"""A flow source/destination the parser cannot read was silently dropped.

source() and destination() in exabgp.configuration.flow.parser are generators with
three if/elif branches: IPv4, IPv6, IPv6-with-offset. A value matching none of them
(or matching a branch but failing the int()/IP.pton conversion inside it) used to
yield nothing and raise nothing. The caller, configuration/flow/__init__.py route(),
does `for adding in handler(tokeniser): flow_nlri.add(adding)` -- an empty generator
never adds a component, so `source not-an-ip;` parsed successfully into a FlowSpec
rule with the source match silently dropped. Per RFC 5575 a rule with no match
components matches ALL traffic, so a mitigation rule silently became a much broader
one: `flow { route x { source not-an-ip; then discard; } }` produced a zero-length
NLRI (a discard-everything rule) instead of a configuration error.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.core.parser import Tokeniser
from exabgp.configuration.flow.parser import destination, source
from exabgp.bgp.message.update.nlri.flow import (
    Flow4Destination,
    Flow4Source,
    Flow6Destination,
    Flow6Source,
)


def tokeniser_for(token: str) -> Tokeniser:
    return Tokeniser().replenish([token])


# -- garbage that matches none of the three branches -------------------------


def test_source_rejects_unrecognised_token() -> None:
    with pytest.raises(ValueError, match='not-an-ip'):
        list(source(tokeniser_for('not-an-ip')))


def test_destination_rejects_unrecognised_token() -> None:
    with pytest.raises(ValueError, match='not-an-ip'):
        list(destination(tokeniser_for('not-an-ip')))


def test_source_rejects_ipv4_missing_mask() -> None:
    """Two dots and no colon looks IPv4-shaped but has no '/', so no branch matches."""
    with pytest.raises(ValueError, match=r'10\.0\.0'):
        list(source(tokeniser_for('10.0.0/24')))


def test_destination_rejects_ipv4_missing_mask() -> None:
    with pytest.raises(ValueError, match=r'10\.0\.0'):
        list(destination(tokeniser_for('10.0.0/24')))


# -- garbage that matches a branch but fails the conversion inside it --------


def test_source_rejects_out_of_range_octet() -> None:
    with pytest.raises(ValueError, match='10.0.0.256'):
        list(source(tokeniser_for('10.0.0.256/24')))


def test_destination_rejects_out_of_range_octet() -> None:
    with pytest.raises(ValueError, match='10.0.0.256'):
        list(destination(tokeniser_for('10.0.0.256/24')))


# -- negative space: a fix that rejects everything must not pass -------------


def test_source_accepts_valid_ipv4() -> None:
    result = list(source(tokeniser_for('10.0.0.0/24')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Source)


def test_destination_accepts_valid_ipv4() -> None:
    result = list(destination(tokeniser_for('10.0.0.0/24')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Destination)


def test_source_accepts_valid_ipv6() -> None:
    result = list(source(tokeniser_for('2001:db8::/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)


def test_destination_accepts_valid_ipv6() -> None:
    result = list(destination(tokeniser_for('2001:db8::/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)


def test_source_accepts_valid_ipv6_with_offset() -> None:
    result = list(source(tokeniser_for('2001:db8::/32/64')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)


def test_destination_accepts_valid_ipv6_with_offset() -> None:
    result = list(destination(tokeniser_for('2001:db8::/32/64')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)
