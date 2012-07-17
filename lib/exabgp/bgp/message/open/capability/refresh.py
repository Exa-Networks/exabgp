#!/usr/bin/env python
# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

# =================================================================== RouteRefresh

class RouteRefresh (list):
	def __str__ (self):
		return "Route Refresh (unparsed)"

	def extract (self):
		return []

class CiscoRouteRefresh (list):
	def __str__ (self):
		return "Cisco Route Refresh (unparsed)"

	def extract (self):
		return []

