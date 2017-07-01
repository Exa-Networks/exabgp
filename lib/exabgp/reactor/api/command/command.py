# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import OUT
from exabgp.configuration.static import ParseStaticRoute


class Command (object):
	callback = {
		'text': {},
		'json': {},
	}

	functions = []

	@classmethod
	def register (cls, encoding, name):
		if name not in cls.functions:
			cls.functions.append(name)
			cls.functions.sort(reverse=True)

		def register (function):
			cls.callback[encoding][name] = function
			function.func_name = name.replace(' ','_')
			return function

		return register


@Command.register('text','show neighbor')
def show_neighbor (self, reactor, service, command):
	words = command.split()

	extensive = 'extensive' in words
	configuration = 'configuration' in words
	summary = 'summary' in words

	if summary:
		words.remove('summary')
	if extensive:
		words.remove('extensive')
	if configuration:
		words.remove('configuration')

	limit = words[-1] if words[-1] != 'neighbor' else ''

	def callback_configuration ():
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name,None)
			if not neighbor:
				continue
			if limit and limit not in neighbor_name:
				continue
			for line in str(neighbor).split('\n'):
				reactor.processes.answer(service,line)
				yield True
		reactor.processes.answer_done(service)

	def callback_extensive ():
		for peer_name in reactor.peers.keys():
			peer = reactor.peers.get(peer_name,None)
			if not peer:
				continue
			if limit and limit not in peer.neighbor.name():
				continue
			for line in Neighbor.extensive(peer.cli_data()).split('\n'):
				reactor.processes.answer(service,line)
				yield True
		reactor.processes.answer_done(service)

	def callback_summary ():
		reactor.processes.answer(service,Neighbor.summary_header)
		for peer_name in reactor.peers.keys():
			peer = reactor.peers.get(peer_name,None)
			if not peer:
				continue
			if limit and limit not in peer.neighbor.name():
				continue
			for line in Neighbor.summary(peer.cli_data()).split('\n'):
				reactor.processes.answer(service,line)
				yield True
		reactor.processes.answer_done(service)

	if summary:
		reactor.async.schedule(service,command,callback_summary())
		return True

	if extensive:
		reactor.async.schedule(service,command,callback_extensive())
		return True

	if configuration:
		reactor.async.schedule(service,command,callback_configuration())
		return True

	reactor.processes.answer(service,'please specify summary, extensive or configuration')
	reactor.processes.answer(service,'you can filter by per ip address adding it after the word neighbor')
	reactor.processes.answer_done(service)


# @Command.register('text','show neighbor status')
# def show_neighbor_status (self, reactor, service, command):
# 	def callback ():
# 		for peer_name in reactor.peers.keys():
# 			peer = reactor.peers.get(peer_name, None)
# 			if not peer:
# 				continue
# 			peer_name = peer.neighbor.name()
# 			detailed_status = peer.fsm.name()
# 			families = peer.negotiated_families()
# 			if families:
# 				families = "negotiated %s" % families
# 			reactor.processes.answer(service, "%s %s state %s" % (peer_name, families, detailed_status),force=True)
# 			yield True
# 		reactor.processes.answer(service,"done")
#
# 	reactor.async.schedule(service,command,callback())
# 	return True

@Command.register('text','show adj-rib')
def show_adj_rib (self, reactor, service, command):
	words = command.split()
	extensive = command.endswith(' extensive')
	try:
		rib = words[2]
	except IndexError:
		if words[1] == 'adj-rib-in':
			rib = 'in'
		elif words[1] == 'adj-rib-out':
			rib = 'out'
		else:
			reactor.processes.answer(service,"error")
			return False

	if rib not in ('in','out'):
		reactor.processes.answer(service,"error")
		return False

	klass = NLRI

	if 'inet' in words:
		klass = INET
	elif 'flow' in words:
		klass = Flow
	elif 'l2vpn' in words:
		klass = (VPLS, EVPN)

	for remove in ('show','adj-rib','adj-rib-in','adj-rib-out','in','out','extensive'):
		if remove in words:
			words.remove(remove)
	last = '' if not words else words[0]
	callback = _show_adjrib_callback(reactor, service, last, klass, False, rib, extensive)
	reactor.async.schedule(service,command,callback())
	return True


@Command.register('text','announce watchdog')
def announce_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.announce_watchdog(name)
			yield False

		reactor.schedule_rib_check()
		reactor.processes.answer_done(service)

	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.async.schedule(service,command,callback(name))
	return True


