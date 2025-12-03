"""__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.open.version import Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.capability import Capabilities

__all__ = [
    'Open',
    'Version',
    'ASN',
    'HoldTime',
    'RouterID',
    'Capabilities',
]

# =================================================================== Open

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+
# |    Version    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |     My Autonomous System      |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |           Hold Time           |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                         BGP Identifier                        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |Non-Ext OP Len.|Non-Ext OP Type|  Extended Opt. Parm. Length   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# |             Optional Parameters (variable)                    |
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# Optional Parameters:

# 0                   1                   2
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Parm. Type   |        Parameter Length       |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# ~            Parameter Value (variable)         ~
# |                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@Message.register
class Open(Message):
    ID = Message.CODE.OPEN
    TYPE = bytes([Message.CODE.OPEN])

    def __init__(
        self, version: Version, asn: ASN, hold_time: HoldTime, router_id: RouterID, capabilities: Capabilities
    ) -> None:
        self.version: Version = version
        self.asn: ASN = asn
        self.hold_time: HoldTime = hold_time
        self.router_id: RouterID = router_id
        self.capabilities: Capabilities = capabilities

    def pack_message(self, negotiated: Negotiated) -> bytes:
        # OPEN message ASN field is always 2 bytes (RFC 4271)
        # 4-byte ASN is negotiated via ASN4 capability
        return self._message(
            self.version.pack_version()
            + self.asn.trans().pack_asn2()
            + self.hold_time.pack_holdtime()
            + self.router_id.pack_ip()
            + self.capabilities.pack_capabilities(),
        )

    def __str__(self) -> str:
        return 'OPEN version=%d asn=%d hold_time=%s router_id=%s capabilities=[%s]' % (
            self.version,
            self.asn.trans(),
            self.hold_time,
            self.router_id,
            self.capabilities,
        )

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Open:
        version = data[0]
        if version != Version.BGP_4:
            # Only version 4 is supported nowdays ..
            raise Notify(2, 1, 'version number: %d' % data[0])

        asn = unpack('!H', data[1:3])[0]
        hold_time = unpack('!H', data[3:5])[0]
        numeric = unpack('!L', data[5:9])[0]
        router_id = '%d.%d.%d.%d' % (numeric >> 24, (numeric >> 16) & 0xFF, (numeric >> 8) & 0xFF, numeric & 0xFF)
        return cls(Version(version), ASN(asn), HoldTime(hold_time), RouterID(router_id), Capabilities.unpack(data[9:]))
