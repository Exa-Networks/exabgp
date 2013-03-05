#!/usr/bin/env python
# encoding: utf-8
"""
watchdog.py

Created by Thomas Mangin on 2012-11-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.id import AttributeID

# Global status of a watchdog

class _Status (dict):
	_instance = None

	def flick (self,watchdog):
		if watchdog not in self:
			self[watchdog] = True

	def disable (self,watchdog):
		self[watchdog] = False

	def enable (self,watchdog):
		self[watchdog] = True

def Status ():
	if _Status._instance is None:
		_Status._instance = _Status()
	return _Status._instance

# Route withdrawn in the configuration file

class Withdrawn (dict):
	def add (self,index,watchdog):
		self[index] = watchdog

	def remove (self,watchdog):
		# make a copy of the data so we can modify it in the loop
		for index in self.keys()[:]:
			if self[index] == watchdog:
				del self[index]

# Watchdog control

class Watchdog (object):
	def __init__ (self):
		self.status = Status()
		self.withdrawn = Withdrawn()
		self.watchdog = {}

	def integrate (self,route):
		index = route.index()

		if index in self.watchdog:
			# we reloaded the configuration, do not change watchdogs
			return

		watchdog = route.attributes.get(AttributeID.INTERNAL_WATCHDOG,None)
		if not watchdog:
			# should never happen though !
			return

		self.status.flick(watchdog)

		withdrawn = route.attributes.get(AttributeID.INTERNAL_WITHDRAW,None)
		if withdrawn:
			self.withdrawn.add(index,watchdog)

		self.watchdog[index] = watchdog

	def announce (self,watchdog):
		self.status.enable(watchdog)
		self.withdrawn.remove(watchdog)

	def withdraw (self,watchdog):
		self.status.disable(watchdog)

	def filtered (self,routes_generator):
		for route in routes_generator:
			index = route.index()
			watchdog = self.watchdog.get(index,None)
			if not watchdog:
				yield route
			elif self.status[watchdog] and index not in self.withdrawn:
				yield route
