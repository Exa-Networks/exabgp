"""
mup/__init__.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

# Every MUP should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from exabgp.bgp.message.update.nlri.mup.nlri import MUP

from exabgp.bgp.message.update.nlri.mup.isd import InterworkSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.dsd import DirectSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup.t1st import Type1SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mup.t2st import Type2SessionTransformedRoute
