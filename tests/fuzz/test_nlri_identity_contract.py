#!/usr/bin/env python3
# encoding: utf-8

"""What it means for two NLRIs to be the same route, held across every family

__eq__ and __hash__ are a pair over one identity, and Python requires that a == b
implies hash(a) == hash(b). Nothing in this tree asserted it, so nothing noticed
when the halves disagreed.

They disagreed here, and I caused it. Masking the reserved bits of a BGP-LS MT-ID
fixed __eq__, which compares the decoded value, and left __hash__ hashing
str(self), which renders the packed bytes. Before the mask both said "different",
wrongly but coherently; after it one said "same" and the other did not. A set
holding both kept two entries and a dict lookup could miss, which at this level
means the RIB holding one link under two keys.

The mutation that mattered: reverting the hash fix passed every test in the file
that fixed __eq__, because that file tested the half I had been thinking about.
This one tests the pair rather than either half, and it does it for every
registered family so that fixing one side of any of them is caught.

The third shape below states the consequence the way the RIB sees it, a set and a
dict lookup, rather than as two dunder methods. That is the version worth reading
in a failure message.

Found through the session working main, whose own version of this defect lost a
route distinguisher on copy, and who made the point that a seed set matters more
than the assertions: a plain BGP-LS route carries no route distinguisher, so it
copies correctly by having nothing to lose, and only a VPN seed can say whether
a populated one survives.
"""

import copy

from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

from .corpus import NLRI_SEEDS

# A BGP-LS VPN route: an eight byte route distinguisher, then the NLRI. The plain
# bgp-ls seed has no route distinguisher at all, so it cannot say whether one is
# carried through a copy: the field it would lose is empty.
BGPLS_LOCAL_NODE = pack('!HH', 256, 8) + pack('!HH', 512, 4) + b'\x00\x00\xff\xfd'
BGPLS_VPN_BODY = bytes([0, 1]) + bytes([10, 0, 0, 1]) + bytes([0, 7]) + b'\x03' + b'\x00' * 8 + BGPLS_LOCAL_NODE
EXTRA_SEEDS = {
    'bgp-ls/bgp-ls-vpn': [pack('!HH', 2, len(BGPLS_VPN_BODY)) + BGPLS_VPN_BODY],
}

# Ratchet. A sweep which decodes nothing satisfies every assertion below, so the
# number of families which actually yielded an NLRI is asserted too.
FAMILY_FLOOR = 14


def seeds(family):
    return list(NLRI_SEEDS.get(family, ())) + list(EXTRA_SEEDS.get(family, ()))


def decode(family, payload):
    afi_name, safi_name = family.split('/')
    klass = NLRI.registered_nlri.get(family)
    if klass is None:
        return None
    try:
        result = klass.unpack_nlri(AFI.value(afi_name), SAFI.value(safi_name), payload, Action.ANNOUNCE, False)
    except (Notify, Exception):  # noqa: BLE001 - a seed which will not decode is not this test's subject
        return None
    nlri = result[0] if isinstance(result, tuple) else result
    return nlri


def routes():
    """One decoded NLRI per seed, across every family which has one"""
    for family in sorted(set(NLRI_SEEDS) | set(EXTRA_SEEDS)):
        for payload in seeds(family):
            nlri = decode(family, payload)
            if nlri is not None:
                yield family, payload, nlri


def comparable(nlri):
    """Whether this class answers == and hash at all, rather than refusing"""
    try:
        hash(nlri)
        nlri == nlri
    except Exception:  # noqa: BLE001
        return False
    return True


ROUTES = [(f, p, n) for f, p, n in routes() if comparable(n)]
IDS = [f'{f}-{i}' for i, (f, _p, _n) in enumerate(ROUTES)]


class TestTheSweepMeansSomething:
    @pytest.mark.registry_floor
    def test_enough_families_decode(self) -> None:
        families = {family for family, _p, _n in ROUTES}
        assert len(families) >= FAMILY_FLOOR, sorted(families)

    def test_the_vpn_bgpls_seed_decodes_and_carries_a_route_distinguisher(self) -> None:
        # the seed this file exists to add: without it nothing here exercises a
        # populated route distinguisher, and a field which is empty cannot be lost
        nlri = decode('bgp-ls/bgp-ls-vpn', EXTRA_SEEDS['bgp-ls/bgp-ls-vpn'][0])
        assert nlri is not None
        assert getattr(nlri, 'route_d', None), 'the seed carries no route distinguisher, so it proves nothing'


class TestTwoDecodesOfOneRoute:
    @pytest.mark.parametrize('family,payload,_nlri', ROUTES, ids=IDS)
    def test_are_equal(self, family, payload, _nlri) -> None:
        one, two = decode(family, payload), decode(family, payload)
        assert one == two

    @pytest.mark.parametrize('family,payload,_nlri', ROUTES, ids=IDS)
    def test_and_hash_equally(self, family, payload, _nlri) -> None:
        one, two = decode(family, payload), decode(family, payload)
        assert hash(one) == hash(two)


class TestARouteAndItsCopy:
    @pytest.mark.parametrize('family,payload,nlri', ROUTES, ids=IDS)
    def test_deepcopy_is_equal_and_hashes_equally(self, family, payload, nlri) -> None:
        duplicate = copy.deepcopy(nlri)
        assert duplicate == nlri
        assert hash(duplicate) == hash(nlri)

    @pytest.mark.parametrize('family,payload,nlri', ROUTES, ids=IDS)
    def test_copy_is_equal_and_hashes_equally(self, family, payload, nlri) -> None:
        duplicate = copy.copy(nlri)
        assert duplicate == nlri
        assert hash(duplicate) == hash(nlri)

    @pytest.mark.parametrize('family,payload,nlri', ROUTES, ids=IDS)
    def test_a_copy_keeps_its_route_distinguisher(self, family, payload, nlri) -> None:
        # the shape of the defect on the main branch: the copy methods reasoned
        # from a base class __slots__ which did not mention route_d, so a copied
        # VPN route lost it and could not be compared to itself afterwards
        original = getattr(nlri, 'route_d', None)
        if original is None:
            pytest.skip('this family carries no route distinguisher')
        assert getattr(copy.deepcopy(nlri), 'route_d', None) == original


class TestTheConsequenceTheRibSees:
    """The two dunder methods stated as what they actually do

    A failure here reads as "the RIB holds this route twice", which is the thing
    that goes wrong, rather than as "hash disagrees with eq", which is the
    mechanism.
    """

    @pytest.mark.parametrize('family,payload,_nlri', ROUTES, ids=IDS)
    def test_a_set_of_two_equal_routes_holds_one(self, family, payload, _nlri) -> None:
        one, two = decode(family, payload), decode(family, payload)
        assert len({one, two}) == 1

    @pytest.mark.parametrize('family,payload,nlri', ROUTES, ids=IDS)
    def test_a_dict_keyed_on_a_route_finds_its_copy(self, family, payload, nlri) -> None:
        index = {nlri: 'announced'}
        assert index.get(copy.deepcopy(nlri)) == 'announced'
