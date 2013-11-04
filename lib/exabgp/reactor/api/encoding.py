#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time

from exabgp.bgp.message.direction import IN

class APIOptions (object):
	def __init__ (self):
		self.neighbor_changes = False
		self.receive_packets = False
		self.send_packets = False
		self.receive_routes = False
		self.receive_operational = False

def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return ''.join(spaced(value))


class Text (object):
	def __init__ (self,version):
		self.version = version

	def up (self,neighbor):
		return 'neighbor %s up\n' % neighbor

	def connected (self,neighbor):
		return 'neighbor %s connected\n' % neighbor

	def down (self,neighbor,reason=''):
		return 'neighbor %s down - %s\n' % (neighbor,reason)

	def shutdown (self):
		return 'shutdown'

	def receive (self,neighbor,category,header,body):
		return 'neighbor %s received %s header %s body %s\n' % (neighbor,ord(category),hexstring(header),hexstring(body))

	def send (self,neighbor,category,header,body):
		return 'neighbor %s sent %s header %s body %s\n' % (neighbor,ord(category),hexstring(header),hexstring(body))

	def update (self,neighbor,update):
		r = 'neighbor %s update start\n' % neighbor
		attributes = str(update.attributes)
		for nlri in update.nlris:
			if nlri.action == IN.announced:
				r += 'neighbor %s announced route %s%s\n' % (neighbor,nlri.nlri(),attributes)
			else:
				r += 'neighbor %s withdrawn route %s\n' % (neighbor,nlri.nlri())
		r += 'neighbor %s update end\n' % neighbor
		return r

	def refresh (self,neighbor,refresh):
		return 'neighbor %s route-refresh afi %s safi %s %s' % (
			neighbor,refresh.afi,refresh.safi,refresh.reserved
		)

	def _operational_advisory (self,neighbor,operational):
		return 'neighbor %s operational %s afi %s safi %s advisory "%s"' % (
			neighbor,operational.name,operational.afi,operational.safi,operational.data
		)

	def _operational_query (self,neighbor,operational):
		return 'neighbor %s operational %s afi %s safi %s' % (
			neighbor,operational.name,operational.afi,operational.safi
		)

	def _operational_counter (self,neighbor,operational):
		return 'neighbor %s operational %s afi %s safi %s router-id %s sequence %d counter %d' % (
			neighbor,operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.counter
		)

	def _operational_interface (self,neighbor,operational):
		return 'neighbor %s operational %s afi %s safi %s router-id %s sequence %d rxc %d txc %d' % (
			neighbor,operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.rxc,operational.txc
		)

	def operational (self,neighbor,what,operational):
		if what == 'advisory':
			return self._operational_advisory(neighbor,operational)
		elif what == 'query':
			return self._operational_query(neighbor,operational)
		elif what == 'counter':
			return self._operational_counter(neighbor,operational)
		elif what == 'interface':
			return self._operational_interface(neighbor,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')

class JSON (object):
	def __init__ (self,version):
		self.version = version

	def _string (self,_):
		return '%s' % _ if issubclass(_.__class__,int) or issubclass(_.__class__,long) else '"%s"' %_

	def _header (self,content):
		return \
		'{ '\
			'"exabgp": "%s", '\
			'"time": %s, ' \
			'%s' \
		'}' % (self.version,long(time.time()),content)

	def _neighbor (self,neighbor,content):
		return \
		'"neighbor": { ' \
			'"ip": "%s", ' \
			'%s' \
		'} '% (neighbor,content)

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

	def up (self,neighbor):
		return self._header(self._neighbor(neighbor,self._kv({'state':'up'})))

	def connected (self,neighbor):
		return self._header(self._neighbor(neighbor,self._kv({'state':'connected'})))

	def down (self,neighbor,reason=''):
		return self._header(self._neighbor(neighbor,self._kv({'state':'down','reason':reason})))

	def shutdown (self):
		return self._header(self._kv({'notification':'shutdown'}))

	def receive (self,neighbor,category,header,body):
		return self._header(self._neighbor(neighbor,'"update": { %s } ' % self._minimalkv({'received':ord(category),'header':hexstring(header),'body':hexstring(body)})))

	def send (self,neighbor,category,header,body):
		return self._header(self._neighbor(neighbor,'"update": { %s } ' % self._minimalkv({'sent':ord(category),'header':hexstring(header),'body':hexstring(body)})))

	def _update (self,update):
		plus = {}
		minus = {}
		for nlri in update.nlris:
			if nlri.action == IN.announced:
				plus.setdefault(nlri.family(),[]).append(nlri)
			if nlri.action == IN.withdrawn:
				minus.setdefault(nlri.family(),[]).append(nlri)

		add = []
		for family in plus:
			nlris = plus[family]
			s  = '"%s %s": { ' % family
			s += ', '.join('%s' % nlri.json() for nlri in nlris)
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

	def update (self,neighbor,update):
		return self._header(self._neighbor(neighbor,self._update(update)))

	def refresh (self,neighbor,refresh):
		return self._header(
			self._neighbor(
				neighbor,
				'"route-refresh": { "afi": "%s", "safi": "%s", "subtype": "%s"' % (
					refresh.afi,refresh.safi,refresh.reserved
				)
			)
		)

	def bmp (self,bmp,update):
		return self._header(self._bmp(bmp,self._update(update)))

	def _operational_advisory (self,neighbor,operational):
		return self._header(
			self._neighbor(
				neighbor,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s", "advisory": "%s"' % (
					operational.name,operational.afi,operational.safi,operational.data
				)
			)
		)

	def _operational_query (self,neighbor,operational):
		return self._header(
			self._neighbor(
				neighbor,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s"' % (
					operational.name,operational.afi,operational.safi
				)
			)
		)

	def _operational_counter (self,neighbor,operational):
		return self._header(
			self._neighbor(
				neighbor,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s", "router-id": "%s", "sequence": %d, "counter": %d' % (
					operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.counter
				)
			)
		)

	def _operational_interface (self,neighbor,operational):
		return self._header(
			self._neighbor(
				neighbor,
				'"operational": { "name": "%s", "afi": "%s", "safi": "%s", "router-id": "%s", "sequence": %d, "rxc": "%s", "txc": "%s"' % (
					operational.name,operational.afi,operational.safi,operational.routerid,operational.sequence,operational.rxc,operational.txc
				)
			)
		)

	def operational (self,neighbor,what,operational):
		if what == 'advisory':
			return self._operational_advisory(neighbor,operational)
		elif what == 'query':
			return self._operational_query(neighbor,operational)
		elif what == 'counter':
			return self._operational_counter(neighbor,operational)
		elif what == 'interface':
			return self._operational_interface(neighbor,operational)
		else:
			raise RuntimeError('the code is broken, we are trying to print a unknown type of operational message')
