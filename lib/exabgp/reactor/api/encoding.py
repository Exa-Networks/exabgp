#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time

from exabgp.bgp.message.direction import IN
from exabgp.bgp.message import Message

class APIOptions (object):
	def __init__ (self):
		self.receive_parsed = False
		self.receive_packets = False
		self.consolidate = False

		self.send_packets = False

		self.neighbor_changes = False
		self.receive_notifications = False
		self.receive_opens = False
		self.receive_keepalives = False
		self.receive_updates = False
		self.receive_refresh = False
		self.receive_operational = False

def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return ''.join(spaced(value))


class Text (object):
	def __init__ (self,version):
		self.version = version

	def _header_body(self,header,body):
		header = ' header %s' % hexstring(header) if header else ''
		body = ' body %s' % hexstring(body) if body else ''

		total_string = header+body if body else header

		return total_string

	def reset (self,peer):
		return None

	def increase (self,peer):
		return None

	def up (self,peer):
		return 'neighbor %s up\n' % peer.neighbor.peer_address

	def connected (self,peer):
		return 'neighbor %s connected\n' % peer.neighbor.peer_address

	def down (self,peer,reason=''):
		return 'neighbor %s down - %s\n' % (peer.neighbor.peer_address,reason)

	def shutdown (self,peer_address):
		return 'shutdown %s\n' % peer_address

	def notification (self,peer,code,subcode,data):
		return 'notification code %d subcode %d data %s\n' % (code,subcode,hexstring(data))

	def receive (self,peer,category,header,body):
		return 'neighbor %s received %d header %s body %s\n' % (peer.neighbor.peer_address,category,hexstring(header),hexstring(body))

	def keepalive (self,peer,header,body):
		return 'neighbor %s keepalive%s\n' % (peer.neighbor.peer_address,self._header_body(header,body))

	def open (self,peer,direction,sent_open,header,body):
		return 'neighbor %s open direction %s version %d asn %d hold_time %s router_id %s capabilities [%s]%s\n' % (peer.neighbor.peer_address,direction,sent_open.version, sent_open.asn, sent_open.hold_time, sent_open.router_id,str(sent_open.capabilities).lower(),self._header_body(header,body))

	def send (self,peer,category,header,body):
		return 'neighbor %s sent %d header %s body %s\n' % (peer.neighbor.peer_address,category,hexstring(header),hexstring(body))

	def update (self,peer,update,header,body):
		neighbor = peer.neighbor.peer_address
		r = 'neighbor %s update start\n' % neighbor
		attributes = str(update.attributes)
		for nlri in update.nlris:
			if nlri.action == IN.announced:
				if nlri.nexthop:
					r += 'neighbor %s announced route %s next-hop %s%s\n' % (neighbor,nlri.extensive(),nlri.nexthop,attributes)
				else:
					# This is an EOR or Flow or ... something newer
					r += 'neighbor %s announced %s %s\n' % (neighbor,nlri.extensive(),attributes)
			else:
				r += 'neighbor %s withdrawn route %s\n' % (neighbor,nlri.extensive())
		if header or body:
			r += '%s\n' % self._header_body(header,body)
		r += 'neighbor %s update end\n' % neighbor
		return r

	def refresh (self,peer,refresh,header,body):
		header = 'header %s' % hexstring(header) if header else ''
		body = 'body %s' % hexstring(body) if body else ''
		return 'neighbor %s route-refresh afi %s safi %s %s%s\n' % (
			peer.neighbor.peer_address,refresh.afi,refresh.safi,refresh.reserved,self._header_body(header,body)
		)

	def _operational_advisory (self,peer,operational,header,body):
		return 'neighbor %s operational %s afi %s safi %s advisory "%s"%s' % (
			peer.neighbor.peer_address,operational.name,operational.afi,operational.safi,operational.data,self._header_body(header,body)
		)

	def _operational_query (self,peer,operational,header,body):
		return 'neighbor %s operational %s afi %s safi %s%s' % (
			peer.neighbor.peer_address,operational.name,operational.afi,operational.safi,self._header_body(header,body)
		)

	def _operational_counter (self,peer,operational,header,body):
		return 'neighbor %s operational %s afi %s safi %s router-id %s sequence %d counter %d%s' % (
			peer.neighbor.peer_address,operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.counter,self._header_body(header,body)
		)

	def operational (self,peer,what,operational,header,body):
		if what == 'advisory':
			return self._operational_advisory(peer,operational,header,body)
		elif what == 'query':
			return self._operational_query(peer,operational,header,body)
		elif what == 'counter':
			return self._operational_counter(peer,operational,header,body)
