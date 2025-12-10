"""check.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# common

from __future__ import annotations

import sys
import copy
import struct
from typing import Callable, TYPE_CHECKING

from exabgp.environment import getenv

from exabgp.bgp.message import Update, UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction

from exabgp.logger import log, lazymsg
from exabgp.logger import option

# check_neighbor

from exabgp.util.od import od
from exabgp.rib.route import Route

# check_update

from exabgp.reactor.api.response import Response

# check_notification

from exabgp.bgp.message import Notification

# JSON version

from exabgp.version import json as json_version
from exabgp.version import json_v4 as json_v4_version

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

# Type alias for log message lambdas
LogMsg = Callable[[], str]

# BGP message type constants (RFC 4271)
BGP_MSG_OPEN = 1  # BGP OPEN message type
BGP_MSG_UPDATE = 2  # BGP UPDATE message type
BGP_MSG_NOTIFICATION = 3  # BGP NOTIFICATION message type


def _hexa(data: str) -> bytes:
    full = data.replace(':', '')
    hexa = [full[i * 2 : (i * 2) + 2] for i in range(len(full) // 2)]
    return bytes([int(_, 16) for _ in hexa])


def _negotiated(neighbor: Neighbor) -> tuple[Negotiated, Negotiated]:
    capa = Capabilities().new(neighbor, False)
    # Override ADD_PATH with neighbor's configured addpath families
    if neighbor.capability.add_path:
        capa[Capability.CODE.ADD_PATH] = AddPath(neighbor.addpaths(), neighbor.capability.add_path)
    # Override MULTIPROTOCOL with neighbor's families
    mp = MultiProtocol()
    mp.extend(neighbor.families())
    capa[Capability.CODE.MULTIPROTOCOL] = mp
    # capa[Capability.CODE.FOUR_BYTES_ASN] = True

    routerid_1 = str(neighbor.session.router_id)
    routerid_2 = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor.session.router_id).split('.', -1))

    o1 = Open.make_open(Version(4), ASN(neighbor.session.local_as), HoldTime(180), RouterID(routerid_1), capa)
    o2 = Open.make_open(Version(4), ASN(neighbor.session.peer_as), HoldTime(180), RouterID(routerid_2), capa)
    negotiated_in = Negotiated.make_negotiated(neighbor, Direction.IN)
    negotiated_out = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated_in.sent(o1)
    negotiated_in.received(o2)
    negotiated_out.sent(o1)
    negotiated_out.received(o2)
    # grouped = False
    return negotiated_in, negotiated_out


# =============================================================== check_neighbor
# ...


def check_generation(neighbors: dict[str, Neighbor]) -> bool:
    option.enabled['parser'] = True

    for name in neighbors.keys():
        neighbor = copy.deepcopy(neighbors[name])
        neighbor.session.local_as = neighbor.session.peer_as
        negotiated_in, negotiated_out = _negotiated(neighbor)

        if not neighbor.rib.enabled:
            continue
        for _ in neighbor.rib.outgoing.updates(False):
            pass

        for route1 in neighbor.rib.outgoing.cached_routes():
            str1 = route1.extensive()
            packed = list(
                UpdateCollection([RoutedNLRI(route1.nlri, route1.nexthop)], [], route1.attributes).messages(
                    negotiated_out
                )
            )
            pack1 = packed[0]

            _packed = packed  # type: list[bytes]
            _pack1 = pack1  # type: bytes
            log.debug(lazymsg('parsed route requires {count} updates', count=len(_packed)), 'parser')
            log.debug(lazymsg('update size is {size}', size=len(_pack1)), 'parser')

            _str1 = str1  # type: str
            log.debug(lazymsg('parsed route {route}', route=_str1), 'parser')
            log.debug(lazymsg('parsed hex   {hex}', hex=od(_pack1)), 'parser')

            # This does not take the BGP header - let's assume we will not break that :)
            try:
                log.debug(lazymsg('check.update.processing'), 'parser')  # separator

                pack1s = pack1[19:] if pack1.startswith(b'\xff' * 16) else pack1
                update = UpdateCollection.unpack_message(pack1s, negotiated_in)

                # update.announces contains RoutedNLRI, update.nlris extracts bare NLRIs
                nlri = update.nlris[0]
                route2 = Route(nlri, update.attributes, nexthop=nlri.nexthop)
                str2 = route2.extensive()
                # Use the RoutedNLRI from announces (or create one for recoding)
                routed = update.announces[0] if update.announces else RoutedNLRI(update.nlris[0], route2.nexthop)
                pack2 = list(UpdateCollection([routed], [], update.attributes).messages(negotiated_out))[0]

                _str2 = str2  # type: str
                _pack2 = pack2  # type: bytes
                log.debug(lazymsg('recoded route {route}', route=_str2), 'parser')
                log.debug(lazymsg('recoded hex   {hex}', hex=od(_pack2)), 'parser')

                str1 = str1.replace('attribute [ 0x04 0x80 0x00000064 ]', 'med 100')
                str1r = (
                    str1.lower().replace(' med 100', '').replace(' local-preference 100', '').replace(' origin igp', '')
                )
                str2r = (
                    str2.lower().replace(' med 100', '').replace(' local-preference 100', '').replace(' origin igp', '')
                )
                str2r = str2r.replace(
                    'large-community [ 1:2:3 10:11:12 ]',
                    'attribute [ 0x20 0xc0 0x0000000100000002000000030000000a0000000b0000000c ]',
                )

                if 'next-hop self' in str1r:
                    if ':' in str1r:
                        str1r = str1r.replace('next-hop self', 'next-hop ::1')
                    else:
                        str1r = str1r.replace('next-hop self', 'next-hop {}'.format(neighbor.session.local_address))

                if ' name ' in str1r:
                    parts = str1r.split(' ')
                    pos = parts.index('name')
                    str1r = ' '.join(parts[:pos] + parts[pos + 2 :])

                skip = False

                if str1r != str2r:
                    if 'attribute [' in str1r and ' 0x00 ' in str1r:
                        # we do not decode non-transitive attributes
                        log.debug(lazymsg('check.skip reason=non_transitive_attributes'), 'parser')
                        skip = True
                    elif '=http' in str1r or '=ndl-aas' in str1r:
                        log.debug(lazymsg('check.skip reason=named_flow_attributes'), 'parser')
                        skip = True
                    else:
                        log.debug(lazymsg('check.strings.different'), 'parser')
                        _str1r = str1r  # type: str
                        _str2r = str2r  # type: str
                        log.debug(lazymsg('[{s}]', s=_str1r), 'parser')
                        log.debug(lazymsg('[{s}]', s=_str2r), 'parser')
                        return False
                else:
                    log.debug(lazymsg('check.strings.ok'), 'parser')

                if skip:
                    log.debug(lazymsg('check.encoding.skip reason=non_transitive_attributes'), 'parser')
                elif pack1 != pack2:
                    log.debug(lazymsg('check.encoding.different'), 'parser')
                    _pack1_cmp = pack1  # type: bytes
                    _pack2_cmp = pack2  # type: bytes
                    log.debug(lazymsg('[{hex}]', hex=od(_pack1_cmp)), 'parser')
                    log.debug(lazymsg('[{hex}]', hex=od(_pack2_cmp)), 'parser')
                    return False
                else:
                    log.debug(lazymsg('encoding.verified status=ok'), 'parser')

                _route1_json: Route = route1

                def _log_nlri(_route1_json: Route = _route1_json) -> str:
                    return 'JSON nlri {}'.format(_route1_json.nlri.json())

                def _log_attr(_route1_json: Route = _route1_json) -> str:
                    return 'JSON attr {}'.format(_route1_json.attributes.json())

                log.debug(_log_nlri, 'parser')
                log.debug(_log_attr, 'parser')

            except Notify as exc:
                log.debug(lazymsg('encoding.failed error={err}', err=str(exc)), 'parser')
                return False
        neighbor.rib.clear()

    return True


# ================================================================ check_message
#


def check_message(neighbor: Neighbor, message: str) -> bool:
    raw = _hexa(message)

    if not raw.startswith(b'\xff' * 16):
        return check_update(neighbor, raw)

    kind = raw[18]
    # Validate message size from header matches actual data length
    header_size = (raw[16] << 8) + raw[17]
    if header_size != len(raw):
        sys.stdout.write(f'warning: BGP header size ({header_size}) does not match data length ({len(raw)})\n')

    if kind == BGP_MSG_OPEN:
        return check_open(neighbor, raw[19:])
    if kind == BGP_MSG_UPDATE:
        return check_update(neighbor, raw)
    if kind == BGP_MSG_NOTIFICATION:
        return check_notification(raw)

    sys.stdout.write(f'unknown type {kind}\n')
    return False


def display_message(neighbor: Neighbor, message: str, generic: bool = False, command: bool = False) -> bool:
    raw = _hexa(message)

    if not raw.startswith(b'\xff' * 16):
        header = b'\xff' * 16
        header += struct.pack('!H', len(raw) + 19)
        header += struct.pack('!B', 2)
        # Note: calling display_update directly since we synthesized an UPDATE header
        return display_update(neighbor, header + raw, generic=generic, command=command)

    kind = raw[18]
    # Validate message size from header matches actual data length
    header_size = (raw[16] << 8) + raw[17]
    if header_size != len(raw):
        sys.stdout.write(f'warning: BGP header size ({header_size}) does not match data length ({len(raw)})\n')

    if kind == BGP_MSG_OPEN:
        return display_open(neighbor, raw[19:])
    if kind == BGP_MSG_UPDATE:
        return display_update(neighbor, raw, generic=generic, command=command)
    if kind == BGP_MSG_NOTIFICATION:
        return display_notification(neighbor, raw)
    sys.stdout.write(f'unknown type {kind}\n')
    return False


# =================================================================== check_nlri
#


def _make_nlri(neighbor: Neighbor, routes: str) -> list[NLRI]:
    option.enabled['parser'] = True

    announced = _hexa(routes)
    negotiated_in, negotiated_out = _negotiated(neighbor)

    afi, safi = neighbor.families()[0]

    # Is the peer going to send us some Path Information with the route (AddPath)
    addpath = negotiated_out.addpath.send(afi, safi)

    nlris: list[NLRI] = []
    try:
        while announced:
            _announced = announced  # type: bytes
            log.debug(lazymsg('parsing NLRI {announced}', announced=_announced), 'parser')
            nlri_parsed, announced = NLRI.unpack_nlri(afi, safi, announced, Action.ANNOUNCE, addpath, negotiated_in)
            if nlri_parsed is not NLRI.INVALID:
                nlris.append(nlri_parsed)
    except (Notify, ValueError, IndexError, KeyError, struct.error) as exc:
        log.error(lazymsg('nlri.parse.failed afi={a} safi={s}', a=afi, s=safi), 'parser')
        from exabgp.debug import string_exception

        _exc_nlri = exc  # type: BaseException
        log.error(lazymsg('nlri.parse.error error={msg}', msg=string_exception(_exc_nlri)), 'parser')
        if getenv().debug.pdb:
            raise
        return []

    return nlris


def check_nlri(neighbor: Neighbor, routes: str) -> bool:
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    log.debug(lazymsg('nlri.check.complete'), 'parser')  # separator
    for nlri in nlris:
        log.info(lazymsg('nlri.json json={json}', json=nlri.json()), 'parser')
    return True


def display_nlri(neighbor: Neighbor, routes: str) -> bool:
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    for nlri in nlris:
        sys.stdout.write(f'{nlri.json()}\n')
    return True


# =================================================================== check_open
#


def check_open(neighbor: Neighbor, raw: bytes) -> None:
    import sys
    import traceback

    sys.excepthook = traceback.print_exception

    try:
        negotiated_in, _ = _negotiated(neighbor)
        o = Open.unpack_message(raw, negotiated_in)
        sys.stdout.write(f'{o}\n')
    except (Notify, ValueError, IndexError, KeyError, struct.error):
        sys.stdout.write('\n')
        sys.stdout.write('we could not decode this open message\n')
        sys.stdout.write('here is the traceback to help to figure out why\n')
        sys.stdout.write('\n')
        raise


def display_open(neighbor: Neighbor, raw: bytes) -> bool:
    try:
        negotiated_in, _ = _negotiated(neighbor)
        o = Open.unpack_message(raw, negotiated_in)
        sys.stdout.write(Response.JSON(json_version).open(neighbor, 'in', o, b'', b'', Negotiated.UNSET))
        sys.stdout.write('\n')
        return True
    except (Notify, ValueError, IndexError, KeyError, struct.error):
        return False


# ================================================================= check_update
#


def _make_update(neighbor: Neighbor, raw: bytes) -> Update | None:
    option.enabled['parser'] = True
    negotiated_in, _ = _negotiated(neighbor)

    while raw:
        if raw.startswith(b'\xff' * 16):
            kind = raw[18]
            size = (raw[16] << 16) + raw[17]

            injected, raw = raw[19:size], raw[size:]

            if kind == BGP_MSG_UPDATE:
                log.debug(lazymsg('message.type type=update'), 'parser')
            else:
                _kind = kind  # type: int
                log.debug(lazymsg('message.type.abort type={kind} expected=update', kind=_kind), 'parser')
                return None
        else:
            log.debug(lazymsg('message.header.missing assuming=update'), 'parser')
            injected, raw = raw, b''

        try:
            # This does not take the BGP header - let's assume we will not break that :)
            update = UpdateCollection.unpack_message(injected, negotiated_in)
        except Notify:
            import traceback

            log.error(lazymsg('message.parse.failed'), 'parser')
            log.error(lazymsg('message.parse.traceback trace={t}', t=traceback.format_exc()), 'parser')
            if getenv().debug.pdb:
                raise
            return None
        except (ValueError, IndexError, KeyError, struct.error):
            import traceback

            log.error(lazymsg('message.parse.failed'), 'parser')
            log.error(lazymsg('message.parse.traceback trace={t}', t=traceback.format_exc()), 'parser')
            if getenv().debug.pdb:
                raise
            return None

        return update

    return None


def _make_notification(neighbor: Neighbor, raw: bytes) -> Notification | None:
    option.enabled['parser'] = True
    negotiated_in, negotiated_out = _negotiated(neighbor)

    if raw.startswith(b'\xff' * 16):
        kind = raw[18]
        size = (raw[16] << 16) + raw[17]

        injected, raw = raw[19:size], raw[size:]

        if kind != BGP_MSG_NOTIFICATION:
            log.debug(lazymsg('message.type.abort type={kind} expected=notification', kind=kind), 'parser')
            return None
        log.debug(lazymsg('message.type type=notification'), 'parser')
    else:
        log.debug(lazymsg('message.header.missing assuming=notification'), 'parser')
        injected, raw = raw, b''

    try:
        # This does not take the BGP header - let's assume we will not break that :)
        notification = Notification.unpack_message(injected, negotiated_in)
    except Notify:
        import traceback

        log.error(lazymsg('message.parse.failed'), 'parser')
        log.error(lazymsg('message.parse.traceback trace={t}', t=traceback.format_exc()), 'parser')
        if getenv().debug.pdb:
            raise
        return None
    except (ValueError, IndexError, KeyError, struct.error):
        import traceback

        log.error(lazymsg('message.parse.failed'), 'parser')
        log.error(lazymsg('message.parse.traceback trace={t}', t=traceback.format_exc()), 'parser')
        if getenv().debug.pdb:
            raise
        return None

    return notification


def check_update(neighbor: Neighbor, raw: bytes) -> bool:
    update = _make_update(neighbor, raw)
    if not update:
        return False

    log.debug(lazymsg('update.check.complete'), 'parser')  # separator
    for number in range(len(update.nlris)):
        nlri = update.nlris[number]
        route = Route(nlri, update.attributes, nexthop=nlri.nexthop)
        _route = route  # type: Route
        log.info(
            lazymsg(
                'update.decoded action={action} extensive={extensive}',
                action=_route.action,
                extensive=_route.extensive(),
            ),
            'parser',
        )
    json_update = Response.JSON(json_version).update(neighbor, 'in', update, b'', b'', Negotiated.UNSET)
    log.info(lazymsg('update.json json={json_update}', json_update=json_update), 'parser')

    return True


def _get_json_encoder(generic: bool = False) -> 'Response.JSON | Response.V4.JSON':
    """Get the appropriate JSON encoder based on API version setting.

    Args:
        generic: If True, output generic attributes as hex instead of human-readable
    """
    api_version = getenv().api.version
    if api_version == 4:
        encoder = Response.V4.JSON(json_v4_version)
    else:
        encoder = Response.JSON(json_version)

    if generic:
        encoder.generic_attribute_format = True
    return encoder


def display_update(neighbor: Neighbor, raw: bytes, generic: bool = False, command: bool = False) -> bool:
    update = _make_update(neighbor, raw)
    if not update:
        return False

    if command:
        # Output API command instead of JSON
        from exabgp.configuration.command import decode_to_api_command

        payload = raw[19:].hex()  # Skip BGP header
        cmds = decode_to_api_command(payload, neighbor, generic=generic)
        if cmds:
            for cmd in cmds:
                sys.stdout.write(cmd)
                sys.stdout.write('\n')
            return True
        # Fall through to JSON output if command generation fails
        sys.stdout.write('# could not generate API command, falling back to JSON\n')

    encoder = _get_json_encoder(generic=generic)
    sys.stdout.write(encoder.update(neighbor, 'in', update, b'', b'', Negotiated.UNSET))
    sys.stdout.write('\n')
    return True


def display_notification(neighbor: Neighbor, raw: bytes) -> bool:
    notification = _make_notification(neighbor, raw)
    if not notification:
        return False

    encoder = _get_json_encoder()
    sys.stdout.write(encoder.notification(neighbor, 'in', notification, b'', b'', Negotiated.UNSET))
    sys.stdout.write('\n')
    return True


# ============================================================ check_notification
#


# Dummy negotiated for decoding standalone notifications (parameter unused but required by API)
_DUMMY_NEGOTIATED: Negotiated | None = None


def _get_dummy_negotiated() -> Negotiated:
    """Get or create a dummy Negotiated instance for decoding notifications without neighbor context."""
    global _DUMMY_NEGOTIATED
    if _DUMMY_NEGOTIATED is None:
        _DUMMY_NEGOTIATED = Negotiated.make_negotiated(Neighbor.EMPTY, Direction.IN)
    return _DUMMY_NEGOTIATED


def check_notification(raw: bytes) -> bool:
    notification = Notification.unpack_message(raw[18:], _get_dummy_negotiated())
    _notification = notification  # type: Notification
    log.info(lazymsg('notification.decoded notification={notification}', notification=_notification), 'parser')
    return True
