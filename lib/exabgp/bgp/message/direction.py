# encoding: utf-8
"""
direction.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.util.enumeration import Enumeration

OUT = Enumeration ('announce','withdraw')
IN  = Enumeration ('announced','withdrawn')
