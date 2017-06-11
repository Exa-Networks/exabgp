# encoding: utf-8
"""
icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.enum import Enum

# ============================================================== ICMP Code Field
# http://www.iana.org/assignments/icmp-parameters

class ICMPType (Enum):
	ECHO_REPLY               = 0x00
	DESTINATION_UNREACHEABLE = 0x03
	SOURCE_QUENCH            = 0x04
	REDIRECT                 = 0x05
	ECHO_REQUEST             = 0x08
	ROUTER_ADVERTISEMENT     = 0x09
	ROUTER_SOLICIT           = 0x0A
	TIME_EXCEEDED            = 0x0B
	PARAMETER_PROBLEM        = 0x0C
	TIMESTAMP                = 0x0D
	TIMESTAMP_REPLY          = 0x0E
	INFO_REQUEST             = 0x0F
	INFO_REPLY               = 0x10
	MASK_REQUEST             = 0x11
	MASK_REPLY               = 0x12
	TRACEROUTE               = 0x1E


ICMPType.UNKNOWN = 'unknown icmp type %s'

ICMPType.NAME = {
	ICMPType(ICMPType.ECHO_REPLY):               'echo-reply',
	ICMPType(ICMPType.ECHO_REQUEST):             'echo-request',
	ICMPType(ICMPType.INFO_REPLY):               'info-reply',
	ICMPType(ICMPType.INFO_REQUEST):             'info-request',
	ICMPType(ICMPType.MASK_REPLY):               'mask-reply',
	ICMPType(ICMPType.MASK_REQUEST):             'mask-request',
	ICMPType(ICMPType.PARAMETER_PROBLEM):        'parameter-problem',
	ICMPType(ICMPType.REDIRECT):                 'redirect',
	ICMPType(ICMPType.ROUTER_ADVERTISEMENT):     'router-advertisement',
	ICMPType(ICMPType.ROUTER_SOLICIT):           'router-solicit',
	ICMPType(ICMPType.SOURCE_QUENCH):            'source-quench',
	ICMPType(ICMPType.TIME_EXCEEDED):            'time-exceeded',
	ICMPType(ICMPType.TIMESTAMP):                'timestamp',
	ICMPType(ICMPType.TIMESTAMP_REPLY):          'timestamp-reply',
	ICMPType(ICMPType.DESTINATION_UNREACHEABLE): 'unreachable',
}

ICMPType.VALUE = {
	'echo-reply':               ICMPType(ICMPType.ECHO_REPLY),
	'echo-request':             ICMPType(ICMPType.ECHO_REQUEST),
	'info-reply':               ICMPType(ICMPType.INFO_REPLY),
	'info-request':             ICMPType(ICMPType.INFO_REQUEST),
	'mask-reply':               ICMPType(ICMPType.MASK_REPLY),
	'mask-request':             ICMPType(ICMPType.MASK_REQUEST),
	'parameter-problem':        ICMPType(ICMPType.PARAMETER_PROBLEM),
	'redirect':                 ICMPType(ICMPType.REDIRECT),
	'router-advertisement':     ICMPType(ICMPType.ROUTER_ADVERTISEMENT),
	'router-solicit':           ICMPType(ICMPType.ROUTER_SOLICIT),
	'source-quench':            ICMPType(ICMPType.SOURCE_QUENCH),
	'time-exceeded':            ICMPType(ICMPType.TIME_EXCEEDED),
	'timestamp':                ICMPType(ICMPType.TIMESTAMP),
	'timestamp-reply':          ICMPType(ICMPType.TIMESTAMP_REPLY),
	'unreachable': ICMPType(ICMPType.DESTINATION_UNREACHEABLE),
}


# http://www.iana.org/assignments/icmp-parameters
class ICMPCode (Enum):
	# Destination Unreacheable (type 3)
	NETWORK_UNREACHABLE                   = 0x0
	HOST_UNREACHABLE                      = 0x1
	PROTOCOL_UNREACHABLE                  = 0x2
	PORT_UNREACHABLE                      = 0x3
	FRAGMENTATION_NEEDED                  = 0x4
	SOURCE_ROUTE_FAILED                   = 0x5
	DESTINATION_NETWORK_UNKNOWN           = 0x6
	DESTINATION_HOST_UNKNOWN              = 0x7
	SOURCE_HOST_ISOLATED                  = 0x8
	DESTINATION_NETWORK_PROHIBITED        = 0x9
	DESTINATION_HOST_PROHIBITED           = 0xA
	NETWORK_UNREACHABLE_FOR_TOS           = 0xB
	HOST_UNREACHABLE_FOR_TOS              = 0xC
	COMMUNICATION_PROHIBITED_BY_FILTERING = 0xD
	HOST_PRECEDENCE_VIOLATION             = 0xE
	PRECEDENCE_CUTOFF_IN_EFFECT           = 0xF

	# Redirect (Type 5)
	REDIRECT_FOR_NETWORK                  = 0x0
	REDIRECT_FOR_HOST                     = 0x1
	REDIRECT_FOR_TOS_AND_NET              = 0x2
	REDIRECT_FOR_TOS_AND_HOST             = 0x3

	# Time Exceeded (Type 11)
	TTL_EQ_ZERO_DURING_TRANSIT            = 0x0
	TTL_EQ_ZERO_DURING_REASSEMBLY         = 0x1

	# parameter Problem (Type 12)
	REQUIRED_OPTION_MISSING               = 0x1
	IP_HEADER_BAD                         = 0x2


ICMPCode.UNKNOWN = 'unknown icmp code %s'

ICMPCode.VALUE = {
	'communication-prohibited-by-filtering': ICMPCode(ICMPCode.COMMUNICATION_PROHIBITED_BY_FILTERING),
	'destination-host-prohibited':           ICMPCode(ICMPCode.DESTINATION_HOST_PROHIBITED),
	'destination-host-unknown':              ICMPCode(ICMPCode.DESTINATION_HOST_UNKNOWN),
	'destination-network-prohibited':        ICMPCode(ICMPCode.DESTINATION_NETWORK_PROHIBITED),
	'destination-network-unknown':           ICMPCode(ICMPCode.DESTINATION_NETWORK_UNKNOWN),
	'fragmentation-needed':                  ICMPCode(ICMPCode.FRAGMENTATION_NEEDED),
	'host-precedence-violation':             ICMPCode(ICMPCode.HOST_PRECEDENCE_VIOLATION),
	'host-unreachable':                      ICMPCode(ICMPCode.HOST_UNREACHABLE),
	'host-unreachable-for-tos':              ICMPCode(ICMPCode.HOST_UNREACHABLE_FOR_TOS),
	'ip-header-bad':                         ICMPCode(ICMPCode.IP_HEADER_BAD),
	'network-unreachable':                   ICMPCode(ICMPCode.NETWORK_UNREACHABLE),
	'network-unreachable-for-tos':           ICMPCode(ICMPCode.NETWORK_UNREACHABLE_FOR_TOS),
	'port-unreachable':                      ICMPCode(ICMPCode.PORT_UNREACHABLE),
	'precedence-cutoff-in-effect':           ICMPCode(ICMPCode.PRECEDENCE_CUTOFF_IN_EFFECT),
	'protocol-unreachable':                  ICMPCode(ICMPCode.PROTOCOL_UNREACHABLE),
	'redirect-for-host':                     ICMPCode(ICMPCode.REDIRECT_FOR_HOST),
	'redirect-for-network':                  ICMPCode(ICMPCode.REDIRECT_FOR_NETWORK),
	'redirect-for-tos-and-host':             ICMPCode(ICMPCode.REDIRECT_FOR_TOS_AND_HOST),
	'redirect-for-tos-and-net':              ICMPCode(ICMPCode.REDIRECT_FOR_TOS_AND_NET),
	'required-option-missing':               ICMPCode(ICMPCode.REQUIRED_OPTION_MISSING),
	'source-host-isolated':                  ICMPCode(ICMPCode.SOURCE_HOST_ISOLATED),
	'source-route-failed':                   ICMPCode(ICMPCode.SOURCE_ROUTE_FAILED),
	'ttl-eq-zero-during-reassembly':         ICMPCode(ICMPCode.TTL_EQ_ZERO_DURING_REASSEMBLY),
	'ttl-eq-zero-during-transit':            ICMPCode(ICMPCode.TTL_EQ_ZERO_DURING_TRANSIT),
}

ICMPCode.NAME = {
	ICMPCode(ICMPCode.COMMUNICATION_PROHIBITED_BY_FILTERING): 'communication-prohibited-by-filtering',
	ICMPCode(ICMPCode.DESTINATION_HOST_PROHIBITED):           'destination-host-prohibited',
	ICMPCode(ICMPCode.DESTINATION_HOST_UNKNOWN):              'destination-host-unknown',
	ICMPCode(ICMPCode.DESTINATION_NETWORK_PROHIBITED):        'destination-network-prohibited',
	ICMPCode(ICMPCode.DESTINATION_NETWORK_UNKNOWN):           'destination-network-unknown',
	ICMPCode(ICMPCode.FRAGMENTATION_NEEDED):                  'fragmentation-needed',
	ICMPCode(ICMPCode.HOST_PRECEDENCE_VIOLATION):             'host-precedence-violation',
	ICMPCode(ICMPCode.HOST_UNREACHABLE):                      'host-unreachable',
	ICMPCode(ICMPCode.HOST_UNREACHABLE_FOR_TOS):              'host-unreachable-for-tos',
	ICMPCode(ICMPCode.IP_HEADER_BAD):                         'ip-header-bad',
	ICMPCode(ICMPCode.NETWORK_UNREACHABLE):                   'network-unreachable',
	ICMPCode(ICMPCode.NETWORK_UNREACHABLE_FOR_TOS):           'network-unreachable-for-tos',
	ICMPCode(ICMPCode.PORT_UNREACHABLE):                      'port-unreachable',
	ICMPCode(ICMPCode.PRECEDENCE_CUTOFF_IN_EFFECT):           'precedence-cutoff-in-effect',
	ICMPCode(ICMPCode.PROTOCOL_UNREACHABLE):                  'protocol-unreachable',
	ICMPCode(ICMPCode.REDIRECT_FOR_HOST):                     'redirect-for-host',
	ICMPCode(ICMPCode.REDIRECT_FOR_NETWORK):                  'redirect-for-network',
	ICMPCode(ICMPCode.REDIRECT_FOR_TOS_AND_HOST):             'redirect-for-tos-and-host',
	ICMPCode(ICMPCode.REDIRECT_FOR_TOS_AND_NET):              'redirect-for-tos-and-net',
	ICMPCode(ICMPCode.REQUIRED_OPTION_MISSING):               'required-option-missing',
	ICMPCode(ICMPCode.SOURCE_HOST_ISOLATED):                  'source-host-isolated',
	ICMPCode(ICMPCode.SOURCE_ROUTE_FAILED):                   'source-route-failed',
	ICMPCode(ICMPCode.TTL_EQ_ZERO_DURING_REASSEMBLY):         'ttl-eq-zero-during-reassembly',
	ICMPCode(ICMPCode.TTL_EQ_ZERO_DURING_TRANSIT):            'ttl-eq-zero-during-transit',
}
