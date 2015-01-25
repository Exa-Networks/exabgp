# encoding: utf-8
"""
json.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# from exabgp.configuration.ancient import Configuration
# from exabgp.configuration.format import formated
#
# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI
# from exabgp.protocol.family import Family
# from exabgp.protocol.ip import IP
# from exabgp.bgp.message import OUT
#
# from exabgp.bgp.message.update.nlri.prefix import Prefix
# from exabgp.bgp.message.update.nlri.mpls import MPLS
# from exabgp.bgp.message.refresh import RouteRefresh
# from exabgp.bgp.message.operational import Advisory
# from exabgp.bgp.message.operational import Query
# from exabgp.bgp.message.operational import Response
#
# from exabgp.rib.change import Change
# from exabgp.version import version
# from exabgp.logger import Logger

import pprint as pp

from exabgp.configuration import Configuration

from exabgp.configuration.show import SectionShow


def parse (command):
	conf = Configuration()
	conf.register(SectionShow,['show'])
	return conf.parse_string(command)

SHOWS = [
	'show { version }',
]

for show in SHOWS:
	parsed = parse(show)
	print '--'
	print 'command:',show
	for section in parsed.keys():
		d = parsed[section]
		for k,v in d.items():
			print 'section %s name %s ' % (section,k)
			pp.pprint(v)
			print
		print