@Command.register('text','withdraw watchdog')
def withdraw_watchdog (self, reactor, service, command):
	def callback (name):
		# XXX: move into Action
		for neighbor_name in reactor.configuration.neighbors.keys():
			neighbor = reactor.configuration.neighbors.get(neighbor_name, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.withdraw_watchdog(name)
			yield False

		reactor.schedule_rib_check()
		reactor.processes.answer_done(service)

	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.async.schedule(service,command,callback(name))
	return True


@Command.register('text','flush adj-rib out')
def flush_adj_rib_out (self, reactor, service, command):
	def callback (self, peers):
		self.log_message("Flushing adjb-rib out for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
		for peer_name in peers:
			peer = reactor.peers.get(peer_name, None)
			if not peer:
				continue
			peer.schedule_rib_check(update=True)
			yield False

		reactor.processes.answer_done(service)

	try:
		descriptions,command = self.extract_neighbors(command)
		peers = match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.processes.answer(service,'error')
			return False
		reactor.async.schedule(service,command,callback(self,peers))
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False


@Command.register('text','announce route')
def announce_route (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_route(command)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
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

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','withdraw route')
def withdraw_route (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_route(command)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
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

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','announce vpls')
def announce_vpls (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_vpls(command)
			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			for change in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('vpls added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the vpls')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the vpls')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','withdraw vpls')
def withdraw_vpls (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_vpls(command)

			if not changes:
				self.log_failure('command could not parse vpls in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
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

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the vpls')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the vpls')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','announce attributes')
def announce_attributes (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_attributes(command,peers)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			for change in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('route added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','withdraw attributes')
def withdraw_attribute (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_attributes(command,peers)
			if not changes:
				self.log_failure('command could not parse route in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
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

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the route')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','announce flow')
def announce_flow (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_flow(command)
			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			for change in changes:
				change.nlri.action = OUT.ANNOUNCE
				reactor.configuration.inject_change(peers,change)
				self.log_message('flow added to %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the flow')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the flow')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','withdraw flow')
def withdraw_flow (self, reactor, service, line):
	def callback ():
		try:
			descriptions,command = self.extract_neighbors(line)
			peers = match_neighbors(descriptions)
			if not peers:
				self.log_failure('no neighbor matching the command : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			changes = self.api_flow(command)

			if not changes:
				self.log_failure('command could not parse flow in : %s' % command,'warning')
				reactor.processes.answer(service,'error')
				yield True
				return

			for change in changes:
				change.nlri.action = OUT.WITHDRAW
				if reactor.configuration.inject_change(peers,change):
					self.log_message('flow removed from %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				else:
					self.log_failure('flow not found on %s : %s' % (', '.join(peers) if peers else 'all peers',change.extensive()))
				yield False

			reactor.schedule_rib_check()
			reactor.processes.answer_done(service)
		except ValueError:
			self.log_failure('issue parsing the flow')
			reactor.processes.answer(service,'error')
			yield True
		except IndexError:
			self.log_failure('issue parsing the flow')
			reactor.processes.answer(service,'error')
			yield True

	reactor.async.schedule(service,line,callback())
	return True


@Command.register('text','announce eor')
def announce_eor (self, reactor, service, command):
	def callback (self, command, peers):
		family = self.api_eor(command)
		if not family:
			self.log_failure("Command could not parse eor : %s" % command)
			reactor.processes.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_eor(peers,family)
		self.log_message("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',family.extensive()))
		yield False

		reactor.schedule_rib_check()
		reactor.processes.answer_done(service)

	try:
		descriptions,command = self.extract_neighbors(command)
		peers = match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.processes.answer(service,'error')
			return False
		reactor.async.schedule(service,command,callback(self,command,peers))
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False


@Command.register('text','announce route-refresh')
def announce_refresh (self, reactor, service, command):
	def callback (self, command, peers):
		refresh = self.api_refresh(command)
		if not refresh:
			self.log_failure("Command could not parse route-refresh command : %s" % command)
			reactor.processes.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_refresh(peers,refresh)
		self.log_message("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',refresh.extensive()))

		yield False
		reactor.schedule_rib_check()
		reactor.processes.answer_done(service)

	try:
		descriptions,command = self.extract_neighbors(command)
		peers = match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.processes.answer(service,'error')
			return False
		reactor.async.schedule(service,command,callback(self,command,peers))
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False


@Command.register('text','announce operational')
def announce_operational (self, reactor, service, command):
	def callback (self, command, peers):
		operational = self.api_operational(command)
		if not operational:
			self.log_failure("Command could not parse operational command : %s" % command)
			reactor.processes.answer(service,'error')
			yield True
			return

		reactor.configuration.inject_operational(peers,operational)
		self.log_message("operational message sent to %s : %s" % (
			', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()
			)
		)
		yield False
		reactor.schedule_rib_check()
		reactor.processes.answer_done(service)

	if (command.split() + ['be','safe'])[2].lower() not in ('asm','adm','rpcq','rpcp','apcq','apcp','lpcq','lpcp'):
		reactor.processes.answer_done(service)
		return False

	try:
		descriptions,command = self.extract_neighbors(command)
		peers = match_neighbors(descriptions)
		if not peers:
			self.log_failure('no neighbor matching the command : %s' % command,'warning')
			reactor.processes.answer(service,'error')
			return False
		reactor.async.schedule(service,command,callback(self,command,peers))
		return True
	except ValueError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False
	except IndexError:
		self.log_failure('issue parsing the command')
		reactor.processes.answer(service,'error')
		return False
