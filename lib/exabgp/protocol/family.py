# encoding: utf-8
"""
family.py

Created by Thomas Mangin on 2010-01-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.protocol.resource import Resource


# ======================================================================== AFI
# https://www.iana.org/assignments/address-family-numbers/


class _AFI(int):
    UNDEFINED = 0x00  # internal
    IPv4 = 0x01
    IPv6 = 0x02
    L2VPN = 0x19
    BGPLS = 0x4004

    _names = {
        UNDEFINED: 'undefined',
        IPv4: 'ipv4',
        IPv6: 'ipv6',
        L2VPN: 'l2vpn',
        BGPLS: 'bgp-ls',
    }

    _masks = {
        IPv4: 32,
        IPv6: 128,
    }

    def pack(self):
        return pack('!H', self)

    def name(self):
        return self._names.get(self, 'unknown-afi-0x%s' % hex(self))

    def mask(self):
        return self._masks.get(self, 'invalid request for this family')

    def __repr__(self):
        return self.name()

    def __str__(self):
        return self.name()


class AFI(Resource):
    undefined = _AFI(_AFI.UNDEFINED)
    ipv4 = _AFI(_AFI.IPv4)
    ipv6 = _AFI(_AFI.IPv6)
    l2vpn = _AFI(_AFI.L2VPN)
    bgpls = _AFI(_AFI.BGPLS)

    common = {
        undefined.pack(): undefined,
        ipv4.pack(): ipv4,
        ipv6.pack(): ipv6,
        l2vpn.pack(): l2vpn,
        bgpls.pack(): bgpls,
    }

    codes = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {'ipv4': ipv4, 'ipv6': ipv6, 'l2vpn': l2vpn, 'bgp-ls': bgpls,}.items()
    )

    cache = dict([(r, r) for (l, r) in codes.items()])
    names = dict([(r, l) for (l, r) in codes.items()])

    inet_names = dict([(r, l.replace('ipv', 'inet')) for (l, r) in codes.items()])

    def name(self):
        return self.inet_names.get(self, "unknown afi")

    @staticmethod
    def unpack(data):
        return AFI.common.get(data, _AFI(unpack('!H', data)[0]))

    @classmethod
    def value(cls, name):
        return cls.codes.get(name, None)

    @staticmethod
    def implemented_safi(afi):
        if afi == 'ipv4':
            return ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'flow', 'flow-vpn']
        if afi == 'ipv6':
            return ['unicast', 'mpls-vpn', 'flow', 'flow-vpn']
        if afi == 'l2vpn':
            return ['vpls', 'evpn']
        if afi == 'bgp-ls':
            return ['bgp-ls', 'bgp-ls-vpn']
        return []

    @classmethod
    def fromString(cls, string):
        return cls.codes.get(string, cls.undefined)

    @classmethod
    def create(cls, value):
        return cls.cache.get(value, _AFI(value))


# ======================================================================= SAFI
# https://www.iana.org/assignments/safi-namespace


class _SAFI(int):
    UNDEFINED = 0  # internal
    UNICAST = 1  # [RFC4760]
    MULTICAST = 2  # [RFC4760]
    NLRI_MPLS = 4  # [RFC3107]
    VPLS = 65  # [RFC4761]
    EVPN = 70  # [draft-ietf-l2vpn-evpn]
    BGPLS = 71  # [RFC7752]
    BGPLS_VPN = 72  # [RFC7752]
    MPLS_VPN = 128  # [RFC4364]
    RTC = 132  # [RFC4684]
    FLOW_IP = 133  # [RFC5575]
    FLOW_VPN = 134  # [RFC5575]
    # deprecated = 3            # [RFC4760]
    # mcast_vpn = 5             # [draft-ietf-l3vpn-2547bis-mcast-bgp] (TEMPORARY - Expires 2008-06-19)
    # pseudowire = 6            # [draft-ietf-pwe3-dynamic-ms-pw] (TEMPORARY - Expires 2008-08-23) Dynamic Placement of Multi-Segment Pseudowires
    # encapsulation = 7         # [RFC5512]
    # tunel = 64                # [Nalawade]
    # bgp_mdt = 66              # [Nalawade]
    # bgp_4over6 = 67           # [Cui]
    # bgp_6over4 = 67           # [Cui]
    # vpn_adi = 69              # [RFC-ietf-l1vpn-bgp-auto-discovery-05.txt]
    # mcast_bgp_mpls_vpn = 129  # [RFC2547]
    # rt = 132                  # [RFC4684]
    # vpn_ad = 140              # [draft-ietf-l3vpn-bgpvpn-auto]
    # private = [_ for _ in range(241,254)]   # [RFC4760]
    # unassigned = [_ for _ in range(8,64)] + [_ for _ in range(70,128)]
    # reverved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,]    # [RFC4760]

    _names = {
        UNICAST: 'unicast',
        MULTICAST: 'multicast',
        NLRI_MPLS: 'nlri-mpls',
        VPLS: 'vpls',
        EVPN: 'evpn',
        BGPLS: 'bgp-ls',
        BGPLS_VPN: 'bgp-ls-vpn',
        MPLS_VPN: 'mpls-vpn',
        RTC: 'rtc',
        FLOW_IP: 'flow',
        FLOW_VPN: 'flow-vpn',
    }

    def pack(self):
        return character(self)

    def name(self):
        return self._names.get(self, 'unknown safi %d' % int(self))

    def has_label(self):
        return self in (SAFI.nlri_mpls, SAFI.mpls_vpn)

    def has_rd(self):
        return self in (SAFI.nlri_mpls, SAFI.mpls_vpn, SAFI.flow_vpn)
        # technically self.flow_vpn and self.vpls has an RD but it is not an NLRI

    def has_path(self):
        return self in (SAFI.unicast, SAFI.nlri_mpls)
        # technically self.flow_vpn and self.vpls has an RD but it is not an NLRI

    def __str__(self):
        return self.name()

    def __repr__(self):
        return str(self)


class SAFI(Resource):
    undefined = _SAFI(_SAFI.UNDEFINED)
    unicast = _SAFI(_SAFI.UNICAST)
    multicast = _SAFI(_SAFI.MULTICAST)
    nlri_mpls = _SAFI(_SAFI.NLRI_MPLS)
    vpls = _SAFI(_SAFI.VPLS)
    evpn = _SAFI(_SAFI.EVPN)
    bgp_ls = _SAFI(_SAFI.BGPLS)
    bgp_ls_vpn = _SAFI(_SAFI.BGPLS_VPN)
    mpls_vpn = _SAFI(_SAFI.MPLS_VPN)
    rtc = _SAFI(_SAFI.RTC)
    flow_ip = _SAFI(_SAFI.FLOW_IP)
    flow_vpn = _SAFI(_SAFI.FLOW_VPN)

    common = {
        undefined.pack(): undefined,
        unicast.pack(): unicast,
        multicast.pack(): multicast,
        nlri_mpls.pack(): nlri_mpls,
        vpls.pack(): vpls,
        evpn.pack(): evpn,
        bgp_ls.pack(): bgp_ls,
        bgp_ls_vpn.pack(): bgp_ls_vpn,
        mpls_vpn.pack(): mpls_vpn,
        rtc.pack(): rtc,
        flow_ip.pack(): flow_ip,
        flow_vpn.pack(): flow_vpn,
    }

    codes = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'unicast': unicast,
            'multicast': multicast,
            'nlri-mpls': nlri_mpls,
            'vpls': vpls,
            'evpn': evpn,
            'bgp-ls': bgp_ls,
            'bgp-ls-vpn': bgp_ls_vpn,
            'mpls-vpn': mpls_vpn,
            'rtc': rtc,
            'flow': flow_ip,
            'flow-vpn': flow_vpn,
        }.items()
    )

    names = _SAFI._names

    cache = dict([(r, r) for (l, r) in codes.items()])

    @staticmethod
    def unpack(data):
        return SAFI.common.get(data, _SAFI(ordinal(data)))

    @classmethod
    def value(cls, name):
        return cls.codes.get(name, None)

    @classmethod
    def fromString(cls, string):
        return cls.codes.get(string, cls.undefined)

    @classmethod
    def create(cls, value):
        return cls.cache.get(value, _SAFI(value))


# ===================================================================== FAMILY


class Family(object):
    size = {
        # family                   next-hop   RD
        (AFI.ipv4, SAFI.unicast): ((4,), 0),
        (AFI.ipv4, SAFI.multicast): ((4,), 0),
        (AFI.ipv4, SAFI.nlri_mpls): ((4,), 0),
        (AFI.ipv4, SAFI.mpls_vpn): ((12,), 8),
        (AFI.ipv4, SAFI.flow_ip): ((0, 4), 0),
        (AFI.ipv4, SAFI.flow_vpn): ((0, 4), 0),
        (AFI.ipv4, SAFI.rtc): ((4, 16), 0),
        (AFI.ipv6, SAFI.unicast): ((16, 32), 0),
        (AFI.ipv6, SAFI.nlri_mpls): ((16, 32), 0),
        (AFI.ipv6, SAFI.mpls_vpn): ((24, 40), 8),
        (AFI.ipv6, SAFI.flow_ip): ((0, 16, 32), 0),
        (AFI.ipv6, SAFI.flow_vpn): ((0, 16, 32), 0),
        (AFI.l2vpn, SAFI.vpls): ((4,), 0),
        (AFI.l2vpn, SAFI.evpn): ((4,), 0),
        (AFI.bgpls, SAFI.bgp_ls): ((4,), 0),
    }

    __slots__ = ['afi', 'safi']

    def __init__(self, afi, safi):
        self.afi = AFI.create(afi)
        self.safi = SAFI.create(safi)

    def has_label(self):
        return self.safi.has_label()

    def has_rd(self):
        return self.safi.has_rd()

    def has_path(self):
        return self.safi.has_path()

    def __eq__(self, other):
        return self.afi == other.afi and self.safi == other.safi

    def __neq__(self, other):
        return self.afi != other.afi or self.safi != other.safi

    def __lt__(self, other):
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing Family for ordering does not make sense')

    def family(self):
        return (self.afi, self.safi)

    def extensive(self):
        return 'afi %s safi %s' % (self.afi, self.safi)

    def __repr__(self):
        return "%s %s" % (str(self.afi), str(self.safi))
