#!/usr/bin/env python
# encoding: utf-8
"""
aggregator.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.message.update.attribute import Attribute,Flag,PathAttribute

# =================================================================== Aggregator (7)
# we do not pass routes to other speakers, so we do not care (but could).
