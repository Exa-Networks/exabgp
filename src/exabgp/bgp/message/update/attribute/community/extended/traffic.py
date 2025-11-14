"""traffic.py

Created by Thomas Mangin on 2014-06-21.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import socket

from typing import TYPE_CHECKING, ClassVar, Dict, Optional

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IPv4
from exabgp.protocol.ip import IPv6
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunityIPv6


# ================================================================== TrafficRate
# RFC 5575


@ExtendedCommunity.register
class TrafficRate(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x06

    def __init__(self, asn: ASN, rate: float, community: Optional[bytes] = None) -> None:
        self.asn: ASN = asn
        self.rate: float = rate
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sHf', self._subtype(), asn, rate),
        )

    def __repr__(self) -> str:
        return 'rate-limit:%d' % self.rate

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficRate:
        asn, rate = unpack('!Hf', data[2:8])
        return cls(ASN(asn), rate, data[:8])


# ================================================================ TrafficAction
# RFC 5575


@ExtendedCommunity.register
class TrafficAction(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x07

    _sample: ClassVar[Dict[bool, int]] = {
        False: 0x0,
        True: 0x2,
    }

    _terminal: ClassVar[Dict[bool, int]] = {
        False: 0x0,
        True: 0x1,
    }

    def __init__(self, sample: bool, terminal: bool, community: Optional[bytes] = None) -> None:
        self.sample: bool = sample
        self.terminal: bool = terminal
        bitmask = self._sample[sample] | self._terminal[terminal]
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLBB', self._subtype(), 0, 0, bitmask),
        )

    def __repr__(self) -> str:
        s = []
        if self.sample:
            s.append('sample')
        if self.terminal:
            s.append('terminal')
        return 'action {}'.format('-'.join(s))

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficAction:
        (bit,) = unpack('!B', data[7:8])
        sample = bool(bit & 0x02)
        terminal = bool(bit & 0x01)
        return cls(sample, terminal, data[:8])


# ============================================================== TrafficRedirect
# RFC 5575 and 7674


@ExtendedCommunity.register
class TrafficRedirect(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x08

    def __init__(self, asn: ASN, target: int, community: Optional[bytes] = None) -> None:
        self.asn: ASN = asn
        self.target: int = target
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sHL', self._subtype(), asn, target),
        )

    def __repr__(self) -> str:
        return 'redirect:{}:{}'.format(self.asn, self.target)

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficRedirect:
        asn, target = unpack('!HL', data[2:8])
        return cls(ASN(asn), target, data[:8])


@ExtendedCommunity.register
class TrafficRedirectASN4(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x82
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x08

    def __init__(self, asn: ASN4, target: int, community: Optional[bytes] = None) -> None:
        self.asn: ASN4 = asn
        self.target: int = target
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLH', self._subtype(), asn, target),
        )

    def __str__(self) -> str:
        return 'redirect:{}:{}'.format(self.asn, self.target)

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficRedirectASN4:
        asn, target = unpack('!LH', data[2:8])
        return cls(ASN4(asn), target, data[:8])


# ================================================================== TrafficMark
# RFC 5575


@ExtendedCommunity.register
class TrafficMark(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x09

    def __init__(self, dscp: int, community: Optional[bytes] = None) -> None:
        self.dscp: int = dscp
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLBB', self._subtype(), 0, 0, dscp),
        )

    def __repr__(self) -> str:
        return 'mark %d' % self.dscp

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficMark:
        (dscp,) = unpack('!B', data[7:8])
        return cls(dscp, data[:8])


# =============================================================== TrafficNextHopIPv4IETF
# draft-ietf-idr-flowspec-redirect-02
# see RFC 4360 for ipv4 address specific extended community format


@ExtendedCommunity.register
class TrafficNextHopIPv4IETF(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x01
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0C

    def __init__(self, ip: IPv4, copy: bool, community: Optional[bytes] = None) -> None:
        self.ip: IPv4 = ip
        self.copy: bool = copy
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2s4sH', self._subtype(), ip.pack(), 1 if copy else 0),
        )

    def __repr__(self) -> str:
        return (
            'copy-to-nexthop-ietf {} (with copy)'.format(self.ip)
            if self.copy
            else 'redirect-to-nexthop-ietf {}'.format(self.ip)
        )

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficNextHopIPv4IETF:
        ip, bit = unpack('!4sH', data[2:8])
        return cls(IPv4.ntop(ip), bool(bit & 0x01), data[:8])  # type: ignore[arg-type]


# =============================================================== TrafficNextHopIPv6IETF
# draft-ietf-idr-flowspec-redirect-02
# see RFC 5701 for ipv6 address specific extended community format


@ExtendedCommunityIPv6.register
class TrafficNextHopIPv6IETF(ExtendedCommunityIPv6):
    COMMUNITY_TYPE: ClassVar[int] = 0x00
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0C

    def __init__(self, ip: IPv6, copy: bool, community: Optional[bytes] = None) -> None:
        self.ip: IPv6 = ip
        self.copy: bool = copy
        ExtendedCommunityIPv6.__init__(
            self,
            community if community is not None else pack('!2s16sH', self._subtype(), ip.pack(), 1 if copy else 0),
        )

    def __repr__(self) -> str:
        return (
            'copy-to-nexthop-ietf {} (with copy)'.format(self.ip)
            if self.copy
            else 'redirect-to-nexthop-ietf {}'.format(self.ip)
        )

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficNextHopIPv6IETF:
        ip, bit = unpack('!16sH', data[2:20])
        return cls(IPv6.ntop(ip), bool(bit & 0x01), data[:20])  # type: ignore[arg-type]


# =============================================================== TrafficNextHopSimpson
# draft-simpson-idr-flowspec-redirect-02

# XXX: FIXME: I guess this should be a subclass of NextHop or IP ..


@ExtendedCommunity.register
class TrafficNextHopSimpson(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x08
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00

    def __init__(self, copy: bool, community: Optional[bytes] = None) -> None:
        self.copy: bool = copy
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLH', self._subtype(), 0, 1 if copy else 0),
        )

    def __repr__(self) -> str:
        return 'copy-to-nexthop' if self.copy else 'redirect-to-nexthop'

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficNextHopSimpson:
        (bit,) = unpack('!B', data[7:8])
        return cls(bool(bit & 0x01), data[:8])


# ============================================================ TrafficRedirectIPv6
# https://tools.ietf.org/html/rfc5701


@ExtendedCommunityIPv6.register
class TrafficRedirectIPv6(ExtendedCommunityIPv6):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0B

    def __init__(self, ip: str, asn: int, community: Optional[bytes] = None) -> None:
        self.ip: str = ip
        self.asn: int = asn
        ExtendedCommunityIPv6.__init__(
            self,
            (
                community
                if community is not None
                else pack('!BB16sH', 0x00, 0x02, socket.inet_pton(socket.AF_INET6, ip), asn)
            ),
        )

    def __str__(self) -> str:
        return 'redirect %s:%d' % (self.ip, self.asn)

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> TrafficRedirectIPv6:
        ip, asn = unpack('!16sH', data[2:11])
        return cls(socket.inet_ntop(socket.AF_INET6, ip), asn, data[:11])


# ============================================================ TrafficRedirectIP
# RFC 5575
# If we need to provide the <IP>:<ASN> form for the FlowSpec Redirect ...

# import socket
# Do not use socket, use IPv4.ntop or pton

# TrafficRedirectASN = TrafficRedirect

# class TrafficRedirectIP (ExtendedCommunity):
# 	COMMUNITY_TYPE = 0x80
# 	COMMUNITY_SUBTYPE = 0x08

# 	def __init__ (self, ip, target, community=None):
# 		self.ip = ip
# 		self.target = target
# 		ExtendedCommunity.__init__(self,community if community is not None else pack("!BB4sH",0x80,0x08,socket.inet_pton(socket.AF_INET,ip),target))

# 	def __str__ (self):
# 		return "redirect %s:%d" % (self.ip,self.target)

# 	@staticmethod
# 	def unpack (data):
# 		ip,target = unpack('!4sH',data[2:8])
# 		return TrafficRedirectIP(socket.inet_ntop(socket.AF_INET,ip),target,data[:8])
