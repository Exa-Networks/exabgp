
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.eor import EOR

from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import MPRNLRI
from exabgp.bgp.message.update.attribute import MPURNLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.logger import log
from exabgp.logger import lazyformat

# ======================================================================= Update

# +-----------------------------------------------------+
# |   Withdrawn Routes Length (2 octets)                |
# +-----------------------------------------------------+
# |   Withdrawn Routes (variable)                       |
# +-----------------------------------------------------+
# |   Total Path Attribute Length (2 octets)            |
# +-----------------------------------------------------+
# |   Path Attributes (variable)                        |
# +-----------------------------------------------------+
# |   Network Layer Reachability Information (variable) |
# +-----------------------------------------------------+

# Withdrawn Routes:

# +---------------------------+
# |   Length (1 octet)        |
# +---------------------------+
# |   Prefix (variable)       |
# +---------------------------+


@Message.register
class Update(Message):
    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR = False

    def __init__(self, nlris, attributes):
        self.nlris = nlris
        self.attributes = attributes

    # message not implemented we should use messages below.

    def __str__(self):
        return '\n'.join(['%s%s' % (str(self.nlris[n]), str(self.attributes)) for n in range(len(self.nlris))])

    @staticmethod
    def prefix(data):
        # This function needs renaming
        return pack('!H', len(data)) + data

    @staticmethod
    def split(data):
        length = len(data)

        len_withdrawn = unpack('!H', data[0:2])[0]
        withdrawn = data[2 : len_withdrawn + 2]

        if len(withdrawn) != len_withdrawn:
            raise Notify(3, 1, 'invalid withdrawn routes length, not enough data available')

        start_attributes = len_withdrawn + 4
        len_attributes = unpack('!H', data[len_withdrawn + 2 : start_attributes])[0]
        start_announced = len_withdrawn + len_attributes + 4
        attributes = data[start_attributes:start_announced]
        announced = data[start_announced:]

        if len(attributes) != len_attributes:
            raise Notify(3, 1, 'invalid total path attribute length, not enough data available')

        if 2 + len_withdrawn + 2 + len_attributes + len(announced) != length:
            raise Notify(3, 1, 'error in BGP message length, not enough data for the size announced')

        return withdrawn, attributes, announced

    # The routes MUST have the same attributes ...
    # XXX: FIXME: calculate size progressively to not have to do it every time
    # XXX: FIXME: we could as well track when packed_del, packed_mp_del, etc
    # XXX: FIXME: are emptied and therefore when we can save calculations
    def messages(self, negotiated, include_withdraw=True):
        # sort the nlris

        nlris = []
        mp_nlris = {}

        for nlri in sorted(self.nlris):
            if nlri.family().afi_safi() not in negotiated.families:
                continue

            add_v4 = nlri.afi == AFI.ipv4
            add_v4 = add_v4 and nlri.safi in [SAFI.unicast, SAFI.multicast]

            del_v4 = add_v4 and nlri.action == Action.WITHDRAW

            if del_v4:
                nlris.append(nlri)
                continue

            add_v4 = add_v4 and nlri.action == Action.ANNOUNCE
            add_v4 = add_v4 and nlri.nexthop.afi == AFI.ipv4

            if add_v4:
                nlris.append(nlri)
                continue

            if nlri.nexthop.afi != AFI.undefined:
                mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(nlri.action, []).append(nlri)
                continue

            if nlri.safi in (SAFI.flow_ip, SAFI.flow_vpn):
                mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(nlri.action, []).append(nlri)
                continue

            raise ValueError('unexpected nlri definition (%s)' % nlri)

        if not nlris and not mp_nlris:
            return

        # If all we have is MP_UNREACH_NLRI, we do not need the default
        # attributes. See RFC4760 that states the following:
        #
        #   An UPDATE message that contains the MP_UNREACH_NLRI is not required
        #   to carry any other path attributes.
        #
        include_defaults = True

        if mp_nlris and not nlris:
            for family, actions in mp_nlris.items():
                afi, safi = family
                if safi not in (SAFI.unicast, SAFI.multicast):
                    break
                if set(actions.keys()) != {Action.WITHDRAW}:
                    break
            # no break
            else:
                include_defaults = False

        attr = self.attributes.pack(negotiated, include_defaults)

        # Withdraws/NLRIS (IPv4 unicast and multicast)
        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header

        if msg_size < 0:
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lambda: 'attributes size is so large we can not even pack one NLRI', 'parser')
            return

        if msg_size == 0 and (nlris or mp_nlris):
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lambda: 'attributes size is so large we can not even pack one NLRI', 'parser')
            return

        withdraws = b''
        announced = b''
        for nlri in nlris:
            packed = nlri.pack(negotiated)
            if len(announced + withdraws + packed) <= msg_size:
                if nlri.action == Action.ANNOUNCE:
                    announced += packed
                elif include_withdraw:
                    withdraws += packed
                continue

            if not withdraws and not announced:
                # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
                log.critical(lambda: 'attributes size is so large we can not even pack one NLRI', 'parser')
                return

            if announced:
                yield self._message(Update.prefix(withdraws) + Update.prefix(attr) + announced)
            else:
                yield self._message(Update.prefix(withdraws) + Update.prefix(b'') + announced)

            if nlri.action == Action.ANNOUNCE:
                announced = packed
                withdraws = b''
            elif include_withdraw:
                withdraws = packed
                announced = b''
            else:
                withdraws = b''
                announced = b''

        if announced or withdraws:
            if announced:
                yield self._message(Update.prefix(withdraws) + Update.prefix(attr) + announced)
            else:
                yield self._message(Update.prefix(withdraws) + Update.prefix(b'') + announced)

        for family in mp_nlris.keys():
            afi, safi = family
            mp_reach = b''
            mp_unreach = b''
            mp_announce = MPRNLRI(afi, safi, mp_nlris[family].get(Action.ANNOUNCE, []))
            mp_withdraw = MPURNLRI(afi, safi, mp_nlris[family].get(Action.WITHDRAW, []))

            for mprnlri in mp_announce.packed_attributes(negotiated, msg_size - len(withdraws + announced)):
                if mp_reach:
                    yield self._message(Update.prefix(withdraws) + Update.prefix(attr + mp_reach) + announced)
                    announced = b''
                    withdraws = b''
                mp_reach = mprnlri

            if include_withdraw:
                for mpurnlri in mp_withdraw.packed_attributes(
                    negotiated, msg_size - len(withdraws + announced + mp_reach)
                ):
                    if mp_unreach:
                        yield self._message(
                            Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced
                        )
                        mp_reach = b''
                        announced = b''
                        withdraws = b''
                    mp_unreach = mpurnlri

            yield self._message(
                Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced
            )  # yield mpr/mpur per family
            withdraws = b''
            announced = b''

    # XXX: FIXME: this can raise ValueError. IndexError,TypeError, struct.error (unpack) = check it is well intercepted
    @classmethod
    def unpack_message(cls, data, direction, negotiated):
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        length = len(data)

        # This could be speed up massively by changing the order of the IF
        if length == 4 and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)  # pylint: disable=E1101
        if length == 11 and data.startswith(EOR.NLRI.PREFIX):
            return EOR.unpack_message(data, direction, negotiated)

        withdrawn, _attributes, announced = cls.split(data)

        if not withdrawn:
            log.debug(lambda: 'withdrawn NLRI none', 'routes')

        attributes = Attributes.unpack(_attributes, direction, negotiated)

        if not announced:
            log.debug(lambda: 'announced NLRI none', 'routes')

        # Is the peer going to send us some Path Information with the route (AddPath)
        if direction == Direction.IN:
            addpath = negotiated.addpath.receive(AFI.ipv4, SAFI.unicast)
        else:
            addpath = negotiated.addpath.send(AFI.ipv4, SAFI.unicast)

        # empty string for NoNextHop, the packed IP otherwise (without the 3/4 bytes of attributes headers)
        nexthop = attributes.get(Attribute.CODE.NEXT_HOP, NoNextHop)
        # nexthop = NextHop.unpack(_nexthop.ton())

        # XXX: NEXTHOP MUST NOT be the IP address of the receiving speaker.

        nlris = []
        while withdrawn:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, withdrawn, Action.WITHDRAW, addpath)
            log.debug(lambda: 'withdrawn NLRI %s' % nlri, 'routes')
            withdrawn = left
            nlris.append(nlri)

        while announced:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, announced, Action.ANNOUNCE, addpath)
            nlri.nexthop = nexthop
            log.debug(lambda: 'announced NLRI %s' % nlri, 'routes')
            announced = left
            nlris.append(nlri)

        unreach = attributes.pop(MPURNLRI.ID, None)
        reach = attributes.pop(MPRNLRI.ID, None)

        if unreach is not None:
            nlris.extend(unreach.nlris)

        if reach is not None:
            nlris.extend(reach.nlris)

        if not attributes and not nlris:
            # Careful do not use == or != as the comparaison does not work
            if unreach is None and reach is None:
                return EOR(AFI.ipv4, SAFI.unicast)
            if unreach is not None:
                return EOR(unreach.afi, unreach.safi)
            if reach is not None:
                return EOR(reach.afi, reach.safi)
            raise RuntimeError('This was not expected')

        update = Update(nlris, attributes)

        def parsed(_):
            # we need the import in the function as otherwise we have an cyclic loop
            # as this function currently uses Update..
            from exabgp.reactor.api.response import Response
            from exabgp.version import json as json_version

            return 'json %s' % Response.JSON(json_version).update(negotiated.neighbor, 'receive', update, None, '', '')

        log.debug(lazyformat('decoded UPDATE', '', parsed), 'parser')

        return update
