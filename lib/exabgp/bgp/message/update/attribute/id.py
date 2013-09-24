# encoding: utf-8
"""
id.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

class AttributeID (int):
	# This should move within the classes and not be here
	# RFC 4271
	ORIGIN             = 0x01
	AS_PATH            = 0x02
	NEXT_HOP           = 0x03
	MED                = 0x04
	LOCAL_PREF         = 0x05
	ATOMIC_AGGREGATE   = 0x06
	AGGREGATOR         = 0x07
	# RFC 1997
	COMMUNITY          = 0x08
	# RFC 4456
	ORIGINATOR_ID      = 0x09
	CLUSTER_LIST       = 0x0A  # 10
	# RFC 4760
	MP_REACH_NLRI      = 0x0E  # 14
	MP_UNREACH_NLRI    = 0x0F  # 15
	# RFC 4360
	EXTENDED_COMMUNITY = 0x10  # 16
	# RFC 4893
	AS4_PATH           = 0x11  # 17
	AS4_AGGREGATOR     = 0x12  # 18
	AIGP               = 0x1A  # 26

	INTERNAL_WITHDRAW  = 0xFFFD
	INTERNAL_WATCHDOG  = 0xFFFE
	INTERNAL_SPLIT     = 0xFFFF

	_str = {
		0x01: 'origin',
		0x02: 'as-path',
		0x03: 'next-hop',
		0x04: 'med',
#		0x04: 'multi-exit-disc',
		0x05: 'local-preference',
		0x06: 'atomic-aggregate',
		0x07: 'aggregator',
		0x08: 'community',
		0x09: 'originator-id',
		0x0a: 'cluster-list',
		0x0e: 'mp-reach-nlri',
		0x0f: 'mp-unreach-nlri',
#		0x0e: 'multi-protocol reacheable nlri'
#		0x0f: 'multi-protocol unreacheable nlri'
		0x10: 'extended-community',
		0x11: 'as4-path',
		0x12: 'as4-aggregator',
		0x1a: 'aigp',
		0xfffd: 'internal-withdraw',
		0xfffe: 'internal-watchdog',
		0xffff: 'internal-split',
	}

	def __str__ (self):
		return self._str.get(self,'unknown-attribute-%s' % hex(self))
