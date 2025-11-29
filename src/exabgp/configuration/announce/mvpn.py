from __future__ import annotations


from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI

from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.nlri.mvpn import MVPN

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.static.mpls import mvpn_sourcead
from exabgp.configuration.static.mpls import mvpn_sourcejoin
from exabgp.configuration.static.mpls import mvpn_sharedjoin


class AnnounceMVPN(ParseAnnounce):
    definition = [
        'source-ad source <ip> group <ip> rd <rd>',
        'shared-join rp <ip> group <ip> rd <rd> source-as <source-as>',
        'source-join source <ip> group <ip> rd <rd> source-as <source-as>',
    ] + AnnounceIP.definition

    syntax = '<safi> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known = dict(
        AnnounceIP.known,
    )

    action = dict(
        AnnounceIP.action,
    )

    assign = dict(
        AnnounceIP.assign,
    )

    name = 'mvpn'
    afi: AFI | None = None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        self.scope.to_context(self.name)
        return True

    def post(self) -> bool:
        return ParseAnnounce.post(self) and self._check()

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnounceIP.check(change, afi):
            return False

        return True


def mvpn_route(tokeniser: Tokeniser, afi: AFI) -> list[Change]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    route_type = tokeniser()
    mvpn_nlri: MVPN
    if route_type == 'source-ad':
        mvpn_nlri = mvpn_sourcead(tokeniser, afi, nlri_action)
    elif route_type == 'source-join':
        mvpn_nlri = mvpn_sourcejoin(tokeniser, afi, nlri_action)
    elif route_type == 'shared-join':
        mvpn_nlri = mvpn_sharedjoin(tokeniser, afi, nlri_action)
    else:
        raise ValueError('mup: unknown/unsupported mvpn route type: {}'.format(route_type))

    change = Change(mvpn_nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        command_action = AnnounceMVPN.action.get(command, '')

        if command_action == 'attribute-add':
            change.attributes.add(AnnounceMVPN.known[command](tokeniser))
        elif command_action == 'nlri-set':
            change.nlri.assign(AnnounceMVPN.assign[command], AnnounceMVPN.known[command](tokeniser))
        elif command_action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceMVPN.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    if not AnnounceMVPN.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop, label or rd ?)')

    return [change]


@ParseAnnounce.register('mcast-vpn', 'extend-name', 'ipv4')
def mcast_vpn_v4(tokeniser: Tokeniser) -> list[Change]:
    return mvpn_route(tokeniser, AFI.ipv4)


@ParseAnnounce.register('mcast-vpn', 'extend-name', 'ipv6')
def mcast_vpn_v6(tokeniser: Tokeniser) -> list[Change]:
    return mvpn_route(tokeniser, AFI.ipv6)
