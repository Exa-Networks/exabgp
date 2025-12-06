"""family.py

Created by Thomas Mangin on 2010-01-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import ClassVar


# ======================================================================== AFI
# https://www.iana.org/assignments/address-family-numbers/


class AFI(int):
    # Constants
    UNDEFINED: ClassVar[int] = 0x00  # internal
    IPv4: ClassVar[int] = 0x01
    IPv6: ClassVar[int] = 0x02
    L2VPN: ClassVar[int] = 0x19
    BGPLS: ClassVar[int] = 0x4004

    # Singleton instances (initialized after class definition)
    undefined: ClassVar[AFI]
    ipv4: ClassVar[AFI]
    ipv6: ClassVar[AFI]
    l2vpn: ClassVar[AFI]
    bgpls: ClassVar[AFI]

    # Lookup tables
    _names: ClassVar[dict[int, str]] = {
        0x00: 'undefined',
        0x01: 'ipv4',
        0x02: 'ipv6',
        0x19: 'l2vpn',
        0x4004: 'bgp-ls',
    }

    _masks: ClassVar[dict[int, int]] = {
        0x01: 32,  # IPv4
        0x02: 128,  # IPv6
    }

    _address_lengths: ClassVar[dict[int, int]] = {
        0x01: 4,  # IPv4: 4 bytes = 32 bits
        0x02: 16,  # IPv6: 16 bytes = 128 bits
    }

    # Caches
    common: ClassVar[dict[bytes, AFI]] = {}
    codes: ClassVar[dict[str, AFI]] = {}
    cache: ClassVar[dict[int, AFI]] = {}
    inet_names: ClassVar[dict[int, str]] = {}

    def pack_afi(self) -> bytes:
        return pack('!H', self)

    def mask(self) -> int | None:
        return self._masks.get(self, None)

    def address_length(self) -> int:
        """Return address length in bytes.

        Raises:
            ValueError: If address length is not defined for this AFI
        """
        if self not in self._address_lengths:
            raise ValueError(f'Address length not defined for AFI {self.name()}')
        return self._address_lengths[self]

    def name(self) -> str:
        return self._names.get(self, f'unknown-afi-{hex(self)}')

    def __repr__(self) -> str:
        return self.name()

    def __str__(self) -> str:
        return self.name()

    @staticmethod
    def unpack_afi(data: bytes) -> AFI:
        if len(data) < 2:
            raise ValueError(f'AFI data too short: need 2 bytes, got {len(data)}')
        return AFI.common.get(data[:2], AFI(unpack('!H', data[:2])[0]))

    @classmethod
    def value(cls, name: str) -> AFI | None:
        return cls.codes.get(name, None)

    @staticmethod
    def implemented_safi(afi: str) -> list[str]:
        if afi == 'ipv4':
            return ['unicast', 'multicast', 'nlri-mpls', 'mcast-vpn', 'mpls-vpn', 'flow', 'flow-vpn', 'mup']
        if afi == 'ipv6':
            return ['unicast', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup']
        if afi == 'l2vpn':
            return ['vpls', 'evpn']
        if afi == 'bgp-ls':
            return ['bgp-ls', 'bgp-ls-vpn']
        return []

    @classmethod
    def from_string(cls, string: str) -> AFI:
        return cls.codes.get(string, cls.undefined)

    @classmethod
    def from_int(cls, value: int) -> AFI:
        return cls.cache.get(value, AFI(value))


# Initialize AFI class attributes after class definition
AFI.undefined = AFI(AFI.UNDEFINED)
AFI.ipv4 = AFI(AFI.IPv4)
AFI.ipv6 = AFI(AFI.IPv6)
AFI.l2vpn = AFI(AFI.L2VPN)
AFI.bgpls = AFI(AFI.BGPLS)

AFI.common = {
    AFI.undefined.pack_afi(): AFI.undefined,
    AFI.ipv4.pack_afi(): AFI.ipv4,
    AFI.ipv6.pack_afi(): AFI.ipv6,
    AFI.l2vpn.pack_afi(): AFI.l2vpn,
    AFI.bgpls.pack_afi(): AFI.bgpls,
}

AFI.codes = dict(
    (k.lower().replace('_', '-'), v)
    for (k, v) in {
        'ipv4': AFI.ipv4,
        'ipv6': AFI.ipv6,
        'l2vpn': AFI.l2vpn,
        'bgp-ls': AFI.bgpls,
    }.items()
)

AFI.cache = dict([(inst, inst) for (_, inst) in AFI.codes.items()])
AFI.inet_names = dict([(inst, name.replace('ipv', 'inet')) for (name, inst) in AFI.codes.items()])


# ======================================================================= SAFI
# https://www.iana.org/assignments/safi-namespace


class SAFI(int):
    # Constants
    UNDEFINED: ClassVar[int] = 0  # internal
    UNICAST: ClassVar[int] = 1  # [RFC4760]
    MULTICAST: ClassVar[int] = 2  # [RFC4760]
    NLRI_MPLS: ClassVar[int] = 4  # [RFC3107]
    MCAST_VPN: ClassVar[int] = 5  # [RFC6514]
    VPLS: ClassVar[int] = 65  # [RFC4761]
    EVPN: ClassVar[int] = 70  # [draft-ietf-l2vpn-evpn]
    BGPLS: ClassVar[int] = 71  # [RFC7752]
    BGPLS_VPN: ClassVar[int] = 72  # [RFC7752]
    MUP: ClassVar[int] = 85  # [draft-mpmz-bess-mup-safi]
    MPLS_VPN: ClassVar[int] = 128  # [RFC4364]
    RTC: ClassVar[int] = 132  # [RFC4684]
    FLOW_IP: ClassVar[int] = 133  # [RFC5575]
    FLOW_VPN: ClassVar[int] = 134  # [RFC5575]
    # Unused/deprecated SAFI values (kept for reference):
    # deprecated = 3            # [RFC4760]
    # pseudowire = 6            # [draft-ietf-pwe3-dynamic-ms-pw] (TEMPORARY - Expires 2008-08-23)
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
    # reserved = [0,3] + [130,131] + [_ for _ in range(135,140)] + [_ for _ in range(141,241)] + [255,] # [RFC4760]

    # Singleton instances (initialized after class definition)
    undefined: ClassVar[SAFI]
    unicast: ClassVar[SAFI]
    multicast: ClassVar[SAFI]
    nlri_mpls: ClassVar[SAFI]
    vpls: ClassVar[SAFI]
    evpn: ClassVar[SAFI]
    bgp_ls: ClassVar[SAFI]
    bgp_ls_vpn: ClassVar[SAFI]
    mup: ClassVar[SAFI]
    mpls_vpn: ClassVar[SAFI]
    mcast_vpn: ClassVar[SAFI]
    rtc: ClassVar[SAFI]
    flow_ip: ClassVar[SAFI]
    flow_vpn: ClassVar[SAFI]

    # Lookup tables
    _names: ClassVar[dict[int, str]] = {
        0: 'undefined',
        1: 'unicast',
        2: 'multicast',
        4: 'nlri-mpls',
        5: 'mcast-vpn',
        65: 'vpls',
        70: 'evpn',
        71: 'bgp-ls',
        72: 'bgp-ls-vpn',
        85: 'mup',
        128: 'mpls-vpn',
        132: 'rtc',
        133: 'flow',
        134: 'flow-vpn',
    }

    # Caches
    common: ClassVar[dict[bytes, SAFI]] = {}
    codes: ClassVar[dict[str, SAFI]] = {}
    cache: ClassVar[dict[int, SAFI]] = {}

    def pack_safi(self) -> bytes:
        return bytes([self])

    def name(self) -> str:
        return self._names.get(self, f'unknown safi {int(self)}')

    def has_label(self) -> bool:
        return self in (SAFI.nlri_mpls, SAFI.mpls_vpn, SAFI.mcast_vpn)

    def has_rd(self) -> bool:
        return self in (SAFI.mup, SAFI.mpls_vpn, SAFI.mcast_vpn, SAFI.flow_vpn)

    def has_path(self) -> bool:
        return self in (SAFI.unicast, SAFI.nlri_mpls)

    def __str__(self) -> str:
        return self.name()

    def __repr__(self) -> str:
        return self.name()

    @staticmethod
    def unpack_safi(data: bytes) -> SAFI:
        return SAFI.common.get(data, SAFI(data[0] if data else 0))

    @classmethod
    def value(cls, name: str) -> SAFI | None:
        return cls.codes.get(name, None)

    @classmethod
    def from_string(cls, string: str) -> SAFI:
        return cls.codes.get(string, cls.undefined)

    @classmethod
    def from_int(cls, value: int) -> SAFI:
        return cls.cache.get(value, SAFI(value))


# Initialize SAFI class attributes after class definition
SAFI.undefined = SAFI(SAFI.UNDEFINED)
SAFI.unicast = SAFI(SAFI.UNICAST)
SAFI.multicast = SAFI(SAFI.MULTICAST)
SAFI.nlri_mpls = SAFI(SAFI.NLRI_MPLS)
SAFI.vpls = SAFI(SAFI.VPLS)
SAFI.evpn = SAFI(SAFI.EVPN)
SAFI.bgp_ls = SAFI(SAFI.BGPLS)
SAFI.bgp_ls_vpn = SAFI(SAFI.BGPLS_VPN)
SAFI.mup = SAFI(SAFI.MUP)
SAFI.mpls_vpn = SAFI(SAFI.MPLS_VPN)
SAFI.mcast_vpn = SAFI(SAFI.MCAST_VPN)
SAFI.rtc = SAFI(SAFI.RTC)
SAFI.flow_ip = SAFI(SAFI.FLOW_IP)
SAFI.flow_vpn = SAFI(SAFI.FLOW_VPN)

SAFI.common = {
    SAFI.undefined.pack_safi(): SAFI.undefined,
    SAFI.unicast.pack_safi(): SAFI.unicast,
    SAFI.multicast.pack_safi(): SAFI.multicast,
    SAFI.nlri_mpls.pack_safi(): SAFI.nlri_mpls,
    SAFI.vpls.pack_safi(): SAFI.vpls,
    SAFI.evpn.pack_safi(): SAFI.evpn,
    SAFI.bgp_ls.pack_safi(): SAFI.bgp_ls,
    SAFI.bgp_ls_vpn.pack_safi(): SAFI.bgp_ls_vpn,
    SAFI.mup.pack_safi(): SAFI.mup,
    SAFI.mpls_vpn.pack_safi(): SAFI.mpls_vpn,
    SAFI.mcast_vpn.pack_safi(): SAFI.mcast_vpn,
    SAFI.rtc.pack_safi(): SAFI.rtc,
    SAFI.flow_ip.pack_safi(): SAFI.flow_ip,
    SAFI.flow_vpn.pack_safi(): SAFI.flow_vpn,
}

SAFI.codes = dict(
    (k.lower().replace('_', '-'), v)
    for (k, v) in {
        'unicast': SAFI.unicast,
        'multicast': SAFI.multicast,
        'nlri-mpls': SAFI.nlri_mpls,
        'vpls': SAFI.vpls,
        'evpn': SAFI.evpn,
        'bgp-ls': SAFI.bgp_ls,
        'bgp-ls-vpn': SAFI.bgp_ls_vpn,
        'mup': SAFI.mup,
        'mpls-vpn': SAFI.mpls_vpn,
        'mcast-vpn': SAFI.mcast_vpn,
        'rtc': SAFI.rtc,
        'flow': SAFI.flow_ip,
        'flow-vpn': SAFI.flow_vpn,
    }.items()
)

SAFI.cache = dict([(inst, inst) for (_, inst) in SAFI.codes.items()])


# ===================================================================== FAMILY


class Family:
    size: ClassVar[dict[tuple[AFI, SAFI], tuple[tuple[int, ...], int]]] = {
        # family                   next-hop   RD
        (AFI.ipv4, SAFI.unicast): ((4,), 0),
        (AFI.ipv4, SAFI.multicast): ((4,), 0),
        (AFI.ipv4, SAFI.nlri_mpls): ((4,), 0),
        (AFI.ipv4, SAFI.mup): ((4, 16), 0),
        (AFI.ipv4, SAFI.mpls_vpn): ((12,), 8),
        (AFI.ipv4, SAFI.mcast_vpn): ((4,), 0),
        (AFI.ipv4, SAFI.flow_ip): ((0, 4), 0),
        (AFI.ipv4, SAFI.flow_vpn): ((0, 4), 0),
        (AFI.ipv4, SAFI.rtc): ((4, 16), 0),
        (AFI.ipv6, SAFI.unicast): ((16, 32), 0),
        (AFI.ipv6, SAFI.nlri_mpls): ((16, 32), 0),
        (AFI.ipv6, SAFI.mup): ((4, 16), 0),
        (AFI.ipv6, SAFI.mpls_vpn): ((24, 40), 8),
        (AFI.ipv6, SAFI.mcast_vpn): ((4, 16), 0),
        (AFI.ipv6, SAFI.flow_ip): ((0, 16, 32), 0),
        (AFI.ipv6, SAFI.flow_vpn): ((0, 16, 32), 0),
        (AFI.l2vpn, SAFI.vpls): ((4,), 0),
        (AFI.l2vpn, SAFI.evpn): ((4,), 0),
        (AFI.bgpls, SAFI.bgp_ls): ((4, 16), 0),
    }

    # Class-level AFI/SAFI for single-family types (None = use instance storage)
    _class_afi: ClassVar[AFI | None] = None
    _class_safi: ClassVar[SAFI | None] = None

    # Type hints for afi/safi - may be instance attributes or properties
    afi: AFI
    safi: SAFI

    def __init__(self, afi: int, safi: int) -> None:
        """Initialize Family with AFI and SAFI.

        If the subclass defines _class_afi/_class_safi, those are used via
        property accessors instead of setting instance attributes. This supports:
        - Multi-family NLRI types that need instance storage for AFI
        - Single-family NLRI types that use class-level constants
        """
        # Only set instance afi if no class-level afi defined
        if self._class_afi is None:
            self.afi = AFI.from_int(afi)
        # Only set instance safi if no class-level safi defined
        if self._class_safi is None:
            self.safi = SAFI.from_int(safi)

    def has_label(self) -> bool:
        return self.safi.has_label()

    def has_rd(self) -> bool:
        return self.safi.has_rd()

    def has_path(self) -> bool:
        return self.safi.has_path()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Family):
            return False
        return self.afi == other.afi and self.safi == other.safi

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Family):
            return True
        return self.afi != other.afi or self.safi != other.safi

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Family for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Family for ordering does not make sense')

    def afi_safi(self) -> tuple[AFI, SAFI]:
        return (self.afi, self.safi)

    def family(self) -> Family:
        return Family(self.afi, self.safi)

    def short(self) -> str:
        return f'{self.afi}/{self.safi}'

    def extensive(self) -> str:
        return f'afi {self.afi} safi {self.safi}'

    def index(self) -> bytes:
        return f'{self.afi:02x}{self.safi:02x}'.encode()

    def __repr__(self) -> str:
        return f'{self.afi!s} {self.safi!s}'
