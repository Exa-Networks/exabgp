# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

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

for show in SHOWs:
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
