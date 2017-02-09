# encoding: utf-8
"""
decoder/__init__.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.reactor.api.decoder.text import Text
from exabgp.reactor.api import command
from exabgp.logger import Logger


# ====================================================================== Decoder
#

# XXX: FIXME: everything could be static method ?

class Decoder (object):
	storage = {}

	def __init__ (self):
		self.logger = Logger()
		self.format = Text()

	# callaback code

	@classmethod
	def register_command (cls, command, function):
		cls.storage[command] = function
		return function

	def parse_command (self, reactor, service, command):
		# it must be reversed so longer command are found before the shorter
		# "show neighbor" should not match "show neighbors"
		for registered in sorted(self.storage, reverse=True):
			if registered in command:
				return self.storage[registered](self,reactor,service,command)
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False


FUNCTION = {
	'shutdown':               'shutdown',
	'reload':                 'reload',
	'restart':                'restart',
	'version':                'version',
	'teardown':               'teardown',
	'show neighbor':          'show_neighbor',
	'show neighbors':         'show_neighbors',
	'show neighbor status':   'show_neighbor_status',
	'show routes':            'show_routes',
	'show routes extensive':  'show_routes_extensive',
	'announce watchdog':      'announce_watchdog',
	'withdraw watchdog':      'withdraw_watchdog',
	'flush route':            'flush_route',
	'announce route':         'announce_route',
	'withdraw route':         'withdraw_route',
	'announce vpls':          'announce_vpls',
	'withdraw vpls':          'withdraw_vpls',
	'announce attribute':     'announce_attribute',
	'withdraw attribute':     'withdraw_attribute',
	'announce flow':          'announce_flow',
	'withdraw flow':          'withdraw_flow',
	'announce eor':           'announce_eor',
	'announce route-refresh': 'announce_refresh',
	'announce operational':   'announce_operational',
	'operational':            'announce_operational',
	'#':                      'log',
}

for name in sorted(FUNCTION.keys()):
	Decoder.register_command(name,getattr(command,FUNCTION[name]))
