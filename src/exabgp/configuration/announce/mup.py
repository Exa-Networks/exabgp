# encoding: utf-8
"""
announce/mup.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.mpls import label
from exabgp.configuration.static.mpls import prefix_sid_srv6
from exabgp.configuration.static.mpls import srv6_mup_isd
from exabgp.configuration.static.mpls import srv6_mup_dsd
from exabgp.configuration.static.mpls import srv6_mup_t1st
from exabgp.configuration.static.mpls import srv6_mup_t2st
from exabgp.configuration.static.parser import extended_community

from exabgp.configuration.announce import ParseAnnounce


class AnnounceMup(ParseAnnounce):
    definition = [
        'mup-isd <ip prefix> rd <rd>',
        'mup-dsd <ip address> rd <rd>',
        'mup-t1st <ip prefix> rd <rd> teid <teid> qfi <qfi> endpoint <endpoint> [source <source_addr>]',
        'mup-t2st <endpoint address> rd <rd> teid <teid>',
        'next-hop <ip>',
        'extended-community [ mup:<16 bits number>:<ipv4 formated number> target:<16 bits number>:<ipv4 formated number> ]',
        'bgp-prefix-sid-srv6 ( l3-service <ipv6> <behavior> [<LBL>,<LNL>,<FL>,<AL>,<Tpose-Len>,<Tpose-Offset>])',
    ]

    syntax = 'mup {\n' '  <safi> %s;\n' '}' % ';\n  '.join(definition)

    known = {
        'label': label,
        'bgp-prefix-sid-srv6': prefix_sid_srv6,
        'next-hop': next_hop,
        'extended-community': extended_community,
    }
    action = {
        'label': 'nlri-set',
        'next-hop': 'nexthop-and-attribute',
        'bgp-prefix-sid-srv6': 'attribute-add',
        'extended-community': 'attribute-add',
    }

    assign = dict()
    default = dict()

    name = 'mup'

    def __init__(self, tokeniser, scope, error):
        ParseAnnounce.__init__(self, tokeniser, scope, error)

    def clear(self):
        pass

    def pre(self):
        self.scope.to_context(self.name)
        return True

    def post(self):
        return ParseAnnounce.post() and self._check()

    def check(self):
        return True


def mup(tokeniser, afi, safi):
    muptype = tokeniser()
    if 'mup-isd' == muptype:
        mup_nlri = srv6_mup_isd(tokeniser, afi)
    elif 'mup-dsd' == muptype:
        mup_nlri = srv6_mup_dsd(tokeniser, afi)
    elif 'mup-t1st' == muptype:
        mup_nlri = srv6_mup_t1st(tokeniser, afi)
    elif 'mup-t2st' == muptype:
        mup_nlri = srv6_mup_t2st(tokeniser, afi)
    else:
        raise ValueError('mup: unknown mup type: %s' % muptype)

    change = Change(mup_nlri, Attributes())
    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceMup.action[command]
        if action == 'nlri-add':
            for adding in AnnounceMup.known[command](tokeniser):
                change.nlri.add(adding)
        elif action == 'attribute-add':
            change.attributes.add(AnnounceMup.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceMup.known[command](tokeniser, afi)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        elif action == 'nop':
            pass  # yes nothing to do !
        else:
            raise ValueError('mup: unknown command "%s"' % command)

    return [change]


@ParseAnnounce.register('mup', 'extend-name', 'ipv4')
def mup_ip_v4(tokeniser):
    return mup(tokeniser, AFI.ipv4, SAFI.mup)


@ParseAnnounce.register('mup', 'extend-name', 'ipv6')
def mup_ip_v6(tokeniser):
    return mup(tokeniser, AFI.ipv6, SAFI.mup)
