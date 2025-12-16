"""FlowSpec Traffic Action extended communities (RFC 5575, RFC 7674).

This module implements extended communities that specify actions for
FlowSpec traffic filtering rules. These communities define what happens
to traffic matching a FlowSpec rule.

Actions:
    TrafficRate: Rate-limit matching traffic (rate in bytes/sec)
    TrafficAction: Sample and/or terminate rule evaluation
    TrafficRedirect: Redirect to VRF by Route Target
    TrafficMark: Set DSCP marking on matching packets
    TrafficNextHop*: Redirect to specific next-hop IP

Wire format (8 bytes for IPv4, 20 bytes for IPv6):
    [type(1)][subtype(1)][value(6 or 18)]

Created by Thomas Mangin on 2014-06-21.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import socket

from typing import TYPE_CHECKING, ClassVar

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
from exabgp.util.types import Buffer


# ================================================================== TrafficRate


@ExtendedCommunity.register
class TrafficRate(ExtendedCommunity):
    """Rate-limit matching traffic (RFC 5575).

    Rate is in bytes per second. Rate of 0 means drop all matching traffic.
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x06

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_rate(cls, asn: ASN, rate: float) -> TrafficRate:
        """Create TrafficRate from semantic values."""
        packed = pack('!BBHf', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, asn, rate)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[2:4])[0])

    @property
    def rate(self) -> float:
        value: float = unpack('!f', self._packed[4:8])[0]
        return value

    def __repr__(self) -> str:
        return 'rate-limit:%d' % self.rate

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficRate:
        return cls(data[:8])


# ================================================================ TrafficAction


@ExtendedCommunity.register
class TrafficAction(ExtendedCommunity):
    """Traffic action flags (RFC 5575).

    sample: Copy matching traffic to sampling collector
    terminal: Stop evaluating subsequent FlowSpec rules
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x07

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_action(cls, sample: bool, terminal: bool) -> TrafficAction:
        """Create TrafficAction from semantic values."""
        bitmask = (0x2 if sample else 0x0) | (0x1 if terminal else 0x0)
        packed = pack('!BBLBB', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, 0, 0, bitmask)
        return cls(packed)

    @property
    def sample(self) -> bool:
        return bool(self._packed[7] & 0x02)

    @property
    def terminal(self) -> bool:
        return bool(self._packed[7] & 0x01)

    def __repr__(self) -> str:
        s = []
        if self.sample:
            s.append('sample')
        if self.terminal:
            s.append('terminal')
        return 'action {}'.format('-'.join(s))

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficAction:
        return cls(data[:8])


# ============================================================== TrafficRedirect


@ExtendedCommunity.register
class TrafficRedirect(ExtendedCommunity):
    """Redirect matching traffic to VRF (RFC 5575, RFC 7674).

    Uses Route Target format (2-byte ASN : 4-byte value).
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x08

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_redirect(cls, asn: ASN, target: int) -> TrafficRedirect:
        """Create TrafficRedirect from semantic values."""
        packed = pack('!BBHL', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, asn, target)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!H', self._packed[2:4])[0])

    @property
    def target(self) -> int:
        value: int = unpack('!L', self._packed[4:8])[0]
        return value

    def __repr__(self) -> str:
        return 'redirect:{}:{}'.format(self.asn, self.target)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficRedirect:
        return cls(data[:8])


@ExtendedCommunity.register
class TrafficRedirectASN4(ExtendedCommunity):
    """Redirect to VRF using 4-byte AS number (RFC 7674).

    Uses Route Target format (4-byte ASN : 2-byte value).
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x82
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x08

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_redirect_asn4(cls, asn: ASN4, target: int) -> TrafficRedirectASN4:
        """Create TrafficRedirectASN4 from semantic values."""
        packed = pack('!BBLH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, asn, target)
        return cls(packed)

    @property
    def asn(self) -> ASN4:
        return ASN4(unpack('!L', self._packed[2:6])[0])

    @property
    def target(self) -> int:
        value: int = unpack('!H', self._packed[6:8])[0]
        return value

    def __str__(self) -> str:
        return 'redirect:{}:{}'.format(self.asn, self.target)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficRedirectASN4:
        return cls(data[:8])


# ================================================================== TrafficMark


@ExtendedCommunity.register
class TrafficMark(ExtendedCommunity):
    """Set DSCP value on matching packets (RFC 5575).

    DSCP is 6 bits (0-63), stored in low bits of last byte.
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x09

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_mark(cls, dscp: int) -> TrafficMark:
        """Create TrafficMark from semantic values."""
        packed = pack('!BBLBB', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, 0, 0, dscp)
        return cls(packed)

    @property
    def dscp(self) -> int:
        return self._packed[7]

    def __repr__(self) -> str:
        return 'mark %d' % self.dscp

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficMark:
        return cls(data[:8])


