"""What the peer ends up holding, over sequences the hand written tests do not reach.

The enforcement tests each walk one scenario somebody thought of. The promise PATHS-LIMIT
makes to a peer is not about a scenario: whatever the operator does, the peer must never be
left holding more paths for a prefix than it asked for, and must not be left holding fewer
than the operator offered while the limit had room. Those two are the properties here.
"""

from hypothesis import given, settings, strategies as st

from exabgp.bgp.message import UpdateCollection
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route


IPV4 = (AFI.ipv4, SAFI.unicast)
PREFIXES = ('192.0.2.0/24', '198.51.100.0/24')
PATH_IDS = (1, 2, 3, 4)
ORIGINS = (Origin.IGP, Origin.EGP)


def make_route(prefix: str, path_id: int, origin: int) -> Route:
    address, mask = prefix.split('/')
    cidr = CIDR.create_cidr(IP.pton(address), int(mask))
    nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo.make_from_integer(path_id))
    attributes = AttributeCollection()
    attributes[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attributes, nexthop=IP.NoNextHop)


# One round is some announces and withdrawals followed by a drain. Rounds matter more than
# a flat list of operations: a path only needs promoting once it has actually been sent, and
# a withdrawal which lands in the same batch as its announce cancels it instead. A flat list
# reaches that shape by luck, and a run which never reaches it reports green while the
# promotion code has not been entered.
announce = st.tuples(
    st.just('announce'), st.sampled_from(PREFIXES), st.sampled_from(PATH_IDS), st.sampled_from(ORIGINS)
)
withdraw = st.tuples(st.just('withdraw'), st.sampled_from(PREFIXES), st.sampled_from(PATH_IDS), st.just(Origin.IGP))
rounds = st.lists(st.lists(st.one_of(announce, withdraw), min_size=1, max_size=6), min_size=2, max_size=8)


class PeerView:
    """What the peer holds, rebuilt from the messages it was actually sent."""

    def __init__(self) -> None:
        self.paths: dict[str, set[bytes]] = {}

    def apply(self, update: UpdateCollection, limit: int) -> None:
        for nlri in update.withdraws:
            self.paths.get(prefix_key(nlri), set()).discard(nlri.index())
        for routed in update.announces:
            self.paths.setdefault(prefix_key(routed.nlri), set()).add(routed.nlri.index())
        for prefix, held in self.paths.items():
            assert len(held) <= limit, f'peer holds {len(held)} paths for {prefix}, limit is {limit}'


def prefix_key(nlri) -> str:  # type: ignore[no-untyped-def]
    return str(nlri).split(' ')[0]


@settings(max_examples=400, deadline=None)
@given(
    script=rounds,
    limit=st.integers(min_value=1, max_value=3),
    grouped=st.booleans(),
    cache=st.booleans(),
    refresh=st.booleans(),
)
def test_peer_never_holds_more_than_the_limit(
    script: list[list[tuple[str, str, int, int]]], limit: int, grouped: bool, cache: bool, refresh: bool
) -> None:
    rib = OutgoingRIB(cache=cache, families={IPV4})
    peer = PeerView()
    offered: dict[str, set[bytes]] = {}

    for round_number, operations in enumerate(script):
        for action, prefix, path_id, origin in operations:
            route = make_route(prefix, path_id, origin)
            if action == 'announce':
                rib.add_to_rib(route, force=True)
                offered.setdefault(prefix, set()).add(route.nlri.index())
            else:
                rib.del_from_rib(route)
                offered.setdefault(prefix, set()).discard(route.nlri.index())
        if refresh and cache and round_number % 2:
            rib.resend(False)
        for update in rib.updates(grouped, {IPV4: limit}):
            if isinstance(update, UpdateCollection):
                peer.apply(update, limit)

    # Nothing is left queued, so what the peer holds is now final and can be compared with
    # what was offered: every path it holds was offered, and the limit is filled if it can be.
    for prefix, wanted in offered.items():
        held = peer.paths.get(prefix, set())
        assert held <= wanted, f'{prefix}: peer holds a path which was never announced'
        assert len(held) == min(len(wanted), limit), (
            f'{prefix}: peer holds {len(held)} of {len(wanted)} offered paths, limit {limit}'
        )
