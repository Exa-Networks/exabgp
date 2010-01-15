#!/usr/bin/env python
# encoding: utf-8
"""
icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

# =================================================================== ICMP Code Field

# http://www.iana.org/assignments/icmp-parameters
class ICMP (int):
	ECHO_REPLY               = 0x00
	DESTINATION_UNREACHEABLE = 0x03
	SOURCE_QUENCH            = 0x04
	REDIRECT                 = 0x05
	ECHO                     = 0x08
	TIME_EXCEEDED            = 0x0B
	TRACEROUTE               = 0x1E

