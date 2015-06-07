# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.version import version as _version


class Text (object):
	callback = {}

	def __new__ (cls,name):
		def register (function):
			cls.callback[name] = function
			return function
		return register


@Text('shutdown')
def shutdown (self, reactor, service, command):
	reactor.answer(service,'shutdown in progress')
	return reactor.api.shutdown()


@Text('reload')
def reload (self, reactor, service, command):
	reactor.answer(service,'reload in progress')
	return reactor.api.reload()


@Text('restart')
def restart (self, reactor, service, command):
	reactor.answer(service,'restart in progress')
	return reactor.api.restart()


@Text('version')
def version (self, reactor, service, command):
	reactor.answer(service,'exabgp %s\n' % _version)
	return True


@Text('teardown')
def teardown (self, reactor, service, command):
	try:
		descriptions,command = self.parser.extract_neighbors(command)
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


@Text('show neighbor')
def show_neighbor (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbor.neighbors.keys():
			neighbor = reactor.configuration.neighbor.neighbors[key]
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True

	reactor.plan(callback(),'show_neighbor')
	return True


@Text('show neighbors')
def show_neighbors (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbor.neighbors.keys():
			neighbor = reactor.configuration.neighbor.neighbors[key]
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True

	reactor.plan(callback(),'show_neighbors')
	return True


@Text('show routes')
def show_routes (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'routes':
			neighbors = reactor.configuration.neighbor.neighbors.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbor.neighbors.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbor.neighbors[key]
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.local_address,str(change.nlri)))
				yield True

	reactor.plan(callback(),'show_routes')
	return True


@Text('show routes extensive')
def show_routes_extensive (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'extensive':
			neighbors = reactor.configuration.neighbor.neighbors.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbor.neighbors.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbor.neighbors[key]
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.name(),change.extensive()))
				yield True

	reactor.plan(callback(),'show_routes_extensive')
	return True



@Text('announce watchdog')
def announce_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor in reactor.configuration.neighbor.neighbors:
			reactor.configuration.neighbor.neighbors[neighbor].rib.outgoing.announce_watchdog(name)
			yield False
		reactor.route_update = True

	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.plan(callback(name),'announce_watchdog')
	return True


@Text('withdraw watchdog')
def withdraw_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor in reactor.configuration.neighbor.neighbors:
			reactor.configuration.neighbor.neighbors[neighbor].rib.outgoing.withdraw_watchdog(name)
			yield False
		reactor.route_update = True
	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.plan(callback(name),'withdraw_watchdog')
	return True


@Text('flush route')
def flush_route (self, reactor, service, command):
	def callback (self, peers):
		self.logger.reactor("Flushing routes for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
		yield True
		reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,peers),'flush_route')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce route')
def announce_route (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_route(command,nexthops,'announce')
		if not changes:
			self.logger.reactor("Command could not parse route in : %s" % command,'warning')
			yield True
		else:
			peers = []
			for (peer,change) in changes:
				peers.append(peer)
				reactor.api.change_to_peers(change,[peer,])
				self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
				yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'announce_route')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('withdraw route')
def withdraw_route (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_route(command,nexthops,'withdraw')
		if not changes:
			self.logger.reactor("Command could not parse route in : %s" % command,'warning')
			yield True
		else:
			for (peer,change) in changes:
				if reactor.api.change_to_peers(change,[peer,]):
					self.logger.reactor("Route removed : %s" % change.extensive())
					yield False
				else:
					self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
					yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'withdraw_route')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce vpls')
