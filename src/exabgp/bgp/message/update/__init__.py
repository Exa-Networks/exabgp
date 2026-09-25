"""update/__init__.py

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

# Update message header offsets and constants
UPDATE_WITHDRAWN_LENGTH_OFFSET = 2  # Offset to start of withdrawn routes
UPDATE_ATTR_LENGTH_HEADER_SIZE = 4  # Size of withdrawn length (2) + attr length (2)

# EOR (End-of-RIB) message length constants
EOR_IPV4_UNICAST_LENGTH = 4  # Length of IPv4 unicast EOR marker
EOR_WITH_PREFIX_LENGTH = 11  # Length of EOR with NLRI prefix

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
        return '\n'.join(['{}{}'.format(str(self.nlris[n]), str(self.attributes)) for n in range(len(self.nlris))])

    @staticmethod
    def prefix(data):
        # This function needs renaming
        return pack('!H', len(data)) + data

    @staticmethod
    def split(data):
        length = len(data)

        # RFC 4271 4.3: the body opens with two 2 byte length fields. length was
        # computed and never consulted, so a body shorter than the first of them
        # left struct.error here rather than a NOTIFICATION: one stray byte on
        # the wire was enough
        if length < UPDATE_ATTR_LENGTH_HEADER_SIZE:
            # RFC 4271 6.1: a Length field below the minimum length of an UPDATE
            # is Bad Message Length, with the erroneous Length field as the data.
            # 6.3 Malformed Attribute List is for the lengths INSIDE a message
            # which is itself long enough, which is the check further down
            raise Notify(1, 2, pack('!H', Message.HEADER_LEN + length))

        len_withdrawn = unpack('!H', data[0:UPDATE_WITHDRAWN_LENGTH_OFFSET])[0]
        withdrawn = data[UPDATE_WITHDRAWN_LENGTH_OFFSET : len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET]

        if len(withdrawn) != len_withdrawn:
            raise Notify(3, 1, 'invalid withdrawn routes length, not enough data available')

        start_attributes = len_withdrawn + UPDATE_ATTR_LENGTH_HEADER_SIZE
        # the withdrawn routes are accounted for, but the total path attribute
        # length which follows them still has to be present
        if length < start_attributes:
            raise Notify(3, 1, 'invalid UPDATE, no room for the total path attribute length')
        len_attributes = unpack('!H', data[len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET : start_attributes])[0]
        start_announced = len_withdrawn + len_attributes + UPDATE_ATTR_LENGTH_HEADER_SIZE
        attributes = data[start_attributes:start_announced]
        announced = data[start_announced:]

        if len(attributes) != len_attributes:
            raise Notify(3, 1, 'invalid total path attribute length, not enough data available')

        if (
            UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_withdrawn
            + UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_attributes
            + len(announced)
            != length
        ):
            raise Notify(3, 1, 'error in BGP message length, not enough data for the size announced')

        return withdrawn, attributes, announced

    def _split_nlris(self, negotiated):
        nlris = []
        mp_nlris = {}
        for nlri in sorted(self.nlris):
            if nlri.family().afi_safi() not in negotiated.families:
                continue

            native = nlri.afi == AFI.ipv4 and nlri.safi == SAFI.unicast
            if native and nlri.action == Action.WITHDRAW:
                nlris.append(nlri)
                continue
            if native and nlri.action == Action.ANNOUNCE and nlri.nexthop.afi == AFI.ipv4:
                nlris.append(nlri)
                continue

            # MP_UNREACH carries no next hop, including bare multicast withdrawals.
            if (
                nlri.action == Action.WITHDRAW
                or nlri.nexthop.afi != AFI.undefined
                or nlri.safi in (SAFI.flow_ip, SAFI.flow_vpn)
            ):
                mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(nlri.action, []).append(nlri)
                continue
            raise ValueError('unexpected nlri definition ({})'.format(nlri))
        return nlris, mp_nlris

    @staticmethod
    def _carries_attributes(nlris, mp_nlris):
        # RFC 4760 permits MP_UNREACH-only UPDATEs without other path attributes, and one
        # built here carries none at all.
        #
        # This used to be called _include_defaults and its answer was handed to
        # Attributes.pack as with_default.  False got no attributes only because of a
        # precedence bug in pack(): `set(keys + list(default) if with_default else [])` made
        # the whole concatenation the true branch, so with_default=False encoded nothing
        # whatever the collection held.  With the brackets corrected it would encode the
        # withdrawn route's own attributes and size the withdrawal against them, which is how
        # a withdrawal came to be dropped for the weight of an announcement it was not
        # carrying.  So what this pass wants is said outright: no attribute field.
        if not mp_nlris or nlris:
            return True
        for family, actions in mp_nlris.items():
            afi, safi = family
            if safi not in (SAFI.unicast, SAFI.multicast):
                return True
            if set(actions.keys()) != {Action.WITHDRAW}:
                return True
        return False

    # The routes MUST have the same attributes.
    def messages(self, negotiated, include_withdraw=True):
        nlris, mp_nlris = self._split_nlris(negotiated)
        if not nlris and not mp_nlris:
            return

        attr = self.attributes.pack(negotiated) if self._carries_attributes(nlris, mp_nlris) else b''

        # What is left of an UPDATE once the path attributes of an ANNOUNCEMENT are in it,
        # and what is left of one which carries none.
        #
        # There used to be one number here, the first, and the method returned outright when
        # it reached zero.  RFC 4271 4.3 makes the Path Attributes field optional and RFC
        # 4760 3 says an UPDATE carrying MP_UNREACH_NLRI "is not required to carry any other
        # path attributes", so the announcement's budget has nothing to say about a
        # withdrawal: since the carriers were split below, a withdraw-only UPDATE carries no
        # attribute at all.  Roughly 4060 octets of path attributes therefore made a 27 octet
        # withdraw-only UPDATE disappear, with nothing on the wire, no log an operator would
        # connect to it, and a stale route left on the peer.  The announcement refusal is
        # kept, in front of the announcement pass rather than in front of everything.
        announce_size = negotiated.msg_size - Message.HEADER_LEN - UPDATE_ATTR_LENGTH_HEADER_SIZE - len(attr)
        withdraw_size = negotiated.msg_size - Message.HEADER_LEN - UPDATE_ATTR_LENGTH_HEADER_SIZE

        yield from self._native_messages(nlris, attr, negotiated, announce_size, withdraw_size, include_withdraw)
        yield from self._mp_messages(mp_nlris, attr, negotiated, announce_size, include_withdraw)

    @staticmethod
    def _packed_nlris(nlris, negotiated, budget, reason):
        """The NLRI of one pass, in blobs which each fit `budget`.

        Yields nothing more once a single NLRI is wider than a whole message, since there is
        no way to send it and the blobs after it would arrive without it.
        """
        blob = b''
        for nlri in nlris:
            packed = nlri.pack(negotiated)
            if len(blob) + len(packed) > budget:
                if not blob:
                    log.critical(
                        lambda reason=reason: 'can not pack one NLRI in an UPDATE ({})'.format(reason), 'parser'
                    )
                    return
                yield blob
                blob = b''
            blob += packed
        if blob:
            yield blob

    def _native_messages(self, nlris, attr, negotiated, announce_size, withdraw_size, include_withdraw):
        # RFC 7606 5.1: an UPDATE "MUST NOT contain more than one of the following: non-empty
        # Withdrawn Routes field, non-empty Network Layer Reachability Information field,
        # MP_REACH_NLRI attribute, and MP_UNREACH_NLRI attribute".  The two IPv4 unicast
        # fields used to be filled by one loop and shared a message; they are two passes now.
        # The withdrawals go first, because a prefix in both sets has to be withdrawn before
        # it is re-announced, which is the order the shared message gave for free.  Each pass
        # still fills its field to the negotiated message size, so a table load is still one
        # message per few hundred prefixes.
        withdraws = [nlri for nlri in nlris if nlri.action == Action.WITHDRAW] if include_withdraw else []
        announces = [nlri for nlri in nlris if nlri.action == Action.ANNOUNCE]

        # A withdraw-only UPDATE carries no path attribute, so it has the whole message.
        for withdrawn in self._packed_nlris(withdraws, negotiated, withdraw_size, 'withdrawal_too_large'):
            yield self._message(Update.prefix(withdrawn) + Update.prefix(b''))

        if not announces:
            return
        if announce_size <= 0:
            # The attributes leave no room for a single NLRI, so these routes cannot be
            # announced.  This is the refusal the guard in messages() used to make, now made
            # where it applies: the withdrawals above have already gone out.
            log.critical(lambda: 'attributes size is so large we can not even pack one NLRI', 'parser')
            return
        for announced in self._packed_nlris(announces, negotiated, announce_size, 'attributes_too_large'):
            yield self._message(Update.prefix(b'') + Update.prefix(attr) + announced)

    def _mp_messages(self, mp_nlris, attr, negotiated, msg_size, include_withdraw):
        for family, actions in mp_nlris.items():
            afi, safi = family
            announces = actions.get(Action.ANNOUNCE, [])
            withdraws = actions.get(Action.WITHDRAW, []) if include_withdraw else []

            if msg_size <= 0:
                # Only this family is impossible.  Returning would also drop every family
                # after it.  A budget which is positive but still too narrow for one NLRI is
                # not caught here: packed_attributes logs and leaves that NLRI out.
                log.critical(lambda: 'attributes size is so large we can not even pack one NLRI', 'parser')
                continue

            # RFC 7606 5.1 again: an MP_UNREACH_NLRI never shares a message with an
            # MP_REACH_NLRI.  The last withdrawal chunk used to be held back and packed with
            # the first announcement.  Emitting them all first keeps the ordering that gave,
            # so a prefix is withdrawn before it is re-announced across message boundaries.
            for mpurnlri in MPURNLRI(afi, safi, withdraws).packed_attributes(negotiated, msg_size):
                yield self._message(Update.prefix(b'') + Update.prefix(attr + mpurnlri))

            for mprnlri in MPRNLRI(afi, safi, announces).packed_attributes(negotiated, msg_size):
                yield self._message(Update.prefix(b'') + Update.prefix(attr + mprnlri))

    # XXX: FIXME: this can raise ValueError. IndexError,TypeError, struct.error (unpack) = check it is well intercepted
    @classmethod
    def unpack_message(cls, data, direction, negotiated):
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        length = len(data)

        # This could be speed up massively by changing the order of the IF
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)  # pylint: disable=E1101
        if length == EOR_WITH_PREFIX_LENGTH and data.startswith(EOR.NLRI.PREFIX):
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
            log.debug(lambda nlri=nlri: 'withdrawn NLRI {}'.format(nlri), 'routes')
            withdrawn = left
            nlris.append(nlri)

        while announced:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, announced, Action.ANNOUNCE, addpath)
            nlri.nexthop = nexthop
            log.debug(lambda nlri=nlri: 'announced NLRI {}'.format(nlri), 'routes')
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

            return 'json {}'.format(
                Response.JSON(json_version).update(negotiated.neighbor, 'receive', update, None, '', '')
            )

        log.debug(lazyformat('decoded UPDATE', '', parsed), 'parser')

        return update
