
"""__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.open.version import Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.capability import Capabilities

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

    def __init__(self, version, asn, hold_time, router_id, capabilities):
        self.version = version
        self.asn = asn
        self.hold_time = hold_time
        self.router_id = router_id
        self.capabilities = capabilities

    def message(self, negotiated=None):
        return self._message(
            self.version.pack()
            + self.asn.trans().pack()
            + self.hold_time.pack()
            + self.router_id.pack()
            + self.capabilities.pack(),
        )

    def __str__(self):
        return 'OPEN version=%d asn=%d hold_time=%s router_id=%s capabilities=[%s]' % (
            self.version,
            self.asn.trans(),
            self.hold_time,
            self.router_id,
            self.capabilities,
        )

    @classmethod
    def unpack_message(cls, data, direction=None, negotiated=None):
        version = data[0]
        if version != 4:
            # Only version 4 is supported nowdays ..
            raise Notify(2, 1, 'version number: %d' % data[0])

        asn = unpack('!H', data[1:3])[0]
        hold_time = unpack('!H', data[3:5])[0]
        numeric = unpack('!L', data[5:9])[0]
        router_id = '%d.%d.%d.%d' % (numeric >> 24, (numeric >> 16) & 0xFF, (numeric >> 8) & 0xFF, numeric & 0xFF)
        return cls(Version(version), ASN(asn), HoldTime(hold_time), RouterID(router_id), Capabilities.unpack(data[9:]))
