"""update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar, Generator, List, Tuple

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import MPRNLRI, MPURNLRI, Attribute, Attributes
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

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
    EOR: ClassVar[bool] = False

    def __init__(self, nlris: List[NLRI], attributes: Attributes) -> None:
        self.nlris: List[NLRI] = nlris
        self.attributes: Attributes = attributes

    # message not implemented we should use messages below.

    def __str__(self) -> str:
        return '\n'.join(['{}{}'.format(str(self.nlris[n]), str(self.attributes)) for n in range(len(self.nlris))])

    @staticmethod
    def prefix(data: bytes) -> bytes:
        # This function needs renaming
        return pack('!H', len(data)) + data

    @staticmethod
    def split(data: bytes) -> Tuple[bytes, bytes, bytes]:
        length = len(data)

        len_withdrawn = unpack('!H', data[0:UPDATE_WITHDRAWN_LENGTH_OFFSET])[0]
        withdrawn = data[UPDATE_WITHDRAWN_LENGTH_OFFSET : len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET]

        if len(withdrawn) != len_withdrawn:
            raise Notify(3, 1, 'invalid withdrawn routes length, not enough data available')

        start_attributes = len_withdrawn + UPDATE_ATTR_LENGTH_HEADER_SIZE
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

    # The routes MUST have the same attributes ...
    def messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator[bytes, None, None]:
        # sort the nlris

        nlris: list = []
        mp_nlris: dict[tuple, dict] = {}

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

            raise ValueError('unexpected nlri definition ({})'.format(nlri))

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

        attr = self.attributes.pack_attribute(negotiated, include_defaults)

        # Withdraws/NLRIS (IPv4 unicast and multicast)
        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header

        if msg_size < 0:
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        if msg_size == 0 and (nlris or mp_nlris):
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        withdraws = b''
        announced = b''
        # Track sizes progressively to avoid O(n) len() on concatenation
        # See lab/benchmark_update_size.py for benchmark (1.3-1.5x speedup)
        withdraws_size = 0
        announced_size = 0
        for nlri in nlris:
            packed = nlri.pack_nlri(negotiated)
            packed_size = len(packed)
            if announced_size + withdraws_size + packed_size <= msg_size:
                if nlri.action == Action.ANNOUNCE:
                    announced += packed
                    announced_size += packed_size
                elif include_withdraw:
                    withdraws += packed
                    withdraws_size += packed_size
                continue

            if not withdraws and not announced:
                # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
                log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
                return

            if announced:
                yield self._message(Update.prefix(withdraws) + Update.prefix(attr) + announced)
            else:
                yield self._message(Update.prefix(withdraws) + Update.prefix(b'') + announced)

            if nlri.action == Action.ANNOUNCE:
                announced = packed
                announced_size = packed_size
                withdraws = b''
                withdraws_size = 0
            elif include_withdraw:
                withdraws = packed
                withdraws_size = packed_size
                announced = b''
                announced_size = 0
            else:
                withdraws = b''
                withdraws_size = 0
                announced = b''
                announced_size = 0

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
                    negotiated,
                    msg_size - len(withdraws + announced + mp_reach),
                ):
                    if mp_unreach:
                        yield self._message(
                            Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced,
                        )
                        mp_reach = b''
                        announced = b''
                        withdraws = b''
                    mp_unreach = mpurnlri

            yield self._message(
                Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced,
            )  # yield mpr/mpur per family
            withdraws = b''
            announced = b''

    # Note: This method can raise ValueError, IndexError, TypeError, struct.error (from unpack).
    # These exceptions are caught by the caller in reactor/protocol.py:read_message() which
    # wraps them in a Notify(1, 0) to signal a malformed message to the peer.
    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Update | EOR:  # type: ignore[valid-type]
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        length = len(data)

        # This could be speed up massively by changing the order of the IF
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)  # pylint: disable=E1101
        if length == EOR_WITH_PREFIX_LENGTH and data.startswith(EOR.NLRI.PREFIX):
            return EOR.unpack_message(data, negotiated)

        withdrawn, _attributes, announced = cls.split(data)

        if not withdrawn:
            log.debug(lazymsg('update.withdrawn status=none'), 'routes')

        attributes = Attributes.unpack(_attributes, negotiated)

        if not announced:
            log.debug(lazymsg('update.announced status=none'), 'routes')

        # Is the peer going to send us some Path Information with the route (AddPath)
        addpath = negotiated.required(AFI.ipv4, SAFI.unicast)

        # empty string for IP.NoNextHop, the packed IP otherwise (without the 3/4 bytes of attributes headers)
        nexthop = attributes.get(Attribute.CODE.NEXT_HOP, IP.NoNextHop)
        # nexthop = NextHop.unpack(_nexthop.ton())

        # RFC 4271 Section 5.1.3: NEXT_HOP MUST NOT be the IP address of the receiving speaker
        # Log warning but don't kill session - peer may have misconfigured next-hop
        if nexthop is not IP.NoNextHop and hasattr(negotiated, 'neighbor'):
            try:
                local_address = negotiated.neighbor['local-address']
                if local_address is not None and hasattr(nexthop, '_packed') and hasattr(local_address, '_packed'):
                    if nexthop._packed == local_address._packed:
                        log.warning(
                            lambda: 'received NEXT_HOP {} equals our local address (RFC 4271 violation)'.format(
                                nexthop
                            ),
                            'parser',
                        )
            except (TypeError, KeyError):
                # negotiated.neighbor may be a mock or not support subscripting
                pass

        nlris: List[NLRI] = []
        while withdrawn:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, withdrawn, Action.WITHDRAW, addpath, negotiated)
            log.debug(lazymsg('withdrawn NLRI {nlri}', nlri=nlri), 'routes')
            withdrawn = left
            if nlri is not NLRI.INVALID:
                nlris.append(nlri)

        while announced:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, announced, Action.ANNOUNCE, addpath, negotiated)
            if nlri is not NLRI.INVALID:
                nlri.nexthop = nexthop
                log.debug(lazymsg('announced NLRI {nlri}', nlri=nlri), 'routes')
                nlris.append(nlri)
            announced = left

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

        log.debug(lazyformat('decoded UPDATE', '', parsed), 'parser')  # type: ignore[arg-type]

        return update
