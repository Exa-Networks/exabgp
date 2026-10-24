#!/usr/bin/env python3
# encoding: utf-8

"""ADD-PATH changes the bytes on the wire, and nothing exercised that

Instrumenting the whole suite:

    INET.pack_nlri with add-path negotiated       0    of 1807 calls
    INET.pack_nlri without                     1807
    INET.index with a real path-info               1
    INET.index with NOPATH                    11366

So the branch which prepends the four byte path identifier was never executed by
any test. RFC 7911 add-path is what lets a speaker advertise several paths for
one prefix; if the identifier is packed wrong the paths are mis-associated at
the far end, and every test would still pass.

Found by the session working main, whose mutation testing killed nothing in
those branches because nothing reached them.
"""

import importlib.util
import pathlib

import pytest

from exabgp.bgp.message import Open
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI

FAMILY = (AFI.ipv4, SAFI.unicast)
PATH_ID = 0x01020304


def _neighbor():
    spec = importlib.util.spec_from_file_location(
        'decode_fixtures', pathlib.Path(__file__).parent.parent / 'unit' / 'test_decode.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeNeighbor()


def _session(add_path):
    """A negotiated session which really does agree add-path, both ways

    The capability is built directly rather than through Capabilities.new():
    that path asks the neighbour for addpaths(), which the stub does not have,
    and leaving add-path unset there is what kept this branch unreachable.
    """
    neighbor = _neighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    if add_path:
        paths = AddPath()
        for afi, safi in neighbor.families():
            paths.add_path(afi, safi, add_path)
        capabilities[Capability.CODE.ADD_PATH] = paths
    session = Negotiated(neighbor)
    session.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    session.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return session


def _route(path_id):
    decoded, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0]), Action.ANNOUNCE, False)
    if path_id is not None:
        decoded.path_info = PathInfo(integer=path_id)
    return decoded


class TestTheIdentifierReachesTheWire:
    def test_the_send_branch_is_reachable_at_all(self) -> None:
        # if this is False the rest of the file proves nothing, which is how the
        # branch stayed unexercised in the first place
        assert _session(3).addpath.send(*FAMILY)

    def test_the_path_identifier_is_prepended(self) -> None:
        route = _route(PATH_ID)
        packed = route.pack_nlri(_session(3))
        assert packed[:4] == PATH_ID.to_bytes(4, 'big'), 'the path identifier is not on the wire'
        assert packed[4:] == bytes([24, 10, 0, 0])

    def test_without_add_path_it_is_not(self) -> None:
        route = _route(PATH_ID)
        assert route.pack_nlri(_session(0)) == bytes([24, 10, 0, 0])

    def test_the_wire_round_trips(self) -> None:
        session = _session(3)
        packed = _route(PATH_ID).pack_nlri(session)
        back, remaining = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, packed, Action.ANNOUNCE, True)
        assert remaining == b''
        assert int(back.path_info.pack().hex(), 16) == PATH_ID
        assert str(back.cidr) == '10.0.0.0/24'


class TestTheIdentifierSeparatesRoutesInTheRib:
    """Two paths for one prefix must not collide on their RIB key

    That is the whole point of add-path, and index() is what the RIB keys on.
    """

    def test_two_path_identifiers_give_two_keys(self) -> None:
        first, second = _route(1), _route(2)
        assert first.index() != second.index()

    def test_no_path_info_differs_from_a_path_info(self) -> None:
        assert _route(None).index() != _route(1).index()

    @pytest.mark.parametrize('path_id', [0, 1, 0xFFFFFFFF])
    def test_the_key_carries_the_identifier(self, path_id) -> None:
        assert path_id.to_bytes(4, 'big') in _route(path_id).index()
