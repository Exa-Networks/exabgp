"""open.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import pack, unpack
from typing import ClassVar, TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.version import Version

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


class Open(Message):
    ID: ClassVar = Message.CODE.OPEN

    # RFC 4271 4.2: version(1) + my AS(2) + hold time(2) + identifier(4), then the optional
    # parameters length(1) which is part of the fixed portion; the parameters follow it
    FIXED_SIZE: ClassVar[int] = 10
    PARAMETERS_OFFSET: ClassVar[int] = 9
    LENGTH_MAX: ClassVar = Message.STANDARD_MAX  # RFC 8654 3: an OPEN is never extended

    def __init__(self, packed: Buffer) -> None:
        if len(packed) < self.FIXED_SIZE:
            raise ValueError(f'Open requires at least {self.FIXED_SIZE} bytes, got {len(packed)}')
        self._packed = packed
        # decoded on first use: unpack_message decodes it at once, to refuse a bad one
        self._capabilities: Capabilities | None = None

    @classmethod
    def make_open(
        cls, version: Version, asn: ASN, hold_time: HoldTime, router_id: RouterID, capabilities: Capabilities
    ) -> 'Open':
        # OPEN message ASN field is always 2 bytes (RFC 4271)
        # 4-byte ASN is negotiated via ASN4 capability
        fixed = version.pack_version() + asn.trans().pack_asn2() + hold_time.pack_holdtime() + router_id.pack_ip()
        instance = cls(fixed + capabilities.pack_capabilities())
        # the object given, rather than one decoded from its bytes: what we send is what we
        # configured, and a capability we do not decode must not be lost on the way
        instance._capabilities = capabilities
        return instance

    @property
    def version(self) -> Version:
        return Version(self._packed[0])

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[1:3])[0])

    @property
    def hold_time(self) -> HoldTime:
        return HoldTime(unpack('!H', self._packed[3:5])[0])

    @property
    def router_id(self) -> RouterID:
        numeric = unpack('!L', self._packed[5:9])[0]
        return RouterID('%d.%d.%d.%d' % (numeric >> 24, (numeric >> 16) & 0xFF, (numeric >> 8) & 0xFF, numeric & 0xFF))

    @property
    def capabilities(self) -> Capabilities:
        if self._capabilities is None:
            self._capabilities = Capabilities.unpack(self._packed[self.PARAMETERS_OFFSET :])
        return self._capabilities

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def __str__(self) -> str:
        return 'OPEN version=%d asn=%d hold_time=%s router_id=%s capabilities=[%s]' % (
            self.version,
            self.asn.trans(),
            self.hold_time,
            self.router_id,
            self.capabilities,
        )

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Open:
        # RFC 4271 4.2: the fixed portion is version(1) + my AS(2) + hold time(2) +
        # identifier(4) + optional parameters length(1) = 10 octets, and the RFC states the
        # minimum OPEN is 29 octets including the 19 octet header.  This required 9, so an
        # OPEN with no Optional Parameters Length octet at all was accepted, and the error
        # text said "need 9" so the off by one was written down twice.
        #
        # RFC 4271 6.1: "if the Length field of an OPEN message is less than the minimum
        # length of the OPEN message, then the Error Subcode MUST be set to Bad Message
        # Length".  That is a Message Header Error, code 1 subcode 2, and not the OPEN
        # message error this used to send: 2/0 is Unspecific, which names nothing, and the
        # OPEN subcodes in 6.2 have no entry for a message which is too short to read.
        if len(data) < cls.FIXED_SIZE:
            # RFC 4271 6.1: "The Data field MUST contain the erroneous Length field", which
            # is the two octet Length from the message header, not a sentence describing it
            raise Notify(1, 2, f'OPEN body of {len(data)} octets', data=pack('!H', Message.HEADER_LEN + len(data)))

        version = data[0]
        if version != Version.BGP_4:
            # RFC 4271 6.2: the Data field is the largest version we support below the bid,
            # or failing that the smallest.  We support one, so it is always 4
            raise Notify(2, 1, f'version {version}', data=pack('!H', Version.BGP_4))

        received = cls(data)
        # decoded here, at the boundary, so a malformed parameter is refused with the OPEN
        received._capabilities = Capabilities.unpack(data[cls.PARAMETERS_OFFSET :])
        return received


Message.register(Open)
