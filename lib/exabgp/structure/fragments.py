# encoding: utf-8
"""
fragments.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

class Fragments (int):
#	reserved  = 0xF0
	DONT      = 0x08
	IS        = 0x40
	FIRST     = 0x20
	LAST      = 0x10

	def __str__ (self):
		if self == 0x00:       return 'not-a-fragment'
		if self == self.DONT:  return 'dont-fragment'
		if self == self.IS:    return 'is-fragment'
		if self == self.FIRST: return 'first-fragment'
		if self == self.LAST:  return 'last-fragment'
		return 'unknown fragment value %d' % int.__str__(self)

	def __repr__ (self):
		return str(self)

def NamedFragments (name):
	fragment = name.lower()
	if fragment == 'not-a-fragment': return Fragments(0x00)
	if fragment == 'dont-fragment':  return Fragments(Fragments.DONT)
	if fragment == 'is-fragment':    return Fragments(Fragments.IS)
	if fragment == 'first-fragment': return Fragments(Fragments.FIRST)
	if fragment == 'last-fragment':  return Fragments(Fragments.LAST)
	raise ValueError('invalid fragment name %s' % fragment)
