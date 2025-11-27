"""announce/label.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import List

from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.path import AnnouncePath
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import label


class AnnounceLabel(AnnouncePath):
    # put next-hop first as it is a requirement atm
    definition = [
        'label <15 bits number>',
    ] + AnnouncePath.definition

    syntax = '<safi> <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known = {**AnnouncePath.known, 'label': label}
    action = {**AnnouncePath.action, 'label': 'nlri-set'}
    assign = {**AnnouncePath.assign, 'label': 'labels'}

    name = 'vpn'
    afi: AFI | None = None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        AnnouncePath.__init__(self, parser, scope, error)

    def clear(self) -> bool:
        return True

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnouncePath.check(change, afi):
            return False

        if change.nlri.action == Action.ANNOUNCE and change.nlri.has_label() and change.nlri.labels is Labels.NOLABEL:  # type: ignore[attr-defined]
            return False

        return True


def ip_label(tokeniser: Tokeniser, afi: AFI, safi: SAFI) -> List[Change]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = Label(afi, safi, nlri_action)
    nlri.cidr = CIDR(ipmask.pack_ip(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        command_action = AnnounceLabel.action.get(command, '')

        if command_action == 'attribute-add':
            change.attributes.add(AnnounceLabel.known[command](tokeniser))
        elif command_action == 'nlri-set':
            change.nlri.assign(AnnounceLabel.assign[command], AnnounceLabel.known[command](tokeniser))
        elif command_action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceLabel.known[command](tokeniser)
            change.nlri.nexthop = nexthop  # type: ignore[attr-defined]
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    if not AnnounceLabel.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop or label ?)')

    return [change]


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv4')
def nlri_mpls_v4(tokeniser: Tokeniser) -> List[Change]:
    return ip_label(tokeniser, AFI.ipv4, SAFI.nlri_mpls)


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv6')
def nlri_mpls_v6(tokeniser: Tokeniser) -> List[Change]:
    return ip_label(tokeniser, AFI.ipv6, SAFI.nlri_mpls)
