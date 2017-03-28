# encoding: utf-8
"""
hostname.py

Created by Thomas Mangin on 2015-05-16.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# https://tools.ietf.org/html/draft-walton-bgp-hostname-capability-02

from exabgp.util import ord_
from exabgp.util import concat_strs
from exabgp.bgp.message.open.capability.capability import Capability


class HostName (Capability):
	ID = Capability.CODE.HOSTNAME

	def __init__ (self, host_name, domain_name):
		self.host_name = host_name
		self.domain_name = domain_name

	def __str__ (self):
		return 'Hostname(%s %s)' % (self.host_name,self.domain_name)

	def json (self):
		return '{ "host-name": "%s", "domain-name": "%s" }' % (self.host_name,self.domain_name)

	def extract (self):
		return [concat_strs(
			chr(len(self.host_name)),
			self.host_name,
			chr(len(self.domain_name)),
			self.domain_name,
		)]

	@staticmethod
	def unpack_capability (instance, data, capability=None):  # pylint: disable=W0613
		l1 = ord_(data[0])
		instance.host_name = data[1:l1+1].decode('utf-8')
		l2 = ord_(data[l1+1])
		instance.domain_name = data[l1+2:l1+2+l2].decode('utf-8')
		return instance
