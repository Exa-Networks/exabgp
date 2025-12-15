"""inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# This is a legacy file to handle 3.4.x like format

from __future__ import annotations

from typing import Any, Iterator, cast

from exabgp.protocol.ip import IP

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.settings import INETSettings
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection

from exabgp.rib.route import Route

from exabgp.configuration.core import Section
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, LeafList, ValueType

# from exabgp.configuration.static.parser import inet
from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import aigp
from exabgp.configuration.static.parser import path_information
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw
from exabgp.configuration.static.mpls import route_distinguisher
from exabgp.configuration.static.mpls import label
from exabgp.configuration.static.mpls import prefix_sid
from exabgp.configuration.static.mpls import prefix_sid_srv6


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int(afi: AFI, integer: int) -> bytes:
    return b''.join(bytes([(integer >> (offset * 8)) & 0xFF]) for offset in range(IP.length(afi) - 1, -1, -1))


class ParseStaticRoute(Section):
    # Schema definition for static route attributes
    schema = Container(
        description='Static route configuration',
        children={
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self"',
                target=ActionTarget.NEXTHOP_ATTRIBUTE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'path-information': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Path information (path ID for ADD-PATH)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
            ),
            'rd': Leaf(
                type=ValueType.RD,
                description='Route distinguisher',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
            ),
            'route-distinguisher': Leaf(
                type=ValueType.RD,
                description='Route distinguisher (alias for rd)',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
            ),
            'label': Leaf(
                type=ValueType.LABEL,
                description='MPLS label stack',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
            ),
            'bgp-prefix-sid': Leaf(
                type=ValueType.STRING,
                description='BGP Prefix-SID attribute',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'bgp-prefix-sid-srv6': Leaf(
                type=ValueType.STRING,
                description='BGP Prefix-SID SRv6 attribute',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'attribute': Leaf(
                type=ValueType.HEX_STRING,
                description='Generic BGP attribute in hex format',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'origin': Leaf(
                type=ValueType.ORIGIN,
                description='BGP origin attribute',
                choices=['igp', 'egp', 'incomplete'],
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'med': Leaf(
                type=ValueType.MED,
                description='Multi-exit discriminator',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'as-path': LeafList(
                type=ValueType.AS_PATH,
                description='AS path',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'local-preference': Leaf(
                type=ValueType.LOCAL_PREF,
                description='Local preference',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'atomic-aggregate': Leaf(
                type=ValueType.ATOMIC_AGGREGATE,
                description='Atomic aggregate flag',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'aggregator': Leaf(
                type=ValueType.AGGREGATOR,
                description='Aggregator (AS number and IP)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'originator-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Originator ID (route reflector)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'cluster-list': LeafList(
                type=ValueType.IP_ADDRESS,
                description='Cluster list (route reflector)',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'community': LeafList(
                type=ValueType.COMMUNITY,
                description='Standard BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'large-community': LeafList(
                type=ValueType.LARGE_COMMUNITY,
                description='Large BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'extended-community': LeafList(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Extended BGP communities',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'aigp': Leaf(
                type=ValueType.INTEGER,
                description='Accumulated IGP metric',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'name': Leaf(
                type=ValueType.STRING,
                description='Route name/mnemonic',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'split': Leaf(
                type=ValueType.INTEGER,
                description='Split prefix into smaller prefixes',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'watchdog': Leaf(
                type=ValueType.STRING,
                description='Watchdog name for route withdrawal',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
            'withdraw': Leaf(
                type=ValueType.BOOLEAN,
                description='Mark route for withdrawal',
                target=ActionTarget.ATTRIBUTE,
                operation=ActionOperation.ADD,
                key=ActionKey.NAME,
            ),
        },
    )

    # put next-hop first as it is a requirement atm
    definition = [
        'next-hop <ip>',
        'path-information <ipv4 formated number>',
        'route-distinguisher|rd <ipv4>:<port>|<16bits number>:<32bits number>|<32bits number>:<16bits number>',
        'origin IGP|EGP|INCOMPLETE',
        'as-path [ <asn>.. ]',
        'med <16 bits number>',
        'local-preference <16 bits number>',
        'atomic-aggregate',
        'community <16 bits number>',
        'large-community <96 bits number>',
        'extended-community target:<16 bits number>:<ipv4 formated number>',
        'originator-id <ipv4>',
        'cluster-list <ipv4>',
        'label <15 bits number>',
        'bgp-prefix-sid [ 32 bits number> ] | [ <32 bits number>, [ ( <24 bits number>,<24 bits number> ) ]]',
        'bgp-prefix-sid-srv6 ( l3-service|l2-service <ipv6> <behavior> [<LBL>,<LNL>,<FL>,<AL>,<Tpose-Len>,<Tpose-Offset>])',
        'aigp <40 bits number>',
        'attribute [ generic attribute format ]name <mnemonic>',
        'split /<mask>',
        'watchdog <watchdog-name>',
        'withdraw',
    ]

    syntax: str = 'route <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known: dict[str | tuple[Any, ...], Any] = {
        'path-information': path_information,
        'rd': route_distinguisher,
        'route-distinguisher': route_distinguisher,
        'label': label,
        'bgp-prefix-sid': prefix_sid,
        'bgp-prefix-sid-srv6': prefix_sid_srv6,
        'attribute': attribute,
        'next-hop': next_hop,
        'origin': origin,
        'med': med,
        'as-path': as_path,
        'local-preference': local_preference,
        'atomic-aggregate': atomic_aggregate,
        'aggregator': aggregator,
        'originator-id': originator_id,
        'cluster-list': cluster_list,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
        'aigp': aigp,
        'name': named,
        'split': split,
        'watchdog': watchdog,
        'withdraw': withdraw,
    }

    # action dict removed - derived from schema

    assign: dict[str, str] = {
        'path-information': 'path_info',
        'rd': 'rd',
        'route-distinguisher': 'rd',
        'label': 'labels',
    }

    name: str = 'static/route'

    def __init__(self, parser: Any, scope: Any, error: Any) -> None:
        Section.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        """Enter settings mode for nested route syntax.

        Instead of creating NLRI immediately (legacy mode), we:
        1. Parse the prefix from tokeniser
        2. Create settings object with CIDR
        3. Enter settings mode so nlri-set commands populate settings
        4. Create NLRI in post() when all values are collected
        """
        ipmask = prefix(self.parser.tokeniser)
        settings = INETSettings()
        settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
        settings.afi = IP.toafi(ipmask.top())
        settings.safi = SAFI.mpls_vpn  # Default to IPVPN, can be downgraded in post()
        settings.action = Action.ANNOUNCE
        attributes = AttributeCollection()

        self.scope.set_settings(settings, attributes)
        return True

    def post(self) -> bool:
        """Create NLRI from collected settings and finalize route."""
        # Check if we're in settings mode (nested route syntax: route X { ... })
        if self.scope.in_settings_mode():
            settings = self.scope.get_settings()
            attributes = self.scope.get_settings_attributes()

            # Clear settings mode
            self.scope.clear_settings()

            # Determine NLRI class based on what was actually parsed
            has_rd = settings.rd is not None
            has_labels = settings.labels is not None

            if has_rd:
                nlri_class = IPVPN
                settings.safi = SAFI.mpls_vpn
            elif has_labels:
                nlri_class = Label
                settings.safi = SAFI.nlri_mpls
            else:
                nlri_class = INET
                # Use original AFI to determine unicast vs multicast SAFI
                settings.safi = IP.tosafi(settings.cidr.prefix().split('/')[0])

            # Create immutable NLRI from settings
            nlri = nlri_class.from_settings(settings)
            route = Route(nlri, attributes, nexthop=settings.nexthop)
            self.scope.append_route(route)

        # Process routes (from either nested syntax or flat syntax)
        self._split()
        routes = self.scope.pop_routes()
        if routes:
            for route in routes:
                # Recreate NLRI with correct type based on actual RD/labels presence
                # instead of mutating SAFI after creation
                route.nlri = self._normalize_nlri_type(route.nlri)
                self.scope.append_route(route)
        return True

    @staticmethod
    def _normalize_nlri_type(nlri: NLRI) -> NLRI:
        """Ensure NLRI has the correct type based on RD/labels presence.

        Parser creates IPVPN instances which can hold all data (RD, labels, cidr).
        This method checks what's actually present and recreates with the minimal
        type needed: IPVPN (has RD), Label (has labels only), or INET (neither).

        This avoids SAFI mutation which is incompatible with class-level SAFI.
        """
        # Check if this is an INET-family NLRI (INET, Label, or IPVPN)
        if not isinstance(nlri, INET):
            return nlri

        # Check actual data presence using class-level capability flags
        # INET < Label < IPVPN hierarchy, each adds capability
        # Use class methods has_rd()/type checks instead of hasattr() per coding standards
        #
        # Note: We need to check ACTUAL data presence, not SAFI capability:
        # - SAFI.has_label() returns True for nlri_mpls/mpls_vpn SAFIs
        # - But an NLRI might have SAFI=nlri_mpls but no actual labels (NOLABEL)
        # - Similarly for RD: SAFI=mpls_vpn but RD might be empty
        #
        # The class type tells us what the class CAN hold:
        # - INET: no labels, no RD
        # - Label: has _has_labels flag (may be True or False)
        # - IPVPN: has _has_labels flag AND _has_rd flag

        # Check RD: only IPVPN class has _has_rd attribute
        has_rd = isinstance(nlri, IPVPN) and nlri._has_rd

        # Check labels: Label and IPVPN classes have _has_labels flag
        has_label = isinstance(nlri, Label) and nlri._has_labels

        # Determine target type and SAFI
        if has_rd:
            # IPVPN: has RD (and likely labels)
            target_cls = IPVPN
            target_safi = SAFI.mpls_vpn
            # Early return if already correct type AND safi
            if isinstance(nlri, IPVPN) and nlri.safi == target_safi:
                return nlri
        elif has_label:
            # Label: has labels but no RD
            target_cls = Label
            target_safi = SAFI.nlri_mpls
            # Early return if already correct type AND safi (and not IPVPN subclass)
            if isinstance(nlri, Label) and not isinstance(nlri, IPVPN) and nlri.safi == target_safi:
                return nlri
        else:
            # INET: no RD, no labels - determine SAFI from IP prefix
            target_cls = INET
            # Determine SAFI based on IP range (multicast vs unicast)
            # IPVPN/Label have class-level SAFI that's not the intended value
            cidr = nlri.cidr
            target_safi = IP.tosafi(cidr.prefix().split('/')[0])
            # Early return if already correct type
            if type(nlri) is INET:  # noqa: E721 - exact type check
                return nlri

        # Build kwargs for from_cidr - pass labels/rd if target supports them
        kwargs: dict = {}
        if has_label:
            # Safe: has_label is True only if isinstance(nlri, Label)
            kwargs['labels'] = cast(Label, nlri).labels
        if has_rd:
            # Safe: has_rd is True only if isinstance(nlri, IPVPN)
            kwargs['rd'] = cast(IPVPN, nlri).rd

        # Create new NLRI with correct type and all values upfront
        new_nlri = target_cls.from_cidr(
            nlri.cidr,
            nlri.afi,
            target_safi,
            nlri.action,
            nlri.path_info,
            **kwargs,
        )
        # Note: nexthop is stored in Route, not NLRI - caller handles nexthop
        return new_nlri

    def _check(self) -> bool:
        change = self.scope.get(self.name)
        if not self.check(change):
            self.error.set(self.syntax)
            return False
        return True

    @staticmethod
    def check(route: Route) -> bool:
        nlri: NLRI = route.nlri
        # Check route.nexthop instead of nlri.nexthop (nexthop is stored in Route)
        if (
            route.nexthop is IP.NoNextHop
            and nlri.action == Action.ANNOUNCE
            and nlri.afi == AFI.ipv4
            and nlri.safi in (SAFI.unicast, SAFI.multicast)
        ):
            return False
        return True

    @staticmethod
    def split(last: Route) -> Iterator[Route]:
        if Attribute.CODE.INTERNAL_SPLIT not in last.attributes:
            yield last
            return

        # The NLRI is an Inet subclass with cidr, nexthop, etc. attributes
        # Use Any to access dynamically since the actual type depends on AFI/SAFI
        nlri: Any = last.nlri

        # ignore if the request is for an aggregate, or the same size
        mask = nlri.cidr.mask
        cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
        if mask >= cut:
            yield last
            return

        # calculate the number of IP in the /<size> of the new route
        increment = pow(2, nlri.afi.mask() - cut)
        # how many new routes are we going to create from the initial one
        number = pow(2, cut - nlri.cidr.mask)

        # convert the IP into a integer/long
        ip = 0
        for c in nlri.cidr.packed_cidr():
            ip <<= 8
            ip += c

        afi = nlri.afi
        safi = nlri.safi

        # Extract data from original NLRI and Route before clearing
        # Check NLRI class type rather than SAFI (SAFI may be unicast even for VPN routes)
        klass = nlri.__class__
        nexthop = last.nexthop  # Get nexthop from Route, not NLRI
        path_info = nlri.path_info if safi.has_path() else None
        # Check class type since SAFI may not reflect actual capabilities
        labels = nlri.labels if isinstance(nlri, Label) else None
        rd = nlri.rd if isinstance(nlri, IPVPN) else None

        last.nlri = NLRI.EMPTY  # Clear reference after extracting data

        # generate the new routes
        for _ in range(number):
            # update ip to the next route, this recalculate the "ip" field of the Inet class
            new_cidr = CIDR.make_cidr(pack_int(afi, ip), cut)

            # Build kwargs for from_cidr - NLRI are immutable, must pass all values upfront
            kwargs: dict = {}
            if path_info is not None:
                kwargs['path_info'] = path_info
            if labels is not None:
                kwargs['labels'] = labels
            if rd is not None:
                kwargs['rd'] = rd

            new_nlri: Any = klass.from_cidr(new_cidr, afi, safi, Action.ANNOUNCE, **kwargs)
            # next ip
            ip += increment
            yield Route(new_nlri, last.attributes, nexthop=nexthop)

    def _split(self) -> None:
        for route in self.scope.pop_routes():
            for splat in self.split(route):
                self.scope.append_route(splat)
