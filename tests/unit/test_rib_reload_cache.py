"""The RIB kept across a reload follows the new configuration, and a copy never clears it.

A reload hands a neighbour the tables RIB._cache kept under its name. The adj-rib-in and
adj-rib-out switches of the new configuration were applied to a new RIB only: the cached
tables kept the switches of the configuration they were first built for.

check_generation() validates a deep copy of each neighbour and calls clear() on it. clear()
rebuilt the tables of the cache entry under the copy's name, which is the original
neighbour's RIB, or raised KeyError when no RIB of that name was cached.
"""

from __future__ import annotations

from copy import deepcopy

from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPv4
from exabgp.rib import RIB
from exabgp.rib.route import Route

FAMILIES = {(AFI.ipv4, SAFI.unicast)}


def _route() -> Route:
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton('10.0.0.0'), 24), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes[Origin.ID] = Origin.from_int(Origin.IGP)
    return Route(nlri, attributes, nexthop=IPv4.from_string('192.0.2.1'))


def test_make_rib_on_reload_takes_the_new_cache_switches() -> None:
    RIB.make_rib('audit-reload-make', False, False, FAMILIES)
    rib = RIB.make_rib('audit-reload-make', True, True, FAMILIES)
    assert rib.incoming.cache is True
    assert rib.outgoing.cache is True


def test_enable_on_reload_takes_the_new_cache_switches() -> None:
    first = RIB.make_rib('disabled-audit-1', True, True, set(), enabled=False)
    first.enable('audit-reload-enable', False, False, FAMILIES)
    assert first.outgoing.cache is False
    second = RIB.make_rib('disabled-audit-2', True, True, set(), enabled=False)
    second.enable('audit-reload-enable', True, True, FAMILIES)
    assert second.incoming.cache is True
    assert second.outgoing.cache is True


def test_clearing_a_copy_leaves_the_original_routes() -> None:
    original = RIB.make_rib('audit-clear-copy', True, True, FAMILIES)
    original.outgoing.add_to_rib(_route())
    copied = deepcopy(original)
    copied.clear()
    assert list(copied.outgoing.cached_routes()) == []
    assert len(list(original.outgoing.cached_routes())) == 1
    assert len(list(RIB._cache['audit-clear-copy'].outgoing.cached_routes())) == 1


def test_clearing_a_rib_not_in_the_cache() -> None:
    original = RIB.make_rib('audit-not-cached', True, True, FAMILIES)
    copied = deepcopy(original)
    original.uncache()
    copied.outgoing.add_to_rib(_route())
    copied.clear()
    assert list(copied.outgoing.cached_routes()) == []
    assert copied.outgoing.membership is copied.incoming


def test_clearing_the_cached_rib_clears_what_a_reload_returns() -> None:
    RIB.make_rib('audit-clear-cached', True, True, FAMILIES)
    rib = RIB.make_rib('audit-clear-cached', True, True, FAMILIES)
    rib.outgoing.add_to_rib(_route())
    rib.clear()
    reloaded = RIB.make_rib('audit-clear-cached', True, True, FAMILIES)
    assert list(reloaded.outgoing.cached_routes()) == []
