"""RFC 4486 section 4: ending a session whose peer sent more prefixes than configured.

The ledger these tests are joined to is qa/rfc/rfc4486.toml.

`ipv4 unicast prefix-limit 10000;` in a family block caps what the peer may hold in that
family.  The announcement which takes it past the cap ends the session with Cease,
Maximum Number of Prefixes Reached, (6, 1), carrying the AFI, the SAFI and the bound.
A prefix sent again replaces itself and a withdrawn one frees its place, so the count is
of distinct routes the peer currently holds with us, not of announcements.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.message import Message

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers.update import UpdateHandler
from exabgp.rib import RIB
from exabgp.rib.incoming import IncomingRIB

CEASE = 6
MAXIMUM_NUMBER_OF_PREFIXES_REACHED = 1

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def configuration(family: str) -> Configuration:
    return Configuration(
        [
            f"""neighbor 192.0.2.1 {{
                router-id 192.0.2.2;
                local-address 192.0.2.2;
                local-as 65001;
                peer-as 65002;
                family {{ {family} }}
            }}"""
        ],
        text=True,
    )


def parsed_neighbor(family: str) -> Neighbor:
    config = configuration(family)
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    return neighbor


def nlri(prefix: str, afi: AFI = AFI.ipv4) -> INET:
    address, mask = prefix.split('/')
    return INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), afi, SAFI.unicast)


def update(
    announces: tuple[str, ...] | list[str] = (), withdraws: tuple[str, ...] | list[str] = (), afi: AFI = AFI.ipv4
) -> Any:
    parsed = Mock()
    parsed.announces = [RoutedNLRI(nlri(prefix, afi), IP.NoNextHop) for prefix in announces]
    parsed.withdraws = [nlri(prefix, afi) for prefix in withdraws]
    parsed.attributes = AttributeCollection()
    message = Mock()
    message.ID = Message.CODE.UPDATE
    message.IS_EOR = False
    message.data = parsed
    return message


def context(limits: dict[FamilyTuple, int]) -> Any:
    ctx = Mock(spec=PeerContext)
    ctx.neighbor = Mock()
    ctx.neighbor.prefix_limit = limits
    ctx.neighbor.rib = Mock()
    ctx.neighbor.rib.incoming = IncomingRIB(True, {IPV4_UNICAST, IPV6_UNICAST})
    ctx.negotiated = Mock()
    ctx.negotiated.advertised_paths_limit = {}
    ctx.peer_id = 'test-peer'
    ctx.stats = {'receive-prefixes': 0, 'receive-withdraws': 0}
    return ctx


def receive(ctx: Any, *messages: Any) -> None:
    handler = UpdateHandler()
    for message in messages:
        list(handler.handle(ctx, message))


# =========================================================== configuration


def test_a_family_takes_a_prefix_limit() -> None:
    neighbor = parsed_neighbor('ipv4 unicast prefix-limit 10; ipv6 unicast;')

    assert neighbor.families() == [IPV4_UNICAST, IPV6_UNICAST]
    assert neighbor.prefix_limit == {IPV4_UNICAST: 10}


def test_a_family_without_a_limit_is_unlimited() -> None:
    assert parsed_neighbor('ipv4 unicast;').prefix_limit == {}


def test_the_largest_bound_the_data_field_can_carry_is_accepted() -> None:
    assert parsed_neighbor('ipv4 unicast prefix-limit 4294967295;').prefix_limit == {IPV4_UNICAST: 0xFFFFFFFF}


@pytest.mark.parametrize(
    'line,wanted',
    [
        ('ipv4 unicast prefix-limit 0;', 'prefix-limit must be 1-4294967295'),
        ('ipv4 unicast prefix-limit 4294967296;', 'prefix-limit must be 1-4294967295'),
        ('ipv4 unicast prefix-limit;', 'prefix-limit requires a number'),
        ('ipv4 unicast prefix-limit many;', 'prefix-limit must be a number'),
        ('ipv4 unicast prefix-limit 10 20;', 'unexpected token after the prefix-limit'),
        ('ipv4 unicast limit 10;', 'unexpected token after ipv4 unicast: limit'),
    ],
)
def test_a_malformed_prefix_limit_is_refused(line: str, wanted: str) -> None:
    config = configuration(line)

    assert not config.reload(), f'{line} was accepted'
    assert wanted in str(config.error), str(config.error)


def test_the_limit_survives_a_round_trip_through_the_configuration_dump() -> None:
    dumped = str(parsed_neighbor('ipv4 unicast prefix-limit 10; ipv6 unicast;'))

    assert 'ipv4 unicast prefix-limit 10;' in dumped
    assert 'ipv6 unicast;' in dumped


def test_changing_the_limit_does_not_drop_the_session_on_reload() -> None:
    """The limit is ours alone, the peer never learns it, so there is nothing to renegotiate."""
    assert parsed_neighbor('ipv4 unicast prefix-limit 10;') == parsed_neighbor('ipv4 unicast prefix-limit 20;')


# =========================================================== counting


def test_the_count_is_of_distinct_routes() -> None:
    incoming = IncomingRIB(True, {IPV4_UNICAST})

    assert incoming.count_prefix(nlri('10.0.0.0/24')) == 1
    assert incoming.count_prefix(nlri('10.0.0.0/24')) == 1
    assert incoming.count_prefix(nlri('10.0.1.0/24')) == 2


def test_a_withdrawal_frees_its_place_and_a_new_session_starts_at_zero() -> None:
    incoming = IncomingRIB(True, {IPV4_UNICAST})
    incoming.count_prefix(nlri('10.0.0.0/24'))
    incoming.count_prefix(nlri('10.0.1.0/24'))

    incoming.uncount_prefix(nlri('10.0.0.0/24'))
    assert incoming.count_prefix(nlri('10.0.2.0/24')) == 2

    incoming.clear()
    assert incoming.count_prefix(nlri('10.0.3.0/24')) == 1


def test_the_count_does_not_depend_on_adj_rib_in() -> None:
    """A neighbour with adj-rib-in off keeps no routes, and must still be held to its limit."""
    incoming = IncomingRIB(False, {IPV4_UNICAST})

    incoming.count_prefix(nlri('10.0.0.0/24'))
    assert incoming.count_prefix(nlri('10.0.1.0/24')) == 2


# =========================================================== 4, the NOTIFICATION


@pytest.mark.rfc('rfc4486#4-maximum-prefixes-must-send-subcode-one')
@pytest.mark.rfc('rfc4486#4-data-may-carry-the-family-and-the-bound')
def test_the_prefix_past_the_limit_ends_the_session_with_subcode_one() -> None:
    ctx = context({IPV4_UNICAST: 2})

    with pytest.raises(Notify) as caught:
        receive(ctx, update(['10.0.0.0/24', '10.0.1.0/24', '10.0.2.0/24']))

    assert (caught.value.code, caught.value.subcode) == (CEASE, MAXIMUM_NUMBER_OF_PREFIXES_REACHED)
    assert caught.value.has_defined_data
    assert caught.value.data == pack('!HBI', AFI.ipv4, SAFI.unicast, 2), 'the Data field is not <AFI, SAFI, bound>'


@pytest.mark.rfc('rfc4486#4-maximum-prefixes-must-send-subcode-one', polarity='negative')
def test_a_peer_at_its_limit_is_not_cut_off() -> None:
    """The half which finds bugs: refusing every UPDATE also sends subcode one."""
    ctx = context({IPV4_UNICAST: 2})

    receive(
        ctx,
        update(['10.0.0.0/24', '10.0.1.0/24']),
        update(['10.0.0.0/24', '10.0.1.0/24']),
        update(withdraws=['10.0.0.0/24']),
        update(['10.0.2.0/24']),
    )

    assert ctx.stats['receive-prefixes'] == 5


def test_the_limit_of_one_family_does_not_count_another() -> None:
    ctx = context({IPV4_UNICAST: 1})

    receive(ctx, update(['2001:db8::/32', '2001:db8:1::/48'], afi=AFI.ipv6), update(['10.0.0.0/24']))

    with pytest.raises(Notify) as caught:
        receive(ctx, update(['10.0.1.0/24']))
    assert caught.value.data == pack('!HBI', AFI.ipv4, SAFI.unicast, 1)


def test_the_ipv6_data_field_names_ipv6() -> None:
    ctx = context({IPV6_UNICAST: 1})

    with pytest.raises(Notify) as caught:
        receive(ctx, update(['2001:db8::/32', '2001:db8:1::/48'], afi=AFI.ipv6))

    assert caught.value.data == pack('!HBI', AFI.ipv6, SAFI.unicast, 1)


def test_a_family_without_a_limit_is_not_counted() -> None:
    ctx = context({})

    receive(ctx, update([f'10.0.{index}.0/24' for index in range(50)]))

    assert ctx.stats['receive-prefixes'] == 50


@pytest.mark.asyncio
async def test_the_asynchronous_handler_enforces_the_same_limit() -> None:
    ctx = context({IPV4_UNICAST: 1})
    handler = UpdateHandler()

    await handler.handle_async(ctx, update(['10.0.0.0/24']))
    with pytest.raises(Notify) as caught:
        await handler.handle_async(ctx, update(['10.0.1.0/24']))

    assert (caught.value.code, caught.value.subcode) == (CEASE, MAXIMUM_NUMBER_OF_PREFIXES_REACHED)


@pytest.mark.asyncio
async def test_a_peering_ended_for_too_many_prefixes_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator chose the normal reconnect backoff for (6, 1), unlike (2, 7)."""
    neighbor = Mock()
    neighbor.uid = '1'
    neighbor.ephemeral = False
    neighbor.api = {'neighbor-changes': False, 'fsm': False}
    peer = Peer(neighbor, Mock())
    notify = Notify(CEASE, MAXIMUM_NUMBER_OF_PREFIXES_REACHED, data=pack('!HBI', AFI.ipv4, SAFI.unicast, 1))
    monkeypatch.setattr(peer, '_establish', AsyncMock(side_effect=notify))

    await peer._run()

    assert peer._restart


def test_a_limit_lowered_by_a_reload_below_what_the_peer_holds_ends_the_session_cleanly() -> None:
    """A reload applies a new limit live, so the count can already be past it."""
    ctx = context({IPV4_UNICAST: 3})
    receive(ctx, update(['10.0.0.0/24', '10.0.1.0/24', '10.0.2.0/24']))

    ctx.neighbor.prefix_limit = {IPV4_UNICAST: 1}
    with pytest.raises(Notify) as caught:
        receive(ctx, update(['10.0.3.0/24']))

    assert (caught.value.code, caught.value.subcode) == (CEASE, MAXIMUM_NUMBER_OF_PREFIXES_REACHED)
    assert caught.value.data == pack('!HBI', AFI.ipv4, SAFI.unicast, 1)
