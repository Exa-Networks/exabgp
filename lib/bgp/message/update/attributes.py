#!/usr/bin/env python
# encoding: utf-8
"""
set.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.message.update.attribute import Attribute

# =================================================================== Attributes

class MultiAttributes (list):
	def __init__ (self,attribute):
		self.ID = attribute.ID
		self.FLAG = attribute.FLAG
		self.MULTIPLE = True
		self.append(attribute)

	def pack (self):
		r = []
		for attribute in self:
			r.append(attribute.pack())
		return ''.join(r)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return "MultiAttribute"

class Attributes (dict):
	autocomplete = True
	
	def has (self,k):
		return self.has_key(k)

	def add (self,attribute):
		if self.has(attribute.ID):
			if attribute.MULTIPLE:
				self[attribute.ID].append(attribute)
				return True
			return False
		else:
			if attribute.MULTIPLE:
				self[attribute.ID] = MultiAttributes(attribute)
			else:
				self[attribute.ID] = attribute
			return True

	def __str__ (self):
		origin = ''
		if self.has(Attribute.ORIGIN):
			origin = ' origin %s' % str(self[Attribute.ORIGIN]).lower()

		aspath = ''
		if self.has(Attribute.AS_PATH):
			aspath = ' %s' % str(self[Attribute.AS_PATH]).lower().replace('_','-')

		local_pref= ''
		if self.has(Attribute.LOCAL_PREFERENCE):
			l = self[Attribute.LOCAL_PREFERENCE]
			local_pref= ' local_preference %s' % l

		med = ''
		if self.has(Attribute.MULTI_EXIT_DISC):
			m = self[Attribute.MULTI_EXIT_DISC]
			med = ' med %s' % m

		communities = ''
		if self.has(Attribute.COMMUNITY):
			communities = ' community %s' % str(self[Attribute.COMMUNITY])

		return "%s%s%s%s%s" % (origin,aspath,local_pref,med,communities)

