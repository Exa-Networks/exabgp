#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import socket
import time

from exabgp.bgp.message import Message
from exabgp.bgp.message import IN


class APIOptions (dict):
	def set (self, key, value):
		self[key] = self.get(key,False) or value

	def set_value (self, direction, name, value):
		key = '%s-%s' % (direction,name)
		self[key] = self.get(key,False) or value

	def set_message (self, direction, name, value):
		key = '%s-%d' % (direction,name)
		self[key] = self.get(key,False) or value

	def __missing__ (self, key):
		return False


def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return ''.join(spaced(value))


class Text (object):
	def __init__ (self, version):
		self.version = version

	def _header_body (self, header, body):
		header = ' header %s' % hexstring(header) if header else ''
		body = ' body %s' % hexstring(body) if body else ''

		total_string = header+body if body else header

		return total_string

	def reset (self, peer):
		return None

	def increase (self, peer):
		return None

	def up (self, peer):
		return 'neighbor %s up\n' % (
			peer.neighbor.peer_address
		)

	def connected (self, peer):
		return 'neighbor %s connected\n' % (
			peer.neighbor.peer_address
		)

	def down (self, peer, reason=''):
		return 'neighbor %s down - %s\n' % (
			peer.neighbor.peer_address,
			reason
		)

	def shutdown (self):
		return 'shutdown %d %d\n' % (
			os.getpid(),
			os.getppid()
		)

	def notification (self, peer, direction, code, subcode, data):
		return 'neighbor %s %s notification %s code %d subcode %d data %s\n' % (
			peer.neighbor.peer_address,
			direction,
			code,
			subcode,
			hexstring(data)
		)

	def packets (self, peer, direction, category, header, body):
		return 'neighbor %s %s %d header %s body %s\n' % (
			peer.neighbor.peer_address,
			direction,
			category,
			hexstring(header),
			hexstring(body)
		)

	def keepalive (self, peer, direction, header, body):
		return 'neighbor %s %s keepalive%s\n' % (
			peer.neighbor.peer_address,
			direction,
			self._header_body(header,body)
		)

	def open (self, peer, direction, sent_open, header, body):
		return 'neighbor %s %s open version %d asn %d hold_time %s router_id %s capabilities [%s]%s\n' % (
			peer.neighbor.peer_address,
			direction,
			sent_open.version,
			sent_open.asn,
			sent_open.hold_time,
			sent_open.router_id,
			str(sent_open.capabilities).lower(),
			self._header_body(header,body)
		)

	def update (self, peer, direction, update, header, body):
		prefix = 'neighbor %s %s update' % (
			peer.neighbor.peer_address,
			direction,
		)

		r = '%s start\n' % prefix

		attributes = str(update.attributes)
		for nlri in update.nlris:
			if nlri.EOR:
				r += '%s route %s\n' % (prefix,nlri.extensive())
			elif nlri.action == IN.ANNOUNCED:  # pylint: disable=E1101
				if nlri.nexthop:
					r += '%s announced %s%s\n' % (prefix,nlri.extensive(),attributes)
				else:
					# This is an EOR or Flow or ... something newer
					r += '%s %s %s\n' % (prefix,nlri.extensive(),attributes)
			else:
				r += '%s withdrawn %s\n' % (prefix,nlri.extensive())
		if header or body:
			r += '%s\n' % self._header_body(header,body)

		r += '%s end\n' % prefix

		return r

	def refresh (self, peer, direction, refresh, header, body):
		return 'neighbor %s %s route-refresh afi %s safi %s %s%s\n' % (
			peer.neighbor.peer_address,
			direction,
			refresh.afi,
			refresh.safi,
			refresh.reserved,
			self._header_body(
				'header %s' % hexstring(header) if header else '',
				'body %s' % hexstring(body) if body else ''
			)
		)

	def _operational_advisory (self, peer, direction, operational, header, body):
		return 'neighbor %s %s operational %s afi %s safi %s advisory "%s"%s' % (
			peer.neighbor.peer_address,
			direction,
			operational.name,
			operational.afi,
			operational.safi,
			operational.data,
			self._header_body(header,body)
		)

	def _operational_query (self, peer, direction, operational, header, body):
		return 'neighbor %s %s operational %s afi %s safi %s%s' % (
			peer.neighbor.peer_address,
			direction,
			operational.name,
			operational.afi,
			operational.safi,
			self._header_body(header,body)
		)

	def _operational_counter (self, peer, direction, operational, header, body):
		return 'neighbor %s %s operational %s afi %s safi %s router-id %s sequence %d counter %d%s' % (
			peer.neighbor.peer_address,
			direction,
			operational.name,
			operational.afi,
			operational.safi,
			operational.routerid,
			operational.sequence,
			operational.counter,
			self._header_body(header,body)
		)

	def operational (self, peer, direction, what, operational, header, body):
		if what == 'advisory':
			return self._operational_advisory(peer,direction,operational,header,body)
		elif what == 'query':
			return self._operational_query(peer,direction,operational,header,body)
		elif what == 'counter':
			return self._operational_counter(peer,direction,operational,header,body)
		# elif what == 'interface':
		# 	return self._operational_interface(peer,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')