def announce_vpls (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_vpls(command,nexthops,'announce')
		if not changes:
			self.logger.reactor("Command could not parse vpls in : %s" % command,'warning')
			yield True
		else:
			peers = []
			for (peer,change) in changes:
				peers.append(peer)
				reactor.api.change_to_peers(change,[peer,])
				self.logger.reactor("vpls added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
				yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'announce_vpls')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('withdraw vpls')
def withdraw_vpls (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_vpls(command,nexthops,'withdraw')
		if not changes:
			self.logger.reactor("Command could not parse vpls in : %s" % command,'warning')
			yield True
		else:
			for (peer,change) in changes:
				if reactor.api.change_to_peers(change,[peer,]):
					self.logger.reactor("vpls removed : %s" % change.extensive())
					yield False
				else:
					self.logger.reactor("Could not find therefore remove vpls : %s" % change.extensive(),'warning')
					yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'withdraw_vpls')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce attribute')
def announce_attribute (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_attribute(command,nexthops,'announce')
		if not changes:
			self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
			yield True
		else:
			for (peers,change) in changes:
				reactor.api.change_to_peers(change,peers)
				self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
			yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'announce_attribute')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('withdraw attribute')
def withdraw_attribute (self, reactor, service, command):
	def callback (self, command, nexthops):
		changes = self.parser.api_attribute(command,nexthops,'withdraw')
		if not changes:
			self.logger.reactor("Command could not parse attribute in : %s" % command,'warning')
			yield True
		else:
			for (peers,change) in changes:
				if reactor.api.change_to_peers(change,peers):
					self.logger.reactor("Route removed : %s" % change.extensive())
					yield False
				else:
					self.logger.reactor("Could not find therefore remove route : %s" % change.extensive(),'warning')
					yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)),'withdraw_attribute')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce flow')
def announce_flow (self, reactor, service, command):
	def callback (self, command, peers):
		changes = self.parser.api_flow(command,'announce')
		if not changes:
			self.logger.reactor("Command could not parse flow in : %s" % command)
			yield True
		else:
			for change in changes:
				reactor.api.change_to_peers(change,peers)
				self.logger.reactor("Flow added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
				yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers),'announce_flow')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('withdraw flow')
def withdraw_flow (self, reactor, service, command):
	def callback (self, command, peers):
		changes = self.parser.api_flow(command,'withdraw')
		if not changes:
			self.logger.reactor("Command could not parse flow in : %s" % command)
			yield True
		else:
			for change in changes:
				if reactor.api.change_to_peers(change,peers):
					self.logger.reactor("Flow found and removed : %s" % change.extensive())
					yield False
				else:
					self.logger.reactor("Could not find therefore remove flow : %s" % change.extensive(),'warning')
					yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers),'withdraw_flow')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce eor')
def announce_eor (self, reactor, service, command):
	def callback (self, command, peers):
		family = self.parser.api_eor(command)
		if not family:
			self.logger.reactor("Command could not parse eor : %s" % command)
			yield True
		else:
			reactor.api.eor_to_peers(family,peers)
			self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',family.extensive()))
			yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers),'announce_eor')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce route-refresh')
def announce_refresh (self, reactor, service, command):
	def callback (self, command, peers):
		refresh = self.parser.api_refresh(command)
		if not refresh:
			self.logger.reactor("Command could not parse flow in : %s" % command)
			yield True
		else:
			reactor.api.refresh_to_peers(refresh,peers)
			self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',refresh.extensive()))
			yield False
			reactor.route_update = True

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers),'announce_refresh')
		return True
	except ValueError:
		return False
	except IndexError:
		return False


@Text('announce operational')
def announce_operational (self, reactor, service, command):
	def callback (self, command, peers):
		operational = self.parser.api_operational(command)
		if not operational:
			self.logger.reactor("Command could not parse operational command : %s" % command)
			yield True
		else:
			reactor.api.operational_to_peers(operational,peers)
			self.logger.reactor("operational message sent to %s : %s" % (
				', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()
				)
			)
			yield False
			reactor.route_update = True

	if (command.split() + ['be','safe'])[2].lower() not in ('asm','adm','rpcq','rpcp','apcq','apcp','lpcq','lpcp'):
		return False

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers),'announce_operational')
		return True
	except ValueError:
		return False
	except IndexError:
		return False
