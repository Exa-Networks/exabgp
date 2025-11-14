"""announce/label.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import List, Optional

from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.parser import path_information


class AnnouncePath(AnnounceIP):
    # put next-hop first as it is a requirement atm
    definition = [
        'label <15 bits number>',
    ] + AnnounceIP.definition

    syntax = '<safi> <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known = dict(
        AnnounceIP.known,
        **{
            'path-information': path_information,
        },
    )

    action = dict(
        AnnounceIP.action,
        **{
            'path-information': 'nlri-set',
        },
    )

    assign = dict(
        AnnounceIP.assign,
        **{
            'path-information': 'path_info',
        },
    )

    name = 'path'
    afi: Optional[AFI] = None

    def __init__(self, tokeniser: Tokeniser, scope: Scope, error: Error) -> None:
        AnnounceIP.__init__(self, tokeniser, scope, error)

    def clear(self) -> bool:
        return True

    @staticmethod
    def check(change: Change, afi: Optional[AFI]) -> bool:
        if not AnnounceIP.check(change, afi):
            return False

        return True


def ip_unicast(tokeniser: Tokeniser, afi: AFI, safi: SAFI) -> List[Change]:
    action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = INET(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnouncePath.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnouncePath.known[command](tokeniser))  # type: ignore[operator]
        elif action == 'nlri-set':
            change.nlri.assign(AnnouncePath.assign[command], AnnouncePath.known[command](tokeniser))  # type: ignore[operator]
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnouncePath.known[command](tokeniser)  # type: ignore[operator]
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    if not AnnouncePath.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop ?)')

    return [change]


@ParseAnnounce.register('unicast', 'extend-name', 'ipv4')
def unicast_v4(tokeniser: Tokeniser) -> List[Change]:
    return ip_unicast(tokeniser, AFI.ipv4, SAFI.unicast)


@ParseAnnounce.register('unicast', 'extend-name', 'ipv6')
def unicast_v6(tokeniser: Tokeniser) -> List[Change]:
    return ip_unicast(tokeniser, AFI.ipv6, SAFI.unicast)
