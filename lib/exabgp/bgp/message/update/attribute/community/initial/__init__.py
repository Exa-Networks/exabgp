# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.bgp.message.update.attribute.community.initial.community import Community
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities


# TODO: we should have the common code for the three kind of community separated
# TODO: and this is what should be used for inheritance.
