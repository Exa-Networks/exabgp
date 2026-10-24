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

from exabgp.environment import getenv

from exabgp.bgp.message import Update
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message import Notify
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction

from exabgp.logger import log
from exabgp.logger import option

# check_neighbor

from exabgp.util.od import od
from exabgp.rib.change import Change

# check_update

from exabgp.reactor.api.response import Response

# check_notification

from exabgp.bgp.message import Notification

# JSON version

from exabgp.version import json as json_version

# BGP message type constants (RFC 4271)
BGP_MSG_OPEN = 1  # BGP OPEN message type
BGP_MSG_UPDATE = 2  # BGP UPDATE message type
BGP_MSG_NOTIFICATION = 3  # BGP NOTIFICATION message type


def _hexa(data):
    full = data.replace(':', '')
    hexa = [full[i * 2 : (i * 2) + 2] for i in range(len(full) // 2)]
    return bytes([int(_, 16) for _ in hexa])


def _negotiated(neighbor):
    path = {}
    for f in NLRI.known_families():
        if neighbor['capability']['add-path']:
            path[f] = neighbor['capability']['add-path']

    local_as = neighbor['local-as'] or neighbor['peer-as']
    capa = Capabilities().new(neighbor, False, local_as=local_as)
    capa[Capability.CODE.ADD_PATH] = path
    capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    # capa[Capability.CODE.FOUR_BYTES_ASN] = True

    routerid_1 = str(neighbor['router-id'])
    routerid_2 = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor['router-id']).split('.', -1))

    o1 = Open(Version(4), ASN(local_as), HoldTime(180), RouterID(routerid_1), capa)
    o2 = Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID(routerid_2), capa)
    negotiated = Negotiated(neighbor)
    negotiated.sent(o1)
    negotiated.received(o2)
    # grouped = False
    return negotiated


# =============================================================== check_neighbor
# ...


def _normalise_route_strings(neighbor, original, recoded):
    original = original.replace('attribute [ 0x04 0x80 0x00000064 ]', 'med 100')
    original = original.lower().replace(' med 100', '').replace(' local-preference 100', '').replace(' origin igp', '')
    recoded = recoded.lower().replace(' med 100', '').replace(' local-preference 100', '').replace(' origin igp', '')
    recoded = recoded.replace(
        'large-community [ 1:2:3 10:11:12 ]',
        'attribute [ 0x20 0xc0 0x0000000100000002000000030000000a0000000b0000000c ]',
    )
    if 'next-hop self' in original:
        if ':' in original:
            original = original.replace('next-hop self', 'next-hop ::1')
        else:
            original = original.replace('next-hop self', 'next-hop {}'.format(neighbor['local-address']))
    if ' name ' in original:
        parts = original.split(' ')
        position = parts.index('name')
        original = ' '.join(parts[:position] + parts[position + 2 :])
    return original, recoded


def _compare_route_encoding(neighbor, original, decoded, packed, recoded):
    original, decoded = _normalise_route_strings(neighbor, original, decoded)
    if original != decoded:
        if 'attribute [' in original and ' 0x00 ' in original:
            # Unknown non-transitive attributes are deliberately not decoded.
            log.debug(lambda: 'skipping string and encoding checks on non-transitive attribute(s)', 'parser')
            return True
        if '=http' in original or '=ndl-aas' in original:
            log.debug(lambda: 'skipping string and encoding checks on named flow attribute(s)', 'parser')
            return True
        log.debug(lambda: 'strings are different:', 'parser')
        log.debug(lambda: f'[{original}]', 'parser')
        log.debug(lambda: f'[{decoded}]', 'parser')
        return False
    log.debug(lambda: 'strings are fine', 'parser')
    if packed != recoded:
        log.debug(lambda: 'encoding are different', 'parser')
        log.debug(lambda: str([od(message) for message in packed]), 'parser')
        log.debug(lambda: str([od(message) for message in recoded]), 'parser')
        return False
    log.debug(lambda: 'encoding is fine', 'parser')
    log.debug(lambda: '----------------------------------------', 'parser')
    return True


