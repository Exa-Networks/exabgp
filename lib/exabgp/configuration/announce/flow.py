# encoding: utf-8
"""
announce/flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.flow.parser import source
from exabgp.configuration.flow.parser import destination
from exabgp.configuration.flow.parser import any_port
from exabgp.configuration.flow.parser import source_port
from exabgp.configuration.flow.parser import destination_port
from exabgp.configuration.flow.parser import tcp_flags
from exabgp.configuration.flow.parser import protocol
from exabgp.configuration.flow.parser import next_header
from exabgp.configuration.flow.parser import fragment
from exabgp.configuration.flow.parser import packet_length
from exabgp.configuration.flow.parser import icmp_code
from exabgp.configuration.flow.parser import icmp_type
from exabgp.configuration.flow.parser import dscp
from exabgp.configuration.flow.parser import traffic_class
from exabgp.configuration.flow.parser import flow_label

from exabgp.configuration.flow.parser import accept
from exabgp.configuration.flow.parser import discard
from exabgp.configuration.flow.parser import rate_limit
from exabgp.configuration.flow.parser import redirect
from exabgp.configuration.flow.parser import redirect_next_hop
from exabgp.configuration.flow.parser import redirect_next_hop_ietf
from exabgp.configuration.flow.parser import copy
from exabgp.configuration.flow.parser import mark
from exabgp.configuration.flow.parser import action

from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community

from exabgp.configuration.flow.parser import interface_set

from exabgp.configuration.announce import ParseAnnounce


class AnnounceFlow(ParseAnnounce):
    definition = [
        'source 10.0.0.0/24',
        'source ::1/128/0',
        'destination 10.0.1.0/24',
        'port 25',
        'source-port >1024',
        'destination-port [ =80 =3128 >8080&<8088 ]',
        'packet-length [ >200&<300 >400&<500 ]',
        'tcp-flags [ 0x20+0x8+0x1 #name-here ]  # to check',
        '(ipv4 only) protocol [ udp tcp ]',
        '(ipv4 only) fragment [ not-a-fragment dont-fragment is-fragment first-fragment last-fragment ]',
        '(ipv6 only) next-header [ udp tcp ]',
        '(ipv6 only) flow-label >100&<2000',
        '(ipv6 only) icmp-type 35  # to check',
        '(ipv6 only) icmp-code 55  # to check',
        'accept',
        'discard',
        'rate-limit 9600',
        'redirect 30740:12345',
        'redirect 1.2.3.4:5678',
        'redirect 1.2.3.4',
        'redirect-next-hop',
        'copy 1.2.3.4',
        'mark 123',
        'action sample|terminal|sample-terminal',
    ]

    syntax = 'flow {\n' '  <safi> %s;\n' '}' % ';\n  '.join(definition)

    known = {
        'source': source,
        'source-ipv4': source,
        'source-ipv6': source,
        'destination': destination,
        'destination-ipv4': destination,
        'destination-ipv6': destination,
        'protocol': protocol,
        'next-header': next_header,
        'port': any_port,
        'destination-port': destination_port,
        'source-port': source_port,
        'icmp-type': icmp_type,
        'icmp-code': icmp_code,
        'tcp-flags': tcp_flags,
        'packet-length': packet_length,
        'dscp': dscp,
        'traffic-class': traffic_class,
        'fragment': fragment,
        'flow-label': flow_label,
        'accept': accept,
        'discard': discard,
        'rate-limit': rate_limit,
        'redirect': redirect,
        'redirect-to-nexthop': redirect_next_hop,
        'redirect-to-nexthop-ietf': redirect_next_hop_ietf,
        'copy': copy,
        'mark': mark,
        'action': action,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
        'interface-set': interface_set,
    }

    # 'source-ipv4','destination-ipv4',

    action = {
        'source': 'nlri-add',
        'source-ipv4': 'nlri-add',
        'source-ipv6': 'nlri-add',
        'destination': 'nlri-add',
        'destination-ipv4': 'nlri-add',
        'destination-ipv6': 'nlri-add',
        'port': 'nlri-add',
        'source-port': 'nlri-add',
        'destination-port': 'nlri-add',
        'protocol': 'nlri-add',
        'packet-length': 'nlri-add',
        'tcp-flags': 'nlri-add',
        'next-header': 'nlri-add',
        'fragment': 'nlri-add',
        'icmp-code': 'nlri-add',
        'icmp-type': 'nlri-add',
        'packet-length': 'nlri-add',
        'dscp': 'nlri-add',
        'traffic-class': 'nlri-add',
        'flow-label': 'nlri-add',
        'accept': 'nop',
        'discard': 'attribute-add',
        'rate-limit': 'attribute-add',
        'redirect': 'nexthop-and-attribute',
        'redirect-to-nexthop': 'attribute-add',
        'redirect-to-nexthop-ietf': 'attribute-add',
        'copy': 'nexthop-and-attribute',
        'mark': 'attribute-add',
        'action': 'attribute-add',
        'community': 'attribute-add',
        'large-community': 'attribute-add',
        'extended-community': 'attribute-add',
        'interface-set': 'attribute-add',
    }

    assign = dict()
    default = dict()

    name = 'flow'

    def __init__(self, tokeniser, scope, error, logger):
        ParseAnnounce.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        pass

    def pre(self):
        self.scope.to_context(self.name)
        return True

    def post(self):
        self.scope.to_context(self.name)
        self.scope.set('routes', self.scope.pop('route', {}).get('routes', []))
        self.scope.extend('routes', self.scope.pop('flow', []))
        return True

    def check(self):
        return True


def flow(tokeniser, afi, safi):
    change = Change(Flow(afi, safi, OUT.ANNOUNCE), Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceFlow.action[command]

        if action == 'nlri-add':
            for adding in AnnounceFlow.known[command](tokeniser):
                change.nlri.add(adding)
        elif action == 'attribute-add':
            change.attributes.add(AnnounceFlow.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceFlow.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        elif action == 'nop':
            pass  # yes nothing to do !
        else:
            raise ValueError('flow: unknown command "%s"' % command)

    return [change]


@ParseAnnounce.register('flow', 'extend-name', 'ipv4')
def flow_ip_v4(tokeniser):
    return flow(tokeniser, AFI.ipv4, SAFI.flow_ip)


@ParseAnnounce.register('flow-vpn', 'extend-name', 'ipv4')
def flow_vpn_v4(tokeniser):
    return flow(tokeniser, AFI.ipv4, SAFI.flow_vpn)


@ParseAnnounce.register('flow', 'extend-name', 'ipv6')
def flow_ip_v6(tokeniser):
    return flow(tokeniser, AFI.ipv6, SAFI.flow_ip)


@ParseAnnounce.register('flow-vpn', 'extend-name', 'ipv6')
def flow_vpn_v6(tokeniser):
    return flow(tokeniser, AFI.ipv6, SAFI.flow_vpn)
