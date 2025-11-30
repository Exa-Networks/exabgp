"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

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

    def extract_capability_bytes(self) -> list[bytes]:
        # ASN4 extends both Capability and ASN
        # Delegate to ASN.extract_asn_bytes() for 4-byte ASN encoding
        return ASN.extract_asn_bytes(self)

    @classmethod
    def unpack_capability(cls, instance: Capability, data: bytes, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        # XXX: FIXME: if instance is not ASN(0) we have two ASN - raise
        # ASN4 extends both Capability and ASN, so the result is a Capability
        result: ASN4 = ASN.unpack_asn(data, cls)  # type: ignore[assignment]
        return result

    def json(self) -> str:
        return '{ "name": "asn4", "asn4": %d }' % int(self)
