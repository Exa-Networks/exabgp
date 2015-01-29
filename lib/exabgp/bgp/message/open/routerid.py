# encoding: utf-8
"""
routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IPv4

# ===================================================================== RouterID
#


class RouterID (IPv4):
	@classmethod
	def unpack (cls, data):  # pylint: disable=W0221
		return cls('.'.join(str(ord(_)) for _ in data),data)
