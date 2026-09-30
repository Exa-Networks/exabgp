"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.util.types import Buffer

# ========================================================================= ASN4
#


class ASN4(Capability):
    """The four-octet AS number capability (RFC 6793): the AS number, on four octets.

    It inherited from both Capability and ASN, which mypyc cannot compile: the number is
    now held in `.asn`.
    """

    ID: ClassVar[CapabilityCode] = Capability.CODE.FOUR_BYTES_ASN

    def __init__(self, value: int = 0) -> None:
        self.asn = ASN(value)

    # int(capability) was the AS number when ASN4 was one
    def __int__(self) -> int:
        return self.asn.value

    # and it compared, and hashed, as the number
    def __eq__(self, other: object) -> bool:
        if isinstance(other, ASN4):
            return self.asn == other.asn
        if isinstance(other, (int, ASN)):
            return self.asn == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other

    def __hash__(self) -> int:
        return hash(self.asn)

    def __str__(self) -> str:
        return 'ASN4(%d)' % self.asn.value

    def extract_capability_bytes(self) -> list[bytes]:
        return self.asn.extract_asn_bytes()

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
        return cls(ASN.unpack_asn(data, ASN).value)

    def json(self) -> str:
        return '{ "name": "asn4", "asn4": %d }' % self.asn.value

    @classmethod
    def validate(cls, value: int) -> bool:
        """Validate value is within 32-bit ASN range.

        Args:
            value: Integer ASN value

        Returns:
            True if valid, False otherwise
        """
        return bool(0 <= value <= ASN.MAX_4BYTE)


Capability.register()(ASN4)
