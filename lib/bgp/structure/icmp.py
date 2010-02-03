#!/usr/bin/env python
# encoding: utf-8
"""
icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
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
	TIMESTAMP_REQUEST        = 0x0D # wonder why junos call all the other ones _REQUEST but not this one
	TIMESTAMP_REPLY          = 0x0E
	INFO_REQUEST             = 0x0F
	INFO_REPLY               = 0x10
	MASK_REQUEST             = 0x11
	MASK_REPLY               = 0x12
	TRACEROUTE               = 0x1E

	def __str__ (self):
		if self == self.ICMPType.ECHO_REPLY:               return 'echo-reply'
		if self == self.ICMPType.ECHO_REQUEST:             return 'echo-request'
		if self == self.ICMPType.INFO_REPLY:               return 'info-reply'
		if self == self.ICMPType.INFO_REQUEST:             return 'info-request'
		if self == self.ICMPType.MASK_REPLY:               return 'mask-reply'
		if self == self.ICMPType.MASK_REQUEST:             return 'mask-request'
		if self == self.ICMPType.PARAMETER_PROBLEM:        return 'parameter-problem'
		if self == self.ICMPType.REDIRECT:                 return 'redirect'
		if self == self.ICMPType.ROUTER_ADVERTISEMENT:     return 'router-advertisement'
		if self == self.ICMPType.ROUTER_SOLICIT:           return 'router-solicit'
		if self == self.ICMPType.SOURCE_QUENCH:            return 'source-quench'
		if self == self.ICMPType.TIME_EXCEEDED:            return 'time-exceeded'
		if self == self.ICMPType.TIMESTAMP_REQUEST:        return 'timestamp'
		if self == self.ICMPType.TIMESTAMP_REPLY:          return 'timestamp-reply'
		if self == self.ICMPType.DESTINATION_UNREACHEABLE: return 'unreachable'
		return 'invalid icmp type %d' % int.__str__(self)

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
	return ValueError('unknow icmp type %s' % icmp)
