"""The peers an API command selects are the ones its selector names, no more.

- `neighbor * peer-as X` matched every peer: the wildcard answered before the qualifiers
  after it were looked at, in v4 and in v6 alike.
- `peer [ ]` names no peer, and selected every one: match_neighbors given no description
  answers all the peers, which is what a command with no selector at all wants.
- `peer delete <selector>` and `neighbor <selector> delete` could never succeed: the first
  was dispatched before its selector was read, so it had no peer to delete, and the second
  was not dispatched at all.
"""

from __future__ import annotations

import pytest

from exabgp.reactor.api.command.limit import match_neighbor
from exabgp.reactor.api.command.neighbor import teardown
from exabgp.reactor.api.command.peer import peer_delete
from exabgp.reactor.api.dispatch.common import NoMatchingPeers
from exabgp.reactor.api.dispatch.v4 import dispatch_v4
from exabgp.reactor.api.dispatch.v6 import dispatch_v6
from exabgp.reactor.loop import Reactor
from exabgp.reactor.peer import Peer
from exabgp.rib import RIB
from tests import negotiation

ONE = 'neighbor 127.0.0.1 local-ip 127.0.0.2 local-as 1 peer-as 1 router-id 1.1.1.1 family-allowed in-open'
TWO = 'neighbor 127.0.0.3 local-ip 127.0.0.2 local-as 1 peer-as 2 router-id 1.1.1.1 family-allowed in-open'

# the service of the reactor's own CLI, which every peer answers to
SERVICE = ''


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def two_peers() -> Reactor:
    reactor, _ = negotiation.reactor()
    reactor._peers = {
        ONE: Peer(negotiation.neighbor(peer_address='127.0.0.1', peer_as=1), reactor),
        TWO: Peer(negotiation.neighbor(peer_address='127.0.0.3', peer_as=2), reactor),
    }
    return reactor


# ---------------------------------------------------------------- the wildcard and its qualifiers


def test_a_wildcard_with_a_qualifier_matches_only_what_the_qualifier_allows() -> None:
    assert match_neighbor(['neighbor *', 'peer-as 2'], TWO)
    assert not match_neighbor(['neighbor *', 'peer-as 2'], ONE)


def test_a_wildcard_alone_still_matches_every_peer() -> None:
    assert match_neighbor(['neighbor *'], ONE)
    assert match_neighbor(['peer *'], TWO)


@pytest.mark.parametrize(
    'command',
    ['peer * peer-as 2 teardown 4', 'neighbor * peer-as 2 teardown 4', 'peer [ * peer-as 2 ] teardown 4'],
)
def test_the_qualifiers_after_a_wildcard_are_applied(command: str) -> None:
    dispatch = dispatch_v6 if command.startswith('peer') else dispatch_v4
    handler, peers, _ = dispatch(command, two_peers(), SERVICE)
    assert handler is teardown
    assert peers == [TWO]


# ---------------------------------------------------------------- a selector which names nothing


def test_an_empty_v6_selector_selects_no_peer() -> None:
    with pytest.raises(NoMatchingPeers):
        dispatch_v6('peer [ ] teardown 4', two_peers(), SERVICE)


def test_an_empty_v4_selector_selects_no_peer() -> None:
    with pytest.raises(NoMatchingPeers):
        dispatch_v4('neighbor [ ] teardown 4', two_peers(), SERVICE)


# ---------------------------------------------------------------- delete


@pytest.mark.parametrize(
    'command',
    ['peer delete 127.0.0.1', 'peer delete [ 127.0.0.1 ]', 'neighbor 127.0.0.1 delete', 'delete neighbor 127.0.0.1'],
)
def test_delete_is_given_the_peers_its_selector_names(command: str) -> None:
    dispatch = dispatch_v4 if command.startswith(('neighbor', 'delete')) else dispatch_v6
    handler, peers, _ = dispatch(command, two_peers(), SERVICE)
    assert handler is peer_delete
    assert peers == [ONE]


def test_delete_naming_no_peer_is_refused() -> None:
    with pytest.raises(NoMatchingPeers):
        dispatch_v6('peer delete 127.0.0.9', two_peers(), SERVICE)
