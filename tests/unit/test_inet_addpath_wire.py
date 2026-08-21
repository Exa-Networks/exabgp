"""The four ways an INET NLRI can be packed, and the RIB key which separates them.

Mutation testing over the unicast decoder, once the register decorator stopped hiding it,
found that nothing exercised pack_nlri with add-path negotiated: replacing
`negotiated.addpath.send(self.afi, self.safi)` with None left the whole suite green, and so
did turning the NOPATH concatenation into a subtraction, which cannot even run.

pack_nlri decides on two independent things, what the session negotiated and what the
stored bytes already carry, so there are four cases and all four are here. TIGER_STYLE 1.1:
what a decoder accepts, it must be able to re-encode.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

PATH_INFO_SIZE = 4
PREFIX = bytes([24, 10, 0, 0])  # 10.0.0.0/24
PATH_ID = bytes([0x00, 0x00, 0x00, 0x07])


def negotiated(send_addpath: bool) -> Negotiated:
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    result = Negotiated.make_negotiated(neighbor, Direction.OUT)
    result.addpath.send = Mock(return_value=send_addpath)  # type: ignore[method-assign]
    return result


def decode(data: bytes, addpath: bool) -> NLRI:
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, addpath, None)
    return nlri


@pytest.mark.parametrize(
    'stored_addpath, send_addpath, expected',
    [
        (True, True, PATH_ID + PREFIX),  # carried and wanted: sent as it arrived
        (True, False, PREFIX),  # carried but not wanted: the path id is stripped
        (False, True, bytes(PATH_INFO_SIZE) + PREFIX),  # wanted but absent: NOPATH is prepended
        (False, False, PREFIX),  # neither: sent as it arrived
    ],
    ids=['carried-wanted', 'carried-unwanted', 'absent-wanted', 'absent-unwanted'],
)
def test_pack_nlri_covers_what_was_stored_and_what_was_negotiated(
    stored_addpath: bool, send_addpath: bool, expected: bytes
) -> None:
    data = (PATH_ID + PREFIX) if stored_addpath else PREFIX
    nlri = decode(data, stored_addpath)
    assert bytes(nlri.pack_nlri(negotiated(send_addpath))) == expected


def test_a_path_id_of_zero_is_not_the_same_route_as_no_path_id() -> None:
    """The RIB key carries a discriminator, and this is the collision it exists for.

    An NLRI with add-path and a path id of 0x00000000 has the same wire bytes after its
    header as one with no add-path at all. Without the discriminator the RIB would treat
    them as one route, so a peer announcing path 0 would overwrite the path-less entry.

    Mutation testing rewrote that discriminator and nothing failed.
    """
    with_zero_path = decode(bytes(PATH_INFO_SIZE) + PREFIX, True)
    without_path = decode(PREFIX, False)

    assert with_zero_path.index() != without_path.index()


def test_two_paths_for_one_prefix_share_a_prefix_index() -> None:
    """What the paths-limit audit counts with.

    IncomingRIB.track_path groups by prefix_index, so two path ids for one prefix have to
    land in the same group or the count against the peer's advertised limit is wrong.
    """
    first = decode(bytes([0, 0, 0, 1]) + PREFIX, True)
    second = decode(bytes([0, 0, 0, 2]) + PREFIX, True)

    assert first.index() != second.index(), 'two paths are two routes'
    assert first.prefix_index() == second.prefix_index(), 'but one prefix'


def test_the_stored_bytes_survive_a_pack_and_unpack_with_add_path() -> None:
    """What arrives with a path id has to leave with the same one."""
    nlri = decode(PATH_ID + PREFIX, True)
    packed = bytes(nlri.pack_nlri(negotiated(True)))
    again, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, packed, Action.ANNOUNCE, True, None)
    assert again.index() == nlri.index()
    assert packed[:PATH_INFO_SIZE] == PATH_ID