def _check_route_generation(neighbor, change, negotiated):
    try:
        original = change.extensive()
        packed = list(Update([change.nlri], change.attributes).messages(negotiated))
        if not packed:
            return False
        first = packed[0]
        log.debug(lambda: 'parsed route requires %d updates' % len(packed), 'parser')
        log.debug(lambda: 'update size is %d' % len(first), 'parser')
        log.debug(lambda: 'parsed route {}'.format(original), 'parser')
        log.debug(lambda: 'parsed hex   {}'.format(od(first)), 'parser')

        payload = first[19:] if first.startswith(b'\xff' * 16) else first
        update = Update.unpack_message(payload, Direction.IN, negotiated)
        if not update.nlris:
            # An UPDATE which re-decodes to no NLRI at all. A flow route with no match block
            # reaches here: it packs a FlowSpec NLRI of length zero, which RFC 8955 4.2 makes a
            # match on every packet, and which does not survive its own decode. Indexing
            # nlris[0] answered that with IndexError out of a validation tool, and the traceback
            # asked the operator to open a bug report about their own configuration. Whether
            # such a rule should be refused outright is a separate question; a validator must
            # say what it found either way.
            log.error(lambda: 'the route generated no NLRI when read back: {}'.format(original), 'parser')
            return False
        decoded = Change(update.nlris[0], update.attributes).extensive()
        recoded = list(Update([update.nlris[0]], update.attributes).messages(negotiated))
        if not recoded:
            return False
        log.debug(lambda: 'recoded route {}'.format(decoded), 'parser')
        log.debug(lambda: 'recoded hex   {}'.format(od(recoded[0])), 'parser')
        if not _compare_route_encoding(neighbor, original, decoded, packed, recoded):
            return False
        log.debug(lambda: 'JSON nlri {}'.format(change.nlri.json()), 'parser')
        log.debug(lambda: 'JSON attr {}'.format(change.attributes.json()), 'parser')
        return True
    except (Notify, ValueError) as exc:
        log.debug(lambda: '----------------------------------------', 'parser')
        log.debug(lambda exc=exc: str(exc), 'parser')
        log.debug(lambda: '----------------------------------------', 'parser')
        return False


def check_generation(neighbors):
    option.enabled['parser'] = True
    for name in neighbors.keys():
        neighbor = copy.deepcopy(neighbors[name])
        # Validate through synthetic iBGP without discarding the only known ASN.
        neighbor['local-as'] = neighbor['peer-as'] or neighbor['local-as']
        neighbor['peer-as'] = neighbor['local-as']
        negotiated = _negotiated(neighbor)
        for _ in neighbor.rib.outgoing.updates(False):
            pass
        for change in neighbor.rib.outgoing.cached_changes():
            if not _check_route_generation(neighbor, change, negotiated):
                return False
        neighbor.rib.clear()
    return True


# ================================================================ check_message
#


def check_message(neighbor, message):
    raw = _hexa(message)

    if not raw.startswith(b'\xff' * 16):
        return check_update(neighbor, raw)

    kind = raw[18]
    # XXX: FIXME: check size
    # size = (raw[16] << 16) + raw[17]

    if kind == BGP_MSG_OPEN:
        return check_open(neighbor, raw[19:])
    if kind == BGP_MSG_UPDATE:
        return check_update(neighbor, raw)
    if kind == BGP_MSG_NOTIFICATION:
        return check_notification(raw)

    sys.stdout.write(f'unknown type {kind}\n')
    return False


def display_message(neighbor, message):
    raw = _hexa(message)

    if not raw.startswith(b'\xff' * 16):
        header = b'\xff' * 16
        header += struct.pack('!H', len(raw) + 19)
        header += struct.pack('!B', 2)
        # XXX: should be calling message not update
        return display_update(neighbor, header + raw)

    kind = raw[18]
    # XXX: FIXME: check size
    # size = (raw[16] << 16) + raw[17]

    if kind == BGP_MSG_OPEN:
        return display_open(neighbor, raw[19:])
    if kind == BGP_MSG_UPDATE:
        return display_update(neighbor, raw)
    if kind == BGP_MSG_NOTIFICATION:
        return display_notification(neighbor, raw)
    sys.stdout.write(f'unknown type {kind}\n')
    return False


# =================================================================== check_nlri
#


def _make_nlri(neighbor, routes):
    option.enabled['parser'] = True

    announced = _hexa(routes)
    negotiated = _negotiated(neighbor)

    afi, safi = neighbor.families()[0]

    # Is the peer going to send us some Path Information with the route (AddPath)
    addpath = negotiated.addpath.send(afi, safi)

    nlris = []
    try:
        while announced:
            log.debug(lambda announced=announced: 'parsing NLRI {}'.format(announced), 'parser')
            nlri, announced = NLRI.unpack_nlri(afi, safi, announced, Action.ANNOUNCE, addpath)
            nlris.append(nlri)
    except Exception as exc:
        log.error(lambda: f'could not parse the nlri for afi={afi}, safi={safi}', 'parser')
        from exabgp.debug import string_exception

        log.error(lambda exc=exc: string_exception(exc), 'parser')
        if getenv().debug.pdb:
            raise
        return []

    return nlris


def check_nlri(neighbor, routes):
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    log.debug(lambda: '', 'parser')  # new line
    for nlri in nlris:
        log.info(lambda nlri=nlri: 'nlri json {}'.format(nlri.json()), 'parser')
    return True