#		elif what == 'interface':
#			return self._operational_interface(peer,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')


def nop (_): return _

class JSON (object):
	_counter = {}

	def __init__ (self,version,highres=False):
		self.version = version
		self.time = nop if highres else int

	def reset (self,peer):
		self._counter[peer.neighbor.peer_address] = 1

	def increase (self,peer):
		self._counter[peer.neighbor.peer_address] += 1

	def count (self,peer):
		return self._counter.get(peer.neighbor.peer_address,1)

	def _string (self,_):
		return '%s' % _ if issubclass(_.__class__,int) or issubclass(_.__class__,long) or ('{' in str(_)) else '"%s"' % _

	def _header (self,content,header,body,ident=None,count=None,type=None):
		identificator = '"id": "%s", ' % ident if ident else ''
		counter = '"counter": %s, ' % count if count else ''
		header = '"header": "%s", ' % hexstring(header) if header else ''
		body = '"body": "%s", ' % hexstring(body) if body else ''
		type = '"type": "%s",' % type if type else 'default'

		return \
		'{ '\
			'"exabgp": "%s", '\
			'"time": %s, ' \
			'%s%s%s%s%s%s' \
		'}' % (self.version,self.time(time.time()),identificator,counter,type,header,body,content)

	def _neighbor (self,peer,content):
		peer_neighbor_adress='"ip": "%s", ' % peer.neighbor.peer_address
		return \
		'"neighbor": { ' \
			'%s' \
			'%s' \
		'} '% (peer_neighbor_adress,content)

	def _bmp (self,neighbor,content):
		return \
		'"bmp": { ' \
			'"ip": "%s", ' \
			'%s' \
		'} '% (neighbor,content)

	def _kv (self,extra):
		return ", ".join('"%s": %s' % (_,self._string(__)) for (_,__) in extra.iteritems()) + ' '

	def _minimalkv (self,extra):
		return ", ".join('"%s": %s' % (_,self._string(__)) for (_,__) in extra.iteritems() if __) + ' '

	def up (self,peer):
		return self._header(self._neighbor(peer,self._kv({
			'state' : 'up',
		})),'','',peer.neighbor.identificator(),self.count(peer),type='state')

	def connected (self,peer):
		return self._header(self._neighbor(peer,self._kv({
			'state' : 'connected',
		})),'','',peer.neighbor.identificator(),self.count(peer),type='state')

	def down (self,peer,reason=''):
		return self._header(self._neighbor(peer,self._kv({
			'state'  : 'down',
			'reason' : reason,
		})),'','',peer.neighbor.identificator(),self.count(peer),type='state')

	def shutdown (self,ppid):
		return self._header(self._kv({
			'notification' : 'shutdown',
		}),'','',ppid,1,type='notification')

	def notification (self,peer,code,subcode,data):
		return self._header(self._kv({
			'notification' : '{ %s } ' % self._kv({
				'code'    : code,
				'subcode' : subcode,
				'data'    : hexstring(data),
			})
		}),'','',peer.neighbor.identificator(),self.count(peer),type='notification')

	def receive (self,peer,category,header,body):
		return self._header(self._neighbor(peer,self._kv({
			'message': '{ %s } ' % self._kv({
				'received' : category,
				'header'   : hexstring(header),
				'body'     : hexstring(body),
			})
		})),'','',peer.neighbor.identificator(),self.count(peer),type='raw')

	def keepalive (self,peer,header,body):
		return self._header(self._neighbor(peer,''),header,body,peer.neighbor.identificator(),self.count(peer),type='keepalive')

	def open (self,peer,direction,sent_open,header,body):
		return self._header(self._neighbor(peer,self._kv({
			'direction' : direction,
			'open':'{ %s } ' % self._kv({
				'version'      : sent_open.version,
				'asn'          : sent_open.asn,
				'hold_time'    : sent_open.hold_time,
				'router_id'    : sent_open.router_id,
				'capabilities' : '{ %s } ' % self._kv(sent_open.capabilities),
			})
		})),header,body,peer.neighbor.identificator(),self.count(peer),type='open')

	def send (self,peer,category,header,body):
		return self._header(self._neighbor(peer,self._kv({
			'message':'{ %s } ' % self._kv({
				'sent'   : category,
				'header' : hexstring(header),
				'body'   : hexstring(body),
			})
		})),'','',peer.neighbor.identificator(),self.count(peer),type=Message.string(category))

	def _update (self,update):
		plus = {}
		minus = {}

		# all the next-hops should be the same but let's not assume it

		for nlri in update.nlris:
			nexthop = str(nlri.nexthop) if nlri.nexthop else 'null'
			if nlri.action == IN.announced:
				plus.setdefault(nlri.family(),{}).setdefault(nexthop,[]).append(nlri)
			if nlri.action == IN.withdrawn:
				minus.setdefault(nlri.family(),[]).append(nlri)

		add = []
		for family in plus:
			s  = '"%s %s": { ' % family
			m = ''
			for nexthop in plus[family]:
				nlris = plus[family][nexthop]
				m += '"%s" : { ' % nexthop
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
		if add: nlri += '"announce": { %s }' % ', '.join(add)
		if add and remove: nlri += ', '
		if remove: nlri+= '"withdraw": { %s }' % ', '.join(remove)

		attributes = '' if not update.attributes else '"attribute": { %s }' % update.attributes.json()
		if not attributes or not nlri:
			return '"update": { %s%s } ' % (attributes,nlri)
		return '"update": { %s, %s } ' % (attributes,nlri)

	def update (self,peer,update,header,body):
		return self._header(self._neighbor(peer,self._kv({
			'message': '{ %s }' % self._update(update)})),header,body,peer.neighbor.identificator(),self.count(peer),type='update')

	def refresh (self,peer,refresh,header,body):
		return self._header(
			self._neighbor(
				peer,
				'"route-refresh": { "afi": "%s", "safi": "%s", "subtype": "%s" }' % (
					refresh.afi,refresh.safi,refresh.reserved
				)
			)
		,header,body,peer.neighbor.identificator(),self.count(peer),state='refresh')

	def bmp (self,bmp,update):
		return self._header(self._bmp(bmp,self._update(update)),'','',state='bmp')

	def _operational_advisory (self,peer,operational,header,body):
		return self._header(
			self._neighbor(
				peer.neighbor.peer_address,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s", "advisory": "%s"' % (
					operational.name,operational.afi,operational.safi,operational.data
				)
			)
		,header,body,peer.neighbor.identificator(),self.count(peer),type='operational')

	def _operational_query (self,peer,operational,header,body):
		return self._header(
			self._neighbor(
				peer.neighbor.peer_address,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s"' % (
					operational.name,operational.afi,operational.safi
				)
			)
		,header,body,peer.neighbor.identificator(),self.count(peer),type='operational')

	def _operational_counter (self,peer,operational,header,body):
		return self._header(
			self._neighbor(
				peer.neighbor.peer_address,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s", "router-id": "%s", "sequence": %d, "counter": %d' % (
					operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.counter
				)
			)
		,header,body,peer.neighbor.identificator(),self.count(peer),type='operational')

	def operational (self,peer,what,operational,header,body):
		if what == 'advisory':
			return self._operational_advisory(peer,operational,header,body)
		elif what == 'query':
			return self._operational_query(peer,operational,header,body)
		elif what == 'counter':
			return self._operational_counter(peer,operational,header,body)
#		elif what == 'interface':
#			return self._operational_interface(peer,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
