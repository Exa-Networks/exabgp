# encoding: utf-8
"""
version.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# =================================================================== Version
#


class Version (int):
	def pack (self):
		return chr(self)
