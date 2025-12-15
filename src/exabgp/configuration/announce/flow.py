"""announce/flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.route import Route

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.settings import FlowSettings

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import (
    RouteBuilder,
    Leaf,
    LeafList,
    ValueType,
    ActionTarget,
    ActionOperation,
    ActionKey,
)
from exabgp.configuration.validator import LegacyParserValidator

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

from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.mpls import route_distinguisher

from exabgp.configuration.flow.parser import interface_set


class AnnounceFlow(ParseAnnounce):
    # Schema for FlowSpec routes using RouteBuilder (no prefix, factory needs AFI)
    schema = RouteBuilder(
        description='FlowSpec route announcement',
        nlri_factory=Flow,
        nlri_class=Flow,
        settings_class=FlowSettings,
        prefix_parser=None,  # FlowSpec has no prefix
        factory_with_afi=True,  # Factory needs (afi, safi, action)
        assign={'rd': 'rd'},  # Map rd command to rd field in settings
        children={
            # Route Distinguisher (for flow-vpn)
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher (for VPN)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=route_distinguisher, name='rd'),
            ),
            # Match components (NLRI APPEND FIELD)
            'source': LeafList(
                type=ValueType.IP_PREFIX,
                description='Source IP prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=source, name='source'),
            ),
            'source-ipv4': LeafList(
                type=ValueType.IP_PREFIX,
                description='Source IPv4 prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=source, name='source-ipv4'),
            ),
            'source-ipv6': LeafList(
                type=ValueType.IP_PREFIX,
                description='Source IPv6 prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=source, name='source-ipv6'),
            ),
            'destination': LeafList(
                type=ValueType.IP_PREFIX,
                description='Destination IP prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=destination, name='destination'),
            ),
            'destination-ipv4': LeafList(
                type=ValueType.IP_PREFIX,
                description='Destination IPv4 prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=destination, name='destination-ipv4'),
            ),
            'destination-ipv6': LeafList(
                type=ValueType.IP_PREFIX,
                description='Destination IPv6 prefix',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=destination, name='destination-ipv6'),
            ),
            'protocol': LeafList(
                type=ValueType.STRING,
                description='IP protocol',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=protocol, name='protocol'),
            ),
            'next-header': LeafList(
                type=ValueType.STRING,
                description='IPv6 next header',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=next_header, name='next-header'),
            ),
            'port': LeafList(
                type=ValueType.INTEGER,
                description='Any port (source or destination)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=any_port, name='port'),
            ),
            'destination-port': LeafList(
                type=ValueType.INTEGER,
                description='Destination port',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=destination_port, name='destination-port'),
            ),
            'source-port': LeafList(
                type=ValueType.INTEGER,
                description='Source port',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=source_port, name='source-port'),
            ),
            'icmp-type': LeafList(
                type=ValueType.INTEGER,
                description='ICMP type',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=icmp_type, name='icmp-type'),
            ),
            'icmp-code': LeafList(
                type=ValueType.INTEGER,
                description='ICMP code',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=icmp_code, name='icmp-code'),
            ),
            'tcp-flags': LeafList(
                type=ValueType.STRING,
                description='TCP flags',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=tcp_flags, name='tcp-flags'),
            ),
            'packet-length': LeafList(
                type=ValueType.INTEGER,
                description='Packet length',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=packet_length, name='packet-length'),
            ),
            'dscp': LeafList(
                type=ValueType.INTEGER,
                description='DSCP value',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=dscp, name='dscp'),
            ),
            'traffic-class': LeafList(
                type=ValueType.INTEGER,
                description='IPv6 traffic class',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=traffic_class, name='traffic-class'),
            ),
            'fragment': LeafList(
                type=ValueType.STRING,
                description='Fragment flags',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=fragment, name='fragment'),
            ),
            'flow-label': LeafList(
                type=ValueType.INTEGER,
                description='IPv6 flow label',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=flow_label, name='flow-label'),
            ),
            # Action components
            'accept': Leaf(
                type=ValueType.BOOLEAN,
                description='Accept traffic (no-op)',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.NOP,
                key=ActionKey.COMMAND,
                validator=LegacyParserValidator(parser_func=accept, name='accept'),
            ),
            'discard': Leaf(
                type=ValueType.BOOLEAN,
                description='Discard traffic',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=discard, name='discard'),
            ),
            'rate-limit': Leaf(
                type=ValueType.INTEGER,
                description='Rate limit in bytes/second',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=rate_limit, name='rate-limit'),
            ),
            'redirect': Leaf(
                type=ValueType.STRING,
                description='Redirect to RT or IP',
                target=ActionTarget.NEXTHOP_ATTRIBUTE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
                validator=LegacyParserValidator(parser_func=redirect, name='redirect'),
            ),
            'redirect-to-nexthop': Leaf(
                type=ValueType.BOOLEAN,
                description='Redirect to next-hop',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=redirect_next_hop, name='redirect-to-nexthop'),
            ),
            'redirect-to-nexthop-ietf': Leaf(
                type=ValueType.BOOLEAN,
                description='Redirect to next-hop (IETF)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=redirect_next_hop_ietf, name='redirect-to-nexthop-ietf'),
            ),
            'copy': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Copy traffic to IP',
                target=ActionTarget.NEXTHOP_ATTRIBUTE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
                validator=LegacyParserValidator(parser_func=copy, name='copy'),
            ),
            'mark': Leaf(
                type=ValueType.INTEGER,
                description='Set DSCP marking',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=mark, name='mark'),
            ),
            'action': Leaf(
                type=ValueType.STRING,
                description='Traffic action (sample|terminal|sample-terminal)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=action, name='action'),
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='BGP community',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=community, name='community'),
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='BGP large community',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=large_community, name='large-community'),
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='BGP extended community',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=extended_community, name='extended-community'),
            ),
            'interface-set': LeafList(
                type=ValueType.STRING,
                description='Interface set',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=interface_set, name='interface-set'),
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute in hex format',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
                validator=LegacyParserValidator(parser_func=attribute, name='attribute'),
            ),
        },
    )

    name = 'flow'

    @property
    def syntax(self) -> str:
        """Syntax generated from schema (FlowSpec format without prefix)."""
        defn = ';\n  '.join(self.schema.definition)
        return f'flow {{\n  <safi> {defn};\n}}'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.to_context(self.name)
        return True

    def post(self) -> bool:
        self.scope.to_context(self.name)
        self.scope.set_value('routes', self.scope.pop('route', {}).get('routes', []))
        self.scope.extend('routes', self.scope.pop('flow', []))
        return True


@ParseAnnounce.register_family(AFI.ipv4, SAFI.flow_ip, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def flow_ip_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceFlow.schema, AFI.ipv4, SAFI.flow_ip)


@ParseAnnounce.register_family(AFI.ipv4, SAFI.flow_vpn, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def flow_vpn_v4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceFlow.schema, AFI.ipv4, SAFI.flow_vpn)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.flow_ip, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def flow_ip_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceFlow.schema, AFI.ipv6, SAFI.flow_ip)


@ParseAnnounce.register_family(AFI.ipv6, SAFI.flow_vpn, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def flow_vpn_v6(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceFlow.schema, AFI.ipv6, SAFI.flow_vpn)
