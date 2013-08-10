# encoding: utf-8
"""
delta.py

Created by Thomas Mangin on 2009-11-07.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update import Update

from exabgp.logger import Logger


class Delta (object):
	def __init__ (self,table):
		self.logger = Logger()
		self.table = table
		self.last = 0

	def updates  (self,negotiated,grouped):
		self.table.recalculate()
		if grouped:
			return self.group_updates(negotiated)
		else:
			return self.simple_updates(negotiated)

	def simple_updates (self,negotiated):
		# table.changed always returns changes to remove before changes to add
		for action,change in self.table.changed(self.last):
			if action == '':
				self.last = change  # when action is '' change is a timestamp
				continue

			if action == '+':
				self.logger.rib('announcing %s %s' % (change.nlri,change.attributes))
				for update in Update().new([change.nlri],change.attributes).announce(negotiated):
					yield update
			elif action == '*':
				self.logger.rib('updating %s %s' % (change.nlri,change.attributes))
				for update in Update().new([change.nlri],change.attributes).announce(negotiated):
					yield update
			elif action == '-':
				self.logger.rib('withdrawing %s %s' % (change.nlri,change.attributes)	)
				for update in Update().new([change.nlri],change.attributes).withdraw(negotiated):
					yield update

	def group_updates (self,negotiated):
		grouped = {
			'+' : {},
			'*' : {},
			'-' : {},
		}
		attributes = {}

		# table.changed always returns changes to remove before changes to add
		for action,change in self.table.changed(self.last):
			if action == '':
				self.last = change  # when action is '' change is a timestamp
				continue
			attribute_index = str(change.attributes)
			grouped[action].setdefault(attribute_index,[]).append(change.nlri)
			if not attribute_index in attributes:
				attributes[attribute_index] = change.attributes

		group = 0
		for attribute_index in grouped['+']:
			changes = grouped['+'][attribute_index]
			for change in changes:
				self.logger.rib('announcing group %d %s %s' % (group,change.nlri,change.attributes))
			group += 1
			for update in Update().new(changes,attributes[attribute_index]).announce(negotiated):
				yield update
		for attribute_index in grouped['*']:
			changes = grouped['*'][attribute_index]
			for change in changes:
				self.logger.rib('updating group %d %s %s' % (group,change.nlri,change.attributes))
			group += 1
			for update in Update().new(changes,attributes[attribute_index]).update(negotiated):
				yield update
		for attribute_index in grouped['*']:
			changes = grouped['*'][attribute_index]
			for change in changes:
				self.logger.rib('updating group %d %s %s' % (group,change.nlri,change.attributes))
			group += 1
			for update in Update().new(changes,attributes[attribute_index]).withdraw(negotiated):
				yield update
