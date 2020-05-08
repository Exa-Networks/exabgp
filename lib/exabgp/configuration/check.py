# encoding: utf-8
"""
check.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# common

import sys
import traceback
import copy

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i

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

from exabgp.logger import Logger

# check_neighbor

from exabgp.util.od import od
from exabgp.rib.change import Change

# check_update

from exabgp.reactor.api.response import Response

# check_notification

from exabgp.bgp.message import Notification

# JSON version

from exabgp.version import json as json_version


if sys.version_info[0] >= 3:
    StandardError = Exception

# =============================================================== check_neighbor
# ...


def check_neighbor(neighbors):
    logger = Logger()
    logger._option['parser'] = True

    logger.notice('\ndecoding routes in configuration', 'parser')

    for name in neighbors.keys():
        neighbor = copy.deepcopy(neighbors[name])
        neighbor.local_as = neighbor.peer_as

        path = {}
        for f in NLRI.known_families():
            if neighbor.add_path:
                path[f] = neighbor.add_path

        capa = Capabilities().new(neighbor, False)
        if path:
            capa[Capability.CODE.ADD_PATH] = path
        capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()

        routerid_1 = str(neighbor.router_id)
        routerid_2 = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor.router_id).split('.', -1))

        o1 = Open(Version(4), ASN(neighbor.local_as), HoldTime(180), RouterID(routerid_1), capa)
        o2 = Open(Version(4), ASN(neighbor.peer_as), HoldTime(180), RouterID(routerid_2), capa)
        negotiated = Negotiated(neighbor)
        negotiated.sent(o1)
        negotiated.received(o2)
        # grouped = False

        for _ in neighbor.rib.outgoing.updates(False):
            pass

        for change1 in neighbor.rib.outgoing.cached_changes():
            str1 = change1.extensive()
            packed = list(Update([change1.nlri], change1.attributes).messages(negotiated))
            pack1 = packed[0]

            logger.debug('parsed route requires %d updates' % len(packed), 'parser')
            logger.debug('update size is %d' % len(pack1), 'parser')

            logger.debug('parsed route %s' % str1, 'parser')
            logger.debug('parsed hex   %s' % od(pack1), 'parser')

            # This does not take the BGP header - let's assume we will not break that :)
            try:
                logger.debug('')  # new line

                pack1s = pack1[19:] if pack1.startswith(b'\xFF' * 16) else pack1
                update = Update.unpack_message(pack1s, negotiated)

                change2 = Change(update.nlris[0], update.attributes)
                str2 = change2.extensive()
                pack2 = list(Update([update.nlris[0]], update.attributes).messages(negotiated))[0]

                logger.debug('recoded route %s' % str2, 'parser')
                logger.debug('recoded hex   %s' % od(pack2), 'parser')

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
                        str1r = str1r.replace('next-hop self', 'next-hop %s' % neighbor.local_address)

                if ' name ' in str1r:
                    parts = str1r.split(' ')
                    pos = parts.index('name')
                    str1r = ' '.join(parts[:pos] + parts[pos + 2 :])

                skip = False

                if str1r != str2r:
                    if 'attribute [' in str1r and ' 0x00 ' in str1r:
                        # we do not decode non-transitive attributes
                        logger.debug('skipping string check on update with non-transitive attribute(s)', 'parser')
                        skip = True
                    else:
                        logger.debug('strings are different:', 'parser')
                        logger.debug('[%s]' % (str1r), 'parser')
                        logger.debug('[%s]' % (str2r), 'parser')
                        return False
                else:
                    logger.debug('strings are fine', 'parser')

                if skip:
                    logger.debug('skipping encoding for update with non-transitive attribute(s)', 'parser')
                elif pack1 != pack2:
                    logger.debug('encoding are different', 'parser')
                    logger.debug('[%s]' % (od(pack1)), 'parser')
                    logger.debug('[%s]' % (od(pack2)), 'parser')
                    return False
                else:
                    logger.debug('encoding is fine', 'parser')
                    logger.debug('----------------------------------------', 'parser')

                logger.debug('JSON nlri %s' % change1.nlri.json(), 'parser')
                logger.debug('JSON attr %s' % change1.attributes.json(), 'parser')

            except Notify as exc:
                logger.debug('----------------------------------------', 'parser')
                logger.debug(str(exc), 'parser')
                logger.debug('----------------------------------------', 'parser')
                return False
        neighbor.rib.clear()

    return True


# ================================================================ check_message
#


def check_message(neighbor, message):
    message = message.replace(':', '')
    raw = concat_bytes_i(
        character(int(_, 16)) for _ in (message[i * 2 : (i * 2) + 2] for i in range(len(message) // 2))
    )

    if raw.startswith(b'\xff' * 16):
        kind = ordinal(raw[18])
        # XXX: FIXME: check size
        # size = (ordinal(raw[16]) << 16) + (ordinal(raw[17]))

        if kind == 1:
            return check_open(neighbor, raw[18:])
        elif kind == 2:
            return check_update(neighbor, raw)
        elif kind == 3:
            return check_notification(raw)
    else:
        return check_update(neighbor, raw)


# ================================================================= check_update
#


def check_open(neighbor, raw):
    pass


# ================================================================= check_update
#


def check_update(neighbor, raw):
    logger = Logger()
    logger._option['parser'] = True
    logger.debug('\ndecoding routes in configuration', 'parser')

    neighbor = neighbor[list(neighbor)[0]]

    path = {}
    for f in NLRI.known_families():
        if neighbor.add_path:
            path[f] = neighbor.add_path

    capa = Capabilities().new(neighbor, False)
    capa[Capability.CODE.ADD_PATH] = path
    capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    # capa[Capability.CODE.FOUR_BYTES_ASN] = True

    routerid_1 = str(neighbor.router_id)
    routerid_2 = '.'.join(str((int(_) + 1) % 250) for _ in str(neighbor.router_id).split('.', -1))

    o1 = Open(Version(4), ASN(neighbor.local_as), HoldTime(180), RouterID(routerid_1), capa)
    o2 = Open(Version(4), ASN(neighbor.peer_as), HoldTime(180), RouterID(routerid_2), capa)
    negotiated = Negotiated(neighbor)
    negotiated.sent(o1)
    negotiated.received(o2)
    # grouped = False

    while raw:
        if raw.startswith(b'\xff' * 16):
            kind = ordinal(raw[18])
            size = (ordinal(raw[16]) << 16) + (ordinal(raw[17]))

            injected, raw = raw[19:size], raw[size:]

            if kind == 2:
                logger.debug('the message is an update', 'parser')
                decoding = 'update'
            else:
                logger.debug('the message is not an update (%d) - aborting' % kind, 'parser')
                return False
        else:
            logger.debug('header missing, assuming this message is ONE update', 'parser')
            decoding = 'update'
            injected, raw = raw, ''

        try:
            # This does not take the BGP header - let's assume we will not break that :)
            update = Update.unpack_message(injected, negotiated)
        except KeyboardInterrupt:
            raise
        except Notify:
            logger.error('could not parse the message', 'parser')
            logger.error(traceback.format_exc(), 'parser')
            return False
        except StandardError:
            logger.error('could not parse the message', 'parser')
            logger.error(traceback.format_exc(), 'parser')
            return False

        logger.debug('', 'parser')  # new line
        for number in range(len(update.nlris)):
            change = Change(update.nlris[number], update.attributes)
            logger.info('decoded %s %s %s' % (decoding, change.nlri.action, change.extensive()), 'parser')
        logger.info(
            'update json %s' % Response.JSON(json_version).update(neighbor, 'in', update, None, '', ''), 'parser'
        )

    return True


# ================================================================= check_update
#


def check_notification(raw):
    notification = Notification.unpack_message(raw[18:], None)
    # XXX: FIXME: should be using logger here
    print(notification)
    return True
