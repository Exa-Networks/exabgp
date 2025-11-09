
"""srv6/__init__.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

# draft-ietf-bess-srv6-services-11

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
