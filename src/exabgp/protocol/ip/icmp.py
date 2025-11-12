
"""icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, Dict

from exabgp.protocol.resource import Resource


# ============================================================== ICMP Code Field
# https://www.iana.org/assignments/icmp-parameters


class ICMPType(Resource):
    NAME: ClassVar[str] = 'icmp type'

    ECHO_REPLY: ClassVar[int] = 0x00
    UNREACHABLE: ClassVar[int] = 0x03
    REDIRECT: ClassVar[int] = 0x05
    ECHO_REQUEST: ClassVar[int] = 0x08
    ROUTER_ADVERTISEMENT: ClassVar[int] = 0x09
    ROUTER_SOLICIT: ClassVar[int] = 0x0A
    TIME_EXCEEDED: ClassVar[int] = 0x0B
    PARAMETER_PROBLEM: ClassVar[int] = 0x0C
    TIMESTAMP: ClassVar[int] = 0x0D
    TIMESTAMP_REPLY: ClassVar[int] = 0x0E
    PHOTURIS: ClassVar[int] = 0x28
    EXPERIMENTAL_MOBILITY: ClassVar[int] = 0x29
    EXTENDED_ECHO_REQUEST: ClassVar[int] = 0x2A
    EXTENDED_ECHO_REPLY: ClassVar[int] = 0x2B
    EXPERIMENTAL_ONE: ClassVar[int] = 0xFD
    EXPERIMENTAL_TWO: ClassVar[int] = 0xFE

    codes: ClassVar[Dict[str, int]] = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'ECHO_REPLY': ECHO_REPLY,
            'UNREACHABLE': UNREACHABLE,
            'REDIRECT': REDIRECT,
            'ECHO_REQUEST': ECHO_REQUEST,
            'ROUTER_ADVERTISEMENT': ROUTER_ADVERTISEMENT,
            'ROUTER_SOLICIT': ROUTER_SOLICIT,
            'TIME_EXCEEDED': TIME_EXCEEDED,
            'PARAMETER_PROBLEM': PARAMETER_PROBLEM,
            'TIMESTAMP': TIMESTAMP,
            'TIMESTAMP_REPLY': TIMESTAMP_REPLY,
            'PHOTURIS': PHOTURIS,
            'EXPERIMENTAL_MOBILITY': EXPERIMENTAL_MOBILITY,
            'EXTENDED_ECHO_REQUEST': EXTENDED_ECHO_REQUEST,
            'EXTENDED_ECHO_REPLY': EXTENDED_ECHO_REPLY,
            'EXPERIMENTAL_ONE': EXPERIMENTAL_ONE,
            'EXPERIMENTAL_TWO': EXPERIMENTAL_TWO,
        }.items()
    )

    names: ClassVar[Dict[int, str]] = dict([(value, name) for (name, value) in codes.items()])


# https://www.iana.org/assignments/icmp-parameters
class ICMPCode(Resource):
    NAME: ClassVar[str] = 'icmp code'

    # Destination Unreacheable (type 3)
    NETWORK_UNREACHABLE: ClassVar[int] = 0x0
    HOST_UNREACHABLE: ClassVar[int] = 0x1
    PROTOCOL_UNREACHABLE: ClassVar[int] = 0x2
    PORT_UNREACHABLE: ClassVar[int] = 0x3
    FRAGMENTATION_NEEDED: ClassVar[int] = 0x4
    SOURCE_ROUTE_FAILED: ClassVar[int] = 0x5
    DESTINATION_NETWORK_UNKNOWN: ClassVar[int] = 0x6
    DESTINATION_HOST_UNKNOWN: ClassVar[int] = 0x7
    SOURCE_HOST_ISOLATED: ClassVar[int] = 0x8
    DESTINATION_NETWORK_PROHIBITED: ClassVar[int] = 0x9
    DESTINATION_HOST_PROHIBITED: ClassVar[int] = 0xA
    NETWORK_UNREACHABLE_FOR_TOS: ClassVar[int] = 0xB
    HOST_UNREACHABLE_FOR_TOS: ClassVar[int] = 0xC
    COMMUNICATION_PROHIBITED_BY_FILTERING: ClassVar[int] = 0xD
    HOST_PRECEDENCE_VIOLATION: ClassVar[int] = 0xE
    PRECEDENCE_CUTOFF_IN_EFFECT: ClassVar[int] = 0xF

    # Redirect (Type 5)
    REDIRECT_FOR_NETWORK: ClassVar[int] = 0x0
    REDIRECT_FOR_HOST: ClassVar[int] = 0x1
    REDIRECT_FOR_TOS_AND_NET: ClassVar[int] = 0x2
    REDIRECT_FOR_TOS_AND_HOST: ClassVar[int] = 0x3

    # Time Exceeded (Type 11)
    TTL_EQ_ZERO_DURING_TRANSIT: ClassVar[int] = 0x0
    TTL_EQ_ZERO_DURING_REASSEMBLY: ClassVar[int] = 0x1

    # parameter Problem (Type 12)
    REQUIRED_OPTION_MISSING: ClassVar[int] = 0x1
    IP_HEADER_BAD: ClassVar[int] = 0x2

    codes: ClassVar[Dict[str, int]] = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'NETWORK_UNREACHABLE': NETWORK_UNREACHABLE,
            'HOST_UNREACHABLE': HOST_UNREACHABLE,
            'PROTOCOL_UNREACHABLE': PROTOCOL_UNREACHABLE,
            'PORT_UNREACHABLE': PORT_UNREACHABLE,
            'FRAGMENTATION_NEEDED': FRAGMENTATION_NEEDED,
            'SOURCE_ROUTE_FAILED': SOURCE_ROUTE_FAILED,
            'DESTINATION_NETWORK_UNKNOWN': DESTINATION_NETWORK_UNKNOWN,
            'DESTINATION_HOST_UNKNOWN': DESTINATION_HOST_UNKNOWN,
            'SOURCE_HOST_ISOLATED': SOURCE_HOST_ISOLATED,
            'DESTINATION_NETWORK_PROHIBITED': DESTINATION_NETWORK_PROHIBITED,
            'DESTINATION_HOST_PROHIBITED': DESTINATION_HOST_PROHIBITED,
            'NETWORK_UNREACHABLE_FOR_TOS': NETWORK_UNREACHABLE_FOR_TOS,
            'HOST_UNREACHABLE_FOR_TOS': HOST_UNREACHABLE_FOR_TOS,
            'COMMUNICATION_PROHIBITED_BY_FILTERING': COMMUNICATION_PROHIBITED_BY_FILTERING,
            'HOST_PRECEDENCE_VIOLATION': HOST_PRECEDENCE_VIOLATION,
            'PRECEDENCE_CUTOFF_IN_EFFECT': PRECEDENCE_CUTOFF_IN_EFFECT,
            'REDIRECT_FOR_NETWORK': REDIRECT_FOR_NETWORK,
            'REDIRECT_FOR_HOST': REDIRECT_FOR_HOST,
            'REDIRECT_FOR_TOS_AND_NET': REDIRECT_FOR_TOS_AND_NET,
            'REDIRECT_FOR_TOS_AND_HOST': REDIRECT_FOR_TOS_AND_HOST,
            'TTL_EQ_ZERO_DURING_TRANSIT': TTL_EQ_ZERO_DURING_TRANSIT,
            'TTL_EQ_ZERO_DURING_REASSEMBLY': TTL_EQ_ZERO_DURING_REASSEMBLY,
            'REQUIRED_OPTION_MISSING': REQUIRED_OPTION_MISSING,
            'IP_HEADER_BAD': IP_HEADER_BAD,
        }.items()
    )

    # names would have non-unique keys (some codes overlap for different types)

    def __str__(self) -> str:
        return '%d' % int(self)
