# encoding: utf-8
"""
decoding.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# This is to break a circular depency chain
# http://en.wikipedia.org/wiki/Dependency_injection
from exabgp.configuration.ancient import Configuration
from exabgp.configuration.ancient import formated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.protocol.ip import IP
from exabgp.bgp.message import OUT

from exabgp.bgp.message.update.nlri.prefix import Prefix
from exabgp.bgp.message.update.nlri.mpls import MPLS
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.operational import Advisory
from exabgp.bgp.message.operational import Query
from exabgp.bgp.message.operational import Response

from exabgp.rib.change import Change
from exabgp.version import version
from exabgp.logger import Logger


# ========================================================================= Text
#

class Text (Configuration):
	def __init__ (self):
		Configuration.__init__(self,'','')

	def parse_api_route (self,command,peers,action):
		tokens = formated(command).split(' ')[1:]
		lt = len(tokens)

		if lt < 1: return False

		message = tokens[0]

		if message not in ('route',):
			return False

		if lt == 2 and action == 'withdraw' and 'next-hop' not in tokens:
			tokens.extend(['next-hop','0.0.0.0'])

		changes = []
		if 'self' in command:
			for peer,nexthop in peers.iteritems():
				scope = [{}]
				self._nexthopself = nexthop
				if not self._single_static_route(scope,tokens[1:]):
					self._nexthopself = None
					return False
				for change in scope[0]['announce']:
					changes.append((peer,change))
			self._nexthopself = None
		else:
			scope = [{}]
			if not self._single_static_route(scope,tokens[1:]):
				return False
			for peer in peers:
				for change in scope[0]['announce']:
					changes.append((peer,change))

		if action == 'withdraw':
			for (peer,change) in changes:
				change.nlri.action = OUT.withdraw
		return changes


	def parse_api_vpls (self,command,peers,action):
		tokens = formated(command).split(' ')[1:]
		if len(tokens) < 4:
			return False
		if tokens[0] != 'vpls':
			return False
		changes = []
		if 'self' in command:
			for peer,nexthop in peers.iteritems():
				scope = [{}]
				self._nexthopself = nexthop
				if not self._single_l2vpn_vpls(scope,tokens[1:]):
					self._nexthopself = None
					return False
				for change in scope[0]['announce']:
					changes.append((peer,change))
			self._nexthopself = None
		else:
			scope = [{}]
			if not self._single_l2vpn_vpls(scope,tokens[1:]):
				return False
			for peer in peers:
				for change in scope[0]['announce']:
					changes.append((peer,change))
		if action == 'withdraw':
			for (peer,change) in changes:
				change.nlri.action = OUT.withdraw
		return changes

	def parse_api_attribute (self,command,peers,action):
		# This is a quick solution which does not support next-hop self
		attribute,nlris = command.split('nlri')
		route = '%s route 0.0.0.0/0 %s' % (action, ' '.join(attribute.split()[2:]))
		parsed = self.parse_api_route(route,peers,action)
		if parsed in (True,False,None):
			return parsed
		attributes = parsed[0][1].attributes
		nexthop = parsed[0][1].nlri.nexthop
		changes = []
		for nlri in nlris.split():
			ip,mask = nlri.split('/')
			klass = Prefix if 'path-information' in command else MPLS
			change = Change(
				klass(
					afi=IP.toafi(ip),
					safi=IP.tosafi(ip),
					packed=IP.pton(ip),
					mask=int(mask),
					nexthop=nexthop.packed,
					action=action
				)
				,attributes
			)
			if action == 'withdraw':
				change.nlri.action = OUT.withdraw
			else:
				change.nlri.action = OUT.announce
			changes.append((peers.keys(),change))
		return changes

	def parse_api_flow (self,command,action):
		self._tokens = self._tokenise(' '.join(formated(command).split(' ')[2:]).split('\\n'))
		scope = [{}]
		if not self._dispatch(scope,'flow',['route',],[],['root']):
			return False
		if not self._check_flow_route(scope):
			return False
		changes = scope[0]['announce']
		if action == 'withdraw':
			for change in changes:
				change.nlri.action = OUT.withdraw
		return changes

	def parse_api_refresh (self,command):
		tokens = formated(command).split(' ')[2:]
		if len(tokens) != 2:
			return False
		afi = AFI.value(tokens.pop(0))
		safi = SAFI.value(tokens.pop(0))
		if afi is None or safi is None:
			return False
		return RouteRefresh(afi,safi)

	def parse_api_eor (self,command):
		tokens = formated(command).split(' ')[2:]
		lt = len(tokens)

		if not lt:
			return Family(1,1)

		if lt !=2:
			return False

		afi = AFI.fromString(tokens[0])
		if afi == AFI.undefined:
			return False

		safi = SAFI.fromString(tokens[1])
		if safi == SAFI.undefined:
			return False

		return Family(afi,safi)

	def parse_api_operational (self,command):
		tokens = formated(command).split(' ',2)
		scope = [{}]

		if len(tokens) != 3:
			return False

		operational = tokens[0].lower()
		what = tokens[1].lower()

		if operational != 'operational':
			return False

		if what == 'asm':
			if not self._single_operational(Advisory.ASM,scope,['afi','safi','advisory'],tokens[2]):
				return False
		elif what == 'adm':
			if not self._single_operational(Advisory.ADM,scope,['afi','safi','advisory'],tokens[2]):
				return False
		elif what == 'rpcq':
			if not self._single_operational(Query.RPCQ,scope,['afi','safi','sequence'],tokens[2]):
				return False
		elif what == 'rpcp':
			if not self._single_operational(Response.RPCP,scope,['afi','safi','sequence','counter'],tokens[2]):
				return False
		elif what == 'apcq':
			if not self._single_operational(Query.APCQ,scope,['afi','safi','sequence'],tokens[2]):
				return False
		elif what == 'apcp':
			if not self._single_operational(Response.APCP,scope,['afi','safi','sequence','counter'],tokens[2]):
				return False
		elif what == 'lpcq':
			if not self._single_operational(Query.LPCQ,scope,['afi','safi','sequence'],tokens[2]):
				return False
		elif what == 'lpcp':
			if not self._single_operational(Response.LPCP,scope,['afi','safi','sequence','counter'],tokens[2]):
				return False
		else:
			return False

		operational = scope[0]['operational'][0]
		return operational


# ====================================================================== Decoder
#

# XXX: FIXME: everything could be static method ?

class Decoder (object):
	_dispatch = {}
	_order = {}

	def __init__ (self):
		self.logger = Logger()
		self.format = Text()

	# callaback code

	def register_command (command,storage,order):
		def closure (f):
			def wrap (*args):
				f(*args)
			storage[command] = wrap
			order = sorted(storage.keys(),key=len)
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


	#

	@register_command('shutdown',_dispatch,_order)
	def _shutdown (self,reactor,service,command):
		reactor.api_shutdown()
		reactor.answer(service,'shutdown in progress')
		return True

	@register_command('reload',_dispatch,_order)
	def _reload (self,reactor,service,command):
		reactor.api_reload()
		reactor.answer(service,'reload in progress')
		return True

	@register_command('reload',_dispatch,_order)
	def _restart (self,reactor,service,command):
		reactor.api_restart()
		reactor.answer(service,'restart in progress')
		return True

	@register_command('version',_dispatch,_order)
	def _version (self,reactor,service,command):
		reactor.answer(service,'exabgp %s' % version)
		return True

	# teardown

	@register_command('teardown',_dispatch,_order)
	def _t (self,reactor,service,command):
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

	@register_command('show neighbor',_dispatch,_order)
	def _show_neighbor (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for line in str(neighbor).split('\n'):
					reactor.answer(service,line)
					yield True

		reactor.plan(_callback())
		return True

	@register_command('show neighbors',_dispatch,_order)
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

	@register_command('show routes',_dispatch,_order)
	def _show_routes (self,reactor,service,command):
		def _callback ():
			for key in reactor.configuration.neighbor.keys():
				neighbor = reactor.configuration.neighbor[key]
				for change in list(neighbor.rib.outgoing.sent_changes()):
					reactor.answer(service,'neighbor %s %s' % (neighbor.local_address,str(change.nlri)))
					yield True

		reactor.plan(_callback())
		return True

	@register_command('show routes extensive',_dispatch,_order)
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

	@register_command('announce watchdog',_dispatch,_order)
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


	@register_command('withdraw watchdog',_dispatch,_order)
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

	@register_command('flush route',_dispatch,_order)
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

	@register_command('announce route',_dispatch,_order)
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
					yield False
				self.logger.reactor("Route added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
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

	@register_command('withdraw route',_dispatch,_order)
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

	@register_command('announce vpls',_dispatch,_order)
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
					yield False
				self.logger.reactor("vpls added to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',change.extensive()))
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

	@register_command('withdraw vpls',_dispatch,_order)
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

	@register_command('announce attribute',_dispatch,_order)
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

	@register_command('withdraw attribute',_dispatch,_order)
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

	@register_command('announce flow',_dispatch,_order)
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


	@register_command('withdraw flow',_dispatch,_order)
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

	@register_command('announce eor',_dispatch,_order)
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

	@register_command('announce route-refresh',_dispatch,_order)
	def _announce_refresh (self,reactor,service,command):
		def _callback (self,command,peers):
			rr = self.format.parse_api_refresh(command)
			if not rr:
				self.logger.reactor("Command could not parse flow in : %s" % command)
				yield True
			else:
				reactor.configuration.refresh_to_peers(rr,peers)
				self.logger.reactor("Sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',rr.extensive()))
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

	@register_command('operational',_dispatch,_order)
	def _announce_operational (self,reactor,service,command):
		def _callback (self,command,peers):
			operational = self.format.parse_api_operational(command)
			if not operational:
				self.logger.reactor("Command could not parse operational command : %s" % command)
				yield True
			else:
				reactor.configuration.operational_to_peers(operational,peers)
				self.logger.reactor("operational message sent to %s : %s" % (', '.join(peers if peers else []) if peers is not None else 'all peers',operational.extensive()))
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
