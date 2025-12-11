"""match.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType


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


class ParseFlowMatch(Section):
    # Schema definition for FlowSpec match criteria
    # All match fields use NLRI target, APPEND operation, FIELD key
    schema = Container(
        description='FlowSpec match criteria',
        children={
            'source': Leaf(
                type=ValueType.IP_PREFIX,
                description='Source IP prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'source-ipv4': Leaf(
                type=ValueType.IP_PREFIX,
                description='Source IPv4 prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'source-ipv6': Leaf(
                type=ValueType.IP_PREFIX,
                description='Source IPv6 prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'destination': Leaf(
                type=ValueType.IP_PREFIX,
                description='Destination IP prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'destination-ipv4': Leaf(
                type=ValueType.IP_PREFIX,
                description='Destination IPv4 prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'destination-ipv6': Leaf(
                type=ValueType.IP_PREFIX,
                description='Destination IPv6 prefix to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'protocol': Leaf(
                type=ValueType.STRING,
                description='IP protocol to match (IPv4 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'next-header': Leaf(
                type=ValueType.STRING,
                description='Next header to match (IPv6 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'port': Leaf(
                type=ValueType.STRING,
                description='Port range to match (source or destination)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'destination-port': Leaf(
                type=ValueType.STRING,
                description='Destination port range to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'source-port': Leaf(
                type=ValueType.STRING,
                description='Source port range to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'icmp-type': Leaf(
                type=ValueType.INTEGER,
                description='ICMP type to match (IPv6 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'icmp-code': Leaf(
                type=ValueType.INTEGER,
                description='ICMP code to match (IPv6 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'tcp-flags': Leaf(
                type=ValueType.STRING,
                description='TCP flags to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'packet-length': Leaf(
                type=ValueType.STRING,
                description='Packet length range to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'dscp': Leaf(
                type=ValueType.INTEGER,
                description='DSCP value to match',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'traffic-class': Leaf(
                type=ValueType.INTEGER,
                description='Traffic class to match (IPv6 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'fragment': Leaf(
                type=ValueType.STRING,
                description='Fragment flags to match (IPv4 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
            'flow-label': Leaf(
                type=ValueType.STRING,
                description='Flow label to match (IPv6 only)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.APPEND,
                key=ActionKey.FIELD,
            ),
        },
    )
    definition: list[str] = [
        'source 10.0.0.0/24',
        'source ::1/128/0',
        'destination 10.0.1.0/24',
        'port 25',
        'source-port >1024',
        'destination-port [ =80 =3128 >8080&<8088 ]',
        'packet-length [ >200&<300 >400&<500 ]',
        'tcp-flags [ 0x20+0x8+0x1 #name-here ]  # to check',
        '(ipv4 only) protocol [ udp tcp ]',
        '(ipv4 only) fragment [ dont-fragment is-fragment first-fragment last-fragment ]',
        '(ipv6 only) next-header [ udp tcp ]',
        '(ipv6 only) flow-label >100&<2000',
        '(ipv6 only) icmp-type 35  # to check',
        '(ipv6 only) icmp-code 55  # to check',
    ]

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'match {{\n  {joined};\n}}'

    known: dict[str | tuple[Any, ...], object] = {
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
    }

    # action dict removed - derived from schema

    name: str = 'flow/match'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
