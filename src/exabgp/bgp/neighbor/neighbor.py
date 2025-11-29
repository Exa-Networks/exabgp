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
from exabgp.bgp.message.update.attribute import Attribute, NextHop
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB

if TYPE_CHECKING:
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.open.routerid import RouterID
    from exabgp.protocol.ip import IP
    from exabgp.rib.change import Change


# The definition of a neighbor (from reading the configuration)
class Neighbor:
    _GLOBAL: ClassVar[dict[str, int]] = {'uid': 1}

    # Singleton empty neighbor (initialized after class definition)
    EMPTY: ClassVar['Neighbor']

    # Configuration attributes (previously in defaults dict)
    description: str
    router_id: 'RouterID' | None
    local_address: 'IP' | None
    source_interface: str | None
    peer_address: 'IP' | None
    local_as: 'ASN' | None
    peer_as: 'ASN' | None
    passive: bool
    listen: int
    connect: int
    hold_time: HoldTime
    rate_limit: int
    host_name: str | None
    domain_name: str | None
    group_updates: bool
    auto_flush: bool
    adj_rib_in: bool
    adj_rib_out: bool
    manual_eor: bool
    md5_password: str | None
    md5_base64: bool
    md5_ip: 'IP' | None
    outgoing_ttl: int | None
    incoming_ttl: int | None

    # Other instance attributes
    api: dict[str, Any, None]
    capability: NeighborCapability
    auto_discovery: bool
    range_size: int
    generated: bool
    _families: list[tuple[AFI, SAFI]]
    _nexthop: list[tuple[AFI, SAFI, AFI]]
    _addpath: list[tuple[AFI, SAFI]]
    rib: RIB | None
    changes: list['Change']
    previous: 'Neighbor' | None
    eor: deque[tuple[AFI, SAFI]]
    asm: dict[tuple[AFI, SAFI], Message]
    messages: deque[Message]
    refresh: deque[tuple[AFI, SAFI]]
    counter: Counter[str]
    uid: str

    def __init__(self) -> None:
        # Configuration attributes with defaults
        self.description = ''
        self.router_id = None
        self.local_address = None
        self.source_interface = None
        self.peer_address = None
        self.local_as = None
        self.peer_as = None
        self.passive = False
        self.listen = 0
        self.connect = 0
        self.hold_time = HoldTime(180)
        self.rate_limit = 0
        self.host_name = None
        self.domain_name = None
        self.group_updates = True
        self.auto_flush = True
        self.adj_rib_in = True
        self.adj_rib_out = True
        self.manual_eor = False
        self.md5_password = None
        self.md5_base64 = False
        self.md5_ip = None
        self.outgoing_ttl = None
        self.incoming_ttl = None

        # API configuration
        self.api = None

        # Capability configuration (typed dataclass)
        self.capability = NeighborCapability()

        # local_address uses auto discovery
        self.auto_discovery = False

        self.range_size = 1

        # was this Neighbor generated from a range
        self.generated = False

        self._families = []
        self._nexthop = []
        self._addpath = []
        self.rib = None

        # The routes we have parsed from the configuration
        self.changes = []
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

    def infer(self) -> None:
        if self.md5_ip is None:
            self.md5_ip = self.local_address

        # If graceful-restart is enabled but time is 0, use hold-time
        if self.capability.graceful_restart.is_enabled() and self.capability.graceful_restart.time == 0:
            self.capability.graceful_restart = GracefulRestartConfig.with_time(int(self.hold_time))

    def id(self) -> str:
        return f'neighbor-{self.uid}'

    # This set must be unique between peer, not full draft-ietf-idr-bgp-multisession-07
    def index(self) -> str:
        if self.listen != 0:
            return f'peer-ip {self.peer_address} listen {self.listen}'
        return self.name()

    def make_rib(self) -> None:
        self.rib = RIB(self.name(), self.adj_rib_in, self.adj_rib_out, self._families)

    # will resend all the routes once we reconnect
    def reset_rib(self) -> None:
        assert self.rib is not None, 'RIB not initialized - call make_rib() first'
        self.rib.reset()
        self.messages = deque()
        self.refresh = deque()

    # back to square one, all the routes are removed
    def clear_rib(self) -> None:
        assert self.rib is not None, 'RIB not initialized - call make_rib() first'
        self.rib.clear()
        self.messages = deque()
        self.refresh = deque()

    def name(self) -> str:
        if self.capability.multi_session.is_enabled():
            session = '/'.join(f'{afi.name()}-{safi.name()}' for (afi, safi) in self.families())
        else:
            session = 'in-open'
        local_addr = self.local_address if self.peer_address is not None else 'auto'
        local_as = self.local_as if self.local_as is not None else 'auto'
        peer_as = self.peer_as if self.peer_as is not None else 'auto'
        return f'neighbor {self.peer_address} local-ip {local_addr} local-as {local_as} peer-as {peer_as} router-id {self.router_id} family-allowed {session}'

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
        if self.local_address is None and not self.auto_discovery:
            return 'local-address'
        if self.listen > 0 and self.auto_discovery:
            return 'local-address'
        if self.peer_address is None:
            return 'peer-address'
        if self.auto_discovery and not self.router_id:
            return 'router-id'
        if self.peer_address.afi == AFI.ipv6 and not self.router_id:
            return 'router-id'
        return ''

    # This function only compares the neighbor BUT NOT ITS ROUTES
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Neighbor):
            return False
        # Comparing local_address is skipped in the case where either
        # peer is configured to auto discover its local address. In
        # this case it can happen that one local_address is None and
        # the other one will be set to the auto disocvered IP address.
        auto_discovery = self.auto_discovery or other.auto_discovery
        return (
            self.router_id == other.router_id
            and self.local_as == other.local_as
            and self.peer_address == other.peer_address
            and self.peer_as == other.peer_as
            and self.passive == other.passive
            and self.listen == other.listen
            and self.connect == other.connect
            and self.hold_time == other.hold_time
            and self.rate_limit == other.rate_limit
            and self.host_name == other.host_name
            and self.domain_name == other.domain_name
            and self.md5_password == other.md5_password
            and self.md5_ip == other.md5_ip
            and self.incoming_ttl == other.incoming_ttl
            and self.outgoing_ttl == other.outgoing_ttl
            and self.group_updates == other.group_updates
            and self.auto_flush == other.auto_flush
            and self.adj_rib_in == other.adj_rib_in
            and self.adj_rib_out == other.adj_rib_out
            and (auto_discovery or self.local_address == other.local_address)
            and self.capability == other.capability
            and self.auto_discovery == other.auto_discovery
            and self.families() == other.families()
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def ip_self(self, afi: AFI) -> 'IP':
        if self.local_address is not None and afi == self.local_address.afi:
            return self.local_address

        # attempting to not barf for next-hop self when the peer is IPv6
        if afi == AFI.ipv4 and self.router_id is not None:
            return self.router_id

        local_afi = self.local_address.afi if self.local_address else 'unknown'
        raise TypeError(
            f'use of "next-hop self": the route ({afi}) does not have the same family as the BGP tcp session ({local_afi})',
        )

    def remove_self(self, changes: Change) -> Change:
        change = deepcopy(changes)
        if not change.nlri.nexthop.SELF:
            return change
        neighbor_self = self.ip_self(change.nlri.afi)
        change.nlri.nexthop = neighbor_self
        if Attribute.CODE.NEXT_HOP in change.attributes:
            change.attributes[Attribute.CODE.NEXT_HOP] = NextHop(str(neighbor_self), neighbor_self.pack_ip())
        return change

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
    def configuration(cls, neighbor: Neighbor, with_changes: bool = True) -> str:
        changes = ''
        if with_changes:
            assert neighbor.rib is not None, 'RIB not initialized'
            changes += '\nstatic { '
            for change in neighbor.rib.outgoing.queued_changes():
                changes += f'\n\t\t{change.extensive()}'
            changes += '\n}'

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

        md5_base64_str = 'true' if neighbor.md5_base64 is True else 'false' if neighbor.md5_base64 is False else 'auto'
        cap = neighbor.capability
        add_path_str = AddPath.string[cap.add_path] if cap.add_path else 'disable'
        graceful_str = str(cap.graceful_restart.time) if cap.graceful_restart.is_enabled() else 'disable'

        returned = (
            f'neighbor {neighbor.peer_address} {{\n'
            f'\tdescription "{neighbor.description}";\n'
            f'\trouter-id {neighbor.router_id};\n'
            f'\thost-name {neighbor.host_name};\n'
            f'\tdomain-name {neighbor.domain_name};\n'
            f'\tlocal-address {neighbor.local_address if not neighbor.auto_discovery else "auto"};\n'
            f'\tsource-interface {neighbor.source_interface};\n'
            f'\tlocal-as {neighbor.local_as};\n'
            f'\tpeer-as {neighbor.peer_as};\n'
            f'\thold-time {neighbor.hold_time};\n'
            f'\trate-limit {"disable" if neighbor.rate_limit == 0 else neighbor.rate_limit};\n'
            f'\tmanual-eor {"true" if neighbor.manual_eor else "false"};\n'
            f'\n\tpassive {"true" if neighbor.passive else "false"};\n'
            + (f'\n\tlisten {neighbor.listen};\n' if neighbor.listen else '')
            + (f'\n\tconnect {neighbor.connect};\n' if neighbor.connect else '')
            + f'\tgroup-updates {"true" if neighbor.group_updates else "false"};\n'
            f'\tauto-flush {"true" if neighbor.auto_flush else "false"};\n'
            f'\tadj-rib-in {"true" if neighbor.adj_rib_in else "false"};\n'
            f'\tadj-rib-out {"true" if neighbor.adj_rib_out else "false"};\n'
            + (f'\tmd5-password "{neighbor.md5_password}";\n' if neighbor.md5_password else '')
            + f'\tmd5-base64 {md5_base64_str};\n'
            + (f'\tmd5-ip "{neighbor.md5_ip}";\n' if not neighbor.auto_discovery else '')
            + (f'\toutgoing-ttl {neighbor.outgoing_ttl};\n' if neighbor.outgoing_ttl else '')
            + (f'\tincoming-ttl {neighbor.incoming_ttl};\n' if neighbor.incoming_ttl else '')
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
            f'{apis}{changes}'
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
