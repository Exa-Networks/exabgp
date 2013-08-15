# encoding: utf-8
"""
icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

# =================================================================== ICMP Code Field

# http://www.iana.org/assignments/icmp-parameters
class ICMPType (int):
	ECHO_REPLY               = 0x00
	DESTINATION_UNREACHEABLE = 0x03
	SOURCE_QUENCH            = 0x04
	REDIRECT                 = 0x05
	ECHO_REQUEST             = 0x08
	ROUTER_ADVERTISEMENT     = 0x09
	ROUTER_SOLICIT           = 0x0A
	TIME_EXCEEDED            = 0x0B
	PARAMETER_PROBLEM        = 0x0C
	TIMESTAMP_REQUEST        = 0x0D  # wonder why junos call all the other ones _REQUEST but not this one
	TIMESTAMP_REPLY          = 0x0E
	INFO_REQUEST             = 0x0F
	INFO_REPLY               = 0x10
	MASK_REQUEST             = 0x11
	MASK_REPLY               = 0x12
	TRACEROUTE               = 0x1E

	def __str__ (self):
		if self == ICMPType.ECHO_REPLY:               return 'echo-reply'
		if self == ICMPType.ECHO_REQUEST:             return 'echo-request'
		if self == ICMPType.INFO_REPLY:               return 'info-reply'
		if self == ICMPType.INFO_REQUEST:             return 'info-request'
		if self == ICMPType.MASK_REPLY:               return 'mask-reply'
		if self == ICMPType.MASK_REQUEST:             return 'mask-request'
		if self == ICMPType.PARAMETER_PROBLEM:        return 'parameter-problem'
		if self == ICMPType.REDIRECT:                 return 'redirect'
		if self == ICMPType.ROUTER_ADVERTISEMENT:     return 'router-advertisement'
		if self == ICMPType.ROUTER_SOLICIT:           return 'router-solicit'
		if self == ICMPType.SOURCE_QUENCH:            return 'source-quench'
		if self == ICMPType.TIME_EXCEEDED:            return 'time-exceeded'
		if self == ICMPType.TIMESTAMP_REQUEST:        return 'timestamp'
		if self == ICMPType.TIMESTAMP_REPLY:          return 'timestamp-reply'
		if self == ICMPType.DESTINATION_UNREACHEABLE: return 'unreachable'
		return 'invalid icmp type %d' % int(self)

def NamedICMPType (name):
	icmp = name.lower()
	if icmp == 'echo-reply':          return ICMPType.ECHO_REPLY
	if icmp == 'echo-request':        return ICMPType.ECHO_REQUEST
	if icmp == 'info-reply':          return ICMPType.INFO_REPLY
	if icmp == 'info-request':        return ICMPType.INFO_REQUEST
	if icmp == 'mask-reply':          return ICMPType.MASK_REPLY
	if icmp == 'mask-request':        return ICMPType.MASK_REQUEST
	if icmp == 'parameter-problem':   return ICMPType.PARAMETER_PROBLEM
	if icmp == 'redirect':            return ICMPType.REDIRECT
	if icmp == 'router-advertisement':return ICMPType.ROUTER_ADVERTISEMENT
	if icmp == 'router-solicit':      return ICMPType.ROUTER_SOLICIT
	if icmp == 'source-quench':       return ICMPType.SOURCE_QUENCH
	if icmp == 'time-exceeded':       return ICMPType.TIME_EXCEEDED
	if icmp == 'timestamp':           return ICMPType.TIMESTAMP_REQUEST
	if icmp == 'timestamp-reply':     return ICMPType.TIMESTAMP_REPLY
	if icmp == 'unreachable':         return ICMPType.DESTINATION_UNREACHEABLE
	raise ValueError('unknow icmp type %s' % icmp)


# http://www.iana.org/assignments/icmp-parameters
class ICMPCode (int):
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

	def __str__ (self):
		return 'icmp code %d' % int(self)

def NamedICMPCode (name):
	icmp = name.lower()
	if icmp == 'communication-prohibited-by-filtering': return ICMPCode.COMMUNICATION_PROHIBITED_BY_FILTERING
	if icmp == 'destination-host-prohibited':           return ICMPCode.DESTINATION_HOST_PROHIBITED
	if icmp == 'destination-host-unknown':              return ICMPCode.DESTINATION_HOST_UNKNOWN
	if icmp == 'destination-network-prohibited':        return ICMPCode.DESTINATION_NETWORK_PROHIBITED
	if icmp == 'destination-network-unknown':           return ICMPCode.DESTINATION_NETWORK_UNKNOWN
	if icmp == 'fragmentation-needed':                  return ICMPCode.FRAGMENTATION_NEEDED
	if icmp == 'host-precedence-violation':             return ICMPCode.HOST_PRECEDENCE_VIOLATION
	if icmp == 'host-unreachable':                      return ICMPCode.HOST_UNREACHABLE
	if icmp == 'host-unreachable-for-tos':              return ICMPCode.HOST_UNREACHABLE_FOR_TOS
	if icmp == 'ip-header-bad':                         return ICMPCode.IP_HEADER_BAD
	if icmp == 'network-unreachable':                   return ICMPCode.NETWORK_UNREACHABLE
	if icmp == 'network-unreachable-for-tos':           return ICMPCode.NETWORK_UNREACHABLE_FOR_TOS
	if icmp == 'port-unreachable':                      return ICMPCode.PORT_UNREACHABLE
	if icmp == 'precedence-cutoff-in-effect':           return ICMPCode.PRECEDENCE_CUTOFF_IN_EFFECT
	if icmp == 'protocol-unreachable':                  return ICMPCode.PROTOCOL_UNREACHABLE
	if icmp == 'redirect-for-host':                     return ICMPCode.REDIRECT_FOR_HOST
	if icmp == 'redirect-for-network':                  return ICMPCode.REDIRECT_FOR_NETWORK
	if icmp == 'redirect-for-tos-and-host':             return ICMPCode.REDIRECT_FOR_TOS_AND_HOST
	if icmp == 'redirect-for-tos-and-net':              return ICMPCode.REDIRECT_FOR_TOS_AND_NET
	if icmp == 'required-option-missing':               return ICMPCode.REQUIRED_OPTION_MISSING
	if icmp == 'source-host-isolated':                  return ICMPCode.SOURCE_HOST_ISOLATED
	if icmp == 'source-route-failed':                   return ICMPCode.SOURCE_ROUTE_FAILED
	if icmp == 'ttl-eq-zero-during-reassembly':         return ICMPCode.TTL_EQ_ZERO_DURING_REASSEMBLY
	if icmp == 'ttl-eq-zero-during-transit':            return ICMPCode.TTL_EQ_ZERO_DURING_TRANSIT
	raise ValueError('unknow icmp-code %s' % icmp)
