# encoding: utf-8
"""
interface.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import socket
from struct import unpack
from collections import namedtuple

from exabgp.netlink.attributes import Attributes
from exabgp.netlink.route import NetLinkRoute


class InfoMessage (object):
	# to be defined by the subclasses
	format = namedtuple('Parent', 'to be subclassed')

	# to be defined by the subclasses
	class Header (object):
		PACK = ''
		LEN = 0

	def __init__ (self, route):
		self.route = route

	def decode (self, data):
		extracted = list(unpack(self.Header.PACK,data[:self.Header.LEN]))
		attributes = Attributes.decode(data[self.Header.LEN:])
		extracted.append(dict(attributes))
		return self.format(*extracted)

	def extract (self, atype, flags=NetLinkRoute.Flags.NLM_F_REQUEST | NetLinkRoute.Flags.NLM_F_DUMP, family=socket.AF_UNSPEC):
		for data in self.route.send(atype,flags,family):
			yield self.decode(data)
