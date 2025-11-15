"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations
from typing import Optional

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode

# ========================================================================= ASN4
#


@Capability.register()
class ASN4(Capability, ASN):
    ID = Capability.CODE.FOUR_BYTES_ASN

    # This makes python2.6 complain !
    # def __init__ (self, value=0):
    # 	ASN.__init__(self,value)

    def __str__(self) -> str:
        return 'ASN4(%d)' % int(self)

    @staticmethod
    def unpack_capability(instance: ASN, data: bytes, capability: Optional[CapabilityCode] = None) -> ASN:  # pylint: disable=W0613
        # XXX: FIXME: if instance is not ASN(0) we have two ASN - raise
        instance = ASN.unpack_asn(data, ASN4)
        return instance

    def json(self) -> str:
        return '{ "name": "asn4", "asn4": %d }' % int(self)
