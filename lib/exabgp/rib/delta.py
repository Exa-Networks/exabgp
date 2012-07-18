# encoding: utf-8
"""
delta.py

Created by Thomas Mangin on 2009-11-07.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update import Update

from exabgp.structure.log import Logger
logger = Logger()


class Delta (object):
	def __init__ (self,table):
		self.table = table
		self.last = 0

	def updates  (self,asn4,local_asn,peer_asn,grouped,use_path,msg_size):
		self.table.recalculate()
		if grouped:
			return self.group_updates (asn4,local_asn,peer_asn,use_path,msg_size)
		else:
			return self.simple_updates (asn4,local_asn,peer_asn,use_path,msg_size)

	def simple_updates (self,asn4,local_asn,peer_asn,use_path,msg_size):
		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route # when action is '' route is a timestamp
				continue

			add_path = use_path.send(route.nlri.afi,route.nlri.safi)

			if action == '+':
				logger.rib('announcing %s' % route)
				for update in Update().new([route]).announce(asn4,local_asn,peer_asn,add_path,msg_size):
					yield update
			elif action == '*':
				logger.rib('updating %s' % route)
				for update in Update().new([route]).update(asn4,local_asn,peer_asn,add_path,msg_size):
					yield update
			elif action == '-':
				logger.rib('withdrawing %s' % route)
				for update in Update().new([route]).withdraw(asn4,local_asn,peer_asn,add_path,msg_size):
					yield update

	def group_updates (self,asn4,local_asn,peer_asn,use_path,msg_size):
		grouped = {
			'+' : {},
			'*' : {},
			'-' : {},
		}

		# table.changed always returns routes to remove before routes to add
		for action,route in self.table.changed(self.last):
			if action == '':
				self.last = route # when action is '' route is a timestamp
				continue
			add_path = use_path.send(route.nlri.afi,route.nlri.safi)
			grouped[action].setdefault(str(route.attributes),[]).append(route)

		group = 0
		for attributes in grouped['+']:
			routes = grouped['+'][attributes]
			for route in routes:
				logger.rib('announcing group %d %s' % (group,route))
			group += 1
			for update in Update().new(routes).announce(asn4,local_asn,peer_asn,add_path,msg_size):
				yield update
		for attributes in grouped['*']:
			routes = grouped['*'][attributes]
			for route in routes:
				logger.rib('updating group %d %s' % (group,route))
			group += 1
			for update in Update().new(routes).update(asn4,local_asn,peer_asn,add_path,msg_size):
				yield update
		for attributes in grouped['*']:
			routes = grouped['*'][attributes]
			for route in routes:
				logger.rib('updating group %d %s' % (group,route))
			group += 1
			for update in Update().new(routes).withdraw(asn4,local_asn,peer_asn,add_path,msg_size):
				yield update