def display_nlri(neighbor, routes):
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    for nlri in nlris:
        sys.stdout.write(f'{nlri.json()}\n')
    return True


# =================================================================== check_open
#


def check_open(neighbor, raw):
    import sys
    import traceback

    sys.excepthook = traceback.print_exception

    try:
        o = Open.unpack_message(raw, Direction.IN, _negotiated(neighbor))
        sys.stdout.write(f'{o}\n')
    except Exception:
        sys.stdout.write('\n')
        sys.stdout.write('we could not decode this open message\n')
        sys.stdout.write('here is the traceback to help to figure out why\n')
        sys.stdout.write('\n')
        raise


def display_open(neighbor, raw):
    try:
        o = Open.unpack_message(raw)
        sys.stdout.write(Response.JSON(json_version).open(neighbor, 'in', o, None, '', ''))
        sys.stdout.write('\n')
        return True
    except Exception:
        return False


# ================================================================= check_update
#


def _make_update(neighbor, raw):
    option.enabled['parser'] = True
    negotiated = _negotiated(neighbor)

    while raw:
        if raw.startswith(b'\xff' * 16):
            kind = raw[18]
            size = (raw[16] << 16) + raw[17]

            injected, raw = raw[19:size], raw[size:]

            if kind == BGP_MSG_UPDATE:
                log.debug(lambda: 'the message is an update', 'parser')
            else:
                log.debug(lambda kind=kind: 'the message is not an update (%d) - aborting' % kind, 'parser')
                return False
        else:
            log.debug(lambda: 'header missing, assuming this message is ONE update', 'parser')
            injected, raw = raw, ''

        try:
            # This does not take the BGP header - let's assume we will not break that :)
            update = Update.unpack_message(injected, Direction.IN, negotiated)
        except Notify:
            import traceback

            log.error(lambda: 'could not parse the message', 'parser')
            log.error(lambda: traceback.format_exc(), 'parser')
            if getenv().debug.pdb:
                raise
            return None
        except Exception:
            import traceback

            log.error(lambda: 'could not parse the message', 'parser')
            log.error(lambda: traceback.format_exc(), 'parser')
            if getenv().debug.pdb:
                raise
            return None

        return update

    return None


def _make_notification(neighbor, raw):
    option.enabled['parser'] = True
    negotiated = _negotiated(neighbor)

    if raw.startswith(b'\xff' * 16):
        kind = raw[18]
        size = (raw[16] << 16) + raw[17]

        injected, raw = raw[19:size], raw[size:]

        if kind != BGP_MSG_NOTIFICATION:
            log.debug(lambda: 'the message is not an notification (%d) - aborting' % kind, 'parser')
            return False
        log.debug(lambda: 'the message is an notification', 'parser')
    else:
        log.debug(lambda: 'header missing, assuming this message is ONE notification', 'parser')
        injected, raw = raw, ''

    try:
        # This does not take the BGP header - let's assume we will not break that :)
        notification = Notification.unpack_message(injected, Direction.IN, negotiated)
    except Notify:
        import traceback

        log.error(lambda: 'could not parse the message', 'parser')
        log.error(lambda: traceback.format_exc(), 'parser')
        if getenv().debug.pdb:
            raise
        return None
    except Exception:
        import traceback

        log.error(lambda: 'could not parse the message', 'parser')
        log.error(lambda: traceback.format_exc(), 'parser')
        if getenv().debug.pdb:
            raise
        return None

    return notification


def check_update(neighbor, raw):
    update = _make_update(neighbor, raw)
    if not update:
        return False

    log.debug(lambda: '', 'parser')  # new line
    for number in range(len(update.nlris)):
        change = Change(update.nlris[number], update.attributes)
        log.info(lambda change=change: f'decoded update {change.nlri.action} {change.extensive()}', 'parser')
    json_update = Response.JSON(json_version).update(neighbor, 'in', update, None, '', '')
    log.info(lambda: f'update json {json_update}', 'parser')

    return True


def display_update(neighbor, raw):
    update = _make_update(neighbor, raw)
    if not update:
        return False

    sys.stdout.write(Response.JSON(json_version).update(neighbor, 'in', update, None, '', ''))
    sys.stdout.write('\n')
    return True


def display_notification(neighbor, raw):
    notification = _make_notification(neighbor, raw)
    if not notification:
        return False

    sys.stdout.write(Response.JSON(json_version).notification(neighbor, 'in', notification, None, '', ''))
    sys.stdout.write('\n')
    return True


# ================================================================= check_update
#


def check_notification(raw):
    notification = Notification.unpack_message(raw[18:], None, None)
    # XXX: FIXME: should be using logger here
    sys.stdout.write(f'{notification}\n')
    return True
