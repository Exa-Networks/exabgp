"""RFC 5668, the four octet AS specific extended community.

The document is three pages and contains exactly one RFC 2119 sentence, the SHOULD in
section 3 asking a speaker whose AS fits two octets to use the two octet community rather
than this one.  `qa/rfc/rfc5668.toml` records it and `test_a_two_octet_as_uses_the_two_octet_community`
below proves it.

The two facts exabgp is actually built on carry no keyword, exactly as RFC 4360 section 2
states the eight octet encoding:

    section 2  "The value of the high-order octet of this extended type is either
               0x02 (for transitive communities) or 0x42 (for non-transitive
               communities)."
    section 4  four-octet AS specific Route Target 0x0202
               four-octet AS specific Route Origin 0x0203

So the tests for those are ordinary regression tests with no marker, held here because
this is where a reader looking for RFC 5668 coverage will come.  They exist because
getting the type octet wrong is not a decode failure anybody notices: `origin:70500:5000`
went out for years as type 0x01, the IPv4 address specific form, which put the AS on the
wire as the address 0.1.19.100 and read back as one.  A peer accepts that happily and
treats it as a different community.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.static.parser import _extended_community

# RFC 5668 section 2 and section 4
FOUR_OCTET_AS_TRANSITIVE = 0x02
ROUTE_TARGET = 0x02
ROUTE_ORIGIN = 0x03

# RFC 4360 section 3.1 and its IANA section, for the contrast
TWO_OCTET_AS_TRANSITIVE = 0x00
IPV4_ADDRESS_TRANSITIVE = 0x01

# the largest AS which fits the two octet Global Administrator sub-field
MAX_TWO_OCTET_AS = 0xFFFF


def packed(community: str) -> bytes:
    return bytes(_extended_community(community).pack())


def kind(community: str) -> tuple[int, int]:
    """The two octet Type field: high-order octet, then sub-type."""
    raw = packed(community)
    assert len(raw) == 8, 'an extended community is eight octets'
    return raw[0], raw[1]


@pytest.mark.rfc('rfc5668#3-two-octet-as-uses-two-octet-community')
def test_a_two_octet_as_uses_the_two_octet_community():
    assert kind('target:100:1000') == (TWO_OCTET_AS_TRANSITIVE, ROUTE_TARGET)
    assert kind('origin:100:1000') == (TWO_OCTET_AS_TRANSITIVE, ROUTE_ORIGIN)


@pytest.mark.rfc('rfc5668#3-two-octet-as-uses-two-octet-community')
def test_the_largest_two_octet_as_still_uses_the_two_octet_community():
    # the boundary, because a > against the wrong constant is the usual way this slips
    assert kind(f'target:{MAX_TWO_OCTET_AS}:1000') == (TWO_OCTET_AS_TRANSITIVE, ROUTE_TARGET)


def test_an_as_too_large_for_two_octets_uses_the_four_octet_community():
    # section 2: high-order octet 0x02.  This went out as 0x01 before, which is the
    # IPv4 address specific form, so 70500 appeared on the wire as 0.1.19.100
    assert kind(f'target:{MAX_TWO_OCTET_AS + 1}:1000') == (FOUR_OCTET_AS_TRANSITIVE, ROUTE_TARGET)
    assert kind('origin:70500:5000') == (FOUR_OCTET_AS_TRANSITIVE, ROUTE_ORIGIN)


def test_the_four_octet_as_is_carried_in_the_global_administrator_sub_field():
    # section 2: Global Administrator sub-field 4 octets, Local Administrator 2
    raw = packed('origin:70500:5000')

    assert raw[2:6] == (70500).to_bytes(4, 'big')
    assert raw[6:8] == (5000).to_bytes(2, 'big')


def test_the_assigned_type_values_are_used():
    # section 4 assigns 0x0202 to Route Target and 0x0203 to Route Origin
    assert packed('target-as4:70500:5000')[0:2] == bytes([0x02, 0x02])
    assert packed('origin-as4:70500:5000')[0:2] == bytes([0x02, 0x03])


def test_a_dotted_global_administrator_stays_the_ipv4_form():
    """RFC 4360 section 3.2, kept here because this is the case 0x02 is confused with."""
    assert kind('target:7.7.7.7:7000') == (IPV4_ADDRESS_TRANSITIVE, ROUTE_TARGET)
    assert kind('origin4:7.7.7.7:7000') == (IPV4_ADDRESS_TRANSITIVE, ROUTE_ORIGIN)


def test_an_operator_may_name_the_four_octet_form_for_a_small_as():
    """The note in the ledger: a request exabgp honours rather than rewrites."""
    assert kind('target-as4:100:1000') == (FOUR_OCTET_AS_TRANSITIVE, ROUTE_TARGET)


def test_a_trailing_l_names_the_four_octet_form():
    assert kind('target:100L:1000') == (FOUR_OCTET_AS_TRANSITIVE, ROUTE_TARGET)
