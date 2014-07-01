# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised,Entry,Data

class Neighbor (Entry,Data):
	syntax = \
