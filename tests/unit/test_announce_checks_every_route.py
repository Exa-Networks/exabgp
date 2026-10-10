"""Every announce command refuses a route which can not be sent, before announcing any.

Only `announce route` checked its routes. `announce attributes ... rd 100:100 nlri ...`, a
VPN route with no label, was taken and answered `done`, and failed later, when the RIB
packed it for the peer. Found by qa/bin/test_old_commands: 5.0 took it too, and sent a
route whose label was the first octets of the route distinguisher.
"""

from __future__ import annotations

import pytest

from tests.api_daemon import HELPER, Daemon

# the families the VPN commands below are for, so only the missing label refuses them
VPN = 'ipv4 mpls-vpn; ipv6 mpls-vpn;'


def configuration(capability: str = '', family: str = 'ipv6 unicast') -> str:
    """One neighbor carrying `family`, which the API helper of the Daemon announces to."""
    return f"""
    process {HELPER} {{
        run /usr/bin/true;
        encoder json;
    }}

    neighbor 127.0.0.1 {{
        router-id 10.0.0.2;
        local-address 127.0.0.1;
        local-as 65533;
        peer-as 65533;
        family {{ {family} }}
        capability {{ {capability} }}
        api {{
            processes [ {HELPER} ];
        }}
    }}
    """


def answered(command: str, configured: str) -> tuple[list[str], list[str]]:
    """The routes the API 4 command put in the outgoing RIB, and what the helper was answered.

    The objects are the ones ExaBGP runs (tests/api_daemon.py): the compiled dispatch
    refuses a Mock where it declares a Reactor.
    """
    daemon = Daemon(configured)
    try:
        lines = daemon.send(command)
        return daemon.announced('127.0.0.1'), lines
    finally:
        daemon.close()


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
    announced, lines = answered(command, configuration(family=VPN))
    assert announced == []
    assert lines[-1:] == ['error'], 'the helper was told done'


def test_the_routes_of_attributes_are_announced_when_they_can_be_sent() -> None:
    announced, lines = answered(
        'announce attributes next-hop 1.2.3.4 rd 100:100 label 10 nlri 10.0.0.0/24 20.0.0.0/24',
        configuration(family=VPN),
    )
    assert lines == ['done']
    assert len(announced) == 2


def test_a_link_local_next_hop_is_refused_without_the_capability() -> None:
    # it was taken, and raised when the RIB packed it for the peer
    announced, lines = answered('announce route 2001:db8::/32 next-hop fe80::1', configuration())
    assert announced == []
    assert lines[-1:] == ['error']


def test_a_link_local_next_hop_is_announced_with_the_capability() -> None:
    announced, lines = answered(
        'announce route 2001:db8::/32 next-hop fe80::1', configuration('link-local-nexthop enable;')
    )
    assert lines == ['done']
    assert len(announced) == 1
