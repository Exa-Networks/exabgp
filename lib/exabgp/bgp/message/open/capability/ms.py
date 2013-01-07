# encoding: utf-8
"""
ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# =================================================================== MultiSession

class MultiSession (list):
	def __str__ (self):
		return 'Multisession %s' % ' '.join([str(capa) for capa in self])

	def extract (self):
		rs = [chr(0),]
		for v in self:
			rs.append(chr(v))
		return rs
