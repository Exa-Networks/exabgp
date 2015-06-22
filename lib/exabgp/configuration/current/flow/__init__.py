# encoding: utf-8
"""
parse_route.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section


class ParseFlow (Section):
	syntax = \
		'syntax:\n' \
		'flow {\n' \
		'   route give-me-a-name\n' \
		'      route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535; (optional)\n' \
		'      next-hop 1.2.3.4; (to use with redirect-to-nexthop)\n' \
		'      match {\n' \
		'        source 10.0.0.0/24;\n' \
		'        source ::1/128/0;\n' \
		'        destination 10.0.1.0/24;\n' \
		'        port 25;\n' \
		'        source-port >1024\n' \
		'        destination-port =80 =3128 >8080&<8088;\n' \
		'        protocol [ udp tcp ];  (ipv4 only)\n' \
		'        next-header [ udp tcp ]; (ipv6 only)\n' \
		'        fragment [ not-a-fragment dont-fragment is-fragment first-fragment last-fragment ]; (ipv4 only)\n' \
		'        packet-length >200&<300 >400&<500;\n' \
		'        flow-label >100&<2000; (ipv6 only)\n' \
		'      }\n' \
		'      then {\n' \
		'        accept;\n' \
		'        discard;\n' \
		'        rate-limit 9600;\n' \
		'        redirect 30740:12345;\n' \
		'        redirect 1.2.3.4:5678;\n' \
		'        redirect 1.2.3.4;\n' \
		'        redirect-next-hop;\n' \
		'        copy 1.2.3.4;\n' \
		'        mark 123;\n' \
		'        action sample|terminal|sample-terminal;\n' \
		'      }\n' \
		'   }\n' \
		'}\n\n' \
		'one or more match term, one action\n' \
		'fragment code is totally untested\n'

	# _str_bad_flow = "you tried to filter a flow using an invalid port for a component .."

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	# def clear (self):
	# 	self.state = 'out'

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		routes = self.scope.pop(self.name)
		if routes:
			self.scope.extend('routes',routes)
		return True

	def _check (self,configuration):
		self.logger.configuration('warning: no check on flows are implemented')
		return True
