# encoding: utf-8
"""
delta.py

Created by Thomas Mangin on 2009-11-07.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.message.update import Update

from exabgp.log import Logger
logger = Logger()

class Delta (object):
	def __init__ (self,table):
		self.table = table
		self.last = 0

	def announce (self,asn4,local_asn,peer_asn):
		return self.update(asn4,local_asn,peer_asn,False)

	def update (self,asn4,local_asn,peer_asn,remove=True):
		self.table.recalculate()

		# Here we should perform intelligent message re-organisation (group announcements)
		# and intelligence like if we resdrawn a resdrawal, we need to re-announce
		# but for the moment, let just be daft but correct as we are just no a full bgp router

		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route # when action is '' route is a timestamp
				continue
			if action == '-':
				if remove:
					logger.rib('withdrawing %s' % route)
					yield Update([route]).withdraw(asn4)
				else:
					logger.rib('keeping %s' % route)
			if action == '*':
				logger.rib('updating %s' % route)
				yield Update([route]).update(asn4,local_asn,peer_asn)
			if action == '+':
				logger.rib('announcing %s' % route)
				yield Update([route]).announce(asn4,local_asn,peer_asn)
