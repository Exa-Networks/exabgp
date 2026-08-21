"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.util.types import Buffer

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
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        # RFC 5492: duplicate capabilities use the last one received
        # RFC 6793 section 3: the capability value is always a 4 octet AS number
        # RFC 6793 says four octets, and a peer which sends two has its session up today:
        # refusing it would drop that peering the moment someone upgraded. A shorter value
        # is read as the ASN it encodes; anything else has no reading at all.
        if len(data) not in (ASN.SIZE_2BYTE, ASN.SIZE_4BYTE):
            raise Notify(
                2,
                0,
                f'AS4 capability must be {ASN.SIZE_2BYTE} or {ASN.SIZE_4BYTE} bytes long, got {len(data)}',
            )
        # ASN4 extends both Capability and ASN, so the result is a Capability
        result: ASN4 = ASN.unpack_asn(data, cls)
        return result

    def json(self) -> str:
        return '{ "name": "asn4", "asn4": %d }' % int(self)

    @classmethod
    def validate(cls, value: int) -> bool:
        """Validate value is within 32-bit ASN range.

        Args:
            value: Integer ASN value

        Returns:
            True if valid, False otherwise
        """
        return bool(0 <= value <= ASN.MAX_4BYTE)
