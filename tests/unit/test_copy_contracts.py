#!/usr/bin/env python3
# encoding: utf-8

"""The copy hooks are part of the public surface, so hold them to their protocol

copy.copy(x) calls x.__copy__() with NO argument and copy.deepcopy(x) calls
x.__deepcopy__(memo) with one. A hook whose signature disagrees raises instead of
copying, and nothing notices until something copies that object.

_NoNextHop.__copy__ took an extra parameter and had never been called. It is not
reachable from src today, the only copy.copy() there is of a Neighbor, but it is
a dunder a library user can reach and the fix is a signature.

The RIB deep-copies a change on the withdraw path (rib/outgoing.py), so the
deepcopy half IS on the wire path and is not hypothetical.
"""

import copy

import pytest

from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.ip import NoNextHop


class TestTheSingletonStaysItself:
    """Two no-nexthops would compare unequal and break every `is NoNextHop`"""

    def test_deepcopy_returns_the_singleton(self) -> None:
        assert copy.deepcopy(NoNextHop) is NoNextHop

    def test_copy_returns_the_singleton(self) -> None:
        # this raised TypeError: __copy__() missing 1 required positional argument
        assert copy.copy(NoNextHop) is NoNextHop

    def test_deepcopy_inside_a_container_returns_the_singleton(self) -> None:
        # the shape the RIB actually produces: the nexthop is a field of a change
        holder = {'nexthop': NoNextHop, 'other': [NoNextHop]}
        copied = copy.deepcopy(holder)
        assert copied['nexthop'] is NoNextHop
        assert copied['other'][0] is NoNextHop


class TestTheRouteDistinguisherCopies:
    FILLED = RouteDistinguisher(b'\x00\x01\x02\x03\x04\x05\x06\x07')

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy])
    def test_a_real_rd_keeps_every_field(self, duplicate) -> None:
        # by value on the whole object, not by a proxy like index(): a copy which
        # drops a field still compares equal on anything the key does not include
        copied = duplicate(self.FILLED)
        assert copied == self.FILLED
        assert copied.rd == self.FILLED.rd
        assert str(copied) == str(self.FILLED)
        assert copied.json() == self.FILLED.json()

    @pytest.mark.parametrize('duplicate', [copy.copy, copy.deepcopy])
    def test_the_nord_singleton_stays_itself(self, duplicate) -> None:
        assert duplicate(RouteDistinguisher.NORD) is RouteDistinguisher.NORD

    def test_the_copy_is_a_distinct_object(self) -> None:
        assert copy.deepcopy(self.FILLED) is not self.FILLED

    def test_sharing_the_immutable_bytes_is_correct(self) -> None:
        # NOT an anti-sharing assertion: the packed bytes are immutable, sharing
        # them is what makes the copy cheap, and asserting nothing is shared
        # fails on classes which are right
        assert copy.deepcopy(self.FILLED).rd == self.FILLED.rd
