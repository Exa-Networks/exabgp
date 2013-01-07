# encoding: utf-8
"""
fragment.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# =================================================================== Fragment

class _Fragment (int):
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

def NamedFragment (name):
	fragment = name.lower()
	if fragment == 'not-a-fragment': return _Fragment(0x00)
	if fragment == 'dont-fragment':  return _Fragment(_Fragment.DONT)
	if fragment == 'is-fragment':    return _Fragment(_Fragment.IS)
	if fragment == 'first-fragment': return _Fragment(_Fragment.FIRST)
	if fragment == 'last-fragment':  return _Fragment(_Fragment.LAST)
	raise ValueError('invalid fragment name %s' % fragment)
