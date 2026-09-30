"""A query sent without a sequence gets the next one, not the first one every time.

`SequencedOperationalFamily.pack_message` read the last sequence under the router-id it was
given, None when the operator gave none, and stored the new one under the router-id it
resolved from the session's OPEN.  The read key was never written, so every query without
an explicit sequence went out numbered 1, and a reply could not be told apart from the
reply to any earlier query.
"""

from struct import unpack
from tests import negotiation

import pytest

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.operational import Query, SequencedOperationalFamily
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.open.capability.negotiated import Negotiated

HEADER = 19
# operational type(2) + length(2) + afi(2) + safi(1) + router-id(4), then the sequence
SEQUENCE_OFFSET = HEADER + 4 + 3 + 4


@pytest.fixture(autouse=True)
def fresh_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SequencedOperationalFamily, '_sequence_sent', {})


def sent_sequence(wire: bytes) -> int:
    sequence: int = unpack('!L', wire[SEQUENCE_OFFSET : SEQUENCE_OFFSET + 4])[0]
    return sequence


def session(router_id: str) -> Negotiated:
    negotiated = negotiation.negotiated()
    negotiated.sent_open = negotiation.open_message(router_id=router_id)
    return negotiated


def test_each_query_without_a_sequence_gets_the_next_one() -> None:
    negotiated = session('192.0.2.1')
    query = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, None, None)

    sequences = [sent_sequence(query.pack_message(negotiated)) for _ in range(3)]

    assert sequences == [1, 2, 3]


def test_the_router_id_filled_in_is_the_one_of_our_open() -> None:
    query = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, None, None)

    wire = query.pack_message(session('192.0.2.7'))

    assert wire[HEADER + 7 : HEADER + 11] == bytes([192, 0, 2, 7])


def test_packing_does_not_change_the_message() -> None:
    """The query queued for many peers is the same query after it went to one of them."""
    query = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, None, None)
    before = bytes(query.pack_body(session('192.0.2.1')))

    query.pack_message(session('192.0.2.1'))

    assert query.routerid is None
    assert query.sequence is None
    assert before != bytes(query.pack_body(session('192.0.2.1'))), 'the next one takes the next sequence'


def test_a_given_sequence_is_sent_as_given() -> None:
    query = Query.RPCQ.make_query(AFI.ipv4, SAFI.unicast, RouterID('192.0.2.1'), 42)

    assert sent_sequence(query.pack_message(session('192.0.2.9'))) == 42
