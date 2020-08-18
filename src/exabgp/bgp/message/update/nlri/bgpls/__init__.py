"""
bgpls/__init__.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every BGP LINK_STATE NLRI should be imported from this file
# as it makes sure that all the registering decorator are run

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS

from exabgp.bgp.message.update.nlri.bgpls.node import NODE
from exabgp.bgp.message.update.nlri.bgpls.link import LINK
from exabgp.bgp.message.update.nlri.bgpls.prefixv4 import PREFIXv4
from exabgp.bgp.message.update.nlri.bgpls.prefixv6 import PREFIXv6
