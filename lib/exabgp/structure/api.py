#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time


class APIOptions (object):
	def __init__ (self):
		self.neighbor_changes = False
		self.receive_packets = False
		self.send_packets = False
		self.receive_routes = False

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

	def routes (self,neighbor,routes):
		r = 'neighbor %s update start\n' % neighbor
		for route in routes:
			r += 'neighbor %s %s\n' % (neighbor,str(route))
		r += 'neighbor %s update end\n' % neighbor
		return r

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

	# all those routes come from the same update, so let's save some parsing and group by attributes
	def _routes (self,routes):
		plus = {}
		minus = {}
		route = None
		for route in routes:
			if route.action == 'announced':
				plus.setdefault((route.nlri.afi,route.nlri.safi),[]).append(route)
			if route.action == 'withdrawn':
				minus.setdefault((route.nlri.afi,route.nlri.safi),[]).append(route)

		add = []
		for family in plus:
			routes = plus[family]
			s  = '"%s %s": { ' % (routes[0].nlri.afi,routes[0].nlri.safi)
			s += ', '.join('%s' % _.nlri.json() for _ in routes)
			s += ' }'
			add.append(s)

		remove = []
		for family in minus:
			routes = minus[family]
			s  = '"%s %s": [ ' % (routes[0].nlri.afi,routes[0].nlri.safi)
			s += ', '.join('"%s"' % str(_.nlri) for _ in routes)
			s += ' ]'
			remove.append(s)

		nlri = ''
		if add: nlri += '"announce": { %s }' % ', '.join(add)
		if add and remove: nlri += ', '
		if remove: nlri+= '"withdraw": { %s }' % ', '.join(remove)

		attributes = '' if not route or not route.attributes else '"attribute": { %s }' % route.attributes.json()
		if not attributes or not nlri:
			return '"update": { %s%s } ' % (attributes,nlri)
		return '"update": { %s, %s } ' % (attributes,nlri)

	def routes (self,neighbor,routes):
		return self._header(self._neighbor(neighbor,self._routes(routes)))

	def bmp (self,bmp,routes):
		return self._header(self._bmp(bmp,self._routes(routes)))

