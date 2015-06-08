# encoding: utf-8
"""
json.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# ***********************************
# *******************************
# ***************************
# NOT IN use
# ***************************
# *******************************
# ***********************************

import pprint as pp

from exabgp.configuration.experimental import Configuration

from exabgp.configuration.experimental.show import SectionShow


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
