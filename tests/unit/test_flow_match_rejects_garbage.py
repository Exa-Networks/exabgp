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

A second round closed the same bug class one level down: make_prefix4()/make_prefix6()
pack whatever netmask (and, for IPv6, offset) they are given into a wire byte without
checking it, so `source 10.0.0.0/99` or `source 2001:db8::/32/200` used to reach the
wire as a malformed FlowSpec prefix length or offset instead of failing at
configuration time. netmask is now bounded to 0-32 (IPv4) / 0-128 (IPv6). The IPv6
offset is bounded to 0..netmask: RFC 8956 encodes (netmask - offset) significant bits
following the offset, so an offset past the netmask leaves nothing for it to offset
into. make_prefix6() itself imposes no bound (offset is opaque pass-through data,
only later squeezed into a single wire byte by pack()), so this is a policy choice
made for this task rather than a boundary read verbatim off the RFC text -- offset
equal to the netmask (zero significant bits remaining) is accepted as the more
permissive reading, consistent with the bound specified for this fix.
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
    with pytest.raises(ValueError, match=r'10\.0\.0\.256'):
        list(source(tokeniser_for('10.0.0.256/24')))


def test_destination_rejects_out_of_range_octet() -> None:
    with pytest.raises(ValueError, match=r'10\.0\.0\.256'):
        list(destination(tokeniser_for('10.0.0.256/24')))


# -- out-of-range netmask/offset: same bug class, worse consequence ----------
# make_prefix4()/make_prefix6() pack the mask (and IPv6 offset) into a wire byte
# without checking it, so these used to reach the wire as a malformed FlowSpec
# prefix length/offset -- or, for a negative netmask, raise only by accident via
# the octet-range check -- instead of failing here with the token named.

OUT_OF_RANGE_CASES = [
    ('10.0.0.0/33', r'netmask 33'),  # IPv4 mask above the 0-32 range
    ('10.0.0.0/-1', r'netmask -1'),  # negative mask -- must not rely on the
    #                                   octet-range check catching this by accident
    ('2001:db8::/129', r'netmask 129'),  # IPv6 mask above the 0-128 range
    ('2001:db8::/-1', r'netmask -1'),  # negative IPv6 mask
    ('2001:db8::/32/33', r'offset 33'),  # offset beyond its own netmask
    ('2001:db8::/32/-1', r'offset -1'),  # negative offset
]


@pytest.mark.parametrize('token, expected', OUT_OF_RANGE_CASES, ids=[c[0] for c in OUT_OF_RANGE_CASES])
def test_source_rejects_out_of_range_netmask_or_offset(token: str, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        list(source(tokeniser_for(token)))


@pytest.mark.parametrize('token, expected', OUT_OF_RANGE_CASES, ids=[c[0] for c in OUT_OF_RANGE_CASES])
def test_destination_rejects_out_of_range_netmask_or_offset(token: str, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        list(destination(tokeniser_for(token)))


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
    """netmask 48 / offset 16: a legal pair (offset <= netmask), matching the
    example already established in test_flowspec.py's TestFlow6Components."""
    result = list(source(tokeniser_for('2001:db8::/48/16')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)
    assert result[0].offset == 16


def test_destination_accepts_valid_ipv6_with_offset() -> None:
    result = list(destination(tokeniser_for('2001:db8::/48/16')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)
    assert result[0].offset == 16


# -- negative space: the new range check's own boundaries --------------------
# The main risk of a range check is being one off at a boundary and silently
# breaking a real deployment, so every edge gets its own explicit test.


def test_source_accepts_ipv4_netmask_zero() -> None:
    result = list(source(tokeniser_for('10.0.0.0/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Source)


def test_destination_accepts_ipv4_netmask_zero() -> None:
    result = list(destination(tokeniser_for('10.0.0.0/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Destination)


def test_source_accepts_ipv4_netmask_max() -> None:
    result = list(source(tokeniser_for('10.0.0.0/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Source)


def test_destination_accepts_ipv4_netmask_max() -> None:
    result = list(destination(tokeniser_for('10.0.0.0/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow4Destination)


def test_source_accepts_ipv6_netmask_zero() -> None:
    result = list(source(tokeniser_for('2001:db8::/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)


def test_destination_accepts_ipv6_netmask_zero() -> None:
    result = list(destination(tokeniser_for('2001:db8::/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)


def test_source_accepts_ipv6_netmask_max() -> None:
    result = list(source(tokeniser_for('2001:db8::/128')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)


def test_destination_accepts_ipv6_netmask_max() -> None:
    result = list(destination(tokeniser_for('2001:db8::/128')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)


def test_source_accepts_ipv6_offset_zero() -> None:
    result = list(source(tokeniser_for('2001:db8::/32/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)
    assert result[0].offset == 0


def test_destination_accepts_ipv6_offset_zero() -> None:
    result = list(destination(tokeniser_for('2001:db8::/32/0')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)
    assert result[0].offset == 0


def test_source_accepts_ipv6_offset_equal_to_netmask() -> None:
    """offset == netmask is the other boundary of the accepted range: zero
    significant bits are left to encode. The 0 <= offset <= netmask bound this
    fix enforces is a policy choice for this task (make_prefix6() itself imposes
    no bound), and it deliberately includes this edge rather than excluding it,
    so the boundary needs its own test rather than being inferred."""
    result = list(source(tokeniser_for('2001:db8::/32/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Source)
    assert result[0].offset == 32


def test_destination_accepts_ipv6_offset_equal_to_netmask() -> None:
    result = list(destination(tokeniser_for('2001:db8::/32/32')))
    assert len(result) == 1
    assert isinstance(result[0], Flow6Destination)
    assert result[0].offset == 32
