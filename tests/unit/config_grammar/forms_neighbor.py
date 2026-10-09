"""The forms of a neighbor and of the sections inside it, written against the legacy parser.

Each form is given once, by its path below `neighbor`, and is run both in a neighbor and
in a template the neighbor inherits.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

# (path below neighbor, statement, whether the legacy parser accepts it)
BOOLEANS = ['true', 'false', 'enable', 'disable', 'enabled', 'disabled', 'yes', 'no', '1', '0', 'TRUE', 'No']
ENABLES = ['true', 'false', 'enable', 'disable', 'enabled', 'disabled', 'TRUE', 'Disable']

NEIGHBOR_FORMS: list[tuple[tuple[str, ...], str, bool]] = [
    # addresses
    ((), 'peer-address 127.0.0.2', True),
    ((), 'peer-address 127.0.0.0/8', False),  # a range needs passive
    ((), 'peer-address ::1', False),  # not the family of the local address
    ((), 'peer-address nowhere', False),
    ((), 'peer-address', False),
    ((), 'local-address 127.0.0.2', True),
    ((), 'local-address auto', True),  # auto-discovery, with the router-id the wrapper gives
    ((), 'local-address ::1', False),
    ((), 'local-address AUTO', False),
    ((), 'local-address', False),
    ((), 'local-link-local fe80::1', True),
    ((), 'local-link-local 2001:db8::1', False),
    ((), 'local-link-local 10.0.0.1', False),
    ((), 'local-link-local nothing', False),
    ((), 'md5-ip 127.0.0.1', True),
    ((), 'md5-ip 10.0.0.1', True),
    ((), 'md5-ip nothing', False),
    ((), 'router-id 1.2.3.4', True),
    ((), 'router-id 0.0.0.0', True),
    ((), 'router-id ::1', False),
    ((), 'router-id nothing', False),
    # AS numbers
    ((), 'local-as 1', True),
    ((), 'local-as 4200000000', True),
    ((), 'local-as 1.1', True),
    ((), 'local-as 0', True),
    ((), 'local-as auto', True),
    ((), 'local-as AUTO', False),
    ((), 'local-as 4294967296', False),
    ((), 'local-as -1', False),
    ((), 'local-as', False),
    ((), 'peer-as 65001', True),
    ((), 'peer-as auto', True),
    ((), 'peer-as x', False),
    # text
    ((), 'description "a peer"', True),
    ((), 'description one', True),
    ((), 'description', True),
    ((), 'description ""', True),
    ((), 'host-name router', True),
    ((), 'host-name "not a host name!"', True),
    ((), 'domain-name example.com', True),
    ((), 'source-interface eth0', True),
    ((), 'source-interface abcdefghijklmnopqrstuvwxyz', False),
    ((), 'source-interface "eth 0"', False),
    ((), 'source-interface a/b', False),
    ((), 'md5-password secret', True),
    ((), 'md5-password 0123456789abcdef', True),
    ((), 'md5-password "' + 'x' * 81 + '"', False),
    # numbers
    ((), 'hold-time 0', True),
    ((), 'hold-time 3', True),
    ((), 'hold-time 65535', True),
    ((), 'hold-time 1', False),
    ((), 'hold-time 2', False),
    ((), 'hold-time 65536', False),
    ((), 'hold-time -1', False),
    ((), 'hold-time x', False),
    ((), 'hold-time', False),
    ((), 'rate-limit 10', True),
    ((), 'rate-limit 0', True),
    ((), 'rate-limit -5', False),  # a number has no sign
    # ASCII digits only: int() also read a sign, `_` between digits and every script's digits
    ((), 'hold-time +180', False),
    ((), 'hold-time 1_80', False),
    ((), 'hold-time \u0661\u0668\u0660', False),
    ((), 'rate-limit +5', False),
    ((), 'listen 1_79', False),
    # 5.0 reads both as no limit, and str(neighbor) prints the first
    ((), 'rate-limit disable', True),
    ((), 'rate-limit disabled', True),
    ((), 'rate-limit DISABLE', True),
    ((), 'rate-limit enable', False),
    ((), 'rate-limit', False),
    ((), 'listen 179', True),
    ((), 'listen 1', True),
    ((), 'listen 65535', True),
    ((), 'listen 0', False),
    ((), 'listen 65536', False),
    ((), 'listen x', False),
    ((), 'connect 1790', True),
    ((), 'connect 0', False),
    ((), 'outgoing-ttl 1', True),
    ((), 'outgoing-ttl 0', True),
    ((), 'outgoing-ttl 255', True),
    ((), 'outgoing-ttl disable', True),
    ((), 'outgoing-ttl disabled', True),
    ((), 'outgoing-ttl false', True),
    ((), 'outgoing-ttl DISABLE', False),
    ((), 'outgoing-ttl 256', False),
    ((), 'outgoing-ttl -1', False),
    ((), 'incoming-ttl 254', True),
    ((), 'incoming-ttl x', False),
    # booleans with their leaf default as the value of the bare keyword
    *[((), f'passive {spelling}', True) for spelling in BOOLEANS],
    ((), 'passive', True),
    ((), 'passive maybe', False),
    *[
        ((), f'{keyword} {spelling}', True)
        for keyword in ('group-updates', 'auto-flush')
        for spelling in ('true', 'no')
    ],
    *[((), f'{keyword} {spelling}', True) for keyword in ('adj-rib-out', 'adj-rib-in') for spelling in ('yes', '0')],
    *[
        ((), f'{keyword} {spelling}', True)
        for keyword in ('manual-eor', 'shutdown')
        for spelling in ('enable', 'false')
    ],
    *[
        ((), keyword, True)
        for keyword in ('group-updates', 'auto-flush', 'adj-rib-out', 'adj-rib-in', 'manual-eor', 'shutdown')
    ],
    *[
        ((), f'{keyword} 2', False)
        for keyword in ('group-updates', 'auto-flush', 'adj-rib-out', 'adj-rib-in', 'manual-eor', 'shutdown')
    ],
    *[((), f'md5-base64 {spelling}', True) for spelling in ENABLES],
    ((), 'md5-base64', True),
    ((), 'md5-base64 yes', False),
    ((), 'md5-base64 auto', False),
    ((), 'md5-base64 AUTO', False),
    ((), 'as-set withdraw', True),
    ((), 'as-set accept', True),
    ((), 'as-set ACCEPT', True),
    ((), 'as-set maybe', False),
    ((), 'as-set', False),
    ((), 'tunnel-encapsulation auto', True),
    ((), 'tunnel-encapsulation filter', True),
    ((), 'tunnel-encapsulation accept', True),
    ((), 'tunnel-encapsulation AUTO', True),
    ((), 'tunnel-encapsulation maybe', False),
    ((), 'tunnel-encapsulation', False),
    ((), 'route-target-filter true', True),
    ((), 'route-target-filter false', True),
    ((), 'route-target-filter', True),
    ((), 'route-target-filter maybe', False),
    ((), 'enforce-first-as true', True),
    ((), 'enforce-first-as false', True),
    ((), 'enforce-first-as', True),
    ((), 'enforce-first-as maybe', False),
    ((), 'flow-validation disable', True),
    ((), 'flow-validation enable', True),
    ((), 'flow-validation relaxed', True),
    ((), 'flow-validation ENABLE', True),
    ((), 'flow-validation maybe', False),
    ((), 'flow-validation', False),
    ((), 'inherit t', True),
    ((), 'inherit [ t ]', True),
    ((), 'inherit [ t u ]', True),
    ((), 'inherit [ t, u ]', True),
    ((), 'inherit nothing', True),
    # a name no template can have is refused: any word was taken, and matched nothing
    ((), 'inherit t$', False),
    ((), 'inherit [ t u$ ]', False),
    ((), 'inherit t u', False),
    ((), 'inherit [ ]', False),
    ((), 'inherit [ t', False),
    ((), 'inherit', False),
    # family
    *[
        (('family',), f'ipv4 {safi}', True)
        for safi in ('unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn')
    ],
    *[(('family',), f'ipv4 {safi}', True) for safi in ('mcast-vpn', 'flow', 'flow-vpn', 'mup', 'sr-policy', 'rtc')],
    *[(('family',), f'ipv6 {safi}', True) for safi in ('unicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn', 'flow')],
    # refused while `all` negotiated it (plan/done-agent-reported-bugs.md item 8)
    (('family',), 'ipv6 multicast', True),
    (('family',), 'ipv6 rtc', False),
    (('family',), 'l2vpn vpls', True),
    (('family',), 'l2vpn evpn', True),
    (('family',), 'bgp-ls bgp-ls', True),
    (('family',), 'bgp-ls bgp-ls-vpn', True),
    (('family',), 'ipv4 UNICAST', True),
    (('family',), 'ipv4 unicast prefix-limit 1', True),
    (('family',), 'ipv4 unicast prefix-limit 4294967295', True),
    (('family',), 'ipv4 unicast prefix-limit 0', False),
    (('family',), 'ipv4 unicast prefix-limit 4294967296', False),
    (('family',), 'ipv4 unicast prefix-limit x', False),
    (('family',), 'ipv4 unicast prefix-limit', False),
    (('family',), 'ipv4 unicast prefix-limit 5 x', False),
    (('family',), 'ipv4 unicast extra', False),
    (('family',), 'ipv4', False),
    (('family',), 'ipv4 nothing', False),
    (('family',), 'l2vpn unicast', False),
    (('family',), 'bgp-ls unicast', False),
    (('family',), 'all', True),
    (('family',), 'all extra', False),
    # add-path, which only matters with the capability, given by the documents
    *[(('add-path',), f'ipv4 {safi}', True) for safi in ('unicast', 'multicast', 'mpls-vpn', 'rtc', 'flow')],
    (('add-path',), 'ipv6 unicast', True),
    (('add-path',), 'l2vpn evpn', True),
    (('add-path',), 'bgp-ls bgp-ls', True),
    (('add-path',), 'ipv4 unicast limit 1', True),
    (('add-path',), 'ipv4 unicast limit 65535', True),
    (('add-path',), 'ipv4 unicast limit 0', False),
    (('add-path',), 'ipv4 unicast limit 65536', False),
    (('add-path',), 'ipv4 unicast limit x', False),
    (('add-path',), 'ipv4 unicast limit', False),
    (('add-path',), 'ipv4 unicast limit 5 x', False),
    (('add-path',), 'ipv4 unicast extra', False),
    (('add-path',), 'ipv4 UNICAST', False),
    (('add-path',), 'ipv4', False),
    (('add-path',), 'ipv6 rtc', False),
    (('add-path',), 'all', True),
    *[(('add-path',), f'{afi} nothing', False) for afi in ('ipv4', 'ipv6', 'l2vpn', 'bgp-ls')],
    *[(('family',), f'{afi} nothing', False) for afi in ('ipv6', 'l2vpn', 'bgp-ls')],
    (('nexthop',), 'ipv6 unicast ipv6', False),
    # nexthop
    *[
        (('nexthop',), f'ipv4 {safi} ipv6', True)
        for safi in ('unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn')
    ],
    *[
        (('nexthop',), f'ipv6 {safi} ipv4', True)
        for safi in ('unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn')
    ],
    (('nexthop',), 'ipv4 UNICAST IPV6', True),
    (('nexthop',), 'ipv4 unicast ipv4', False),
    (('nexthop',), 'ipv4 flow ipv6', False),
    (('nexthop',), 'ipv4 unicast', False),
    (('nexthop',), 'ipv4', False),
    (('nexthop',), 'ipv4 unicast ipv6 extra', False),
    # capability
    *[
        (('capability',), f'{keyword} {value}', True)
        for keyword in ('asn4', 'route-refresh')
        for value in ('enable', 'require', 'no')
    ],
    *[
        (('capability',), f'{keyword} {value}', True)
        for keyword in ('extended-message', 'operational')
        for value in ('disable', 'REQUIRE')
    ],
    *[
        (('capability',), f'{keyword} {value}', True)
        for keyword in ('software-version', 'nexthop')
        for value in ('enable', 'require')
    ],
    *[
        (('capability',), keyword, True)
        for keyword in ('asn4', 'route-refresh', 'extended-message', 'operational', 'software-version', 'nexthop')
    ],
    (('capability',), 'link-local-nexthop enable', True),
    (('capability',), 'link-local-nexthop require', True),
    (('capability',), 'link-local-nexthop disable', True),
    (('capability',), 'link-local-nexthop', True),  # enable when bare, as every boolean
    *[
        (('capability',), f'{keyword} maybe', False)
        for keyword in (
            'asn4',
            'route-refresh',
            'route-refresh-normal',
            'route-refresh-enhanced',
            'software-version',
            'link-local-nexthop',
        )
    ],
    *[
        (('capability',), f'route-refresh {value}; {keyword} {value}', True)
        for keyword in ('route-refresh-normal', 'route-refresh-enhanced')
        for value in ('enable', 'require', 'disable')
    ],
    (('capability',), 'route-refresh-normal enable', True),
    (('capability',), 'route-refresh-enhanced enable', False),
    (('capability',), 'extended-message maybe', False),
    (('capability',), 'operational maybe', False),
    (('capability',), 'nexthop maybe', False),
    *[
        (('capability',), f'{keyword} {value}', True)
        for keyword in ('multi-session', 'aigp', 'link-local-prefer')
        for value in ('enable', 'no')
    ],
    *[(('capability',), keyword, True) for keyword in ('multi-session', 'aigp', 'link-local-prefer')],
    *[(('capability',), f'{keyword} require', False) for keyword in ('multi-session', 'aigp', 'link-local-prefer')],
    (('capability',), 'graceful-restart', True),
    (('capability',), 'graceful-restart 0', True),
    (('capability',), 'graceful-restart 120', True),
    (('capability',), 'graceful-restart 4095', True),
    (('capability',), 'graceful-restart disable', True),
    (('capability',), 'graceful-restart DISABLED', True),
    (('capability',), 'graceful-restart 4096', False),
    (('capability',), 'graceful-restart -1', False),
    (('capability',), 'graceful-restart enable', False),
    (('capability',), 'multiple-labels 2', True),
    (('capability',), 'multiple-labels 255', True),
    (('capability',), 'multiple-labels disable', True),
    (('capability',), 'multiple-labels DISABLE', True),
    (('capability',), 'multiple-labels 1', False),
    (('capability',), 'multiple-labels 0', False),
    (('capability',), 'multiple-labels 256', False),
    (('capability',), 'multiple-labels enable', False),
    (('capability',), 'multiple-labels', False),
    *[
        (('capability',), f'add-path {mode}', True)
        for mode in ('disable', 'disabled', 'receive', 'send', 'send/receive', 'SEND')
    ],
    (('capability',), 'add-path receive/send', False),
    (('capability',), 'add-path', False),
    (('capability',), 'add-path both', False),
    # api
    (('api',), 'processes [ a ]', True),
    (('api',), 'processes [ a b ]', True),
    (('api',), 'processes [ ]', True),
    (('api',), 'processes a', False),
    (('api',), 'processes [ a', False),
    (('api',), 'processes', False),
    (('api',), 'processes-match [ ^a ]', True),
    (('api',), 'processes-match [ ( ]', False),
    (('api',), 'processes-match a', False),
    *[
        (('api',), f'{keyword} {value}', True)
        for keyword in ('neighbor-changes', 'negotiated', 'fsm', 'signal')
        for value in ENABLES
    ],
    *[(('api',), keyword, True) for keyword in ('neighbor-changes', 'negotiated', 'fsm', 'signal')],
    *[(('api',), f'{keyword} yes', False) for keyword in ('neighbor-changes', 'negotiated', 'fsm', 'signal')],
    *[
        (('api', direction), f'{message} {value}', True)
        for direction in ('send', 'receive')
        for message in (
            'parsed',
            'packets',
            'consolidate',
            'open',
            'update',
            'notification',
            'keepalive',
            'refresh',
            'operational',
        )
        for value in ('true', 'no')
    ],
    *[
        (('api', direction), f'{message} maybe', False)
        for direction in ('send', 'receive')
        for message in (
            'parsed',
            'packets',
            'consolidate',
            'open',
            'update',
            'notification',
            'keepalive',
            'refresh',
            'operational',
        )
    ],
    # tcp-ao: the three mandatory leaves are in the wrapper, see _WRAP
    (('tcp-ao',), 'keyid 0', True),
    (('tcp-ao',), 'keyid 255', True),
    (('tcp-ao',), 'keyid 256', False),
    (('tcp-ao',), 'keyid x', False),
    *[
        (('tcp-ao',), f'algorithm {name}', True)
        for name in ('hmac-sha-1-96', 'aes-128-cmac-96', 'hmac-sha-256', 'HMAC-SHA-256')
    ],
    (('tcp-ao',), 'algorithm md5', False),
    (('tcp-ao',), 'password other', True),
    (('tcp-ao',), 'password "' + 'x' * 81 + '"', False),
    (('tcp-ao',), 'base64 true', False),  # `secret` is not base64
    (('tcp-ao',), 'base64 false', True),
    (('tcp-ao',), 'base64', False),  # true when bare, as `base64 true`: `secret` is not base64
    (('tcp-ao',), 'base64 maybe', False),
    # role, needing an eBGP session the wrapper has
    *[(('role',), f'local {role}', True) for role in ('provider', 'customer', 'peer', 'rs', 'rs-client')],
    (('role',), 'local PROVIDER', False),
    (('role',), 'local nothing', False),
    (('role',), 'strict enable', True),
    (('role',), 'strict disable', True),
    (('role',), 'strict ENABLE', False),
    (('role',), 'strict true', False),
    (('role',), 'add-meta enable', True),
    (('role',), 'add-meta no', False),
    (('role',), 'otc send', False),
    (('role',), 'otc', False),
    # confederation, needing explicit AS numbers the wrapper has
    (('confederation',), 'identifier 65000', True),
    (('confederation',), 'identifier 0', False),
    (('confederation',), 'identifier 65001', False),  # our own AS
    (('confederation',), 'identifier x', False),
    (('confederation',), 'members 65003', True),
    (('confederation',), 'members [ 65003 65004 ]', True),
    (('confederation',), 'members [ 65003, 65004 ]', True),
    (('confederation',), 'members [ ]', True),
    (('confederation',), 'members [ 65000 ]', False),  # the identifier
    (('confederation',), 'members [ 65003', False),
    (('confederation',), 'members x', False),
]

# leaves which take any word at all, so no form of them is refused
ANY_WORD: frozenset[tuple[tuple[str, ...], str]] = frozenset(
    {
        (('neighbor',), 'description'),
        (('neighbor',), 'host-name'),
        (('neighbor',), 'domain-name'),
        # `all` reads nothing; it is refused with another family, see NEIGHBOR_DOCUMENTS
        (('neighbor', 'family'), 'all'),
        (('neighbor', 'add-path'), 'all'),
        # in a route block, a value-less keyword ignores what follows it, and a name is any word
        (('neighbor', 'static', 'route'), 'atomic-aggregate'),
        (('neighbor', 'static', 'route'), 'withdraw'),
        (('neighbor', 'static', 'route'), 'name'),
        # flow actions which take no value, what follows ignored
        (('neighbor', 'l2vpn', 'vpls'), 'atomic-aggregate'),
        (('neighbor', 'l2vpn', 'vpls'), 'withdraw'),
        (('neighbor', 'l2vpn', 'vpls'), 'name'),
        (('neighbor', 'l2vpn'), 'atomic-aggregate'),
        (('neighbor', 'l2vpn'), 'withdraw'),
        (('neighbor', 'l2vpn'), 'name'),
        (('neighbor', 'flow', 'route', 'then'), 'accept'),
        (('neighbor', 'flow', 'route', 'then'), 'discard'),
        (('neighbor', 'flow', 'route', 'then'), 'redirect-to-nexthop-simpson'),
    }
)

_N = 'router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002;'

# whole configurations, for what one statement can not show
NEIGHBOR_DOCUMENTS: list[tuple[str, bool]] = [
    (f'neighbor 127.0.0.1 {{ {_N} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} }} neighbor 127.0.0.2 {{ {_N} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} }} neighbor 127.0.0.1 {{ {_N} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} }} neighbor 127.0.0.1 {{ {_N} local-as 65003; }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} }} neighbor 127.0.0.1 {{ {_N} listen 1790; }}', True),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as 65001; peer-as 65002; }', True),
    ('neighbor 127.0.0.1 { local-as 65001; peer-as 65002; }', False),  # no router-id to take
    ('neighbor 127.0.0.1 { local-address 127.0.0.1; local-as 65001; peer-as 65002; }', True),
    ('neighbor ::1 { local-address ::1; local-as 65001; peer-as 65002; }', False),  # IPv6 needs a router-id
    ('neighbor ::1 { router-id 10.0.0.1; local-address ::1; local-as 65001; peer-as 65002; }', True),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-address 127.0.0.1; peer-as 65002; }', False),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; }', False),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as auto; peer-as auto; }', True),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; listen 1790; local-as 1; peer-as 2; }', False),
    (f'neighbor 127.0.0.0/8 {{ {_N} }}', False),
    (f'neighbor 127.0.0.0/8 {{ {_N} passive; }}', True),
    (f'neighbor 127.0.0.0/8 {{ {_N} passive false; }}', False),
    (f'neighbor nowhere {{ {_N} }}', False),
    (f'neighbor {{ {_N} }}', False),
    (f'neighbor 127.0.0.1 extra {{ {_N} }}', False),  # the word after the name was ignored
    # family blocks
    (f'neighbor 127.0.0.1 {{ {_N} family {{ }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ all; ipv4 unicast; }} }}', False),
    # `all` is every family: with another, in either order, it is refused (after one, it was taken)
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast; all; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ all; all; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast; ipv4 unicast; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 nlri-mpls; ipv4 labeled-unicast; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast; }} family {{ ipv4 unicast; }} }}', True),
    (
        f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast prefix-limit 5; }} family {{ ipv6 unicast prefix-limit 7; }} }}',
        True,
    ),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast prefix-limit 5; }} family {{ ipv6 unicast; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast prefix-limit 5; ipv6 unicast; }} }}', True),
    # add-path, with and without the capability
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} add-path {{ all; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} add-path {{ ipv4 unicast limit 3; }} }}', True),
    (
        f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} family {{ ipv4 unicast; }} add-path {{ ipv6 unicast; }} }}',
        True,
    ),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} add-path {{ all; ipv4 unicast; }} }}', False),
    (
        f'neighbor 127.0.0.1 {{ {_N} capability {{ add-path send; }} add-path {{ ipv4 unicast; ipv4 unicast; }} }}',
        False,
    ),
    (f'neighbor 127.0.0.1 {{ {_N} add-path {{ ipv4 unicast; }} }}', True),
    # nexthop and its capability
    (f'neighbor 127.0.0.1 {{ {_N} nexthop {{ ipv4 unicast ipv6; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} nexthop {{ }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ nexthop disable; }} nexthop {{ ipv4 unicast ipv6; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} family {{ ipv4 unicast; }} nexthop {{ ipv4 unicast ipv6; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} nexthop {{ ipv4 unicast ipv6; ipv4 unicast ipv6; }} }}', False),
    # capability interplay
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ route-refresh; }} adj-rib-out false; }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ graceful-restart; }} hold-time 30; }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ multi-session; }} family {{ ipv4 unicast; ipv6 unicast; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ multi-session; }} family {{ ipv4 unicast; }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} capability {{ asn4 disable; }} capability {{ aigp enable; }} }}', True),
    # link-local
    ('neighbor fe80::2 { router-id 10.0.0.1; local-address fe80::1; local-as 1; peer-as 2; }', False),
    (
        'neighbor fe80::2 { router-id 10.0.0.1; local-address fe80::1; local-as 1; peer-as 2; '
        'capability { link-local-nexthop enable; } }',
        True,
    ),
    (
        'neighbor fe80::2 { router-id 10.0.0.1; local-address fe80::1; local-as 1; peer-as 2; outgoing-ttl 2; '
        'capability { link-local-nexthop enable; } }',
        False,
    ),
    # authentication
    (f'neighbor 127.0.0.1 {{ {_N} md5-password 0123456789abcdef; }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} md5-password c2VjcmV0; md5-base64 true; }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} md5-password "not base64!"; md5-base64 true; }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} md5-password a; tcp-ao {{ keyid 1; algorithm hmac-sha-256; password b; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} tcp-ao {{ keyid 1; algorithm hmac-sha-256; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} tcp-ao {{ }} }}', True),
    ('neighbor 127.0.0.1 { local-as 1; peer-as 2; router-id 10.0.0.1; md5-ip 10.0.0.9; md5-password x; }', True),
    # role and confederation against the AS numbers
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as 1; peer-as 1; role { local provider; } }', False),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as auto; peer-as 1; role { local provider; } }', False),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as 0; peer-as 1; role { local provider; } }', False),
    (f'neighbor 127.0.0.1 {{ {_N} role {{ strict enable; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} role {{ }} }}', False),
    ('neighbor 127.0.0.1 { router-id 10.0.0.1; local-as auto; peer-as 1; confederation { identifier 9; } }', False),
    (f'neighbor 127.0.0.1 {{ {_N} confederation {{ members [ 1 ]; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} confederation {{ }} }}', False),
    # api
    (f'process a {{ run /bin/cat; }} neighbor 127.0.0.1 {{ {_N} api {{ processes [ a ]; }} }}', True),
    # an api naming a process which does not exist is refused: it was accepted, telling no program
    (f'neighbor 127.0.0.1 {{ {_N} api {{ processes [ undefined ]; }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} api x {{ }} api x {{ }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} api x {{ }} }} neighbor 127.0.0.2 {{ {_N} api x {{ }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} api {{ }} api {{ }} }}', True),
    (f'neighbor 127.0.0.1 {{ {_N} api "a b" {{ }} }}', False),
    (
        'process a { run /bin/cat; } process b { run /bin/cat; } '
        f'neighbor 127.0.0.1 {{ {_N} api {{ processes [ a ]; send {{ packets; }} }} api {{ processes [ b ]; receive {{ update; }} }} }}',
        True,
    ),
    (
        'process a1 { run /bin/cat; } '
        f'neighbor 127.0.0.1 {{ {_N} api {{ processes-match [ ^a ]; neighbor-changes; }} }}',
        True,
    ),
    # templates
    (f'template {{ neighbor t {{ hold-time 60; }} }} neighbor 127.0.0.1 {{ inherit t; {_N} }}', True),
    (f'template {{ neighbor t {{ hold-time 60; }} }} neighbor 127.0.0.1 {{ inherit t; {_N} hold-time 30; }}', True),
    (f'neighbor 127.0.0.1 {{ inherit t; {_N} }} template {{ neighbor t {{ hold-time 60; }} }}', True),
    # the neighbor's own local-as wins over the template's: both set it, which was refused
    (f'template {{ neighbor t {{ local-as auto; }} }} neighbor 127.0.0.1 {{ inherit t; {_N} }}', True),
    (
        'template { neighbor t { local-as auto; } } neighbor 127.0.0.1 { inherit t; router-id 10.0.0.1; peer-as 2; }',
        True,
    ),
    (
        'template { neighbor t { family { ipv4 unicast; } } neighbor u { family { ipv6 unicast; } } } '
        f'neighbor 127.0.0.1 {{ inherit [ t u ]; {_N} }}',
        True,
    ),
    (
        'template { neighbor t { family { ipv4 unicast; } } neighbor u { family { ipv6 unicast; } } } '
        f'neighbor 127.0.0.1 {{ inherit [ t u ]; {_N} }} neighbor 127.0.0.2 {{ inherit t; {_N} }}',
        True,
    ),
    (
        'template { neighbor t { family { ipv4 unicast; } } } '
        f'neighbor 127.0.0.1 {{ inherit t; {_N} family {{ ipv6 unicast; }} }}',
        True,
    ),
    (
        'process a { run /bin/cat; } template { neighbor t { capability { route-refresh; } api { processes [ a ]; } } } '
        f'neighbor 127.0.0.1 {{ inherit t; {_N} }} neighbor 127.0.0.2 {{ inherit t; {_N} }}',
        True,  # the api of the template is read once, when the template is
    ),
    (
        'template { neighbor t { confederation { identifier 9; members [ 3 ]; } } } '
        f'neighbor 127.0.0.1 {{ inherit t; {_N} confederation {{ members [ 4 ]; }} }}',
        True,  # the neighbor's members, the template's identifier: both giving members was refused
    ),
    (f'template {{ neighbor t {{ }} neighbor t {{ }} }} neighbor 127.0.0.1 {{ {_N} }}', False),
    (f'template {{ neighbor t {{ }} }} template {{ neighbor t {{ }} }} neighbor 127.0.0.1 {{ {_N} }}', False),
    (f'template {{ neighbor {{ }} }} neighbor 127.0.0.1 {{ {_N} }}', False),
    (f'template {{ neighbor "a b" {{ }} }} neighbor 127.0.0.1 {{ {_N} }}', False),
    (f'template {{ neighbor t {{ peer-address 127.0.0.9; }} }} neighbor 127.0.0.1 {{ inherit t; {_N} }}', True),
    (f'template {{ }} neighbor 127.0.0.1 {{ {_N} }}', True),
    (f'template {{ hold-time 30; }} neighbor 127.0.0.1 {{ {_N} }}', False),
    # sections a neighbor does not have
    (f'neighbor 127.0.0.1 {{ {_N} process {{ }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} unknown {{ }} }}', False),
    (f'neighbor 127.0.0.1 {{ {_N} hold-tim 30; }}', False),
]

# the families the tests negotiate, so an announced route is not refused for its family
_ALL_FAMILIES = 'family { all; }'

# the statements a section needs around the form under test, when it has mandatory ones
SECTION_NEEDS: dict[tuple[str, ...], str] = {
    ('tcp-ao',): 'keyid 1; algorithm hmac-sha-256; password secret;',
    ('role',): 'local provider;',
    ('confederation',): 'identifier 65000;',
    ('add-path',): '',
    ('static', 'route'): 'next-hop 10.0.0.1;',
}