# =============================================================== TrafficNextHopIPv4IETF


@ExtendedCommunity.register
class TrafficNextHopIPv4IETF(ExtendedCommunity):
    """Redirect to IPv4 next-hop (draft-ietf-idr-flowspec-redirect).

    Contains explicit IPv4 address. Copy flag indicates whether to also
    forward to original next-hop (copy) or replace entirely (redirect).
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x01
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0C

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_nexthop_ipv4(cls, ip: IPv4, copy: bool) -> TrafficNextHopIPv4IETF:
        """Create TrafficNextHopIPv4IETF from semantic values."""
        packed = pack('!BB4sH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, ip.pack_ip(), 1 if copy else 0)
        return cls(packed)

    @property
    def ip(self) -> str:
        return IPv4.ntop(self._packed[2:6])

    @property
    def copy(self) -> bool:
        return bool(unpack('!H', self._packed[6:8])[0] & 0x01)

    def __repr__(self) -> str:
        return (
            'copy-to-nexthop-ietf {} (with copy)'.format(self.ip)
            if self.copy
            else 'redirect-to-nexthop-ietf {}'.format(self.ip)
        )

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficNextHopIPv4IETF:
        return cls(data[:8])


# =============================================================== TrafficNextHopIPv6IETF


@ExtendedCommunityIPv6.register
class TrafficNextHopIPv6IETF(ExtendedCommunityIPv6):
    """Redirect to IPv6 next-hop (draft-ietf-idr-flowspec-redirect, RFC 5701).

    Contains explicit IPv6 address (20 bytes total). Copy flag indicates
    whether to also forward to original next-hop or replace entirely.
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x00
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0C

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunityIPv6.__init__(self, packed)

    @classmethod
    def make_traffic_nexthop_ipv6(cls, ip: IPv6, copy: bool) -> TrafficNextHopIPv6IETF:
        """Create TrafficNextHopIPv6IETF from semantic values."""
        packed = pack('!BB16sH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, ip.pack_ip(), 1 if copy else 0)
        return cls(packed)

    @property
    def ip(self) -> str:
        return IPv6.ntop(self._packed[2:18])

    @property
    def copy(self) -> bool:
        return bool(unpack('!H', self._packed[18:20])[0] & 0x01)

    def __repr__(self) -> str:
        return (
            'copy-to-nexthop-ietf {} (with copy)'.format(self.ip)
            if self.copy
            else 'redirect-to-nexthop-ietf {}'.format(self.ip)
        )

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficNextHopIPv6IETF:
        return cls(data[:20])


# =============================================================== TrafficNextHopSimpson


@ExtendedCommunity.register
class TrafficNextHopSimpson(ExtendedCommunity):
    """Redirect to UPDATE's existing next-hop (draft-simpson-idr-flowspec-redirect).

    Unlike TrafficNextHopIPv4/IPv6 which contain explicit addresses, this signals
    "use the UPDATE message's NextHop attribute". Copy flag works as above.
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x08
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x00

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_traffic_nexthop_simpson(cls, copy: bool) -> TrafficNextHopSimpson:
        """Create TrafficNextHopSimpson from semantic values."""
        packed = pack('!BBLH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, 0, 1 if copy else 0)
        return cls(packed)

    @property
    def copy(self) -> bool:
        return bool(self._packed[7] & 0x01)

    def __repr__(self) -> str:
        return 'copy-to-nexthop' if self.copy else 'redirect-to-nexthop'

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficNextHopSimpson:
        return cls(data[:8])


# ============================================================ TrafficRedirectIPv6


@ExtendedCommunityIPv6.register
class TrafficRedirectIPv6(ExtendedCommunityIPv6):
    """Redirect to VRF using IPv6 address (RFC 5701).

    Uses IPv6 Address Specific Extended Community format (20 bytes).
    """

    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0B

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunityIPv6.__init__(self, packed)

    @classmethod
    def make_traffic_redirect_ipv6(cls, ip: str, asn: int) -> TrafficRedirectIPv6:
        """Create TrafficRedirectIPv6 from semantic values."""
        packed = pack('!BB16sH', 0x00, 0x02, socket.inet_pton(socket.AF_INET6, ip), asn)
        return cls(packed)

    @property
    def ip(self) -> str:
        return socket.inet_ntop(socket.AF_INET6, self._packed[2:18])

    @property
    def asn(self) -> int:
        value: int = unpack('!H', self._packed[18:20])[0]
        return value

    def __str__(self) -> str:
        return 'redirect %s:%d' % (self.ip, self.asn)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> TrafficRedirectIPv6:
        return cls(data[:20])


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
