#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import time
from itertools import tee

from exabgp.structure.utils import dump

def hexstring (value):
	def spaced (value):
		for v in value:
			yield '%02X' % ord(v)
	return ''.join(spaced(value))


class Text (object):
	def __init__ (self,write,version,encoder):
		self.write = write
		self.silence = False
		self.version = version
		self.encoder = encoder

	def up (self,process,neighbor):
		if self.silence: return
		self.write(process,'neighbor %s up\n' % neighbor)

	def connected (self,process,neighbor):
		if self.silence: return
		self.write(process,'neighbor %s connected\n' % neighbor)

	def down (self,process,neighbor,reason=''):
		if self.silence: return
		self.write(process,'neighbor %s down - %s\n' % (neighbor,reason))

	def shutdown (self,process):
		if self.silence: return
		self.write(process,'shutdown')

	def receive (self,process,neighbor,category,header,body):
		if self.silence: return
		self.write(process,'neighbor %s received %s header %s body %s\n' % (neighbor,ord(category),hexstring(header),hexstring(body)))

	def send (self,process,neighbor,category,header,body):
		if self.silence: return
		self.write(process,'neighbor %s sent %s header %s body %s\n' % (neighbor,ord(category),hexstring(header),hexstring(body)))

	def routes (self,process,neighbor,routes):
		if self.silence: return
		self.write(process,'neighbor %s update start\n' % neighbor)
		for route in routes:
			self.write(process,'neighbor %s %s\n' % (neighbor,str(route)))
		self.write(process,'neighbor %s update end\n' % neighbor)

class JSON (object):
	def __init__ (self,write,version,encoder):
		self.write = write
		self.silence = False
		self.version = version
		self.encoder = encoder

	def _header (self,content):
		return '{ '\
		          '"application": "exabgp", '\
		          '"version": "%s", '\
		          '"encoder": "%s", ' \
		          '"time": %s, ' \
		          '%s' \
		       '}' % (self.version,self.encoder,long(time.time()),content)

	def _neighbor (self,neighbor,content):
		return '"neighbor": { ' \
		         '"ip": "%s", ' \
		         '%s' \
		       '} '% (neighbor,content)

	def _kv (self,extra):
		return ", ".join('"%s": "%s"' % (_,__) for (_,__) in extra.iteritems()) + ' '

	def _minimalkv (self,extra):
		return ", ".join('"%s": "%s"' % (_,__) for (_,__) in extra.iteritems() if __) + ' '

	def up (self,process,neighbor):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._kv({'state':'up'}))))

	def connected (self,process,neighbor):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._kv({'state':'connected'}))))

	def down (self,process,neighbor,reason=''):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._kv({'state':'down','reason':reason}))))

	def shutdown (self,process):
		if self.silence: return
		self.write(process,self._header(self._kv({'notification':'shutdown'})))

	def receive (self,process,neighbor,category,header,body):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._minimalkv({'received':ord(category),'header':hexstring(header),'body':hexstring(body)}))))

	def send (self,process,neighbor,category,header,body):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._minimalkv({'sent':ord(category),'header':hexstring(header),'body':hexstring(body)}))))

	# all those routes come from the same update, so let's save some parsing and group by attributes
	def _routes (self,routes):
		announced = []
		withdrawn = []

		plus = {}
		minus = {}
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
			route = minus[family]
			s  = '"%s %s": [ ' % (routes[0].nlri.afi,routes[0].nlri.safi)
			s += ', '.join('"%s"' % str(_.nlri) for _ in routes)
			s += ' ]'
			remove.append(s)

		nlri = ''
		if add: nlri += '"announce": { %s }' % ', '.join(add)
		if add and remove: nlri += ', '
		if remove: nlri+= '"withdraw": { %s }' % ', '.join(remove)

		attributes = '"attribute": { %s }' % route.attributes.json()
		return '"update": { %s, %s } ' % (attributes,nlri)

	def routes (self,process,neighbor,routes):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._routes(routes))))
