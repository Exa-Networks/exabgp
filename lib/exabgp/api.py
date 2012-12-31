#!/usr/bin/env python
# encoding: utf-8
"""
api.py

Created by Thomas Mangin on 2012-12-30.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

import time
from itertools import tee

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
		          '"time": "%s"' \
		          '%s' \
		       '}' % (self.version,self.encoder,time.time(),content)

	def _neighbor (self,neighbor,content):
		return '"neighbor": { ' \
		         '"ip": "%s", ' \
		         '%s' \
		       '} '% (neighbor,content)

	def _kv (self,extra):
		return ", ".join('"%s": "%s"' % (_,__) for (_,__) in extra.iteritems()) + ' '

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

	# all those routes come from the same update, so let's save some parsing and group by attributes
	def _routes (self,routes):
		routes,copy = tee(routes,2)
		route = copy.next()

		prefixes = '"nlri": [ %s ]' % ', '.join('"%s"' % str(_.nlri) for _ in routes)
		attributes = '"attribute": { %s }' % route.attributes.json()
		return '"update": { %s, %s } ' % (attributes,prefixes)

	def routes (self,process,neighbor,routes):
		if self.silence: return
		self.write(process,self._header(self._neighbor(neighbor,self._routes(routes))))
