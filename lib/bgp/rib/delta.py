#!/usr/bin/env python
# encoding: utf-8
"""
delta.py

Created by Thomas Mangin on 2009-11-07.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.message.update import Update

class Delta (object):
	def __init__ (self,table):
		self.table = table
		self.last = 0

	def announce (self,local_asn,peer_asn):
		return self.update(local_asn,peer_asn,False)

	def update (self,local_asn,peer_asn,remove=True):
		self.table.recalculate()

		# Here we should perform intelligent message re-organisation (group announcements)
		# and intelligence like if we resdrawn a resdrawal, we need to re-announce
		# but for the moment, let just be daft but correct as we are just no a full bgp router

		messages = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route # when action is '' route is a timestamp
				continue
			if action == '-':
				if remove:
					print 'withdrawing  ', route
					messages.append(Update([route]).withdraw())
				else:
					print 'keeping route', route
			if action == '*':
				print 'updating     ', route
				messages.append(Update([route]).update(local_asn,peer_asn))
			if action == '+':
				print 'announcing    ', route
				messages.append(Update([route]).announce(local_asn,peer_asn))
		return messages
