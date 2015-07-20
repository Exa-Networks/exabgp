# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


# ===================================================================== PathInfo
# RFC draft-ietf-idr-add-paths-09

class PathInfo (object):

	__slots__ = ['path_info']

	def __init__ (self, packed=None, integer=None, ip=None):
		if packed:
			self.path_info = packed
		elif ip:
			self.path_info = ''.join([chr(int(_)) for _ in ip.split('.')])
		elif integer:
			self.path_info = ''.join([chr((integer >> offset) & 0xff) for offset in [24,16,8,0]])
		else:
			self.path_info = ''
		# sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

	def __eq__ (self, other):
		return self.path_info == other.path_info

	def __neq__ (self, other):
		return self.path_info != other.path_info

	def __lt__ (self, other):
		raise RuntimeError('comparing PathInfo for ordering does not make sense')

	def __le__ (self, other):
		raise RuntimeError('comparing PathInfo for ordering does not make sense')

	def __gt__ (self, other):
		raise RuntimeError('comparing PathInfo for ordering does not make sense')

	def __ge__ (self, other):
		raise RuntimeError('comparing PathInfo for ordering does not make sense')

	def __len__ (self):
		return len(self.path_info)

	def json (self):
		if self.path_info:
			return '"path-information": "%s"' % '.'.join([str(ord(_)) for _ in self.path_info])
		return ''

	def __repr__ (self):
		if self.path_info:
			return ' path-information %s' % '.'.join([str(ord(_)) for _ in self.path_info])
		return ''

	def pack (self):
		if self.path_info:
			return self.path_info
		return '\x00\x00\x00\x00'

PathInfo.NOPATH = PathInfo()
