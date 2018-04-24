# encoding: utf-8
"""
ancient.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import stat
import time
import socket
import shlex

from copy import deepcopy
from struct import pack

from exabgp.util.ip import isipv4

from exabgp.configuration.environment import environment
from exabgp.configuration.format import formated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import known_families

from exabgp.bgp.neighbor import Neighbor

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoIP
from exabgp.bgp.message import OUT

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.message.update.nlri.prefix import Prefix
from exabgp.bgp.message.update.nlri.prefix import PathInfo
from exabgp.bgp.message.update.nlri.mpls import MPLS
from exabgp.bgp.message.update.nlri.mpls import Labels
from exabgp.bgp.message.update.nlri.mpls import RouteDistinguisher
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.flow import BinaryOperator
from exabgp.bgp.message.update.nlri.flow import NumericOperator
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.flow import Flow4Source
from exabgp.bgp.message.update.nlri.flow import Flow4Destination
from exabgp.bgp.message.update.nlri.flow import Flow6Source
from exabgp.bgp.message.update.nlri.flow import Flow6Destination
from exabgp.bgp.message.update.nlri.flow import FlowSourcePort
from exabgp.bgp.message.update.nlri.flow import FlowDestinationPort
from exabgp.bgp.message.update.nlri.flow import FlowAnyPort
from exabgp.bgp.message.update.nlri.flow import FlowIPProtocol
from exabgp.bgp.message.update.nlri.flow import FlowNextHeader
from exabgp.bgp.message.update.nlri.flow import FlowTCPFlag
from exabgp.bgp.message.update.nlri.flow import FlowFragment
from exabgp.bgp.message.update.nlri.flow import FlowPacketLength
from exabgp.bgp.message.update.nlri.flow import FlowICMPType
from exabgp.bgp.message.update.nlri.flow import FlowICMPCode
from exabgp.bgp.message.update.nlri.flow import FlowDSCP
from exabgp.bgp.message.update.nlri.flow import FlowTrafficClass
from exabgp.bgp.message.update.nlri.flow import FlowFlowLabel

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator

from exabgp.bgp.message.update.attribute.community.community import Community
from exabgp.bgp.message.update.attribute.community.communities import Communities
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficAction
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRedirect
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficMark
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHop

from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.bgp.message.update.attribute.generic import GenericAttribute

from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory

from exabgp.bgp.message.update.attribute.attributes import Attributes

from exabgp.rib.change import Change
from exabgp.reactor.api import control
from exabgp.logger import Logger

# Duck class, faking part of the Attribute interface
# We add this to routes when when need o split a route in smaller route
# The value stored is the longer netmask we want to use
# As this is not a real BGP attribute this stays in the configuration file


class Split (int):
	ID = Attribute.CODE.INTERNAL_SPLIT


class Watchdog (str):
	ID = Attribute.CODE.INTERNAL_WATCHDOG


class Withdrawn (object):
	ID = Attribute.CODE.INTERNAL_WITHDRAW


class Name (str):
	ID = Attribute.CODE.INTERNAL_NAME


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer, mask):
	return ''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


class Configuration (object):
	TTL_SECURITY = 255

	_str_bad_flow = "you tried to filter a flow using an invalid port for a component .."
	_str_route_error = \
		'community, extended-communities and as-path can take a single community as parameter.\n' \
		'only next-hop is mandatory\n' \
		'\n' \
		'syntax:\n' \
		'route 10.0.0.1/22 {\n' \
		'   path-information 0.0.0.1;\n' \
		'   route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
		'   next-hop 192.0.1.254;\n' \
		'   origin IGP|EGP|INCOMPLETE;\n' \
		'   as-path [ AS-SEQUENCE-ASN1 AS-SEQUENCE-ASN2 ( AS-SET-ASN3 )] ;\n' \
		'   med 100;\n' \
		'   local-preference 100;\n' \
		'   atomic-aggregate;\n' \
		'   community [ 65000 65001 65002 ];\n' \
		'   extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 ]\n' \
		'   originator-id 10.0.0.10;\n' \
		'   cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'   label [ 100 200 ];\n' \
		'   aggregator ( 65000:10.0.0.10 )\n' \
		'   aigp 100;\n' \
		'   split /24\n' \
		'   watchdog watchdog-name\n' \
		'   withdraw\n' \
		'}\n' \
		'\n' \
		'syntax:\n' \
		'route 10.0.0.1/22' \
		' path-information 0.0.0.1' \
		' route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
		' next-hop 192.0.2.1' \
		' origin IGP|EGP|INCOMPLETE' \
		' as-path AS-SEQUENCE-ASN' \
		' med 100' \
		' local-preference 100' \
		' atomic-aggregate' \
		' community 65000' \
		' extended-community target:1234:5.6.7.8' \
		' originator-id 10.0.0.10' \
		' cluster-list 10.10.0.1' \
		' label 150' \
		' aggregator ( 65000:10.0.0.10 )' \
		' aigp 100' \
		' split /24' \
		' watchdog watchdog-name' \
		' withdraw' \
		' name what-you-want-to-remember-about-the-route' \
		';\n'

	_str_vpls_error = \
		'syntax:\n' \
		'vpls site_name {\n' \
		'   endpoint <vpls endpoint id; integer>\n' \
		'   base <label base; integer>\n' \
		'   offset <block offet; interger>\n' \
		'   size <block size; integer>\n' \
		'   route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535\n' \
		'   next-hop 192.0.1.254;\n' \
		'   origin IGP|EGP|INCOMPLETE;\n' \
		'   as-path [ as as as as] ;\n' \
		'   med 100;\n' \
		'   local-preference 100;\n' \
		'   community [ 65000 65001 65002 ];\n' \
		'   extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 l2info:19:0:1500:111 ]\n' \
		'   originator-id 10.0.0.10;\n' \
		'   cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'   withdraw\n' \
		'   name what-you-want-to-remember-about-the-route\n' \
		'}\n'

	_str_flow_error = \
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
		'fragment code is totally untested\n' \

	_str_process_error = \
		'syntax:\n' \
		'process name-of-process {\n' \
		'   run /path/to/command with its args;\n' \
		'}\n\n' \

	_str_family_error = \
		'syntax:\n' \
		'family {\n' \
		'   all;		  # default if not family block is present, announce all we know\n' \
		'    minimal	  # use the AFI/SAFI required to announce the routes in the configuration\n' \
		'    \n' \
		'    ipv4 unicast;\n' \
		'   ipv4 multicast;\n' \
		'   ipv4 nlri-mpls;\n' \
		'   ipv4 mpls-vpn;\n' \
		'   ipv4 flow;\n' \
		'   ipv4 flow-vpn;\n' \
		'   ipv6 unicast;\n' \
		'   ipv6 flow;\n' \
		'   ipv6 flow-vpn;\n' \
		'}\n'

	_str_capa_error = \
		'syntax:\n' \
		'capability {\n' \
		'   graceful-restart <time in second>;\n' \
		'   asn4 enable|disable;\n' \
		'   add-path disable|send|receive|send/receive;\n' \
		'   multi-session enable|disable;\n' \
		'   operational enable|disable;\n' \
		'}\n'

	_str_vpls_bad_size = "you tried to configure an invalid l2vpn vpls block-size"
	_str_vpls_bad_offset = "you tried to configure an invalid l2vpn vpls block-offset"
	_str_vpls_bad_label = "you tried to configure an invalid l2vpn vpls label"
	_str_vpls_bad_enpoint = "you tried to configure an invalid l2vpn vpls endpoint"

	def __init__ (self, configurations, text=False):
		self.debug = environment.settings().debug.configuration
		self.api_encoder = environment.settings().api.encoder
		self.cli_socket = environment.settings().api.socket

		self.logger = Logger()
		self._text = text
		self._configurations = configurations
		self._dispatch_route_cfg = {
			'origin': self._route_origin,
			'as-path': self._route_aspath,
			# For legacy with version 2.0.x
			'as-sequence': self._route_aspath,
			'med': self._route_med,
			'aigp': self._route_aigp,
			'next-hop': self._route_next_hop,
			'local-preference': self._route_local_preference,
			'atomic-aggregate': self._route_atomic_aggregate,
			'aggregator': self._route_aggregator,
			'path-information': self._route_path_information,
			'originator-id': self._route_originator_id,
			'cluster-list': self._route_cluster_list,
			'split': self._route_split,
			'label': self._route_label,
			'rd': self._route_rd,
			'route-distinguisher': self._route_rd,
			'watchdog': self._route_watchdog,
			# withdrawn is here to not break legacy code
			'withdraw': self._route_withdraw,
			'withdrawn': self._route_withdraw,
			'name': self._route_name,
			'community': self._route_community,
			'extended-community': self._route_extended_community,
			'attribute': self._route_generic_attribute,
		}
		self._dispatch_flow_cfg = {
			'rd': self._route_rd,
			'route-distinguisher': self._route_rd,
			'next-hop': self._flow_route_next_hop,
			'source': self._flow_source,
			'source-ipv4': self._flow_source,
			'destination': self._flow_destination,
			'destination-ipv4': self._flow_destination,
			'port': self._flow_route_anyport,
			'source-port': self._flow_route_source_port,
			'destination-port': self._flow_route_destination_port,
			'protocol': self._flow_route_protocol,
			'next-header': self._flow_route_next_header,
			'tcp-flags': self._flow_route_tcp_flags,
			'icmp-type': self._flow_route_icmp_type,
			'icmp-code': self._flow_route_icmp_code,
			'fragment': self._flow_route_fragment,
			'dscp': self._flow_route_dscp,
			'traffic-class': self._flow_route_traffic_class,
			'packet-length': self._flow_route_packet_length,
			'flow-label': self._flow_route_flow_label,
			'accept': self._flow_route_accept,
			'discard': self._flow_route_discard,
			'rate-limit': self._flow_route_rate_limit,
			'redirect': self._flow_route_redirect,
			'redirect-to-nexthop': self._flow_route_redirect_next_hop,
			'copy': self._flow_route_copy,
			'mark': self._flow_route_mark,
			'action': self._flow_route_action,
			'community': self._route_community,
			'extended-community': self._route_extended_community,
		}
		self._dispatch_vpls_cfg = {
			'endpoint': self._l2vpn_vpls_endpoint,
			'offset': self._l2vpn_vpls_offset,
			'size': self._l2vpn_vpls_size,
			'base': self._l2vpn_vpls_base,
			'origin': self._route_origin,
			'as-path': self._route_aspath,
			'med': self._route_med,
			'next-hop': self._route_next_hop,
			'local-preference': self._route_local_preference,
			'originator-id': self._route_originator_id,
			'cluster-list': self._route_cluster_list,
			'rd': self._route_rd,
			'route-distinguisher': self._route_rd,
			'withdraw': self._route_withdraw,
			'withdrawn': self._route_withdraw,
			'name': self._route_name,
			'community': self._route_community,
			'extended-community': self._route_extended_community,
		}
		self._clear()

	def _clear (self):
		self.process = {}
		self.neighbor = {}
		self.error = ''

		self._neighbor = {}
		self._error = ''
		self._scope = []
		self._location = ['root']
		self._line = []
		self._number = 1
		self._flow_state = 'out'
		self._nexthopself = None

	# Public Interface

	def reload (self):
		try:
			return self._reload()
		except KeyboardInterrupt:
			self.error = 'configuration reload aborted by ^C or SIGINT'
			if self.debug: raise  # noqa
			return False
		except Exception:
			self.error = 'configuration parsing issue'
			if self.debug: raise  # noqa
			return False

	def _reload (self):
		# taking the first configuration available (FIFO buffer)
		self._fname = self._configurations.pop(0)
		self._configurations.append(self._fname)

		# creating the tokeniser for the configuration
		if self._text:
			self._tokens = self._tokenise(self._fname.split('\n'))
		else:
			try:
				f = open(self._fname,'r')
				self._tokens = self._tokenise(f)
				f.close()
			except IOError,exc:
				error = str(exc)
				if error.count(']'):
					self.error = error.split(']')[1].strip()
				else:
					self.error = error
				if self.debug: raise Exception()  # noqa
				return False

		# storing the routes associated with each peer so we can find what changed
		backup_changes = {}
		for neighbor in self._neighbor:
			backup_changes[neighbor] = self._neighbor[neighbor].changes

		# clearing the current configuration to be able to re-parse it
		self._clear()

		# parsing the configurtion
		r = False
		while not self.finished():
			r = self._dispatch(
				self._scope,'configuration',
				['group','neighbor'],
				[]
			)
			if r is False:
				break

		# handling possible parsing errors
		if r not in [True,None]:
			self.error = "\nsyntax error in section %s\nline %d: %s\n\n%s" % (self._location[-1],self.number(),self.line(),self._error)
			return False

		# parsing was sucessful, assigning the result
		self.neighbor = self._neighbor

		# installing in the neighbor what was its previous routes so we can
		# add/withdraw what need to be
		for neighbor in self.neighbor:
			self.neighbor[neighbor].backup_changes = backup_changes.get(neighbor,[])

		# we are not really running the program, just want to ....
		if environment.settings().debug.route:
			from exabgp.configuration.check import check_message
			if check_message(self.neighbor,environment.settings().debug.route):
				sys.exit(0)
			sys.exit(1)

		# we are not really running the program, just want check the configuration validity
		if environment.settings().debug.selfcheck:
			from exabgp.configuration.check import check_neighbor
			if check_neighbor(self.neighbor):
				sys.exit(0)
			sys.exit(1)

		return True

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def change_to_peers (self, change, peers):
		result = True
		for neighbor in self.neighbor:
			if neighbor in peers:
				if change.nlri.family() in self.neighbor[neighbor].families():
					self.neighbor[neighbor].rib.outgoing.insert_announced(change)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def eor_to_peers (self, family, peers):
		result = True
		for neighbor in self.neighbor:
			if neighbor in peers:
				self.neighbor[neighbor].eor.append(family)
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def operational_to_peers (self, operational, peers):
		result = True
		for neighbor in self.neighbor:
			if neighbor in peers:
				if operational.family() in self.neighbor[neighbor].families():
					if operational.name == 'ASM':
						self.neighbor[neighbor].asm[operational.family()] = operational
					self.neighbor[neighbor].messages.append(operational)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def refresh_to_peers (self, refresh, peers):
		result = True
		for neighbor in self.neighbor:
			if neighbor in peers:
				family = (refresh.afi,refresh.safi)
				if family in self.neighbor[neighbor].families():
					self.neighbor[neighbor].refresh.append(refresh.__class__(refresh.afi,refresh.safi))
				else:
					result = False
		return result

	# Tokenisation

	def _tokenise (self, text):
		r = []
		config = ''
		for line in text:
			self.logger.configuration('loading | %s' % line.rstrip())
			replaced = formated(line)
			config += line
			if not replaced:
				continue
			if replaced.startswith('#'):
				continue
			command = replaced[:3]
			if command in ('md5','asm'):
				string = line.strip()[3:].strip()
				if string[-1] == ';':
					string = string[:-1]
				r.append([command,string,';'])
			elif replaced[:3] == 'run':
				r.append([t for t in replaced[:-1].split(' ',1) if t] + [replaced[-1]])
			else:
				r.append([t.lower() for t in replaced[:-1].split(' ') if t] + [replaced[-1]])
		self.logger.config(config)
		return r

	def tokens (self):
		self._number += 1
		self._line = self._tokens.pop(0)
		return self._line

	def number (self):
		return self._number

	def line (self):
		return ' '.join(self._line)

	def finished (self):
		return len(self._tokens) == 0

	# Flow control ......................

	# name is not used yet but will come really handy if we have name collision :D
	def _dispatch (self, scope, name, multi, single, location=None):
		if location:
			self._location = location
			self._flow_state = 'out'
		try:
			tokens = self.tokens()
		except IndexError:
			self._error = 'configuration file incomplete (most likely missing })'
			if self.debug: raise Exception()  # noqa
			return False
		self.logger.configuration("parsing | %-13s | '%s'" % (name,"' '".join(tokens)))
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(scope,name,tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(scope,name,tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				if self.debug: raise Exception()  # noqa
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self, scope, name, tokens, valid):
		command = tokens[0]

		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			if self.debug: raise Exception()  # noqa
			return False

		if name == 'configuration':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'group':
				if len(tokens) != 2:
					self._error = 'syntax: group <name> { <options> }'
					if self.debug: raise Exception()  # noqa
					return False
				return self._multi_group(scope,tokens[1])

		if name == 'group':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'static':
				return self._multi_static(scope,tokens[1:])
			if command == 'flow':
				return self._multi_flow(scope,tokens[1:])
			if command == 'l2vpn':
				return self._multi_l2vpn(scope,tokens[1:])
			if command == 'process':
				return self._multi_process(scope,tokens[1:])
			if command == 'family':
				return self._multi_family(scope,tokens[1:])
			if command == 'capability':
				return self._multi_capability(scope,tokens[1:])
			if command == 'operational':
				return self._multi_operational(scope,tokens[1:])

		if name == 'neighbor':
			if command == 'static':
				return self._multi_static(scope,tokens[1:])
			if command == 'flow':
				return self._multi_flow(scope,tokens[1:])
			if command == 'l2vpn':
				return self._multi_l2vpn(scope,tokens[1:])
			if command == 'process':
				return self._multi_process(scope,tokens[1:])
			if command == 'family':
				return self._multi_family(scope,tokens[1:])
			if command == 'capability':
				return self._multi_capability(scope,tokens[1:])
			if command == 'operational':
				return self._multi_operational(scope,tokens[1:])

		if name == 'static':
			if command == 'route':
				if self._multi_static_route(scope,tokens[1:]):
					return self._check_static_route(scope)
				return False

		if name == 'flow':
			if command == 'route':
				if self._multi_flow_route(scope,tokens[1:]):
					return self._check_flow_route(scope)
				return False

		if name == 'l2vpn':
			if command == 'vpls':
				if self._multi_l2vpn_vpls(scope,tokens[1:]):
					return self._check_l2vpn_vpls(scope)
				return False

		if name == 'flow-route':
			if command == 'match':
				if self._multi_match(scope,tokens[1:]):
					return True
				return False
			if command == 'then':
				if self._multi_then(scope,tokens[1:]):
					return True
				return False

		if name == 'process':
			if command == 'receive':
				if self._multi_receive(scope,tokens[1:]):
					return True
				return False
			if command == 'send':
				if self._multi_send(scope,tokens[1:]):
					return True
				return False
		return False

	def _single_line (self, scope, name, tokens, valid):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'invalid keyword "%s"' % command
			if self.debug: raise Exception()  # noqa
			return False

		elif name == 'route':
			if command in self._dispatch_route_cfg:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_route_cfg[command](scope,tokens[1:],SAFI.mpls_vpn)
				else:
					return self._dispatch_route_cfg[command](scope,tokens[1:])

		elif name == 'l2vpn':
			if command in self._dispatch_vpls_cfg:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_vpls_cfg[command](scope,tokens[1:],SAFI.vpls)
				else:
					return self._dispatch_vpls_cfg[command](scope,tokens[1:])

		elif name == 'flow-route':
			if command in self._dispatch_flow_cfg:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_flow_cfg[command](scope,tokens[1:],SAFI.flow_vpn)
				else:
					return self._dispatch_flow_cfg[command](scope,tokens[1:])

		elif name == 'flow-match':
			if command in self._dispatch_flow_cfg:
					return self._dispatch_flow_cfg[command](scope,tokens[1:])

		elif name == 'flow-then':
			if command in self._dispatch_flow_cfg:
					return self._dispatch_flow_cfg[command](scope,tokens[1:])

		if name in ('neighbor','group'):
			if command == 'description':
				return self._set_description(scope,tokens[1:])
			if command == 'router-id':
				return self._set_router_id(scope,'router-id',tokens[1:])
			if command == 'local-address':
				return self._set_ip(scope,'local-address',tokens[1:])
			if command == 'local-as':
				return self._set_asn(scope,'local-as',tokens[1:])
			if command == 'peer-as':
				return self._set_asn(scope,'peer-as',tokens[1:])
			if command == 'passive':
				return self._set_passive(scope,'passive',tokens[1:])
			if command == 'listen':
				return self._set_listen(scope,'listen',tokens[1:])
			if command == 'connect':
				return self._set_connect(scope,'connect',tokens[1:])
			if command == 'hold-time':
				return self._set_holdtime(scope,'hold-time',tokens[1:])
			if command == 'md5':
				return self._set_md5(scope,'md5',tokens[1:])
			if command == 'ttl-security':
				return self._set_ttl(scope,'ttl-security',tokens[1:])
			if command == 'group-updates':
				return self._set_boolean(scope,'group-updates',tokens[1:],'true')
			if command == 'aigp':
				return self._set_boolean(scope,'aigp',tokens[1:],'false')
			# deprecated
			if command == 'route-refresh':
				return self._set_boolean(scope,'route-refresh',tokens[1:])
			if command == 'graceful-restart':
				return self._set_gracefulrestart(scope,'graceful-restart',tokens[1:])
			if command == 'multi-session':
				return self._set_boolean(scope,'multi-session',tokens[1:])
			if command == 'add-path':
				return self._set_addpath(scope,'add-path',tokens[1:])
			if command == 'auto-flush':
				return self._set_boolean(scope,'auto-flush',tokens[1:])
			if command == 'adj-rib-out':
				return self._set_boolean(scope,'adj-rib-out',tokens[1:])
			if command == 'manual-eor':
				return self._set_boolean(scope,'manual-eor',tokens[1:])

		elif name == 'family':
			if command == 'inet':
				return self._set_family_inet4(scope,tokens[1:])
			if command == 'inet4':
				return self._set_family_inet4(scope,tokens[1:])
			if command == 'inet6':
				return self._set_family_inet6(scope,tokens[1:])
			if command == 'ipv4':
				return self._set_family_ipv4(scope,tokens[1:])
			if command == 'ipv6':
				return self._set_family_ipv6(scope,tokens[1:])
			if command == 'l2vpn':
				return self._set_family_l2vpn(scope,tokens[1:])
			if command == 'minimal':
				return self._set_family_minimal(scope,tokens[1:])
			if command == 'all':
				return self._set_family_all(scope,tokens[1:])

		elif name == 'capability':
			if command == 'route-refresh':
				return self._set_boolean(scope,'route-refresh',tokens[1:])
			if command == 'graceful-restart':
				return self._set_gracefulrestart(scope,'graceful-restart',tokens[1:])
			if command == 'multi-session':
				return self._set_boolean(scope,'multi-session',tokens[1:])
			if command == 'operational':
				return self._set_boolean(scope,'capa-operational',tokens[1:])
			if command == 'add-path':
				return self._set_addpath(scope,'add-path',tokens[1:])
			if command == 'asn4':
				return self._set_asn4(scope,'asn4',tokens[1:])
			if command == 'aigp':
				return self._set_boolean(scope,'aigp',tokens[1:],'false')

		elif name == 'process':
			if command == 'run':
				return self._set_process_run(scope,'process-run',tokens[1:])
			if command == 'encoder':
				return self._set_process_encoder(scope,'encoder',tokens[1:])

			# legacy ...

			if command == 'parse-routes':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				return True

			if command == 'peer-updates':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				return True

			if command == 'send-packets':
				return self._set_process_command(scope,'send-packets',tokens[1:])

			if command == 'neighbor-changes':
				return self._set_process_command(scope,'neighbor-changes',tokens[1:])

			if command == 'receive-packets':
				return self._set_process_command(scope,'receive-packets',tokens[1:])

			if command == 'receive-parsed':
				return self._set_process_command(scope,'receive-parsed',tokens[1:])

			if command == 'receive-routes':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				self._set_process_command(scope,'receive-refresh',tokens[1:])
				return True

			if command == 'receive-operational':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'receive-operational',tokens[1:])
				return True

		elif name == 'send':  # process / send
			if command == 'packets':
				return self._set_process_command(scope,'send-packets',tokens[1:])

		elif name == 'receive':  # process / receive
			if command == 'packets':
				return self._set_process_command(scope,'receive-packets',tokens[1:])
			if command == 'parsed':
				return self._set_process_command(scope,'receive-parsed',tokens[1:])
			if command == 'consolidate':
				return self._set_process_command(scope,'consolidate',tokens[1:])

			if command == 'neighbor-changes':
				return self._set_process_command(scope,'neighbor-changes',tokens[1:])
			if command == 'notification':
				return self._set_process_command(scope,'receive-notifications',tokens[1:])
			if command == 'open':
				return self._set_process_command(scope,'receive-opens',tokens[1:])
			if command == 'keepalive':
				return self._set_process_command(scope,'receive-keepalives',tokens[1:])
			if command == 'refresh':
				return self._set_process_command(scope,'receive-refresh',tokens[1:])
			if command == 'update':
				return self._set_process_command(scope,'receive-updates',tokens[1:])
			if command == 'updates':
				return self._set_process_command(scope,'receive-updates',tokens[1:])
			if command == 'operational':
				return self._set_process_command(scope,'receive-operational',tokens[1:])

		elif name == 'static':
			if command == 'route':
				return self._single_static_route(scope,tokens[1:])

		elif name == 'l2vpn':
			if command == 'vpls':
				return self._single_l2vpn_vpls(scope,tokens[1:])

		elif name == 'operational':
			if command == 'asm':
				return self._single_operational_asm(scope,tokens[1])
			# it does not make sense to have adm

		return False

	# Programs used to control exabgp

	def _multi_process (self, scope, tokens):
		while True:
			r = self._dispatch(
				scope,'process',
				['send','receive'],
				[
					'run','encoder',

					'peer-updates','parse-routes','receive-routes',
					'receive-parsed','receive-packets',
					'neighbor-changes',
					'receive-updates','receive-refresh','receive-operational',
					'send-packets',
				]
			)
			if r is False:
				return False
			if r is None:
				break

		name = tokens[0] if len(tokens) >= 1 else 'conf-only-%s' % str(time.time())[-6:]
		self.process.setdefault(name,{})['neighbor'] = scope[-1]['peer-address'] if 'peer-address' in scope[-1] else '*'

		for key in ['neighbor-changes', 'receive-notifications', 'receive-opens', 'receive-keepalives', 'receive-refresh', 'receive-updates', 'receive-operational', 'receive-parsed', 'receive-packets', 'consolidate', 'send-packets']:
			self.process[name][key] = scope[-1].pop(key,False)

		run = scope[-1].pop('process-run','')
		if run:
			if len(tokens) != 1:
				self._error = self._str_process_error
				if self.debug: raise Exception()  # noqa
				return False
			self.process[name]['encoder'] = scope[-1].get('encoder','') or self.api_encoder
			self.process[name]['run'] = run
			return True
		elif len(tokens):
			self._error = self._str_process_error
			if self.debug: raise Exception()  # noqa
			return False

	def _set_process_command (self, scope, command, value):
		scope[-1][command] = True
		return True

	def _set_process_encoder (self, scope, command, value):
		if value and value[0] in ('text','json'):
			scope[-1][command] = value[0]
			return True

		self._error = self._str_process_error
		if self.debug: raise Exception()  # noqa
		return False

	def _set_process_run (self, scope, command, value):
		line = ' '.join(value).strip()
		if len(line) > 2 and line[0] == line[-1] and line[0] in ['"',"'"]:
			line = line[1:-1]
		if ' ' in line:
			args = shlex.split(line,' ')
			prg,args = args[0],args[1:]
		else:
			prg = line
			args = ''

		if not prg:
			self._error = 'prg requires the program to prg as an argument (quoted or unquoted)'
			if self.debug: raise Exception()  # noqa
			return False

		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')

				env = os.environ.get('ETC','')
				if env:
					options = [
						os.path.join(env.rstrip('/'),*os.path.join(parts[2:])),
						'/etc/exabgp'
					]
				else:
					options = []
					options.append('/etc/exabgp')
					pwd = os.environ.get('PWD','').split('/')
					if pwd:
						# without abspath the path is not / prefixed !
						if pwd[-1] in ('etc','sbin'):
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd[:-1]),os.path.join(*parts))))
						if 'etc' not in pwd:
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd),os.path.join(*parts))))
			else:
				options = [
					os.path.abspath(os.path.join('/etc/exabgp',prg)),
					os.path.abspath(os.path.join(os.path.dirname(self._fname),prg)),
				]
			for option in options:
				if os.path.exists(option):
					prg = option
					break

		if not os.path.exists(prg):
			self._error = 'can not locate the the program "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		# race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			self._error = 'can not execute directories "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		if s.st_mode & stat.S_ISUID:
			self._error = 'refusing to run setuid programs "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			self._error = 'exabgp will not be able to run this program "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		if args:
			scope[-1][command] = [prg] + args
		else:
			scope[-1][command] = [prg,]
		return True

	# Limit the AFI/SAFI pair announced to peers

	def _multi_family (self, scope, tokens):
		# we know all the families we should use
		self._family = False
		scope[-1]['families'] = []
		while True:
			r = self._dispatch(
				scope,'family',
				[],
				['inet','inet4','inet6','ipv4','ipv6','l2vpn','minimal','all']
			)
			if r is False:
				return False
			if r is None:
				break
		self._family = False
		return True

	def _set_family_inet4 (self, scope, tokens):
		self.logger.configuration("the word inet4 is deprecated, please use ipv4 instead",'error')
		return self._set_family_ipv4 (scope,tokens)

	def _set_family_ipv4 (self, scope, tokens):
		if self._family:
			self._error = 'ipv4 can not be used with all or minimal'
			if self.debug: raise Exception()  # noqa
			return False

		try:
			safi = tokens.pop(0)
		except IndexError:
			self._error = 'missing family safi'
			if self.debug: raise Exception()  # noqa
			return False

		if safi == 'unicast':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
		elif safi == 'multicast':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.multicast)))
		elif safi == 'nlri-mpls':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
		elif safi == 'mpls-vpn':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.mpls_vpn)))
		elif safi in ('flow'):
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.flow_ip)))
		elif safi == 'flow-vpn':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.flow_vpn)))
		else:
			return False
		return True

	def _set_family_inet6 (self, scope, tokens):
		self.logger.configuration("the word inet6 is deprecated, please use ipv6 instead",'error')
		return self._set_family_ipv6 (scope,tokens)

	def _set_family_ipv6 (self, scope, tokens):
		try:
			if self._family:
				self._error = 'ipv6 can not be used with all or minimal'
				if self.debug: raise Exception()  # noqa
				return False

			safi = tokens.pop(0)
			if safi == 'unicast':
				scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
			elif safi == 'nlri-mpls':
				scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.nlri_mpls)))
			elif safi == 'mpls-vpn':
				scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.mpls_vpn)))
			elif safi in ('flow'):
				scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.flow_ip)))
			elif safi == 'flow-vpn':
				scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.flow_vpn)))
			else:
				return False
			return True
		except (IndexError,ValueError):
			self._error = 'missing safi'
			if self.debug: raise Exception()  # noqa
			return False

	def _set_family_l2vpn (self, scope, tokens):
		try:
			if self._family:
				self._error = 'l2vpn can not be used with all or minimal'
				if self.debug: raise Exception()  # noqa
				return False

			safi = tokens.pop(0)
			if safi == 'vpls':
				scope[-1]['families'].append((AFI(AFI.l2vpn),SAFI(SAFI.vpls)))
			else:
				return False
			return True
		except (IndexError,ValueError):
			self._error = 'missing safi'
			if self.debug: raise Exception()  # noqa
			return False

	def _set_family_minimal (self, scope, tokens):
		if scope[-1]['families']:
			self._error = 'minimal can not be used with any other options'
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['families'] = 'minimal'
		self._family = True
		return True

	def _set_family_all (self, scope, tokens):
		if scope[-1]['families']:
			self._error = 'all can not be used with any other options'
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['families'] = 'all'
		self._family = True
		return True

	# capacity

	def _multi_capability (self, scope, tokens):
		# we know all the families we should use
		self._capability = False
		while True:
			r = self._dispatch(
				scope,'capability',
				[],
				[
					'route-refresh','graceful-restart',
					'multi-session','operational',
					'add-path','asn4','aigp'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _set_gracefulrestart (self, scope, command, value):
		if not len(value):
			scope[-1][command] = None
			return True
		try:
			if value and value[0] in ('disable','disabled'):
				return True
			# README: Should it be a subclass of int ?
			grace = int(value[0])
			if grace < 0:
				raise ValueError('graceful-restart can not be negative')
			if grace >= pow(2,16):
				raise ValueError('graceful-restart must be smaller than %d' % pow(2,16))
			scope[-1][command] = grace
			return True
		except ValueError:
			self._error = '"%s" is an invalid graceful-restart time' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	def _set_addpath (self, scope, command, value):
		try:
			ap = value[0].lower()
			apv = 0
			if ap.endswith('receive'):
				apv += 1
			if ap.startswith('send'):
				apv += 2
			if not apv and ap not in ('disable','disabled'):
				raise ValueError('invalid add-path')
			scope[-1][command] = apv
			return True
		except (ValueError,IndexError):
			self._error = '"%s" is an invalid add-path' % ' '.join(value) + '\n' + self._str_capa_error
			if self.debug: raise Exception()  # noqa
			return False

	def _set_boolean (self, scope, command, value, default='true'):
		try:
			boolean = value[0].lower() if value else default
			if boolean in ('true','enable','enabled'):
				scope[-1][command] = True
			elif boolean in ('false','disable','disabled'):
				scope[-1][command] = False
			elif boolean in ('unset',):
				scope[-1][command] = None
			else:
				raise ValueError()
			return True
		except (ValueError,IndexError):
			self._error = 'invalid %s command (valid options are true or false)' % command
			if self.debug: raise Exception()  # noqa
			return False

	def _set_asn4 (self, scope, command, value):
		try:
			if not value:
				scope[-1][command] = True
				return True
			asn4 = value[0].lower()
			if asn4 in ('disable','disabled'):
				scope[-1][command] = False
				return True
			if asn4 in ('enable','enabled'):
				scope[-1][command] = True
				return True
			self._error = '"%s" is an invalid asn4 parameter options are enable (default) and disable)' % ' '.join(value)
			return False
		except ValueError:
			self._error = '"%s" is an invalid asn4 parameter options are enable (default) and disable)' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	# route grouping with watchdog

	def _route_watchdog (self, scope, tokens):
		try:
			w = tokens.pop(0)
			if w.lower() in ['announce','withdraw']:
				raise ValueError('invalid watchdog name %s' % w)
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		try:
			scope[-1]['announce'][-1].attributes.add(Watchdog(w))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_withdraw (self, scope, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(Withdrawn())
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	# Route name

	def _route_name (self, scope, tokens):
		try:
			w = tokens.pop(0)
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		try:
			scope[-1]['announce'][-1].attributes.add(Name(w))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	# Group Neighbor

	def _multi_group (self, scope, address):
		scope.append({})
		while True:
			r = self._dispatch(
				scope,'group',
				[
					'static','flow','l2vpn',
					'neighbor','process','family',
					'capability','operational'
				],
				[
					'description','router-id','local-address','local-as','peer-as',
					'passive','listen','connect','hold-time','add-path','graceful-restart','md5',
					'ttl-security','multi-session','group-updates',
					'route-refresh','asn4','aigp','auto-flush','adj-rib-out'
				]
			)
			if r is False:
				return False
			if r is None:
				scope.pop(-1)
				return True

	def _make_neighbor (self, scope):
		# we have local_scope[-2] as the group template and local_scope[-1] as the peer specific
		if len(scope) > 1:
			for key,content in scope[-2].iteritems():
				if key not in scope[-1]:
					scope[-1][key] = deepcopy(content)
				elif key == 'announce':
					scope[-1][key].extend(scope[-2][key])

		# self.logger.configuration("\nPeer configuration complete :")
		# for _key in scope[-1].keys():
		# 	stored = scope[-1][_key]
		# 	if hasattr(stored,'__iter__'):
		# 		for category in scope[-1][_key]:
		# 			for _line in pformat(str(category),3,3,3).split('\n'):
		# 				self.logger.configuration("   %s: %s" %(_key,_line))
		# 	else:
		# 		for _line in pformat(str(stored),3,3,3).split('\n'):
		# 			self.logger.configuration("   %s: %s" %(_key,_line))
		# self.logger.configuration("\n")

		neighbor = Neighbor()
		for local_scope in scope:
			value = local_scope.get('router-id','')
			if value:
				neighbor.router_id = value
			value = local_scope.get('peer-address','')
			if value:
				neighbor.peer_address = value
			value = local_scope.get('local-address','')
			if value:
				neighbor.local_address = value
			value = local_scope.get('local-as','')
			if value:
				neighbor.local_as = value
			value = local_scope.get('peer-as','')
			if value:
				neighbor.peer_as = value
			value = local_scope.get('passive',False)
			if value:
				neighbor.passive = value
			value = local_scope.get('listen',0)
			if value:
				neighbor.listen = value
			value = local_scope.get('connect',0)
			if value:
				neighbor.connect = value
			value = local_scope.get('hold-time','')
			if value:
				neighbor.hold_time = value

			neighbor.changes = local_scope.get('announce',[])
			messages = local_scope.get('operational',[])

		# we want to have a socket for the cli
		if self.cli_socket:
			self.process['__cli__'] = {
				'neighbor': '*',
				'consolidate': False,
				'encoder': 'json',
				'neighbor-changes': False,
				'receive-keepalives': False,
				'receive-notifications': False,
				'receive-opens': False,
				'receive-operational': False,
				'receive-packets': False,
				'receive-parsed': False,
				'receive-refresh': False,
				'receive-updates': False,
				'run': [sys.executable, control.__file__, self.cli_socket]
			}

		for name in self.process.keys():
			process = self.process[name]
			neighbor.api.receive_packets(process.get('receive-packets',False))
			neighbor.api.send_packets(process.get('send-packets',False))

			neighbor.api.neighbor_changes(process.get('neighbor-changes',False))
			neighbor.api.consolidate(process.get('consolidate',False))

			neighbor.api.receive_parsed(process.get('receive-parsed',False))

			neighbor.api.receive_notifications(process.get('receive-notifications',False))
			neighbor.api.receive_opens(process.get('receive-opens',False))
			neighbor.api.receive_keepalives(process.get('receive-keepalives',False))
			neighbor.api.receive_updates(process.get('receive-updates',False))
			neighbor.api.receive_refresh(process.get('receive-refresh',False))
			neighbor.api.receive_operational(process.get('receive-operational',False))

		if not neighbor.router_id:
			neighbor.router_id = neighbor.local_address

		local_scope = scope[-1]
		neighbor.description = local_scope.get('description','')

		neighbor.md5 = local_scope.get('md5',None)
		neighbor.ttl = local_scope.get('ttl-security',None)
		neighbor.group_updates = local_scope.get('group-updates',None)

		neighbor.route_refresh = local_scope.get('route-refresh',0)
		neighbor.graceful_restart = local_scope.get('graceful-restart',0)
		if neighbor.graceful_restart is None:
			# README: Should it be a subclass of int ?
			neighbor.graceful_restart = int(neighbor.hold_time)
		neighbor.multisession = local_scope.get('multi-session',False)
		neighbor.operational = local_scope.get('capa-operational',False)
		neighbor.add_path = local_scope.get('add-path',0)
		neighbor.flush = local_scope.get('auto-flush',True)
		neighbor.adjribout = local_scope.get('adj-rib-out',True)
		neighbor.manual_eor = local_scope.get('manual-eor',False)
		neighbor.asn4 = local_scope.get('asn4',True)
		neighbor.aigp = local_scope.get('aigp',None)

		if neighbor.route_refresh and not neighbor.adjribout:
			self._error = 'incomplete option route-refresh and no adj-rib-out'
			if self.debug: raise Exception()  # noqa
			return False

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			if self.debug: raise Exception()  # noqa(self._error)
			return False
		if neighbor.local_address.afi != neighbor.peer_address.afi:
			self._error = 'local-address and peer-address must be of the same family'
			if self.debug: raise Exception()  # noqa(self._error)
			return False
		if neighbor.peer_address.ip in self._neighbor:
			self._error = 'duplicate peer definition %s' % neighbor.peer_address.ip
			if self.debug: raise Exception()  # noqa(self._error)
			return False

		openfamilies = local_scope.get('families','everything')
		# announce every family we known
		if neighbor.multisession and openfamilies == 'everything':
			# announce what is needed, and no more, no need to have lots of TCP session doing nothing
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		elif openfamilies in ('all','everything'):
			families = known_families()
		# only announce what you have as routes
		elif openfamilies == 'minimal':
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		else:
			families = openfamilies

		# check we are not trying to announce routes without the right MP announcement
		for family in neighbor.families():
			if family not in families:
				afi,safi = family
				self._error = 'Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % (afi,safi)
				if self.debug: raise Exception()  # noqa
				return False

		# add the families to the list of families known
		initial_families = list(neighbor.families())
		for family in families:
			if family not in initial_families	:
				# we are modifying the data used by .families() here
				neighbor.add_family(family)

		if neighbor.group_updates is None:
			neighbor.group_updates = False
			self.logger.configuration('-'*80,'warning')
			self.logger.configuration('group-updates not enabled for peer %s, it surely should, the default will change to true soon' % neighbor.peer_address,'warning')
			self.logger.configuration('-'*80,'warning')

		def _init_neighbor (neighbor):
			families = neighbor.families()
			for change in neighbor.changes:
				if change.nlri.family() in families:
					# This add the family to neighbor.families()
					neighbor.rib.outgoing.insert_announced_watchdog(change)
			for message in messages:
				if message.family() in families:
					if message.name == 'ASM':
						neighbor.asm[message.family()] = message
					else:
						neighbor.messages.append(message)
			self._neighbor[neighbor.name()] = neighbor

		# create one neighbor object per family for multisession
		if neighbor.multisession and len(neighbor.families()) > 1:
			for family in neighbor.families():
				# XXX: FIXME: Ok, it works but it takes LOTS of memory ..
				m_neighbor = deepcopy(neighbor)
				m_neighbor.make_rib()
				m_neighbor.rib.outgoing.families = [family]
				_init_neighbor(m_neighbor)
		else:
			neighbor.make_rib()
			_init_neighbor(neighbor)

		# display configuration
		for line in str(neighbor).split('\n'):
			self.logger.configuration(line)
		self.logger.configuration("\n")

		# ...
		scope.pop(-1)
		return True

	def _multi_neighbor (self, scope, tokens):
		if len(tokens) != 1:
			self._error = 'syntax: neighbor <ip> { <options> }'
			if self.debug: raise Exception()  # noqa
			return False

		address = tokens[0]
		scope.append({})
		try:
			scope[-1]['peer-address'] = IP.create(address)
		except (IndexError,ValueError,socket.error):
			self._error = '"%s" is not a valid IP address' % address
			if self.debug: raise Exception()  # noqa
			return False
		while True:
			r = self._dispatch(
				scope,'neighbor',
				[
					'static','flow','l2vpn',
					'process','family','capability','operational'
				],
				[
					'description','router-id','local-address','local-as','peer-as',
					'passive','listen','connect','hold-time','add-path','graceful-restart','md5',
					'ttl-security','multi-session','group-updates','asn4','aigp',
					'auto-flush','adj-rib-out','manual-eor',
				]
			)
			if r is False:
				return False
			if r is None:
				return True

	# Command Neighbor

	def _set_router_id (self, scope, command, value):
		try:
			ip = RouterID(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1][command] = ip
		return True

	def _set_ip (self, scope, command, value):
		try:
			ip = IP.create(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1][command] = ip
		return True

	def _set_description (self, scope, tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			self._error = 'syntax: description "<description>"'
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['description'] = text[1:-1]
		return True

	# will raise ValueError if the ASN is not correct
	def _newASN (self, value):
		if value.count('.'):
			high,low = value.split('.',1)
			as_number = (int(high) << 16) + int(low)
		else:
			as_number = int(value)
		return ASN(as_number)

	def _set_asn (self, scope, command, value):
		try:
			scope[-1][command] = self._newASN(value[0])
			return True
		except ValueError:
			self._error = '"%s" is an invalid ASN' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	def _set_passive (self, scope, command, value):
		if value:
			self._error = '"%s" is an invalid for passive' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

		scope[-1][command] = True
		return True

	def _set_listen (self, scope, command, value):
		try:
			listen = int(value[0])
			if listen < 0:
				raise ValueError('the listenening port must positive')
			if listen >= pow(2,16):
				raise ValueError('the listening port must be smaller than %d' % pow(2,16))
			scope[-1][command] = listen
			return True
		except ValueError:
			self._error = '"%s" is an invalid port to listen on' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	def _set_connect (self, scope, command, value):
		try:
			connect = int(value[0])
			if connect < 0:
				raise ValueError('the connecting port must positive')
			if connect >= pow(2,16):
				raise ValueError('the connecting port must be smaller than %d' % pow(2,16))
			scope[-1][command] = connect
			return True
		except ValueError:
			self._error = '"%s" is an invalid port to connect on' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	def _set_holdtime (self, scope, command, value):
		try:
			holdtime = HoldTime(value[0])
			if holdtime < 3 and holdtime != 0:
				raise ValueError('holdtime must be zero or at least three seconds')
			if holdtime >= pow(2,16):
				raise ValueError('holdtime must be smaller than %d' % pow(2,16))
			scope[-1][command] = holdtime
			return True
		except ValueError:
			self._error = '"%s" is an invalid hold-time' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	def _set_md5 (self, scope, command, value):
		md5 = value[0]
		if len(md5) > 2 and md5[0] == md5[-1] and md5[0] in ['"',"'"]:
			md5 = md5[1:-1]
		if len(md5) > 80:
			self._error = 'md5 password must be no larger than 80 characters'
			if self.debug: raise Exception()  # noqa
			return False
		if not md5:
			self._error = 'md5 requires the md5 password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.'
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1][command] = md5
		return True

	def _set_ttl (self, scope, command, value):
		if not len(value):
			scope[-1][command] = self.TTL_SECURITY
			return True
		try:
			# README: Should it be a subclass of int ?
			ttl = int(value[0])
			if ttl <= 0:
				raise ValueError('ttl-security must be a positive number (1-254)')
			if ttl >= 255:
				raise ValueError('ttl must be smaller than 255 (1-254)')
			scope[-1][command] = ttl
			return True
		except ValueError:
			self._error = '"%s" is an invalid ttl-security (1-254)' % ' '.join(value)
			if self.debug: raise Exception()  # noqa
			return False

	#  Group Static ................

	def _multi_static (self, scope, tokens):
		if len(tokens) != 0:
			self._error = 'syntax: static { route; route; ... }'
			if self.debug: raise Exception()  # noqa
			return False
		while True:
			r = self._dispatch(
				scope,'static',
				['route',],
				['route',]
			)
			if r is False:
				return False
			if r is None:
				return True

	# Group Route  ........

	def _split_last_route (self, scope):
		# if the route does not need to be broken in smaller routes, return
		change = scope[-1]['announce'][-1]
		if Attribute.CODE.INTERNAL_SPLIT not in change.attributes:
			return True

		# ignore if the request is for an aggregate, or the same size
		mask = change.nlri.mask
		split = change.attributes[Attribute.CODE.INTERNAL_SPLIT]
		if mask >= split:
			return True

		# get a local copy of the route
		change = scope[-1]['announce'].pop(-1)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(change.nlri.packed)*8) - split)
		# how many new routes are we going to create from the initial one
		number = pow(2,split - change.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in change.nlri.packed:
			ip <<= 8
			ip += ord(c)

		afi = change.nlri.afi
		safi = change.nlri.safi

		# Really ugly
		klass = change.nlri.__class__
		if klass is MPLS:
			path_info = change.nlri.path_info
			labels = change.nlri.labels
			rd = change.nlri.rd
		# packed and not pack() but does not matter atm, it is an IP not a NextHop
		nexthop = change.nlri.nexthop.packed

		change.nlri.mask = split
		change.nlri = None
		# generate the new routes
		for _ in range(number):
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			nlri = klass(afi,safi,pack_int(afi,ip,split),split,nexthop,OUT.ANNOUNCE)
			if klass is MPLS:
				nlri.path_info = path_info
				nlri.labels = labels
				nlri.rd = rd
			# next ip
			ip += increment
			# save route
			scope[-1]['announce'].append(Change(nlri,change.attributes))

		return True

	def _insert_static_route (self, scope, tokens):
		try:
			ip = tokens.pop(0)
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		try:
			ip,mask = ip.split('/')
			mask = int(mask)
		except ValueError:
			mask = 32
			if ':' in ip:
				mask = 128
		try:
			if 'rd' in tokens:
				safi = SAFI(SAFI.mpls_vpn)
			elif 'route-distinguisher' in tokens:
				safi = SAFI(SAFI.mpls_vpn)
			elif 'label' in tokens:
				safi = SAFI(SAFI.nlri_mpls)
			else:
				safi = IP.tosafi(ip)

			# nexthop must be false and its str return nothing .. an empty string does that
			update = Change(MPLS(afi=IP.toafi(ip),safi=safi,packed=IP.pton(ip),mask=mask,nexthop=None,action=OUT.ANNOUNCE),Attributes())
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(update)
		return True

	def _check_static_route (self, scope):
		update = scope[-1]['announce'][-1]
		if update.nlri.nexthop is NoIP:
			self._error = 'syntax: route <ip>/<mask> { next-hop <ip>; }'
			if self.debug: raise Exception()  # noqa
			return False
		return True

	def _multi_static_route (self, scope, tokens):
		if len(tokens) != 1:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		if not self._insert_static_route(scope,tokens):
			return False

		while True:
			r = self._dispatch(
				scope,'route',
				[],
				[
					'next-hop','origin','as-path','as-sequence','med','aigp',
					'local-preference','atomic-aggregate','aggregator',
					'path-information','community','originator-id','cluster-list',
					'extended-community','split','label','rd','route-distinguisher',
					'watchdog','withdraw','attribute'
				]
			)
			if r is False:
				return False
			if r is None:
				return self._split_last_route(scope)

	def _single_static_route (self, scope, tokens):
		if len(tokens) < 3:
			return False

		if not self._insert_static_route(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)

			if command in ('withdraw','withdrawn'):
				if self._route_withdraw(scope,tokens):
					continue
				return False

			if len(tokens) < 1:
				return False

			if command in self._dispatch_route_cfg:
				if command in ('rd','route-distinguisher'):
					if self._dispatch_route_cfg[command](scope,tokens,SAFI.mpls_vpn):
						continue
				else:
					if self._dispatch_route_cfg[command](scope,tokens):
						continue
			else:
				return False
			return False

		if not self._check_static_route(scope):
			return False

		return self._split_last_route(scope)

	def _single_l2vpn_vpls (self, scope, tokens):
		# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
		if len(tokens) < 10:
			return False

		if not self._insert_l2vpn_vpls(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if len(tokens) < 1:
				return False
			if command in self._dispatch_vpls_cfg:
				if command in ('rd','route-distinguisher'):
					if self._dispatch_vpls_cfg[command](scope,tokens,SAFI.vpls):
						continue
				else:
					if self._dispatch_vpls_cfg[command](scope,tokens):
						continue
			else:
				return False
			return False

		if not self._check_l2vpn_vpls(scope):
			return False
		return True

	# Command Route

	def _route_generic_attribute (self, scope, tokens):
		try:
			start = tokens.pop(0)
			code = tokens.pop(0).lower()
			flag = tokens.pop(0).lower()
			data = tokens.pop(0).lower()
			end = tokens.pop(0)

			if (start,end) != ('[',']'):
				self._error = self._str_route_error
				if self.debug: raise Exception()  # noqa
				return False

			if not code.startswith('0x'):
				self._error = self._str_route_error
				if self.debug: raise Exception()  # noqa
				return False
			code = int(code[2:],16)

			if not flag.startswith('0x'):
				self._error = self._str_route_error
				if self.debug: raise Exception()  # noqa
				return False
			flag = int(flag[2:],16)

			if not data.startswith('0x'):
				self._error = self._str_route_error
				if self.debug: raise Exception()  # noqa
				return False
			raw = ''
			for i in range(2,len(data),2):
				raw += chr(int(data[i:i+2],16))

			try:
				for ((ID,_),klass) in Attribute.registered_attributes.iteritems():
					if code == ID and flag == klass.FLAG:
						scope[-1]['announce'][-1].attributes.add(klass.unpack(raw,None))
						return True
			except Exception:
				pass

			scope[-1]['announce'][-1].attributes.add(GenericAttribute(code,flag,raw))
			return True
		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_next_hop (self, scope, tokens):
		if scope[-1]['announce'][-1].attributes.has(Attribute.CODE.NEXT_HOP):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		try:
			# next-hop self is unsupported
			ip = tokens.pop(0)
			if ip.lower() == 'self':
				if 'local-address' in scope[-1]:
					la = scope[-1]['local-address']
				elif self._nexthopself:
					la = self._nexthopself
				else:
					self._error = 'next-hop self can only be specified with a neighbor'
					if self.debug: raise ValueError(self._error)  # noqa
					return False
				nh = IP.unpack(la.pack())
			else:
				nh = IP.create(ip)

			change = scope[-1]['announce'][-1]
			nlri = change.nlri
			afi = nlri.afi
			safi = nlri.safi

			nlri.nexthop = nh

			if afi == AFI.ipv4 and safi in (SAFI.unicast,SAFI.multicast):
				change.attributes.add(Attribute.unpack(NextHop.ID,NextHop.FLAG,nh.packed,None))
				# NextHop(nh.ip,nh.packed) does not cache the result, using unpack does
				# change.attributes.add(NextHop(nh.ip,nh.packed))

			return True
		except Exception:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_origin (self, scope, tokens):
		try:
			data = tokens.pop(0).lower()
			if data == 'igp':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.IGP))
				return True
			if data == 'egp':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.EGP))
				return True
			if data == 'incomplete':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.INCOMPLETE))
				return True
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_aspath (self, scope, tokens):
		as_seq = []
		as_set = []
		asn = tokens.pop(0)
		inset = False
		try:
			if asn == '[':
				while True:
					try:
						asn = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise Exception()  # noqa
						return False
					if asn == ',':
						continue
					if asn in ('(','['):
						inset = True
						while True:
							try:
								asn = tokens.pop(0)
							except IndexError:
								self._error = self._str_route_error
								if self.debug: raise Exception()  # noqa
								return False
							if asn == ')':
								break
							as_set.append(self._newASN(asn))
					if asn == ')':
						inset = False
						continue
					if asn == ']':
						if inset:
							inset = False
							continue
						break
					as_seq.append(self._newASN(asn))
			else:
				as_seq.append(self._newASN(asn))
		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['announce'][-1].attributes.add(ASPath(as_seq,as_set))
		return True

	def _route_med (self, scope, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(MED(int(tokens.pop(0))))
			return True
		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_aigp (self, scope, tokens):
		try:
			number = tokens.pop(0)
			base = 16 if number.lower().startswith('0x') else 10
			scope[-1]['announce'][-1].attributes.add(AIGP('\x01\x00\x0b' + pack('!Q',int(number,base))))
			return True
		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_local_preference (self, scope, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(LocalPreference(int(tokens.pop(0))))
			return True
		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_atomic_aggregate (self, scope, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(AtomicAggregate())
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_aggregator (self, scope, tokens):
		try:
			if tokens:
				if tokens.pop(0) != '(':
					raise ValueError('invalid aggregator syntax')
				asn,address = tokens.pop(0).split(':')
				if tokens.pop(0) != ')':
					raise ValueError('invalid aggregator syntax')
				local_as = ASN(asn)
				local_address = RouterID(address)
			else:
				local_as = scope[-1]['local-as']
				local_address = scope[-1]['local-address']
		except (ValueError,IndexError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		except KeyError:
			self._error = 'local-as and/or local-address missing from neighbor/group to make aggregator'
			if self.debug: raise Exception()  # noqa
			return False
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		scope[-1]['announce'][-1].attributes.add(Aggregator(local_as,local_address))
		return True

	def _route_path_information (self, scope, tokens):
		try:
			pi = tokens.pop(0)
			if pi.isdigit():
				scope[-1]['announce'][-1].nlri.path_info = PathInfo(integer=int(pi))
			else:
				scope[-1]['announce'][-1].nlri.path_info = PathInfo(ip=pi)
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _parse_community (self, scope, data):
		separator = data.find(':')
		if separator > 0:
			prefix = int(data[:separator])
			suffix = int(data[separator+1:])
			if prefix >= pow(2,16):
				raise ValueError('invalid community %s (prefix too large)' % data)
			if suffix >= pow(2,16):
				raise ValueError('invalid community %s (suffix too large)' % data)
			return Community.cached(pack('!L',(prefix << 16) + suffix))
		elif len(data) >= 2 and data[1] in 'xX':
			value = long(data,16)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data)
			return Community.cached(pack('!L',value))
		else:
			low = data.lower()
			if low == 'no-export':
				return Community.cached(Community.NO_EXPORT)
			elif low == 'no-advertise':
				return Community.cached(Community.NO_ADVERTISE)
			elif low == 'no-export-subconfed':
				return Community.cached(Community.NO_EXPORT_SUBCONFED)
			# no-peer is not a correct syntax but I am sure someone will make the mistake :)
			elif low == 'nopeer' or low == 'no-peer':
				return Community.cached(Community.NO_PEER)
			elif low == 'blackhole':
				return Community.cached(Community.BLACKHOLE)
			elif data.isdigit():
				value = long(data)
				if value >= pow(2,32):
					raise ValueError('invalid community %s (too large)' % data)
					# return Community.cached(pack('!L',value))
				return Community.cached(pack('!L',value))
			else:
				raise ValueError('invalid community name %s' % data)

	def _route_originator_id (self, scope, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(OriginatorID(tokens.pop(0)))
			return True
		except Exception:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_cluster_list (self, scope, tokens):
		_list = []
		clusterid = tokens.pop(0)
		try:
			if clusterid == '[':
				while True:
					try:
						clusterid = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise Exception()  # noqa
						return False
					if clusterid == ']':
						break
					_list.append(ClusterID(clusterid))
			else:
				_list.append(ClusterID(clusterid))
			if not _list:
				raise ValueError('no cluster-id in the cluster-list')
			clusterlist = ClusterList(_list)
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['announce'][-1].attributes.add(clusterlist)
		return True

	def _route_community (self, scope, tokens):
		communities = Communities()
		community = tokens.pop(0)
		try:
			if community == '[':
				while True:
					try:
						community = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise Exception()  # noqa
						return False
					if community == ']':
						break
					communities.add(self._parse_community(scope,community))
			else:
				communities.add(self._parse_community(scope,community))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		scope[-1]['announce'][-1].attributes.add(communities)
		return True

	def _parse_extended_community (self, scope, data):
		SIZE_H = 0xFFFF

		if data[:2].lower() == '0x':
			try:
				raw = ''
				for i in range(2,len(data),2):
					raw += chr(int(data[i:i+2],16))
			except ValueError:
				raise ValueError('invalid extended community %s' % data)
			if len(raw) != 8:
				raise ValueError('invalid extended community %s' % data)
			return ExtendedCommunity.unpack(raw,None)
		elif data.count(':'):
			_known_community = {
				# header and subheader
				'redirect-to-nexthop': chr(0x80)+chr(0x00),
				'target':              chr(0x00)+chr(0x02),
				'target4':             chr(0x02)+chr(0x02),
				'origin':              chr(0x00)+chr(0x03),
				'origin4':             chr(0x02)+chr(0x03),
				'redirect':            chr(0x80)+chr(0x08),
				'l2info':              chr(0x80)+chr(0x0A),
			}

			_size_community = {
				'redirect-to-nexthop': 2,
				'target':              2,
				'target4':             2,
				'origin':              2,
				'origin4':             2,
				'redirect':            2,
				'l2info':              4,
			}

			components = data.split(':')
			command = 'target' if len(components) == 2 else components.pop(0)

			if command not in _known_community:
				raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)

			if len(components) != _size_community[command]:
				raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))

			header = _known_community.get(command,None)

			if command == 'l2info':
				# encaps, control, mtu, site
				return ExtendedCommunity.unpack(header+pack('!BBHH',*[int(_) for _ in components]),None)

			if command in ('target','origin'):
				# global admin, local admin
				_ga,_la = components
				ga,la = _ga.upper(),_la.upper()

				if '.' in ga or '.' in la:
					gc = ga.count('.')
					lc = la.count('.')
					if gc == 0 and lc == 3:
						# ASN first, IP second
						return ExtendedCommunity.unpack(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]),None)
					if gc == 3 and lc == 0:
						# IP first, ASN second
						return ExtendedCommunity.unpack(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]),None)
				else:
					iga = int(ga[:-1]) if 'L' in ga else int(ga)
					ila = int(la[:-1]) if 'L' in la else int(la)
					if command == 'target':
						if ga.endswith('L') or iga > SIZE_H:
							return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)
						else:
							return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)
					if command == 'origin':
						if ga.endswith('L') or iga > SIZE_H:
							return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)
						else:
							return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)

			if command == 'target4':
				iga = int(ga[:-1]) if 'L' in ga else int(ga)
				ila = int(la[:-1]) if 'L' in la else int(la)
				return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)

			if command == 'orgin4':
				iga = int(ga[:-1]) if 'L' in ga else int(ga)
				ila = int(la[:-1]) if 'L' in la else int(la)
				return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)

			if command in ('redirect',):
				ga,la = components
				return ExtendedCommunity.unpack(header+pack('!HL',int(ga),long(la)),None)

			if command in ('redirect-nexthop',):
				return ExtendedCommunity.unpack(header+pack('!HL',0,0),None)

			raise ValueError('invalid extended community %s' % command)
		else:
			raise ValueError('invalid extended community %s - lc+gc' % data)

	def _route_extended_community (self, scope, tokens):
		attributes = scope[-1]['announce'][-1].attributes
		if Attribute.CODE.EXTENDED_COMMUNITY in attributes:
			extended_communities = attributes[Attribute.CODE.EXTENDED_COMMUNITY]
		else:
			extended_communities = ExtendedCommunities()
			attributes.add(extended_communities)

		extended_community = tokens.pop(0)
		try:
			if extended_community == '[':
				while True:
					try:
						extended_community = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise Exception()  # noqa
						return False
					if extended_community == ']':
						break
					extended_communities.add(self._parse_extended_community(scope,extended_community))
			else:
				extended_communities.add(self._parse_extended_community(scope,extended_community))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False
		return True

	def _route_split (self, scope, tokens):
		try:
			size = tokens.pop(0)
			if not size or size[0] != '/':
				raise ValueError('route "as" require a CIDR')
			scope[-1]['announce'][-1].attributes.add(Split(int(size[1:])))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _route_label (self, scope, tokens):
		labels = []
		label = tokens.pop(0)
		try:
			if label == '[':
				while True:
					try:
						label = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise Exception()  # noqa
						return False
					if label == ']':
						break
					labels.append(int(label))
			else:
				labels.append(int(label))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

		nlri = scope[-1]['announce'][-1].nlri
		if not nlri.safi.has_label():
			nlri.safi = SAFI(SAFI.nlri_mpls)
		nlri.labels = Labels(labels)
		return True

	def _route_rd (self, scope, tokens, safi):
		try:
			try:
				data = tokens.pop(0)
			except IndexError:
				self._error = self._str_route_error
				if self.debug: raise Exception()  # noqa
				return False

			separator = data.find(':')
			if separator > 0:
				prefix = data[:separator]
				suffix = int(data[separator+1:])

			if '.' in prefix:
				data = [chr(0),chr(1)]
				data.extend([chr(int(_)) for _ in prefix.split('.')])
				data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
				rd = ''.join(data)
			else:
				number = int(prefix)
				if number < pow(2,16) and suffix < pow(2,32):
					rd = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
				elif number < pow(2,32) and suffix < pow(2,16):
					rd = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
				else:
					raise ValueError('invalid route-distinguisher %s' % data)

			nlri = scope[-1]['announce'][-1].nlri
			# overwrite nlri-mpls
			nlri.safi = SAFI(safi)
			nlri.rd = RouteDistinguisher(rd)
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	# VPLS

	def _multi_l2vpn (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False
		while True:
			r = self._dispatch(
				scope,'l2vpn',
				['vpls',],
				['vpls',]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _insert_l2vpn_vpls (self, scope, tokens=None):
		try:
			attributes = Attributes()
			change = Change(VPLS(None,None,None,None,None),attributes)
		except ValueError:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(change)
		return True

	def _multi_l2vpn_vpls (self, scope, tokens):
		if len(tokens) > 1:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False

		if not self._insert_l2vpn_vpls(scope):
			return False

		while True:
			r = self._dispatch(
				scope,'l2vpn',
				[],
				[
					'next-hop','origin','as-path','med','local-preference',
					'community','originator-id','cluster-list','extended-community',
					'rd','route-distinguisher','withdraw',
					'endpoint','offset',
					'size','base'
				]
			)
			if r is False:
				return False
			if r is None:
				break

		return True

	# Group Flow  ........

	def _multi_flow (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		while True:
			r = self._dispatch(
				scope,'flow',
				['route',],
				[]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _insert_flow_route (self, scope, tokens=None):
		if self._flow_state != 'out':
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		self._flow_state = 'match'

		try:
			attributes = Attributes()
			attributes[Attribute.CODE.EXTENDED_COMMUNITY] = ExtendedCommunities()
			flow = Change(Flow(),attributes)
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(flow)
		return True

	def _check_flow_route (self, scope):
		self.logger.configuration('warning: no check on flows are implemented')
		return True

	def _check_l2vpn_vpls (self, scope):
		nlri = scope[-1]['announce'][-1].nlri

		if nlri.ve is None:
			raise ValueError(self._str_vpls_bad_enpoint)

		if nlri.base is None:
			raise ValueError(self._str_vpls_bad_label)

		if nlri.offset is None:
			raise ValueError(self._str_vpls_bad_offset)

		if nlri.size is None:
			raise ValueError(self._str_vpls_bad_size)

		if nlri.base > (0xFFFFF - nlri.size):  # 20 bits, 3 bytes
			raise ValueError(self._str_vpls_bad_label)

		return True

	def _multi_flow_route (self, scope, tokens):
		if len(tokens) > 1:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		if not self._insert_flow_route(scope):
			return False

		while True:
			r = self._dispatch(
				scope,'flow-route',
				['match','then'],
				['rd','route-distinguisher','next-hop']
			)
			if r is False:
				return False
			if r is None:
				break

		if self._flow_state != 'out':
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		return True

	def _l2vpn_vpls_endpoint (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_enpoint)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.ve = number
		return True

	def _l2vpn_vpls_size (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_size)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.size = number
		return True

	def _l2vpn_vpls_offset (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_offset)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.offset = number
		return True

	def _l2vpn_vpls_base (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_label)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.base = number
		return True

	# ..........................................

	def _multi_match (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		if self._flow_state != 'match':
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		self._flow_state = 'then'

		while True:
			r = self._dispatch(
				scope,'flow-match',
				[],
				[
					'source','destination',
					'source-ipv4','destination-ipv4',
					'port','source-port','destination-port',
					'protocol','next-header','tcp-flags','icmp-type','icmp-code',
					'fragment','dscp','traffic-class','packet-length','flow-label'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _multi_then (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		if self._flow_state != 'then':
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		self._flow_state = 'out'

		while True:
			r = self._dispatch(
				scope,'flow-then',
				[],
				[
					'accept','discard','rate-limit',
					'redirect','copy','redirect-to-nexthop',
					'mark','action',
					'community','extended-community'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	# ..........................................

	def _multi_receive (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		while True:
			r = self._dispatch(
				scope,'receive',
				[],
				[
					'packets','parsed','consolidate',
					'neighbor-changes',
					'notification','open','keepalive',
					'update','updates','refresh','operational'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _multi_send (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

		while True:
			r = self._dispatch(
				scope,'send',
				[],
				['packets']
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	# Command Flow

	def _flow_source (self, scope, tokens):
		try:
			data = tokens.pop(0)
			if ':' in data:
				if data.count('/') == 1:
					ip,netmask = data.split('/')
					offset = 0
				else:
					ip,netmask,offset = data.split('/')
				change = scope[-1]['announce'][-1]
				change.nlri.afi = AFI(AFI.ipv6)
				if not change.nlri.add(Flow6Source(IP.pton(ip),int(netmask),int(offset))):
					self._error = 'Flow can only have one source'
					if self.debug: raise ValueError(self._error)  # noqa
					return False
			else:
				ip,netmask = data.split('/')
				raw = ''.join(chr(int(_)) for _ in ip.split('.'))

				if not scope[-1]['announce'][-1].nlri.add(Flow4Source(raw,int(netmask))):
					self._error = 'Flow can only have one source'
					if self.debug: raise ValueError(self._error)  # noqa
					return False
			return True

		except (IndexError,ValueError):
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_destination (self, scope, tokens):
		try:
			data = tokens.pop(0)
			if ':' in data:
				if data.count('/') == 1:
					ip,netmask = data.split('/')
					offset = 0
				else:
					ip,netmask,offset = data.split('/')
				change = scope[-1]['announce'][-1]
				# XXX: This is ugly
				change.nlri.afi = AFI(AFI.ipv6)
				if not change.nlri.add(Flow6Destination(IP.pton(ip),int(netmask),int(offset))):
					self._error = 'Flow can only have one destination'
					if self.debug: raise ValueError(self._error)  # noqa
					return False

			else:
				ip,netmask = data.split('/')
				raw = ''.join(chr(int(_)) for _ in ip.split('.'))

				if not scope[-1]['announce'][-1].nlri.add(Flow4Destination(raw,int(netmask))):
					self._error = 'Flow can only have one destination'
					if self.debug: raise ValueError(self._error)  # noqa
					return False
			return True

		except (IndexError,ValueError):
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

	# to parse the port configuration of flow

	def _operator (self, string):
		try:
			if string[0] == '=':
				return NumericOperator.EQ,string[1:]
			elif string[0] == '>':
				operator = NumericOperator.GT
			elif string[0] == '<':
				operator = NumericOperator.LT
			else:
				raise ValueError('Invalid operator in test %s' % string)
			if string[1] == '=':
				operator += NumericOperator.EQ
				return operator,string[2:]
			else:
				return operator,string[1:]
		except IndexError:
			raise Exception('Invalid expression (too short) %s' % string)

	def _value (self, string):
		l = 0
		for c in string:
			if c not in ['&',]:
				l += 1
				continue
			break
		return string[:l],string[l:]

	# parse =80 or >80 or <25 or &>10<20
	def _flow_generic_expression (self, scope, tokens, klass):
		try:
			for test in tokens:
				AND = BinaryOperator.NOP
				while test:
					operator,_ = self._operator(test)
					value,test = self._value(_)
					nlri = scope[-1]['announce'][-1].nlri
					# XXX: should do a check that the rule is valid for the family
					nlri.add(klass(AND | operator,klass.converter(value)))
					if test:
						if test[0] == '&':
							AND = BinaryOperator.AND
							test = test[1:]
							if not test:
								raise ValueError("Can not finish an expresion on an &")
						else:
							raise ValueError("Unknown binary operator %s" % test[0])
			return True
		except ValueError,exc:
			self._error = self._str_route_error + str(exc)
			if self.debug: raise Exception()  # noqa
			return False

	# parse [ content1 content2 content3 ]
	def _flow_generic_list (self, scope, tokens, klass):
		try:
			name = tokens.pop(0)
			AND = BinaryOperator.NOP
			if name == '[':
				while True:
					name = tokens.pop(0)
					if name == ']':
						break
					try:
						nlri = scope[-1]['announce'][-1].nlri
						# XXX: should do a check that the rule is valid for the family
						nlri.add(klass(NumericOperator.EQ | AND,klass.converter(name)))
					except IndexError:
						self._error = self._str_flow_error
						if self.debug: raise Exception()  # noqa
						return False
			else:
				if name[0] == '=':
					name = name[1:]
				scope[-1]['announce'][-1].nlri.add(klass(NumericOperator.EQ | AND,klass.converter(name)))
		except (IndexError,ValueError), exc:
			self._error = self._str_flow_error + str(exc)
			if self.debug: raise Exception()  # noqa
			return False
		return True

	def _flow_generic_condition (self, scope, tokens, klass):
		if tokens[0][0] in ['=','>','<']:
			return self._flow_generic_expression(scope,tokens,klass)
		return self._flow_generic_list(scope,tokens,klass)

	def _flow_route_anyport (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowAnyPort)

	def _flow_route_source_port (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowSourcePort)

	def _flow_route_destination_port (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowDestinationPort)

	def _flow_route_packet_length (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowPacketLength)

	def _flow_route_tcp_flags (self, scope, tokens):
		return self._flow_generic_list(scope,tokens,FlowTCPFlag)

	def _flow_route_protocol (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowIPProtocol)

	def _flow_route_next_header (self, scope, tokens):
		return self._flow_generic_list(scope,tokens,FlowNextHeader)

	def _flow_route_icmp_type (self, scope, tokens):
		return self._flow_generic_list(scope,tokens,FlowICMPType)

	def _flow_route_icmp_code (self, scope, tokens):
		return self._flow_generic_list(scope,tokens,FlowICMPCode)

	def _flow_route_fragment (self, scope, tokens):
		return self._flow_generic_list(scope,tokens,FlowFragment)

	def _flow_route_dscp (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowDSCP)

	def _flow_route_traffic_class (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowTrafficClass)

	def _flow_route_flow_label (self, scope, tokens):
		return self._flow_generic_condition(scope,tokens,FlowFlowLabel)

	def _flow_route_next_hop (self, scope, tokens):
		try:
			change = scope[-1]['announce'][-1]

			if change.nlri.nexthop is not NoIP:
				self._error = self._str_flow_error
				if self.debug: raise Exception()  # noqa
				return False

			change.nlri.nexthop = IP.create(tokens.pop(0))
			return True

		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_accept (self, scope, tokens):
		return True

	def _flow_route_discard (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRate(ASN(0),0))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_rate_limit (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			speed = int(tokens[0])
			if speed < 9600 and speed != 0:
				self.logger.configuration("rate-limiting flow under 9600 bytes per seconds may not work",'warning')
			if speed > 1000000000000:
				speed = 1000000000000
				self.logger.configuration("rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0],'warning')
			scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRate(ASN(0),speed))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_redirect (self, scope, tokens):
		try:
			if tokens[0].count(':') == 1:
				prefix,suffix = tokens[0].split(':',1)
				if prefix.count('.'):
					raise ValueError('this format has been deprecaded as it does not make sense and it is not supported by other vendors')
				else:
					asn = int(prefix)
					route_target = int(suffix)
					if asn >= pow(2,16):
						raise ValueError('asn is a 32 bits number, it can only be 16 bit %s' % route_target)
					if route_target >= pow(2,32):
						raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
					scope[-1]['announce'][-1].attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficRedirect(asn,route_target))
					return True
			else:
				change = scope[-1]['announce'][-1]
				if change.nlri.nexthop is not NoIP:
					self._error = self._str_flow_error
					if self.debug: raise Exception()  # noqa
					return False

				nh = IP.create(tokens.pop(0))
				change.nlri.nexthop = nh
				change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(False))
				return True

		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_redirect_next_hop (self, scope, tokens):
		try:
			change = scope[-1]['announce'][-1]

			if change.nlri.nexthop is NoIP:
				self._error = self._str_flow_error
				if self.debug: raise Exception()  # noqa
				return False

			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(False))
			return True

		except (IndexError,ValueError):
			self._error = self._str_route_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_copy (self, scope, tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			if scope[-1]['announce'][-1].attributes.has(Attribute.CODE.NEXT_HOP):
				self._error = self._str_flow_error
				if self.debug: raise Exception()  # noqa
				return False

			change = scope[-1]['announce'][-1]
			change.nlri.nexthop = IP.create(tokens.pop(0))
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficNextHop(True))
			return True

		except (IndexError,ValueError):
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_mark (self, scope, tokens):
		try:
			dscp = int(tokens.pop(0))

			if dscp < 0 or dscp > 0b111111:
				self._error = self._str_flow_error
				if self.debug: raise Exception()  # noqa
				return False

			change = scope[-1]['announce'][-1]
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficMark(dscp))
			return True

		except (IndexError,ValueError):
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

	def _flow_route_action (self, scope, tokens):
		try:
			action = tokens.pop(0)
			sample = 'sample' in action
			terminal = 'terminal' in action

			if not sample and not terminal:
				self._error = self._str_flow_error
				if self.debug: raise Exception()  # noqa
				return False

			change = scope[-1]['announce'][-1]
			change.attributes[Attribute.CODE.EXTENDED_COMMUNITY].add(TrafficAction(sample,terminal))
			return True
		except (IndexError,ValueError):
			self._error = self._str_flow_error
			if self.debug: raise Exception()  # noqa
			return False

	#  Group Operational ................

	def _multi_operational (self, scope, tokens):
		if len(tokens) != 0:
			self._error = 'syntax: operational { command; command; ... }'
			if self.debug: raise Exception()  # noqa
			return False
		while True:
			r = self._dispatch(
				scope,'operational',
				[],
				['asm',]
			)
			if r is False:
				return False
			if r is None:
				return True

	def _single_operational_asm (self, scope, value):
		return self._single_operational(Advisory.ASM,scope,['afi','safi','advisory'],value)

	def _single_operational (self, klass, scope, parameters, value):
		def utf8 (string): return string.encode('utf-8')[1:-1]

		convert = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': int,
			'counter': long,
			'advisory': utf8
		}

		def valid (_):
			return True

		def u32 (_):
			return int(_) <= 0xFFFFFFFF

		def u64 (_):
			return long(_) <= 0xFFFFFFFFFFFFFFFF

		def advisory (_):
			return len(_.encode('utf-8')) <= MAX_ADVISORY + 2  # the two quotes

		validate = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': u32,
			'counter': u64,
		}

		number = len(parameters)*2
		tokens = formated(value).split(' ',number-1)
		if len(tokens) != number:
			self._error = 'invalid operational syntax, wrong number of arguments'
			return False

		data = {}

		while tokens and parameters:
			command = tokens.pop(0).lower()
			value = tokens.pop(0)

			if command == 'router-id':
				if isipv4(value):
					data['routerid'] = RouterID(value)
				else:
					self._error = 'invalid operational value for %s' % command
					return False
				continue

			expected = parameters.pop(0)

			if command != expected:
				self._error = 'invalid operational syntax, unknown argument %s' % command
				return False
			if not validate.get(command,valid)(value):
				self._error = 'invalid operational value for %s' % command
				return False

			data[command] = convert[command](value)

		if tokens or parameters:
			self._error = 'invalid advisory syntax, missing argument(s) %s' % ', '.join(parameters)
			return False

		if 'routerid' not in data:
			data['routerid'] = None

		if 'operational' not in scope[-1]:
			scope[-1]['operational'] = []

		# iterate on each family for the peer if multiprotocol is set.
		scope[-1]['operational'].append(klass(**data))
		return True

	# ..............................

	def decode (self, update):
		# self check to see if we can decode what we encode
		from exabgp.bgp.message.update import Update
		from exabgp.bgp.message.open import Open
		from exabgp.bgp.message.open.capability.capability import Capability
		from exabgp.bgp.message.open.capability.capabilities import Capabilities
		from exabgp.bgp.message.open.capability.negotiated import Negotiated
		from exabgp.bgp.message.notification import Notify
		from exabgp.reactor.peer import Peer
		from exabgp.reactor.api.encoding import JSON

		self.logger._parser = True

		self.logger.parser('\ndecoding routes in configuration')

		n = self.neighbor[self.neighbor.keys()[0]]
		p = Peer(n,None)

		path = {}
		for f in known_families():
			if n.add_path:
				path[f] = n.add_path

		capa = Capabilities().new(n,False)
		capa[Capability.CODE.ADD_PATH] = path
		capa[Capability.CODE.MULTIPROTOCOL] = n.families()

		o1 = Open(4,n.local_as,str(n.local_address),capa,180)
		o2 = Open(4,n.peer_as,str(n.peer_address),capa,180)
		negotiated = Negotiated(n)
		negotiated.sent(o1)
		negotiated.received(o2)
		# grouped = False

		raw = ''.join(chr(int(_,16)) for _ in (update[i*2:(i*2)+2] for i in range(len(update)/2)))

		while raw:
			if raw.startswith('\xff'*16):
				kind = ord(raw[18])
				size = (ord(raw[16]) << 16) + (ord(raw[17]))

				injected,raw = raw[19:size],raw[size:]

				if kind == 2:
					self.logger.parser('the message is an update')
					decoding = 'update'
				else:
					self.logger.parser('the message is not an update (%d) - aborting' % kind)
					sys.exit(1)
			else:
				self.logger.parser('header missing, assuming this message is ONE update')
				decoding = 'update'
				injected,raw = raw,''

			try:
				# This does not take the BGP header - let's assume we will not break that :)
				update = Update.unpack_message(negotiated,injected)
			except KeyboardInterrupt:
				raise
			except Notify,exc:
				self.logger.parser('could not parse the message')
				self.logger.parser(str(exc))
				sys.exit(1)
			except Exception,exc:
				self.logger.parser('could not parse the message')
				self.logger.parser(str(exc))
				sys.exit(1)

			self.logger.parser('')  # new line
			for number in range(len(update.nlris)):
				change = Change(update.nlris[number],update.attributes)
				self.logger.parser('decoded %s %s %s' % (decoding,change.nlri.action,change.extensive()))
			self.logger.parser('update json %s' % JSON('3.4.0').update(p,update,'',''))
		sys.exit(0)
