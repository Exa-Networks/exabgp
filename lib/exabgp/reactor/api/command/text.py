# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import OUT
from exabgp.configuration.static import ParseStaticRoute

from exabgp.version import version as _version
from exabgp.configuration.environment import environment


class Text (object):
	callback = {}

	def __new__ (cls,name):
		def register (function):
			cls.callback[name] = function
			function.func_name = name.replace(' ','_')
			return function
		return register


def _show_routes_callback(reactor, service, last, route_type, advertised, extensive):
	def callback ():
		families = None
		lines_per_yield = environment.settings().api.chunk
		if last in ('routes', 'extensive', 'static', 'flow', 'l2vpn'):
			peers = list(reactor.peers)
		else:
			peers = [n for n in reactor.peers.keys() if 'neighbor %s' % last in n]
		for key in peers:
			peer = reactor.peers.get(key, None)
			if not peer:
				continue
			if advertised:
				families = peer._outgoing.proto.negotiated.families if peer._outgoing.proto else []
			routes = list(peer.neighbor.rib.outgoing.sent_changes(families))
			while routes:
				changes, routes = routes[:lines_per_yield], routes[lines_per_yield:]
				for change in changes:
					if isinstance(change.nlri, route_type):
						if extensive:
							reactor.answer(service,'neighbor %s %s' % (peer.neighbor.name(),change.extensive()))
						else:
							reactor.answer(service,'neighbor %s %s' % (peer.neighbor.peer_address,str(change.nlri)))
				yield True
		reactor.answer(service,'done')
	return callback


@Text('shutdown')
def shutdown (self, reactor, service, command):
	reactor.answer(service,'shutdown in progress')
	reactor.answer(service,'done')
	return reactor.api.shutdown()


@Text('reload')
def reload (self, reactor, service, command):
	reactor.answer(service,'reload in progress')
	reactor.answer(service,'done')
	return reactor.api.reload()


@Text('restart')
def restart (self, reactor, service, command):
	reactor.answer(service,'restart in progress')
	reactor.answer(service,'done')
	return reactor.api.restart()


@Text('version')
def version (self, reactor, service, command):
	reactor.answer(service,'exabgp %s\n' % _version)
	reactor.answer(service,'done')
	return True


@Text('#')
def comment (self, reactor, service, command):
	self.logger.processes(command.lstrip().lstrip('#').strip())
	reactor.answer(service,'done')
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
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name,None)
			if not neighbor:
				continue
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_neighbor')
	return True


@Text('show neighbors')
def show_neighbors (self, reactor, service, command):
	def callback ():
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name,None)
			if not neighbor:
				continue
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True
		reactor.answer(service,'done')

	reactor.plan(callback(),'show_neighbors')
	return True


@Text('show neighbor status')
def show_neighbor_status (self, reactor, service, command):
	def callback ():
		for peer_name in reactor.peers.keys():
			peer = reactor.peers.get(peer_name, None)
			if not peer:
				continue
			peer_name = peer.neighbor.name()
			detailed_status = peer.detailed_link_status()
			families = peer.negotiated_families()
			if families:
				families = "negotiated %s" % families
			reactor.answer(service, "%s %s state %s" % (peer_name, families, detailed_status))
			yield True
		reactor.answer(service,"done")

	reactor.plan(callback(), 'show_neighbor_status')
	return True


@Text('show routes')
def show_routes (self, reactor, service, command):
	last = command.split()[-1]
	callback = _show_routes_callback(reactor, service, last, NLRI, False, False)
	reactor.plan(callback(),'show_routes')
	return True


@Text('show routes extensive')
def show_routes_extensive (self, reactor, service, command):
	last = command.split()[-1]
	callback = _show_routes_callback(reactor, service, last, NLRI, False, True)
	reactor.plan(callback(),'show_routes_extensive')
	return True


@Text('show routes static')
def show_routes_static (self, reactor, service, command):
	last = command.split()[-1]
	callback = _show_routes_callback(reactor, service, last, INET, True, True)
	reactor.plan(callback(), 'show_routes_static')
	return True


@Text('show routes flow')
def show_routes_flow (self, reactor, service, command):
	last = command.split()[-1]
	callback = _show_routes_callback(reactor, service, last, Flow, True, True)
	reactor.plan(callback(), 'show_routes_flow')
	return True


@Text('show routes l2vpn')
def show_routes_l2vpn (self, reactor, service, command):
	last = command.split()[-1]
	callback = _show_routes_callback(reactor, service, last, (VPLS, EVPN), True, True)
	reactor.plan(callback(), 'show_routes_l2vpn')
	return True


@Text('announce watchdog')
def announce_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.announce_watchdog(name)
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
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.withdraw_watchdog(name)
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
		for peer_name in peers:
			peer = reactor.peers.get(peer_name, None)
			if not peer:
				continue
			peer.send_new(update=True)
			yield False

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

			changes = self.parser.api_route(command)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
				if not ParseStaticRoute.check(change):
					self.log_message('invalid route for %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					continue
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

			changes = self.parser.api_route(command)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
				# Change the action to withdraw before checking the route
				change.nlri.action = OUT.WITHDRAW
				# NextHop is a mandatory field (but we do not require in)
				if change.nlri.nexthop is NoNextHop:
					change.nlri.nexthop = NextHop('0.0.0.0')

				if not ParseStaticRoute.check(change):
					self.log_message('invalid route for %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
					continue
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

			changes = self.parser.api_vpls(command)
			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
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

			changes = self.parser.api_vpls(command)

			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
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

			for change in changes:
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

			for change in changes:
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

			changes = self.parser.api_flow(command)
			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
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

			changes = self.parser.api_flow(command)

			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.answer(service,'error')
				yield True
				return

			for change in changes:
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
			self.log_failure("Command could not parse route-refresh command : %s" % command)
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
		reactor.answer(service,'done')
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
