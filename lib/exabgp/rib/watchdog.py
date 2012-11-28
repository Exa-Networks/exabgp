#!/usr/bin/env python
# encoding: utf-8
"""
watchdog.py

Created by Thomas Mangin on 2012-11-25.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

import time

from exabgp.bgp.message.update.attribute.id import AttributeID

class WatchdogStatus (dict):
	def flick (self,watchdog):
		if watchdog not in self:
			self[watchdog] = True

	def disable (self,watchdog):
		self[watchdog] = False

	def enable (self,watchdog):
		self[watchdog] = True


class DisabledRoute (dict):
	def disable (self,index,watchdog):
		self[index] = watchdog

	def enable (self,watchdog):
		# make a copy of the data so we can modify it in the loop
		for index,w in self.iteritems()[:]:
			if w == watchdog:
				del self[index]


class Watchdog (object):
	def __init__ (self):
		self.watchdog = WatchogStatus()
		self.disabled = DisabledRoute()
		self.routes = {}

	def set (self,route):
		# note it is a POP, not a GET
		watchdog = route.attributes.pop(AttributeID.INTERNAL_WATCHDOG,None)
		if not watchdog:
			# should never happen though !
			return
		self.watchdog.flick(watchdog)

		index = route.index()
		self.routes[index] = watchdog

		# note it is a POP, not a GET
		withdrawn = route.attributes.pop(AttributeID.INTERNAL_WITHDRAW,None)
		if withdrawn:
			self.disabled.disable(index)

	def announce (self,watchdog):
		for index,route in self.routes[watchdog].iteritems():
			if not self.watchdog[watchdog]:
				self.watchdog.enable(watchdog)
			self.disabled.enable(watchdog)

	def withdraw (self,watchdog):
		for index,route in self.routes[watchdog].iteritems():
			if self.watchdog[watchdog]:
				self.watchdog.disable(watchdog)
			# the route will now be disabled thanks to the watchdog only
			self.disabled.enable(watchdog)

	def filtered (self,routes_generator):
		for route in routes_generator:
			index = route.index()
			watchdog = self.routes[index]
			if index in self.disabled:
				continue
			if self.watchdog[watchdog]:
				yield route
