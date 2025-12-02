"""vpls.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.core import Section
from exabgp.configuration.schema import Container, Leaf, LeafList, ValueType

from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw

from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.l2vpn.parser import vpls
from exabgp.configuration.l2vpn.parser import vpls_endpoint
from exabgp.configuration.l2vpn.parser import vpls_size
from exabgp.configuration.l2vpn.parser import vpls_offset
from exabgp.configuration.l2vpn.parser import vpls_base
from exabgp.configuration.l2vpn.parser import next_hop


class ParseVPLS(Section):
    # Schema definition for VPLS configuration
    schema = Container(
        description='VPLS configuration',
        children={
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                action='nlri-set',
            ),
            'endpoint': Leaf(
                type=ValueType.INTEGER,
                description='VPLS endpoint ID',
                action='nlri-set',
            ),
            'base': Leaf(
                type=ValueType.INTEGER,
                description='Label base',
                action='nlri-set',
            ),
            'offset': Leaf(
                type=ValueType.INTEGER,
                description='Block offset',
                action='nlri-set',
            ),
            'size': Leaf(
                type=ValueType.INTEGER,
                description='Block size',
                action='nlri-set',
            ),
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address',
                action='nlri-set',
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute',
                action='attribute-add',
            ),
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                choices=['igp', 'egp', 'incomplete'],
                action='attribute-add',
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                action='attribute-add',
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                action='attribute-add',
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                action='attribute-add',
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                action='attribute-add',
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator',
                action='attribute-add',
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID',
                action='attribute-add',
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list',
                action='attribute-add',
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                action='attribute-add',
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                action='attribute-add',
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name',
                action='attribute-add',
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix',
                action='attribute-add',
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name',
                action='attribute-add',
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark for withdrawal',
                action='attribute-add',
            ),
        },
    )
    definition = [
        'endpoint <vpls endpoint id; integer>',
        'base <label base; integer>',
        'offset <block offet; interger>',
        'size <block size; integer>',
        'next-hop <ip>',
        'med <16 bits number>',
        'route-distinguisher|rd <ipv4>:<port>|<16bits number>:<32bits number>|<32bits number>:<16bits number>',
        'origin IGP|EGP|INCOMPLETE',
        'as-path [ <asn>.. ]',
        'local-preference <16 bits number>',
        'atomic-aggregate',
        'community <16 bits number>',
        'extended-community target:<16 bits number>:<ipv4 formated number>',
        'originator-id <ipv4>',
        'cluster-list <ipv4>',
        'label <15 bits number>',
        'attribute [ generic attribute format ]name <mnemonic>',
        'split /<mask>',
        'watchdog <watchdog-name>',
        'withdraw',
    ]

    syntax = 'vpls {{\n  {}\n}}'.format(' ;\n  '.join(definition))

    known = {
        'rd': route_distinguisher,
        'attribute': attribute,
        'next-hop': next_hop,
        'origin': origin,
        'med': med,
        'as-path': as_path,
        'local-preference': local_preference,
        'atomic-aggregate': atomic_aggregate,
        'aggregator': aggregator,
        'originator-id': originator_id,
        'cluster-list': cluster_list,
        'community': community,
        'extended-community': extended_community,
        'name': named,
        'split': split,
        'watchdog': watchdog,
        'withdraw': withdraw,
        'endpoint': vpls_endpoint,
        'offset': vpls_offset,
        'size': vpls_size,
        'base': vpls_base,
    }

    action = {
        'attribute': 'attribute-add',
        'origin': 'attribute-add',
        'med': 'attribute-add',
        'as-path': 'attribute-add',
        'local-preference': 'attribute-add',
        'atomic-aggregate': 'attribute-add',
        'aggregator': 'attribute-add',
        'originator-id': 'attribute-add',
        'cluster-list': 'attribute-add',
        'community': 'attribute-add',
        'extended-community': 'attribute-add',
        'name': 'attribute-add',
        'split': 'attribute-add',
        'watchdog': 'attribute-add',
        'withdraw': 'attribute-add',
        'next-hop': 'nlri-set',
        'route-distinguisher': 'nlri-set',
        'rd': 'nlri-set',
        'endpoint': 'nlri-set',
        'offset': 'nlri-set',
        'size': 'nlri-set',
        'base': 'nlri-set',
    }

    assign = {
        'next-hop': 'nexthop',
        'rd': 'rd',
        'route-distinguisher': 'rd',
        'endpoint': 'endpoint',
        'offset': 'offset',
        'size': 'size',
        'base': 'base',
    }

    name = 'l2vpn/vpls'

    def __init__(self, parser, scope, error):
        Section.__init__(self, parser, scope, error)

    def clear(self):
        pass

    def pre(self):
        self.scope.append_route(vpls(self.parser.tokeniser))
        return True

    def post(self):
        return self._check()

    def _check(self):
        feedback = self.scope.get_route().feedback()
        if feedback:
            return self.error.set(feedback)
        return True
