"""Every announce command refuses a route which can not be sent, before announcing any.

Only `announce route` checked its routes. `announce attributes ... rd 100:100 nlri ...`, a
VPN route with no label, was taken and answered `done`, and failed later, when the RIB
packed it for the peer. Found by qa/bin/test_old_commands: 5.0 took it too, and sent a
route whose label was the first octets of the route distinguisher.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from exabgp.reactor.api import API
from exabgp.reactor.api.dispatch.version import API_V4, dispatch_for

PEER = 'neighbor 127.0.0.1'


def answered(command: str, neighbors: dict[str, Any] | None = None) -> tuple[list[Any], list[Any]]:
    """The routes the handler announced, and the errors it answered."""
    announced: list[Any] = []
    errors: list[Any] = []
    reactor = MagicMock()
    reactor.configuration.neighbors = neighbors or {}
    reactor.peers.return_value = [next(iter(neighbors))] if neighbors else [PEER]
    reactor.processes.answer_error = AsyncMock(side_effect=lambda service, *why: errors.append(why))
    reactor.processes.answer_done = AsyncMock()
    reactor.processes.get_sync.return_value = False
    reactor.configuration.announce_route.side_effect = lambda peers, route, *_: announced.append(route)
    scheduled: list[Any] = []
    reactor.asynchronous.schedule.side_effect = lambda service, name, coroutine: scheduled.append(coroutine)
    handler, peers, remaining = dispatch_for(API_V4, command, reactor, 'helper')
    handler(API(reactor), reactor, 'helper', peers, remaining, False)
    for coroutine in scheduled:
        asyncio.run(coroutine)
    return announced, errors


@pytest.mark.parametrize(
    'command',
    [
        'announce route 10.0.0.0/24 next-hop 1.2.3.4 rd 100:100',
        'announce attributes next-hop 1.2.3.4 rd 100:100 nlri 10.0.0.0/24 20.0.0.0/24',
        'announce ipv4 mpls-vpn 10.0.0.0/24 next-hop 1.2.3.4 rd 100:100',
        'announce ipv6 mpls-vpn 2001:db8::/32 next-hop 2001:db8::1 rd 100:100',
    ],
)
def test_a_vpn_route_with_no_label_is_refused(command: str) -> None:
    announced, errors = answered(command)
    assert announced == []
    assert errors, 'the helper was told done'


def test_the_routes_of_attributes_are_announced_when_they_can_be_sent() -> None:
    announced, errors = answered(
        'announce attributes next-hop 1.2.3.4 rd 100:100 label 10 nlri 10.0.0.0/24 20.0.0.0/24',
        neighbors('', 'ipv4 mpls-vpn'),
    )
    assert errors == []
    assert len(announced) == 2


def neighbors(capability: str, family: str = 'ipv6 unicast') -> dict[str, Any]:
    from exabgp.configuration.configuration import Configuration

    configuration = Configuration(
        [
            f"""neighbor 127.0.0.1 {{
            router-id 10.0.0.2;
            local-address 127.0.0.1;
            local-as 65533;
            peer-as 65533;
            family {{ {family}; }}
            capability {{ {capability} }}
        }}"""
        ],
        text=True,
    )
    # not an assert: the optimised run of the suite would not load the configuration at all
    if not configuration.reload():
        raise AssertionError(str(configuration.error))
    return dict(configuration.neighbors)


def test_a_link_local_next_hop_is_refused_without_the_capability() -> None:
    # it was taken, and raised when the RIB packed it for the peer
    announced, errors = answered('announce route 2001:db8::/32 next-hop fe80::1', neighbors(''))
    assert announced == []
    assert errors


def test_a_link_local_next_hop_is_announced_with_the_capability() -> None:
    announced, errors = answered(
        'announce route 2001:db8::/32 next-hop fe80::1', neighbors('link-local-nexthop enable;')
    )
    assert errors == []
    assert len(announced) == 1
