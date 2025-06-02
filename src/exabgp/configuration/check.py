# encoding: utf-8
"""
check.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# common

from __future__ import annotations

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


def _hexa(data):
    full = data.replace(':', '')
    hexa = [full[i * 2 : (i * 2) + 2] for i in range(len(full) // 2)]
    return bytes([int(_, 16) for _ in hexa])


def _negotiated(neighbor):
    path = {}
    for f in NLRI.known_families():
        if neighbor['capability']['add-path']:
            path[f] = neighbor['capability']['add-path']

    capa = Capabilities().new(neighbor, False)
    capa[Capability.CODE.ADD_PATH] = path
    capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    # capa[Capability.CODE.FOUR_BYTES_ASN] = True

    routerid_1 = str(neighbor['router-id'])
    routerid_2 = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor['router-id']).split('.', -1))

    o1 = Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID(routerid_1), capa)
    o2 = Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID(routerid_2), capa)
    negotiated = Negotiated(neighbor)
    negotiated.sent(o1)
    negotiated.received(o2)
    # grouped = False
    return negotiated


# =============================================================== check_neighbor
# ...


def check_generation(neighbors):
    option.enabled['parser'] = True

    for name in neighbors.keys():
        neighbor = copy.deepcopy(neighbors[name])
        neighbor['local-as'] = neighbor['peer-as']
        negotiated = _negotiated(neighbor)

        for _ in neighbor.rib.outgoing.updates(False):
            pass

        for change1 in neighbor.rib.outgoing.cached_changes():
            str1 = change1.extensive()
            packed = list(Update([change1.nlri], change1.attributes).messages(negotiated))
            pack1 = packed[0]

            log.debug('parsed route requires %d updates' % len(packed), 'parser')
            log.debug('update size is %d' % len(pack1), 'parser')

            log.debug('parsed route %s' % str1, 'parser')
            log.debug('parsed hex   %s' % od(pack1), 'parser')

            # This does not take the BGP header - let's assume we will not break that :)
            try:
                log.debug('')  # new line

                pack1s = pack1[19:] if pack1.startswith(b'\xff' * 16) else pack1
                update = Update.unpack_message(pack1s, Direction.IN, negotiated)

                change2 = Change(update.nlris[0], update.attributes)
                str2 = change2.extensive()
                pack2 = list(Update([update.nlris[0]], update.attributes).messages(negotiated))[0]

                log.debug('recoded route %s' % str2, 'parser')
                log.debug('recoded hex   %s' % od(pack2), 'parser')

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
                        str1r = str1r.replace('next-hop self', 'next-hop %s' % neighbor['local-address'])

                if ' name ' in str1r:
                    parts = str1r.split(' ')
                    pos = parts.index('name')
                    str1r = ' '.join(parts[:pos] + parts[pos + 2 :])

                skip = False

                if str1r != str2r:
                    if 'attribute [' in str1r and ' 0x00 ' in str1r:
                        # we do not decode non-transitive attributes
                        log.debug('skipping string check on update with non-transitive attribute(s)', 'parser')
                        skip = True
                    elif '=http' in str1r or '=ndl-aas' in str1r:
                        log.debug('skipping string check on update with named flow attribute(s)', 'parser')
                        skip = True
                    else:
                        log.debug('strings are different:', 'parser')
                        log.debug('[%s]' % (str1r), 'parser')
                        log.debug('[%s]' % (str2r), 'parser')
                        return False
                else:
                    log.debug('strings are fine', 'parser')

                if skip:
                    log.debug('skipping encoding for update with non-transitive attribute(s)', 'parser')
                elif pack1 != pack2:
                    log.debug('encoding are different', 'parser')
                    log.debug('[%s]' % (od(pack1)), 'parser')
                    log.debug('[%s]' % (od(pack2)), 'parser')
                    return False
                else:
                    log.debug('encoding is fine', 'parser')
                    log.debug('----------------------------------------', 'parser')

                log.debug('JSON nlri %s' % change1.nlri.json(), 'parser')
                log.debug('JSON attr %s' % change1.attributes.json(), 'parser')

            except Notify as exc:
                log.debug('----------------------------------------', 'parser')
                log.debug(str(exc), 'parser')
                log.debug('----------------------------------------', 'parser')
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

    if kind == 1:
        return check_open(neighbor, raw[19:])
    if kind == 2:
        return check_update(neighbor, raw)
    if kind == 3:
        return check_notification(raw)

    print(f'unknown type {kind}')
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

    if kind == 1:
        return display_open(neighbor, raw[19:])
    if kind == 2:
        return display_update(neighbor, raw)
    if kind == 3:
        return display_notification(neighbor, raw)
    print(f'unknown type {kind}')
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
            log.debug('parsing NLRI %s' % announced, 'parser')
            nlri, announced = NLRI.unpack_nlri(afi, safi, announced, Action.ANNOUNCE, addpath)
            nlris.append(nlri)
    except Exception as exc:
        log.error('could not parse the nlri', 'parser')
        from exabgp.debug import string_exception

        log.error(string_exception(exc), 'parser')
        if getenv().debug.pdb:
            raise
        return []

    return nlris


def check_nlri(neighbor, routes):
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    log.debug('', 'parser')  # new line
    for nlri in nlris:
        log.info('nlri json %s' % nlri.json(), 'parser')
    return True


def display_nlri(neighbor, routes):
    nlris = _make_nlri(neighbor, routes)
    if not nlris:
        return False

    for nlri in nlris:
        print(nlri.json())
    return True


# =================================================================== check_open
#


def check_open(neighbor, raw):
    import sys
    import traceback

    sys.excepthook = traceback.print_exception

    try:
        o = Open.unpack_message(raw, Direction.IN, _negotiated(neighbor))
        print(o)
    except Exception:
        print()
        print('we could not decode this open message')
        print('here is the traceback to help to figure out why')
        print()
        raise


def display_open(neighbor, raw):
    try:
        o = Open.unpack_message(raw)
        print(Response.JSON(json_version).open(neighbor, 'in', o, None, '', ''))
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

            if kind == 2:
                log.debug('the message is an update', 'parser')
            else:
                log.debug('the message is not an update (%d) - aborting' % kind, 'parser')
                return False
        else:
            log.debug('header missing, assuming this message is ONE update', 'parser')
            injected, raw = raw, ''

        try:
            # This does not take the BGP header - let's assume we will not break that :)
            update = Update.unpack_message(injected, Direction.IN, negotiated)
        except Notify:
            import traceback

            log.error('could not parse the message', 'parser')
            log.error(traceback.format_exc(), 'parser')
            if getenv().debug.pdb:
                raise
            return None
        except Exception:
            import traceback

            log.error('could not parse the message', 'parser')
            log.error(traceback.format_exc(), 'parser')
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

        if kind != 3:
            log.debug('the message is not an notification (%d) - aborting' % kind, 'parser')
            return False
        log.debug('the message is an notification', 'parser')
    else:
        log.debug('header missing, assuming this message is ONE notification', 'parser')
        injected, raw = raw, ''

    try:
        # This does not take the BGP header - let's assume we will not break that :)
        notification = Notification.unpack_message(injected, Direction.IN, negotiated)
    except Notify:
        import traceback

        log.error('could not parse the message', 'parser')
        log.error(traceback.format_exc(), 'parser')
        if getenv().debug.pdb:
            raise
        return None
    except Exception:
        import traceback

        log.error('could not parse the message', 'parser')
        log.error(traceback.format_exc(), 'parser')
        if getenv().debug.pdb:
            raise
        return None

    return notification


def check_update(neighbor, raw):
    update = _make_update(neighbor, raw)
    if not update:
        return False

    log.debug('', 'parser')  # new line
    for number in range(len(update.nlris)):
        change = Change(update.nlris[number], update.attributes)
        log.info('decoded %s %s %s' % ('update', change.nlri.action, change.extensive()), 'parser')
    log.info('update json %s' % Response.JSON(json_version).update(neighbor, 'in', update, None, '', ''), 'parser')

    return True


def display_update(neighbor, raw):
    update = _make_update(neighbor, raw)
    if not update:
        return False

    print(Response.JSON(json_version).update(neighbor, 'in', update, None, '', ''))
    return True


def display_notification(neighbor, raw):
    notification = _make_notification(neighbor, raw)
    if not notification:
        return False

    print(Response.JSON(json_version).notification(neighbor, 'in', notification, None, '', ''))
    return True


# ================================================================= check_update
#


def check_notification(raw):
    notification = Notification.unpack_message(raw[18:], None, None)
    # XXX: FIXME: should be using logger here
    print(notification)
    return True
