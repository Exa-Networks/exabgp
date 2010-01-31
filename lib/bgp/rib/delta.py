#!/usr/bin/env python
# encoding: utf-8
"""
delta.py

Created by Thomas Mangin on 2009-11-07.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

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

		message = ''
		messages = []
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route
				continue
			if action == '-':
				if remove:
					pass
					#messages.append(route.withdraw())
			if action == '+':
				if remove:
					print 'annoucing (update)   ', route
					messages.append(route.update().update(local_asn,peer_asn))
				else:
					print 'annoucing (new)      ', route
					messages.append(route.update().announce(local_asn,peer_asn))
		return messages


#	def update (self,local_asn,remote_asn,remove=True):
#		# XXX: disabling route annoucement to test the code
#		return ''
#
#		message = ''
#		withdraw4 = {}
#		announce4 = []
#		mp_route6 = []
#		# table.changed always returns routes to remove before routes to add
#		for action,route in self.table.changed(self.last):
#			if action == '':
#				self.last = route
#				continue
#			if route.nlri.afi == AFI.ipv6:
#				# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
#				if remove:
#					mp_route6.append(self._message(prefix('') + prefix(route.pack(local_asn,remote_asn,'-'))))
#				if action == '+':
#					mp_route6.append(self._message(prefix('') + prefix(route.pack(local_asn,remote_asn,'+'))))
#				continue
#			if route.nlri.afi == AFI.ipv4:
#				if action == '-' and remove:
#					prefix = str(route)
#					withdraw4[prefix] = route.nlri.pack()
#					continue
#				if action == '+':
#					prefix = str(route)
#					if withdraw4.has_key(prefix):
#						del withdraw4[prefix]
#					announce4.append(self._message(prefix(route.nlri.pack()) + prefix(route.pack(local_asn,remote_asn)) + route.nlri.pack()))
#					continue
#
#		if len(withdraw4.keys()) or len(announce4):
#			# XXX: We should keep track of what we have already sent to only remove routes if we have sent them
#			remove4 = self._message(prefix(''.join([withdraw4[prefix] for prefix in withdraw4.keys()])) + prefix(''))
#			adding4 = ''.join(announce4)
#			message += remove4 + adding4
#
#		if len(mp_route6):
#			message += ''.join(mp_route6)
#
#		return message
#
