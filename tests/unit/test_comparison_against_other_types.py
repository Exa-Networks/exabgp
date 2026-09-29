"""Comparing an NLRI or an attribute with something of another type.

Two defects, both from comparison methods typed `other: Any`:

- `IPVPN.__ne__` and the four MUP routes returned `not self.__eq__(other)`.  When __eq__
  answers NotImplemented, that is `not NotImplemented`: a DeprecationWarning since 3.9 and a
  TypeError from 3.14, so `vpn_route != None` stops working on the next Python.
- `Attribute.__lt__` and the other orderings read `other.ID` unchecked, so ordering an
  attribute against anything else raised AttributeError instead of TypeError.
"""

from __future__ import annotations

import operator
import warnings
from collections.abc import Callable

import pytest

from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.mup.dsd import DirectSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


def _vpn() -> IPVPN:
    return IPVPN.from_cidr(
        CIDR.create_cidr(bytes([10, 0, 0, 1]), 32),
        AFI.ipv4,
        SAFI.mpls_vpn,
        labels=Labels.make_labels([100]),
        rd=RouteDistinguisher.make_from_elements('65000', 1),
    )


def _dsd() -> DirectSegmentDiscoveryRoute:
    rd = RouteDistinguisher.make_from_elements('1.2.3.4', 100)
    return DirectSegmentDiscoveryRoute.make_dsd(rd, IP.from_string('10.0.0.1'), AFI.ipv4)


@pytest.mark.parametrize('make', [_vpn, _dsd])
@pytest.mark.parametrize('other', [None, 1, 'route'])
def test_an_nlri_is_unequal_to_another_type_without_a_warning(make: Callable[[], object], other: object) -> None:
    nlri = make()
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert nlri != other
        assert not (nlri == other)


@pytest.mark.parametrize('make', [_vpn, _dsd])
def test_an_nlri_still_compares_with_its_own_kind(make: Callable[[], object]) -> None:
    assert make() == make()
    assert not (make() != make())


def test_an_attribute_cannot_be_ordered_against_another_type() -> None:
    with pytest.raises(TypeError):
        operator.lt(Origin.from_int(0), None)


def test_attributes_still_order_by_code() -> None:
    assert Origin.from_int(0) <= Origin.from_int(1)
    assert not (Origin.from_int(0) < Origin.from_int(1))
