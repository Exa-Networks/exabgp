# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# =================================================================== RouteRefresh

class RouteRefresh (object):
	def __str__ (self):
		return 'Route Refresh'

	def extract (self):
		return ['']

class EnhancedRouteRefresh (object):
	def __str__ (self):
		return 'Enhanced Route Refresh'

	def extract (self):
		return ['']
