# encoding: utf-8
"""
prefixmetric.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                            Metric                             |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.4


@LINKSTATE.register()
class PrefixMetric(object):
	TLV = 1155

	def __init__ (self, prefixmetric):
		self.prefixmetric = prefixmetric

	def __repr__ (self):
		return "prefix_metric: %s" % (self.prefixmetric)

	@classmethod
	def unpack (cls,data,length):
		if length != 4:
			raise Notify(3,5, "Incorrect Prefix Metric size")
		else:
			metric = unpack("!L", data)[0]
			return cls(prefixmetric=metric)

	def json (self,compact=None):
		return '"prefix-metric": %d' % int(self.prefixmetric)
