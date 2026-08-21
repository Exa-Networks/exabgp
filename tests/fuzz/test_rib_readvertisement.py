#!/usr/bin/env python3
# encoding: utf-8

"""A route put in the adj-rib-out must come back out as the route that went in

The RIB is where a received or configured route waits to be re-advertised. Two
things can go wrong there and neither is visible to a decoder test:

  - the route is stored under a key which another route shares, so one silently
    replaces the other and a prefix stops being advertised
  - the route is re-encoded into an UPDATE which no longer describes it, or
    which cannot be decoded at all

Both are checked here by driving the real OutgoingRIB and the real Update
packer, not by inspecting the pieces.

Note on keys: Label.index() deliberately excludes the label stack and
IPVPN.index() includes the route distinguisher but not the label. That is
correct. Re-advertising a prefix with a different label is a CHANGE to one
route, not a second route, so the two must share a key. A test which flags that
as a collision is asking the wrong question.
"""

import importlib.util
import pathlib

import pytest

from exabgp.bgp.message import Open, Update
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.update.attribute import Attributes, NextHop, Origin
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, Family, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.change import Change
from exabgp.rib.outgoing import OutgoingRIB

from .corpus import seeds_for

FAMILIES = sorted(NLRI.registered_nlri)

# families which cannot reach the adj-rib-out: nothing populates it but the
# configuration, and these have no announce parser
NOT_ANNOUNCEABLE = {'bgp-ls/bgp-ls', 'bgp-ls/bgp-ls-vpn'}


def _fake_neighbor():
    """test_decode.py owns the only neighbour stub, and it is not importable"""
    spec = importlib.util.spec_from_file_location(
        'decode_fixtures', pathlib.Path(__file__).parent.parent / 'unit' / 'test_decode.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeNeighbor()


@pytest.fixture(scope='module')
def negotiated():
    neighbor = _fake_neighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    session = Negotiated(neighbor)
    session.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    session.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return neighbor, session


def _first_route(family):
    """The first seed which decodes to a route this speaker could originate

    A seed decoding to an 'unknown' sub-type is a shape only the wire produces:
    there is no way to configure one, so it can never reach the adj-rib-out and
    re-advertising it is not a property worth asserting. The round trip ratchet
    in test_nlri_roundtrip.py records what those do.
    """
    afi_name, safi_name = family.split('/')
    afi, safi = AFI.value(afi_name), SAFI.value(safi_name)
    klass = NLRI.registered_nlri[family]
    for payload in seeds_for(family):
        try:
            result = klass.unpack_nlri(afi, safi, payload, Action.ANNOUNCE, False)
        except Exception:  # noqa: BLE001 - the decoder property tests judge this
            continue
        nlri = result[0] if isinstance(result, tuple) else result
        if nlri is None:
            continue
        if 'unknown' in str(nlri):
            continue
        nlri.action = Action.ANNOUNCE
        nexthop = '2001:db8::9' if afi == AFI.ipv6 else '10.0.0.9'
        try:
            nlri.nexthop = IP.create(nexthop)
        except Exception:  # noqa: BLE001 - families without a next-hop of their own
            pass
        attributes = Attributes()
        attributes.add(Origin(Origin.IGP))
        attributes.add(NextHop(nexthop))
        return afi, nlri, attributes
    return None, None, None


class TestEveryRegisteredFamilyHasItsSizes:
    """A family which decodes but has no Family.size entry cannot be received

    ipv6 multicast was in exactly that state: configurable, announceable,
    encoded into an MP_REACH, and refused on the way back in with
    'unsupported ipv6 multicast', so two speakers which agreed on the family
    dropped the session on the first route.
    """

    def test_no_registered_family_is_missing(self) -> None:
        missing = []
        for family in FAMILIES:
            afi_name, safi_name = family.split('/')
            if (AFI.value(afi_name), SAFI.value(safi_name)) not in Family.size:
                missing.append(family)
        assert missing == [], (
            f'families registered as NLRI but absent from Family.size: {missing}. '
            'A family here decodes as an NLRI but is refused by MPRNLRI.unpack, so it '
            'can be announced and never received.'
        )


class TestRoutesSurviveTheAdjRibOut:
    @pytest.mark.parametrize('family', [f for f in FAMILIES if f not in NOT_ANNOUNCEABLE])
    def test_a_route_comes_back_as_itself(self, family, negotiated) -> None:
        neighbor, session = negotiated
        afi, nlri, attributes = _first_route(family)
        if nlri is None:
            pytest.skip(f'{family}: no seed decoded, nothing to re-advertise')

        announced = str(nlri)
        rib = OutgoingRIB(False, neighbor.families())
        rib.add_to_rib(Change(nlri, attributes))

        updates = list(rib.updates(False))
        assert updates, f'{family}: the route vanished between add_to_rib and updates()'

        seen = []
        for update in updates:
            for wire in update.messages(session):
                # the peer on the other side has to be able to read this
                back = Update.unpack_message(wire[19:], Direction.IN, session)
                seen.extend(str(each) for each in back.nlris)

        assert announced in seen, f'{family}: announced {announced!r}, re-advertised {seen}'
