"""neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from collections import Counter, deque
from copy import deepcopy
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability import AddPath
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.operational import Operational
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.bgp.neighbor.session import Session
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib import RIB

if TYPE_CHECKING:
    from exabgp.bgp.neighbor.settings import NeighborSettings
    from exabgp.rib.route import Route


# The definition of a neighbor (from reading the configuration)
class Neighbor:
    _GLOBAL: ClassVar[dict[str, int]] = {'uid': 1}

    # Singleton empty neighbor (initialized after class definition)
    EMPTY: ClassVar['Neighbor']

    # Session (connection-related) configuration
    session: Session

    # BGP policy configuration (non-session)
    description: str
    hold_time: HoldTime
    rate_limit: int
    host_name: str
    domain_name: str
    group_updates: bool
    auto_flush: bool
    adj_rib_in: bool
    adj_rib_out: bool
    manual_eor: bool

    # Other instance attributes
    api: dict[str, Any]
    capability: NeighborCapability
    range_size: int
    generated: bool
    _families: list[tuple[AFI, SAFI]]
    _nexthop: list[tuple[AFI, SAFI, AFI]]
    _addpath: list[tuple[AFI, SAFI]]
    rib: RIB
    routes: list['Route']
    previous: 'Neighbor' | None
    eor: deque[tuple[AFI, SAFI]]
    asm: dict[tuple[AFI, SAFI], Operational]
    messages: deque[Operational]
    refresh: deque[RouteRefresh]
    counter: Counter[str]
    uid: str

    def __init__(self) -> None:
        # Session (connection-related) configuration
        self.session = Session()

        # BGP policy configuration
        self.description = ''
        self.hold_time = HoldTime(180)
        self.rate_limit = 0
        self.host_name = ''
        self.domain_name = ''
        self.group_updates = True
        self.auto_flush = True
        self.adj_rib_in = True
        self.adj_rib_out = True
        self.manual_eor = False

        # API configuration
        self.api: dict[str, Any] = {}

        # Capability configuration (typed dataclass)
        self.capability = NeighborCapability()

        self.range_size = 1

        # True for neighbors dynamically created from a range (won't restart on disconnect)
        self.ephemeral = False

        self._families = []
        self._nexthop = []
        self._addpath = []
        # Create disabled RIB with placeholder name - will be enabled by make_rib()
        self.rib = RIB(
            name=f'disabled-{self._GLOBAL["uid"]}',
            adj_rib_in=True,
            adj_rib_out=True,
            families=set(),
            enabled=False,
        )

        # The routes we have parsed from the configuration
        self.routes = []
        self.previous = None

        self.eor = deque()
        self.asm = dict()

        self.messages = deque()
        self.refresh = deque()

        self.counter = Counter()
        # It is possible to :
        # - have multiple exabgp toward one peer on the same host ( use of pid )
        # - have more than once connection toward a peer
        # - each connection has it own neihgbor (hence why identificator is not in Protocol)
        self.uid = f'{self._GLOBAL["uid"]}'
        self._GLOBAL['uid'] += 1

    @classmethod
    def _create_empty(cls) -> 'Neighbor':
        """Create the empty neighbor singleton. Called once at module load.

        Used for:
        - Decoding messages (transcoder)
        - Early connection rejection (incoming.py)

        Does NOT support ip_self() - will fail if called.
        """
        return cls()

    @classmethod
    def from_settings(cls, settings: 'NeighborSettings') -> 'Neighbor':
        """Create Neighbor from validated settings.

        This factory method enables programmatic Neighbor creation without
        parsing config files. Useful for testing and API-driven creation.

        Args:
            settings: NeighborSettings with required fields populated.

        Returns:
            Configured Neighbor instance with RIB enabled.

        Raises:
            ValueError: If settings validation fails.
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        neighbor = cls()

        # Create Session from settings (this calls session.infer())
        neighbor.session = Session.from_settings(settings.session)

        # Set BGP policy attributes
        neighbor.description = settings.description
        neighbor.hold_time = HoldTime(settings.hold_time)
        neighbor.rate_limit = settings.rate_limit
        neighbor.host_name = settings.host_name
        neighbor.domain_name = settings.domain_name
        neighbor.group_updates = settings.group_updates
        neighbor.auto_flush = settings.auto_flush
        neighbor.adj_rib_in = settings.adj_rib_in
        neighbor.adj_rib_out = settings.adj_rib_out
        neighbor.manual_eor = settings.manual_eor

        # Set capability (copy to avoid sharing mutable object)
        neighbor.capability = settings.capability.copy()

        # Add families
        for family in settings.families:
            neighbor.add_family(family)
        for afi, safi, nhafi in settings.nexthops:
            neighbor.add_nexthop(afi, safi, nhafi)
        for family in settings.addpaths:
            neighbor.add_addpath(family)

        # Set routes
        neighbor.routes = list(settings.routes)

        # Set API
        neighbor.api = dict(settings.api)

        # Call infer for graceful_restart time derivation
        neighbor.infer()

        # Initialize RIB with families
        neighbor.make_rib()

        return neighbor

    def infer(self) -> None:
        # Delegate session-related inference to Session
        self.session.infer()

        # If graceful-restart is enabled but time is 0, use hold-time
        if self.capability.graceful_restart.is_enabled() and self.capability.graceful_restart.time == 0:
            self.capability.graceful_restart = GracefulRestartConfig.with_time(int(self.hold_time))

    def id(self) -> str:
        return f'neighbor-{self.uid}'

    # This set must be unique between peer, not full draft-ietf-idr-bgp-multisession-07
    def index(self) -> bytes:
        if self.session.listen != 0:
            return f'peer-ip {self.session.peer_address} listen {self.session.listen}'.encode()
        return self.name().encode()

    def make_rib(self) -> None:
        self.rib.enable(self.name(), self.adj_rib_in, self.adj_rib_out, set(self._families))

    # will resend all the routes once we reconnect
    def reset_rib(self) -> None:
        self.rib.reset()
        self.messages = deque()
        self.refresh = deque()

    # back to square one, all the routes are removed
    def clear_rib(self) -> None:
        self.rib.clear()
        self.messages = deque()
        self.refresh = deque()

    def name(self) -> str:
        if self.capability.multi_session.is_enabled():
            session = '/'.join(f'{afi.name()}-{safi.name()}' for (afi, safi) in self.families())
        else:
            session = 'in-open'
        local_addr = 'auto' if self.session.auto_discovery else self.session.local_address
        local_as = self.session.local_as if self.session.local_as else 'auto'
        peer_as = self.session.peer_as if self.session.peer_as else 'auto'
        return f'neighbor {self.session.peer_address} local-ip {local_addr} local-as {local_as} peer-as {peer_as} router-id {self.session.router_id} family-allowed {session}'

    def families(self) -> list[tuple[AFI, SAFI]]:
        # this list() is important .. as we use the function to modify self._families
        return list(self._families)

    def nexthops(self) -> list[tuple[AFI, SAFI, AFI]]:
        # this list() is important .. as we use the function to modify self._nexthop
        return list(self._nexthop)

    def addpaths(self) -> list[tuple[AFI, SAFI]]:
        # this list() is important .. as we use the function to modify self._add_path
        return list(self._addpath)

    def add_family(self, family: tuple[AFI, SAFI]) -> None:
        # the families MUST be sorted for neighbor indexing name to be predictable for API users
        # this list() is important .. as we use the function to modify self._families
        if family not in self.families():
            afi, safi = family
            d: dict[AFI, list[SAFI]] = dict()
            d[afi] = [
                safi,
            ]
            for afi, safi in self._families:
                d.setdefault(afi, []).append(safi)
            self._families = [(afi, safi) for afi in sorted(d) for safi in sorted(d[afi])]

    def add_nexthop(self, afi: AFI, safi: SAFI, nhafi: AFI) -> None:
        if (afi, safi, nhafi) not in self._nexthop:
            self._nexthop.append((afi, safi, nhafi))

    def add_addpath(self, family: tuple[AFI, SAFI]) -> None:
        # the families MUST be sorted for neighbor indexing name to be predictable for API users
        # this list() is important .. as we use the function to modify self._add_path
        if family not in self.addpaths():
            afi, safi = family
            d: dict[AFI, list[SAFI]] = dict()
            d[afi] = [
                safi,
            ]
            for afi, safi in self._addpath:
                d.setdefault(afi, []).append(safi)
            self._addpath = [(afi, safi) for afi in sorted(d) for safi in sorted(d[afi])]

    def remove_family(self, family: tuple[AFI, SAFI]) -> None:
        if family in self.families():
            self._families.remove(family)

    def remove_nexthop(self, afi: AFI, safi: SAFI, nhafi: AFI) -> None:
        if (afi, safi, nhafi) in self.nexthops():
            self._nexthop.remove((afi, safi, nhafi))

    def remove_addpath(self, family: tuple[AFI, SAFI]) -> None:
        if family in self.addpaths():
            self._addpath.remove(family)

    def missing(self) -> str:
        return self.session.missing()

    # This function only compares the neighbor BUT NOT ITS ROUTES
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Neighbor):
            return False
        # Comparing local_address is skipped in the case where either
        # peer is configured to auto discover its local address. In
        # this case it can happen that one local_address is None and
        # the other one will be set to the auto disocvered IP address.
        auto_discovery = self.session.auto_discovery or other.session.auto_discovery
        return (
            self.session.router_id == other.session.router_id
            and self.session.local_as == other.session.local_as
            and self.session.peer_address == other.session.peer_address
            and self.session.peer_as == other.session.peer_as
            and self.session.passive == other.session.passive
            and self.session.listen == other.session.listen
            and self.session.connect == other.session.connect
            and self.hold_time == other.hold_time
            and self.rate_limit == other.rate_limit
            and self.host_name == other.host_name
            and self.domain_name == other.domain_name
            and self.session.md5_password == other.session.md5_password
            and self.session.md5_ip == other.session.md5_ip
            and self.session.incoming_ttl == other.session.incoming_ttl
            and self.session.outgoing_ttl == other.session.outgoing_ttl
            and self.group_updates == other.group_updates
            and self.auto_flush == other.auto_flush
            and self.adj_rib_in == other.adj_rib_in
            and self.adj_rib_out == other.adj_rib_out
            and (auto_discovery or self.session.local_address == other.session.local_address)
            and self.capability == other.capability
            and self.session.auto_discovery == other.session.auto_discovery
            and self.families() == other.families()
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def ip_self(self, afi: AFI) -> IP:
        return self.session.ip_self(afi)

    def resolve_self(self, route: 'Route') -> 'Route':
        nexthop = route.nexthop  # Use route.nexthop, not nlri.nexthop

        # Skip if not a SELF type
        if not nexthop.SELF:
            return route

        # Skip if already resolved
        if nexthop.resolved:
            return route

        route_copy = deepcopy(route)
        # Get nexthop from route_copy._nexthop (deepcopied from route._nexthop)
        nexthop_copy = route_copy._nexthop

        neighbor_self = self.ip_self(route_copy.nlri.afi)

        # Mutate in-place instead of replacing
        nexthop_copy.resolve(neighbor_self)

        if Attribute.CODE.NEXT_HOP in route_copy.attributes:
            nh_attr = route_copy.attributes[Attribute.CODE.NEXT_HOP]
            # NextHopSelf has SELF, resolved, and resolve() attributes
            from exabgp.bgp.message.update.attribute.nexthop import NextHopSelf

            if isinstance(nh_attr, NextHopSelf) and nh_attr.SELF and not nh_attr.resolved:
                nh_attr.resolve(neighbor_self)

        return route_copy

    def __str__(self) -> str:
        return NeighborTemplate.configuration(self, False)


def _en(value: bool | None) -> str:
    if value is None:
        return 'n/a'
    return 'enabled' if value else 'disabled'


def _pr(value: Any) -> str:
    if value is None:
        return 'n/a'
    return str(value)


def _addpath(send: bool, receive: bool) -> str:
    if send and receive:
        return 'send/receive'
    if send:
        return 'send'
    if receive:
        return 'receive'
    return 'disabled'


class NeighborTemplate:
    extensive_kv: ClassVar[str] = '   %-20s %15s %15s %15s'
    extensive_template: ClassVar[str] = """\
Neighbor {peer-address}

    Session                        Local
{local-address}
{state}
{duration}

    Setup                          Local          Remote
{as}
{id}
{hold}

    Capability                     Local          Remote
{capabilities}

    Families                        Local         Remote        Add-Path
{families}

    Message Statistic               Sent        Received
{messages}
""".replace('\t', '  ')

    summary_header: ClassVar[str] = 'Peer            AS        up/down state       |     #sent     #recvd'
    summary_template: ClassVar[str] = '%-15s %-7s %9s %-12s %10d %10d'

    @classmethod
    def configuration(cls, neighbor: Neighbor, with_routes: bool = True) -> str:
        routes_str = ''
        if with_routes:
            routes_str += '\nstatic { '
            for route in neighbor.rib.outgoing.queued_routes():
                routes_str += f'\n\t\t{route.extensive()}'
            routes_str += '\n}'

        families = ''
        for afi, safi in neighbor.families():
            families += f'\n\t\t{afi.name()} {safi.name()};'

        nexthops = ''
        for afi, safi, nexthop in neighbor.nexthops():
            nexthops += f'\n\t\t{afi.name()} {safi.name()} {nexthop.name()};'

        addpaths = ''
        for afi, safi in neighbor.addpaths():
            addpaths += f'\n\t\t{afi.name()} {safi.name()};'

        codes = Message.CODE

        _extension_global = {
            'neighbor-changes': 'neighbor-changes',
            'negotiated': 'negotiated',
            'fsm': 'fsm',
            'signal': 'signal',
        }

        _extension_receive = {
            'receive-packets': 'packets',
            'receive-parsed': 'parsed',
            'receive-consolidate': 'consolidate',
            f'receive-{codes.NOTIFICATION.SHORT}': 'notification',
            f'receive-{codes.OPEN.SHORT}': 'open',
            f'receive-{codes.KEEPALIVE.SHORT}': 'keepalive',
            f'receive-{codes.UPDATE.SHORT}': 'update',
            f'receive-{codes.ROUTE_REFRESH.SHORT}': 'refresh',
            f'receive-{codes.OPERATIONAL.SHORT}': 'operational',
        }

        _extension_send = {
            'send-packets': 'packets',
            'send-parsed': 'parsed',
            'send-consolidate': 'consolidate',
            f'send-{codes.NOTIFICATION.SHORT}': 'notification',
            f'send-{codes.OPEN.SHORT}': 'open',
            f'send-{codes.KEEPALIVE.SHORT}': 'keepalive',
            f'send-{codes.UPDATE.SHORT}': 'update',
            f'send-{codes.ROUTE_REFRESH.SHORT}': 'refresh',
            f'send-{codes.OPERATIONAL.SHORT}': 'operational',
        }

        apis = ''

        for process in neighbor.api.get('processes', []) if neighbor.api else []:
            _global = []
            _receive = []
            _send = []

            for api, name in _extension_global.items():
                _global.extend(
                    [
                        f'\t\t{name};\n',
                    ]
                    if neighbor.api and process in neighbor.api[api]
                    else [],
                )

            for api, name in _extension_receive.items():
                _receive.extend(
                    [
                        f'\t\t\t{name};\n',
                    ]
                    if neighbor.api and process in neighbor.api[api]
                    else [],
                )

            for api, name in _extension_send.items():
                _send.extend(
                    [
                        f'\t\t\t{name};\n',
                    ]
                    if neighbor.api and process in neighbor.api[api]
                    else [],
                )

            _api = '\tapi {\n'
            _api += f'\t\tprocesses [ {process} ];\n'
            _api += ''.join(_global)
            if _receive:
                _api += '\t\treceive {\n'
                _api += ''.join(_receive)
                _api += '\t\t}\n'
            if _send:
                _api += '\t\tsend {\n'
                _api += ''.join(_send)
                _api += '\t\t}\n'
            _api += '\t}\n'

            apis += _api

        md5_base64_str = (
            'true'
            if neighbor.session.md5_base64 is True
            else 'false'
            if neighbor.session.md5_base64 is False
            else 'auto'
        )
        cap = neighbor.capability
        add_path_str = AddPath.string[cap.add_path] if cap.add_path else 'disable'
        graceful_str = str(cap.graceful_restart.time) if cap.graceful_restart.is_enabled() else 'disable'

        returned = (
            f'neighbor {neighbor.session.peer_address} {{\n'
            f'\tdescription "{neighbor.description}";\n'
            f'\trouter-id {neighbor.session.router_id};\n'
            f'\thost-name {neighbor.host_name};\n'
            f'\tdomain-name {neighbor.domain_name};\n'
            f'\tlocal-address {neighbor.session.local_address if not neighbor.session.auto_discovery else "auto"};\n'
            f'\tsource-interface {neighbor.session.source_interface};\n'
            f'\tlocal-as {neighbor.session.local_as};\n'
            f'\tpeer-as {neighbor.session.peer_as};\n'
            f'\thold-time {neighbor.hold_time};\n'
            f'\trate-limit {"disable" if neighbor.rate_limit == 0 else neighbor.rate_limit};\n'
            f'\tmanual-eor {"true" if neighbor.manual_eor else "false"};\n'
            f'\n\tpassive {"true" if neighbor.session.passive else "false"};\n'
            + (f'\n\tlisten {neighbor.session.listen};\n' if neighbor.session.listen else '')
            + (f'\n\tconnect {neighbor.session.connect};\n' if neighbor.session.connect else '')
            + f'\tgroup-updates {"true" if neighbor.group_updates else "false"};\n'
            f'\tauto-flush {"true" if neighbor.auto_flush else "false"};\n'
            f'\tadj-rib-in {"true" if neighbor.adj_rib_in else "false"};\n'
            f'\tadj-rib-out {"true" if neighbor.adj_rib_out else "false"};\n'
            + (f'\tmd5-password "{neighbor.session.md5_password}";\n' if neighbor.session.md5_password else '')
            + f'\tmd5-base64 {md5_base64_str};\n'
            + (f'\tmd5-ip "{neighbor.session.md5_ip}";\n' if not neighbor.session.auto_discovery else '')
            + (f'\toutgoing-ttl {neighbor.session.outgoing_ttl};\n' if neighbor.session.outgoing_ttl else '')
            + (f'\tincoming-ttl {neighbor.session.incoming_ttl};\n' if neighbor.session.incoming_ttl else '')
            + f'\tcapability {{\n'
            f'\t\tasn4 {"enable" if cap.asn4.is_enabled() else "disable"};\n'
            f'\t\troute-refresh {"enable" if cap.route_refresh else "disable"};\n'
            f'\t\tgraceful-restart {graceful_str};\n'
            f'\t\tsoftware-version {"enable" if cap.software_version else "disable"};\n'
            f'\t\tnexthop {"enable" if cap.nexthop.is_enabled() else "disable"};\n'
            f'\t\tadd-path {add_path_str};\n'
            f'\t\tmulti-session {"enable" if cap.multi_session.is_enabled() else "disable"};\n'
            f'\t\toperational {"enable" if cap.operational.is_enabled() else "disable"};\n'
            f'\t\taigp {"enable" if cap.aigp.is_enabled() else "disable"};\n'
            f'\t}}\n'
            f'\tfamily {{{families}\n'
            f'\t}}\n'
            f'\tnexthop {{{nexthops}\n'
            f'\t}}\n'
            f'\tadd-path {{{addpaths}\n'
            f'\t}}\n'
            f'{apis}{routes_str}'
            f'}}'
        )

        # '\t\treceive {\n%s\t\t}\n' % receive if receive else '',
        # '\t\tsend {\n%s\t\t}\n' % send if send else '',
        return returned.replace('\t', '  ')

    @classmethod
    def as_dict(cls, answer: dict[str, Any]) -> dict[str, Any]:
        up = answer['duration']

        formated: dict[str, Any] = {
            'state': 'up' if up else 'down',
            'duration': answer['duration'] if up else answer['down'],
            'fsm': answer['state'],
            'local': {
                'capabilities': {},
                'families': {},
                'add-path': {},
            },
            'peer': {
                'capabilities': {},
                'families': {},
                'add-path': {},
            },
            'messages': {'sent': {}, 'received': {}},
            'capabilities': [],
            'families': [],
            'add-path': {},
        }

        for (a, s), (lf, pf, aps, apr) in answer['families'].items():
            k = f'{a} {s}'
            formated['local']['families'][k] = lf
            formated['peer']['families'][k] = pf
            formated['local']['add-path'][k] = aps
            formated['peer']['add-path'][k] = apr
            if lf and pf:
                formated['families'].append(k)
            formated['add-path'][k] = _addpath(aps, apr)

        for k, (lc, pc) in answer['capabilities'].items():
            formated['local']['capabilities'][k] = lc
            formated['peer']['capabilities'][k] = pc
            if lc and pc:
                formated['capabilities'].append(k)

        for k, (ms, mr) in answer['messages'].items():
            formated['messages']['sent'][k] = ms
            formated['messages']['received'][k] = mr

        formated['local']['address'] = answer['local-address']
        formated['local']['as'] = answer['local-as']
        formated['local']['id'] = answer['local-id']
        formated['local']['hold'] = answer['local-hold']

        formated['peer']['address'] = answer['peer-address']
        formated['peer']['as'] = answer['peer-as']
        formated['peer']['id'] = answer['peer-id']
        formated['peer']['hold'] = answer['peer-hold']

        return formated

    @classmethod
    def formated_dict(cls, answer: dict[str, Any]) -> dict[str, Any]:
        if answer['duration']:
            duration_value = timedelta(seconds=answer['duration'])
            duration = f'    {"up for":<20} {str(duration_value):>15} {"":<15} {"":<15}'
        else:
            down_value = timedelta(seconds=answer['down'])
            duration = f'    {"down for":<20} {str(down_value):>15} {"":<15} {"":<15}'

        formated: dict[str, Any] = {
            'peer-address': answer['peer-address'],
            'local-address': f'    {"local":<20} {answer["local-address"]:>15} {"":<15} {"":<15}',
            'state': f'    {"state":<20} {answer["state"]:>15} {"":<15} {"":<15}',
            'duration': duration,
            'as': f'    {"AS":<20} {answer["local-as"]:>15} {_pr(answer["peer-as"]):>15} {"":<15}',
            'id': f'    {"ID":<20} {answer["local-id"]:>15} {_pr(answer["peer-id"]):>15} {"":<15}',
            'hold': f'    {"hold-time":<20} {answer["local-hold"]:>15} {_pr(answer["peer-hold"]):>15} {"":<15}',
            'capabilities': '\n'.join(
                f'    {f"{k}:":<20} {_en(lc):>15} {_en(pc):>15} {"":<15}'
                for k, (lc, pc) in answer['capabilities'].items()
            ),
            'families': '\n'.join(
                f'    {f"{a} {s}:":<20} {_en(lf):>15} {_en(rf):>15} {_addpath(aps, apr):>15}'
                for (a, s), (lf, rf, apr, aps) in answer['families'].items()
            ),
            'messages': '\n'.join(
                f'    {f"{k}:":<20} {ms!s:>15} {mr!s:>15} {"":<15}' for k, (ms, mr) in answer['messages'].items()
            ),
        }

        return formated

    @classmethod
    def to_json(cls, answer: dict[str, Any]) -> str:
        return json.dumps(cls.formated_dict(answer))

    @classmethod
    def extensive(cls, answer: dict[str, Any]) -> str:
        return cls.extensive_template.format(**cls.formated_dict(answer))

    @classmethod
    def summary(cls, answer: dict[str, Any]) -> str:
        peer_addr = str(answer['peer-address'])
        peer_as_str = _pr(answer['peer-as'])
        # Convert timedelta to string before formatting to support Python 3.12+
        if answer['duration']:
            duration_str = str(timedelta(seconds=answer['duration']))
        else:
            duration_str = 'down'
        state_str = answer['state'].lower()
        update_in = answer['messages']['update'][0]
        update_out = answer['messages']['update'][1]
        return f'{peer_addr:<15} {peer_as_str:<7} {duration_str:>9} {state_str:<12} {update_in:>10} {update_out:>10}'


# Initialize the empty neighbor singleton
Neighbor.EMPTY = Neighbor._create_empty()
