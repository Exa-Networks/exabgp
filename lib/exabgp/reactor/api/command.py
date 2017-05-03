# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import socket

from exabgp.version import version as _version


def _extract_neighbors (command):
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


def shutdown (self, reactor, service, command):
	reactor.api_shutdown()
	reactor.answer(service,'shutdown in progress')
	return True


def reload (self, reactor, service, command):
	reactor.api_reload()
	reactor.answer(service,'reload in progress')
	return True


def restart (self, reactor, service, command):
	reactor.api_restart()
	reactor.answer(service,'restart in progress')
	return True


def version (self, reactor, service, command):
	reactor.answer(service,'exabgp %s' % _version)
	return True

def log (self, reactor, service, command):
	self.logger.processes(command.lstrip().lstrip('#').strip())
	return True

def teardown (self, reactor, service, command):
	try:
		descriptions,command = _extract_neighbors(command)
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


def show_neighbor (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbor.keys():
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True

	reactor.plan(callback())
	return True


def show_neighbors (self, reactor, service, command):
	def callback ():
		for key in reactor.configuration.neighbor.keys():
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			for line in str(neighbor).split('\n'):
				reactor.answer(service,line)
				yield True

	reactor.plan(callback())
	return True


def show_neighbor_status (self, reactor, service, command):
	def callback ():
		for peer_name in reactor.peers.keys():
			peer = reactor.peers.get(peer_name, None)
			if not peer:
				continue
			detailed_status = peer.detailed_link_status()
			families = peer.negotiated_families()
			if families:
				families = "negotiated %s" % families
			reactor.answer(service, "%s %s state %s" % (peer_name, families, detailed_status))
			yield True
		reactor.answer(service,"done")

	reactor.plan(callback())
	return True


def show_routes (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'routes':
			neighbors = reactor.configuration.neighbor.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbor.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.peer_address,str(change.nlri)))
				yield True

	reactor.plan(callback())
	return True


def show_routes_extensive (self, reactor, service, command):
	def callback ():
		last = command.split()[-1]
		if last == 'extensive':
			neighbors = reactor.configuration.neighbor.keys()
		else:
			neighbors = [n for n in reactor.configuration.neighbor.keys() if 'neighbor %s' % last in n]
		for key in neighbors:
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			for change in list(neighbor.rib.outgoing.sent_changes()):
				reactor.answer(service,'neighbor %s %s' % (neighbor.name(),change.extensive()))
				yield True

	reactor.plan(callback())
	return True



def announce_watchdog (self, reactor, service, command):
	def callback (name):
		for key in reactor.configuration.neighbor.keys():
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.announce_watchdog(name)
			yield False
		reactor.route_update = True

	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.plan(callback(name))
	return True


def withdraw_watchdog (self, reactor, service, command):
	def callback (name):
		for key in reactor.configuration.neighbor.keys():
			neighbor = reactor.configuration.neighbor.get(key, None)
			if not neighbor:
				continue
			neighbor.rib.outgoing.withdraw_watchdog(name)
			yield False
		reactor.route_update = True
	try:
		name = command.split(' ')[2]
	except IndexError:
		name = service
	reactor.plan(callback(name))
	return True


def flush_route (self, reactor, service, command):
	def callback (self, peers):
		self.logger.reactor("Flushing routes for %s" % ', '.join(peers if peers else []) if peers is not None else 'all peers')
		for peer_name in peers:
			peer = reactor.peers.get(peer_name, None)
			if not peer:
				continue
			peer.send_new(update=True)
			yield False

	try:
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False


def announce_route (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def withdraw_route (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def announce_vpls (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def withdraw_vpls (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def announce_attribute (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def withdraw_attribute (self, reactor, service, command):
	def callback (self, command, nexthops):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,reactor.nexthops(peers)))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def announce_flow (self, reactor, service, command):
	def callback (self, command, peers):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def withdraw_flow (self, reactor, service, command):
	def callback (self, command, peers):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
	except socket.error:
		return False


def announce_eor (self, reactor, service, command):
	def callback (self, command, peers):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False


def announce_refresh (self, reactor, service, command):
	def callback (self, command, peers):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False


def announce_operational (self, reactor, service, command):
	def callback (self, command, peers):
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
		descriptions,command = _extract_neighbors(command)
		peers = reactor.match_neighbors(descriptions)
		if not peers:
			self.logger.reactor('no neighbor matching the command : %s' % command,'warning')
			return False
		reactor.plan(callback(self,command,peers))
		return True
	except ValueError:
		return False
	except IndexError:
		return False
