# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message import OUT

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


@Text('#')
def version (self, reactor, service, command):
	self.logger.processes(command.lstrip().lstrip('#').strip())
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
					self.log_message('teardown scheduled for %s' % ' '.join(description))
		reactor.answer(service,'done')
		return True
	except ValueError:
		reactor.answer(service,'error')
		return False
	except IndexError:
		reactor.answer(service,'error')
		return False


@Text('show neighbor')
def show_neighbor (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors[key]
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_neighbor')
	return True


@Text('show neighbors')
def show_neighbors (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors[key]
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_neighbors')
	return True


@Text('show routes')
def show_routes (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'routes':
			neighbors = reactor.configuration.neighbors.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbors.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbors[key]
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.peer_address,str(change.nlri)))
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_routes')
	return True


@Text('show routes extensive')
def show_routes_extensive (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'extensive':
			neighbors = reactor.configuration.neighbors.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbors.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbors[key]
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.name(),change.extensive()))
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_routes_extensive')
	return True


@Text('announce watchdog')
def announce_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor in reactor.configuration.neighbors:
			reactor.configuration.neighbors[neighbor].rib.outgoing.announce_watchdog(name)
			yield False

		reactor.route_update = True
		reactor.answer(service,'done')

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
		for neighbor in reactor.configuration.neighbors:
			reactor.configuration.neighbors[neighbor].rib.outgoing.withdraw_watchdog(name)
			yield False

		reactor.route_update = True
		reactor.answer(service,'done')

	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.plan(callback(name),'withdraw_watchdog')
	return True


@Text('flush route')
def flush_route (self, reactor, service, command):
	def callback (self, peers):
		self.log_message("Flushing routes for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
		yield True

		reactor.route_update = True
		reactor.answer(service,'done')

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.answer(service,'error')
			return False
		reactor.plan(callback(self,peers),'flush_route')
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False


@Text('announce route')
def announce_route (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_route(command,peers)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('route added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'announce_route')
	return True


@Text('withdraw route')
def withdraw_route (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_route(command,peers)

			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.WITHDRAW
				if reactor.configuration.inject_change(peers,change):
					self.log_message('route removed from %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False
				else:
					self.log_failure('route not found on %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the route')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			yield True

	reactor.plan(callback(),'withdraw_route')
	return True


@Text('announce vpls')
def announce_vpls (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_vpls(command,peers)
			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('vpls added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the vpls')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the vpls')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'announce_vpls')
	return True


@Text('withdraw vpls')
def withdraw_vpls (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_vpls(command,peers)

			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.WITHDRAW
				if reactor.configuration.inject_change(peers,change):
					self.log_message('vpls removed from %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False
				else:
					self.log_failure('vpls not found on %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the vpls')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the vpls')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'withdraw_vpls')
	return True


@Text('announce attributes')
def announce_attributes (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_attributes(command,peers)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('route added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'announce_attributes')
	return True


@Text('withdraw attributes')
def withdraw_attribute (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_attributes(command,peers)

			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.WITHDRAW
				if reactor.configuration.inject_change(peers,change):
					self.log_message('route removed from %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False
				else:
					self.log_failure('route not found on %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'withdraw_route')
	return True


@Text('announce flow')
def announce_flow (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_flow(command,peers)
			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('flow added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the flow')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the flow')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'announce_flow')
	return True


@Text('withdraw flow')
def withdraw_flow (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.parser.extract_neighbors(line)
			peers = reactor.match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			changes = self.parser.api_flow(command,peers)

			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for (peers,change) in changes:
				change.nlri.action = OUT.WITHDRAW
				if reactor.configuration.inject_change(peers,change):
					self.log_message('flow removed from %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				else:
					self.log_failure('flow not found on %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.route_update = True
			reactor.answer(service,'done')
		except ValueError:
			self.log_failure('issue parsing the flow')
			reactor.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the flow')
			reactor.answer(service,'error')
			yield True

	reactor.plan(callback(),'withdraw_flow')
	return True


@Text('announce eor')
def announce_eor (self, reactor, service, command):
	def callback (self, command, peers):
		family = self.parser.api_eor(command)
		if not family:
			self.log_failure("Command could not parse eor : %s" % command)
			reactor.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_eor(peers,family)
		self.log_message("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',family.extensive()))
		yield False

		reactor.route_update = True
		reactor.answer(service,'done')

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.answer(service,'error')
			return False
		reactor.plan(callback(self,command,peers),'announce_eor')
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False


@Text('announce route-refresh')
def announce_refresh (self, reactor, service, command):
	def callback (self, command, peers):
		refresh = self.parser.api_refresh(command)
		if not refresh:
			self.log_failure("Command could not parse flow in : %s" % command)
			reactor.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_refresh(peers,refresh)
		self.log_message("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',refresh.extensive()))

		yield False
		reactor.route_update = True
		reactor.answer(service,'done')

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.answer(service,'error')
			return False
		reactor.plan(callback(self,command,peers),'announce_refresh')
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False


@Text('announce operational')
def announce_operational (self, reactor, service, command):
	def callback (self, command, peers):
		operational = self.parser.api_operational(command)
		if not operational:
			self.log_failure("Command could not parse operational command : %s" % command)
			reactor.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_operational(peers,operational)
		self.log_message("operational message sent to %s : %s" % (
			', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()
			)
		)
		yield False
		reactor.route_update = True
		reactor.answer(service,'done')

	if (command.split() + ['be','safe'])[2].lower() not in ('asm','adm','rpcq','rpcp','apcq','apcp','lpcq','lpcp'):
		return False

	try:
		descriptions,command = self.parser.extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.answer(service,'error')
			return False
		reactor.plan(callback(self,command,peers),'announce_operational')
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.answer(service,'error')
		return False
