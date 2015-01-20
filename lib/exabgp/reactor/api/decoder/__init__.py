# encoding: utf-8
"""
decoder/__init__.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.reactor.api.decoder.text import Text
from exabgp.version import version
from exabgp.logger import Logger


# ====================================================================== Decoder
#

# XXX: FIXME: everything could be static method ?

class Decoder (object):
	_dispatch = {}

	def __init__ (self):
		self.logger = Logger()
		self.format = Text()

	# callaback code

	def register_command (command,storage):
		def closure (function):
			def wrap (*args):
				function(*args)
			storage[command] = wrap
			# order = sorted(storage.keys(),key=len)
			return wrap
		return closure

	def parse_command (self,reactor,service,command):
		for registered in sorted(self._dispatch, reverse=True):
			if registered in command:
				return self._dispatch[registered](self,reactor,service,command)
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False

	#

	@staticmethod
	def extract_neighbors (command):
		"""return a list of neighbor definition : the neighbor definition is a list of string which are in the neighbor indexing string"""
		# This function returns a list and a string
		# The first list contains parsed neighbor to match against our defined peers
		# The string is the command to be run for those peers
		# The parsed neighbor is a list of the element making the neighbor string so each part can be checked against the neighbor name

		returned = []
		neighbor,remaining = command.split(' ',1)
		if neighbor != 'neighbor':
			return [],command

		ip,command = remaining.split(' ',1)
		definition = ['neighbor %s' % (ip)]

		while True:
			try:
				key,value,remaining = command.split(' ',2)
			except ValueError:
				key,value = command.split(' ',1)
			if key == ',':
				returned.append(definition)
				_,command = command.split(' ',1)
				definition = []
				continue
			if key not in ['neighbor','local-ip','local-as','peer-as','router-id','family-allowed']:
				if definition:
					returned.append(definition)
				break
			definition.append('%s %s' % (key,value))
			command = remaining

		return returned,command

	@register_command('shutdown',_dispatch)
	def _shutdown (self,reactor,service,command):
		reactor.api_shutdown()
		reactor.answer(service,'shutdown in progress')
		return True

	@register_command('reload',_dispatch)
	def _reload (self,reactor,service,command):
		reactor.api_reload()
		reactor.answer(service,'reload in progress')
		return True

	@register_command('reload',_dispatch)
	def _restart (self,reactor,service,command):
		reactor.api_restart()
		reactor.answer(service,'restart in progress')
		return True

	@register_command('version',_dispatch)
	def _version (self,reactor,service,command):
		reactor.answer(service,'exabgp %s' % version)
		return True

	# teardown

	@register_command('teardown',_dispatch)
	def _teardown (self,reactor,service,command):
		try:
			descriptions,command = Decoder.extract_neighbors(command)
			_,code = command.split(' ',1)
			for key in reactor.peers:
				for description in descriptions:
					if reactor.match_neighbor(description,key):
						reactor.peers[key].teardown(int(code))
						self.logger.reactor('teardown scheduled for %s' % ' '.join(description))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# show neighbor(s)

	@register_command('show neighbor',_dispatch)
	def _show_neighbor (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for line in str(neighbor).split('\n'):
					reactor.answer(service,line)
					yield True

		reactor.plan(_callback())
		return True

	@register_command('show neighbors',_dispatch)
	def _show_neighbors (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for line in str(neighbor).split('\n'):
					reactor.answer(service,line)
					yield True

		reactor.plan(_callback())
		return True

	# show route(s)

	@register_command('show routes',_dispatch)
	def _show_routes (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for change in list(neighbor.rib.outgoing.sent_changes()):
					reactor.answer(service,'neighbor %s %s' % (neighbor.local_address,str(change.nlri)))
					yield True

		reactor.plan(_callback())
		return True

	@register_command('show routes extensive',_dispatch)
	def _show_routes_extensive (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for change in list(neighbor.rib.outgoing.sent_changes()):
					reactor.answer(service,'neighbor %s %s' % (neighbor.name(),change.extensive()))
					yield True

		reactor.plan(_callback())
		return True

	# watchdogs

	@register_command('announce watchdog',_dispatch)
	def _announce_watchdog (self,reactor,service,command):
		def _callback (name):
			for neighbor in reactor.configuration.neighbor:
				reactor.configuration.neighbor[neighbor].rib.outgoing.announce_watchdog(name)
				yield False
			reactor.route_update = True

		try:
			name = command.split(' ')[2]
		except IndexError:
			name = service
		reactor.plan(_callback(name))
		return True

	@register_command('withdraw watchdog',_dispatch)
	def _withdraw_watchdog (self,reactor,service,command):
		def _callback (name):
			for neighbor in reactor.configuration.neighbor:
				reactor.configuration.neighbor[neighbor].rib.outgoing.withdraw_watchdog(name)
				yield False
			reactor.route_update = True
		try:
			name = command.split(' ')[2]
		except IndexError:
			name = service
		reactor.plan(_callback(name))
		return True

	# flush routes

	@register_command('flush route',_dispatch)
	def _flush_route (self,reactor,service,command):
		def _callback (self,peers):
			self.logger.reactor("Flushing routes for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
			yield True
			reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# route

	@register_command('announce route',_dispatch)
	def _announce_route (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_route(command,nexthops,'announce')
			if not changes:
				self.logger.reactor("Command could not parse route in : %s" % command,'warning')
				yield True
			else:
				peers = []
				for (peer,change) in changes:
					peers.append(peer)
					reactor.configuration.change_to_peers(change,[peer,])
					self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
					yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	@register_command('withdraw route',_dispatch)
	def _withdraw_route (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_route(command,nexthops,'withdraw')
			if not changes:
				self.logger.reactor("Command could not parse route in : %s" % command,'warning')
				yield True
			else:
				for (peer,change) in changes:
					if reactor.configuration.change_to_peers(change,[peer,]):
						self.logger.reactor("Route removed : %s" % change.extensive())
						yield False
					else:
						self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
						yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# vpls

	@register_command('announce vpls',_dispatch)
	def _announce_vpls (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_vpls(command,nexthops,'announce')
			if not changes:
				self.logger.reactor("Command could not parse vpls in : %s" % command,'warning')
				yield True
			else:
				peers = []
				for (peer,change) in changes:
					peers.append(peer)
					reactor.configuration.change_to_peers(change,[peer,])
					self.logger.reactor("vpls added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
					yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	@register_command('withdraw vpls',_dispatch)
	def _withdraw_change (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_vpls(command,nexthops,'withdraw')
			if not changes:
				self.logger.reactor("Command could not parse vpls in : %s" % command,'warning')
				yield True
			else:
				for (peer,change) in changes:
					if reactor.configuration.change_to_peers(change,[peer,]):
						self.logger.reactor("vpls removed : %s" % change.extensive())
						yield False
					else:
						self.logger.reactor("Could not find therefore remove vpls : %s" % change.extensive(),'warning')
						yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# attribute

	@register_command('announce attribute',_dispatch)
	def _announce_attribute (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_attribute(command,nexthops,'announce')
			if not changes:
				self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
				yield True
			else:
				for (peers,change) in changes:
					reactor.configuration.change_to_peers(change,peers)
					self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
				yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	@register_command('withdraw attribute',_dispatch)
	def _withdraw_attribute (self,reactor,service,command):
		def _callback (self,command,nexthops):
			changes = self.format.parse_api_attribute(command,nexthops,'withdraw')
			if not changes:
				self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
				yield True
			else:
				for (peers,change) in changes:
					if reactor.configuration.change_to_peers(change,peers):
						self.logger.reactor("Route removed : %s" % change.extensive())
						yield False
					else:
						self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
						yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,reactor.nexthops(peers)))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# flow

	@register_command('announce flow',_dispatch)
	def _announce_flow (self,reactor,service,command):
		def _callback (self,command,peers):
			changes = self.format.parse_api_flow(command,'announce')
			if not changes:
				self.logger.reactor("Command could not parse flow in : %s" % command)
				yield True
			else:
				for change in changes:
					reactor.configuration.change_to_peers(change,peers)
					self.logger.reactor("Flow added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
					yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	@register_command('withdraw flow',_dispatch)
	def _withdraw_flow (self,reactor,service,command):
		def _callback (self,command,peers):
			changes = self.format.parse_api_flow(command,'withdraw')
			if not changes:
				self.logger.reactor("Command could not parse flow in : %s" % command)
				yield True
			else:
				for change in changes:
					if reactor.configuration.change_to_peers(change,peers):
						self.logger.reactor("Flow found and removed : %s" % change.extensive())
						yield False
					else:
						self.logger.reactor("Could not find therefore remove flow : %s" % change.extensive(),'warning')
						yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# eor

	@register_command('announce eor',_dispatch)
	def _announce_eor (self,reactor,service,command):
		def _callback (self,command,peers):
			family = self.format.parse_api_eor(command)
			if not family:
				self.logger.reactor("Command could not parse eor : %s" % command)
				yield True
			else:
				reactor.configuration.eor_to_peers(family,peers)
				self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',family.extensive()))
				yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# route-refresh

	@register_command('announce route-refresh',_dispatch)
	def _announce_refresh (self,reactor,service,command):
		def _callback (self,command,peers):
			refresh = self.format.parse_api_refresh(command)
			if not refresh:
				self.logger.reactor("Command could not parse flow in : %s" % command)
				yield True
			else:
				reactor.configuration.refresh_to_peers(refresh,peers)
				self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',refresh.extensive()))
				yield False
				reactor.route_update = True

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False

	# operational

	@register_command('operational',_dispatch)
	def _announce_operational (self,reactor,service,command):
		def _callback (self,command,peers):
			operational = self.format.parse_api_operational(command)
			if not operational:
				self.logger.reactor("Command could not parse operational command : %s" % command)
				yield True
			else:
				reactor.configuration.operational_to_peers(operational,peers)
				self.logger.reactor("operational message sent to %s : %s" % (
					', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()
					)
				)
				yield False
				reactor.route_update = True

		if (command.split() + ['safe'])[1].lower() not in ('asm','adm','rpcq','rpcp','apcq','apcp','lpcq','lpcp'):
			return False

		try:
			descriptions,command = Decoder.extract_neighbors(command)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
				return False
			reactor.plan(_callback(self,command,peers))
			return True
		except ValueError:
			return False
		except IndexError:
			return False
