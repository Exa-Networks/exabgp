#!/usr/bin/env python
# encoding: utf-8
"""
Response/json.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import socket
import time

from exabgp.reactor.api.options import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import IN

from exabgp.configuration.environment import environment


def nop (_): return _


class JSON (object):
	_count = {}

	def __init__ (self, version):
		self.version = version
		self.time = nop
		self.compact = environment.settings().api.compact

	# def _reset (self, neighbor):
	# 	self._count[neighbor.uid] = 0
	# 	return 0

	def _counter (self, neighbor):
		increased = self._count.get(neighbor.uid,0) + 1
		self._count[neighbor.uid] = increased
		return increased

	def _string (self, _):
		return '%s' % _ if issubclass(_.__class__,int) or issubclass(_.__class__,long) or ('{' in str(_)) else '"%s"' % _

	def _header (self, content, header, body, neighbor,message_type=None):
		peer     = '"host" : "%s", '   % socket.gethostname()
		pid      = '"pid" : %s, '      % os.getpid()
		ppid     = '"ppid" : %s, '     % os.getppid()
		counter  = '"counter": %s, '   % self._counter(neighbor) if neighbor is not None else ''
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

	def _neighbor (self, neighbor, direction, content):
		return \
			'"neighbor": { ' \
				'"address": { "local": "%s", "peer": "%s" }, ' \
				'"asn": { "local": "%s", "peer": "%s" }' \
				'%s%s%s%s' \
			' }' % (
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

	def up (self, neighbor):
		return self._header(self._neighbor(neighbor,None,self._kv({
			'state': 'up',
		})),'','',neighbor,message_type='state')

	def connected (self, neighbor):
		return self._header(self._neighbor(neighbor,None,self._kv({
			'state': 'connected',
		})),'','',neighbor,message_type='state')

	def down (self, neighbor, reason=''):
		def escape_quote (reason):
			return reason.replace('"','\\"')
		return self._header(self._neighbor(neighbor,None,self._kv({
			'state':  'down',
			'reason': escape_quote(reason),
		})),'','',neighbor,message_type='state')

	def shutdown (self):
		return self._header(self._kv({
			'notification': 'shutdown',
		}),'','',None,message_type='notification')

	def notification (self, neighbor, direction, message, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'notification': '{ %s } ' % self._kv({
				'code':    message.code,
				'subcode': message.subcode,
				'data':    hexstring(message.data),
			})
		})),header,body,neighbor,message_type='notification')

	def packets (self, neighbor, direction, category, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'message': '{ %s } ' % self._kv({
				'category': category,
				'header':   hexstring(header),
				'body':     hexstring(body),
			})
		})),'','',neighbor,message_type=Message.string(category))

	def keepalive (self, neighbor, direction, header, body):
		return self._header(self._neighbor(neighbor,direction,''),header,body,neighbor,message_type='keepalive')

	def open (self, neighbor, direction, message, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'open':'{ %s } ' % self._kv({
				'version':      message.version,
				'asn':          message.asn,
				'hold_time':    message.hold_time,
				'router_id':    message.router_id,
				'capabilities': '{ %s }' % self._json_kv(message.capabilities),
			})
		})),header,body,neighbor,message_type='open')

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
				m += '"%s": [ ' % nexthop
				m += ', '.join('%s' % nlri.json(compact=self.compact) for nlri in nlris)
				m += ' ], '
			s += m[:-2]
			s += ' }'
			add.append(s)

		remove = []
		for family in minus:
			nlris = minus[family]
			s  = '"%s %s": [ ' % family
			s += ', '.join('%s' % nlri.json(compact=self.compact) for nlri in nlris)
			s += ' ]'
			remove.append(s)

		nlri = ''
		if not add and not remove:
			if update.nlris:  # an EOR
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

	def update (self, neighbor, direction, update, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'message': '{ %s }' % self._update(update)
		})),header,body,neighbor,message_type='update')

	def refresh (self, neighbor, direction, refresh, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'route-refresh': '{ %s }' % self._kv({
				'afi': refresh.afi,
				'safi': refresh.safi,
				'subtype': refresh.reserved
			})
		})),header,body,neighbor,message_type='refresh')

	def bmp (self, bmp, update):
		return self._header(self._bmp(bmp,self._update(update)),'','',None,message_type='bmp')

	def _operational_query (self, neighbor, direction, operational, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
			})
		})),header,body,neighbor,message_type='operational')

	def _operational_advisory (self, neighbor, direction, operational, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
				'advisory': operational.data
			})
		})),header,body,neighbor,message_type='operational')

	def _operational_counter (self, neighbor, direction, operational, header, body):
		return self._header(self._neighbor(neighbor,direction,self._kv({
			'operational': '{ %s }' % self._kv({
				'name': operational.name,
				'afi': operational.afi,
				'safi': operational.safi,
				'router-id': operational.routerid,
				'sequence': operational.sequence,
				'counter': operational.counter
			})
		})),header,body,neighbor,message_type='operational')

	def operational (self, neighbor, direction, what, operational, header, body):
		if what == 'advisory':
			return self._operational_advisory(neighbor,direction,operational,header,body)
		elif what == 'query':
			return self._operational_query(neighbor,direction,operational,header,body)
		elif what == 'counter':
			return self._operational_counter(neighbor,direction,operational,header,body)
		# elif what == 'interface':
		# 	return self._operational_interface(peer,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