def nop (_): return _


class JSON (object):
	_counter = {}

	def __init__ (self, version, highres=False):
		self.version = version
		self.time = nop if highres else int

	def reset (self, peer):
		self._counter[peer.neighbor.peer_address] = 0

	def increase (self, peer):
		address = peer.neighbor.peer_address
		self._counter[address] = self._counter.get(address,0) + 1

	def count (self, peer):
		return self._counter.get(peer.neighbor.peer_address,0)

	def _string (self, _):
		return '%s' % _ if issubclass(_.__class__,int) or issubclass(_.__class__,long) or ('{' in str(_)) else '"%s"' % _

	def _header (self, content, header, body, ident=None,count=None,message_type=None):
		peer     = '"host" : "%s", '   % socket.gethostname()
		pid      = '"pid" : %s, '      % os.getpid()
		ppid     = '"ppid" : %s, '     % os.getppid()
		counter  = '"counter": %s, '   % count if count else ''
		header   = '"header": "%s", '  % hexstring(header) if header else ''
		body     = '"body": "%s", '    % hexstring(body) if body else ''
		mtype    = '"type": "%s", '    % message_type if message_type else 'default'

		return \
			'{ '\
			'"exabgp": "%s", '\
			'"time": %s, ' \
			'%s%s%s%s%s%s%s%s ' \
			'}' % (
				self.version,
				self.time(time.time()),
				peer,
				pid,
				ppid,
				counter,
				mtype,
				header,
				body,
				content
			)

	def _neighbor (self, peer, direction, content):
		neighbor = peer.neighbor

		return \
			'"neighbor": { ' \
				'"address": { "local": "%s", "peer": "%s" }, ' \
				'"asn": { "local": "%s", "peer": "%s" }' \
				'%s%s%s%s' \
			'}' % (
				neighbor.local_address,neighbor.peer_address,
				neighbor.local_as,neighbor.peer_as,
				', ' if direction else '',
				'"direction": "%s"' % direction if direction else '',
				', ' if content else ' ',
				content
			)

	def _bmp (self, neighbor, content):
		return \
			'"bmp": { ' \
			'"ip": "%s", ' \
			'%s' \
			' }' % (neighbor,content)

	def _kv (self, extra):
		return ", ".join('"%s": %s' % (k,self._string(v)) for (k,v) in extra.iteritems())

	def _json_kv (self, extra):
		return ", ".join('"%s": %s' % (k,v.json()) for (k,v) in extra.iteritems())

	def _minimalkv (self, extra):
		return ", ".join('"%s": %s' % (k,self._string(v)) for (k,v) in extra.iteritems() if v)

	def up (self, peer):
		return self._header(self._neighbor(peer,None,self._kv({
			'state': 'up',
		})),'','',peer.neighbor.identificator(),self.count(peer),message_type='state')

	def connected (self, peer):
		return self._header(self._neighbor(peer,None,self._kv({
			'state': 'connected',
		})),'','',peer.neighbor.identificator(),self.count(peer),message_type='state')

	def down (self, peer, reason=''):
		return self._header(self._neighbor(peer,None,self._kv({
			'state':  'down',
			'reason': reason,
		})),'','',peer.neighbor.identificator(),self.count(peer),message_type='state')

	def shutdown (self):
		return self._header(self._kv({
			'notification': 'shutdown',
		}),'','','',1,message_type='notification')

	def notification (self, peer, direction, code, subcode, data):
		return self._header(self._neighbor(peer,direction,self._kv({
			'notification': '{ %s } ' % self._kv({
				'code':    code,
				'subcode': subcode,
				'data':    hexstring(data),
			})
		})),'','',peer.neighbor.identificator(),self.count(peer),message_type='notification')

	def packets (self, peer, direction, category, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'message': '{ %s } ' % self._kv({
				'category': category,
				'header':   hexstring(header),
				'body':     hexstring(body),
			})
		})),'','',peer.neighbor.identificator(),self.count(peer),message_type=Message.string(category))

	def keepalive (self, peer, direction, header, body):
		return self._header(self._neighbor(peer,direction,''),header,body,peer.neighbor.identificator(),self.count(peer),message_type='keepalive')

	def open (self, peer, direction, message, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'open':'{ %s } ' % self._kv({
				'version':      message.version,
				'asn':          message.asn,
				'hold_time':    message.hold_time,
				'router_id':    message.router_id,
				'capabilities': '{ %s }' % self._json_kv(message.capabilities),
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='open')

	def _update (self, update):
		plus = {}
		minus = {}

		# all the next-hops should be the same but let's not assume it

		for nlri in update.nlris:
			nexthop = str(nlri.nexthop) if nlri.nexthop else 'null'
			if nlri.action == IN.ANNOUNCED:  # pylint: disable=E1101
				plus.setdefault(nlri.family(),{}).setdefault(nexthop,[]).append(nlri)
			if nlri.action == IN.WITHDRAWN:  # pylint: disable=E1101
				minus.setdefault(nlri.family(),[]).append(nlri)

		add = []
		for family in plus:
			s  = '"%s %s": { ' % family
			m = ''
			for nexthop in plus[family]:
				nlris = plus[family][nexthop]
				m += '"%s": { ' % nexthop
				m += ', '.join('%s' % nlri.json() for nlri in nlris)
				m += ' }, '
			s += m[:-2]
			s += ' }'
			add.append(s)

		remove = []
		for family in minus:
			nlris = minus[family]
			s  = '"%s %s": { ' % family
			s += ', '.join('%s' % nlri.json() for nlri in nlris)
			s += ' }'
			remove.append(s)

		nlri = ''
		if not add and not remove:  # an EOR
			return update.nlris[0].json()
		if add:
			nlri += '"announce": { %s }' % ', '.join(add)
		if add and remove:
			nlri += ', '
		if remove:
			nlri += '"withdraw": { %s }' % ', '.join(remove)

		attributes = '' if not update.attributes else '"attribute": { %s }' % update.attributes.json()
		if not attributes or not nlri:
			return '"update": { %s%s }' % (attributes,nlri)
		return '"update": { %s, %s }' % (attributes,nlri)

	def update (self, peer, direction, update, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'message': '{ %s }' % self._update(update)
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='update')

	def refresh (self, peer, direction, refresh, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'route-refresh': '{ %s }' % self._kv({
				'afi': refresh.afi,
				'safi': refresh.safi,
				'subtype': refresh.reserved
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='refresh')

	def bmp (self, bmp, update):
		return self._header(self._bmp(bmp,self._update(update)),'','',message_type='bmp')

	def _operational_query (self, peer, direction, operational, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='operational')

	def _operational_advisory (self, peer, direction, operational, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
				'advisory': operational.data
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='operational')

	def _operational_counter (self, peer, direction, operational, header, body):
		return self._header(self._neighbor(peer,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
				'router-id': operational.routerid,
				'sequence': operational.sequence,
				'counter': operational.counter
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),message_type='operational')

	def operational (self, peer, direction, what, operational, header, body):
		if what == 'advisory':
			return self._operational_advisory(peer,direction,operational,header,body)
		elif what == 'query':
			return self._operational_query(peer,direction,operational,header,body)
		elif what == 'counter':
			return self._operational_counter(peer,direction,operational,header,body)
		# elif what == 'interface':
		# 	return self._operational_interface(peer,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
