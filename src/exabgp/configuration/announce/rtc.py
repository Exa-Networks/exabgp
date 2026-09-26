"""announce/rtc.py

Announce parser for RTC NLRI (Route Target Constraint, RFC 4684, AFI 1 SAFI 132).

  announce ipv4 rtc origin-as 65001 route-target 65001:100 next-hop self
  announce ipv4 rtc default next-hop self

The field is `origin-as`, not `origin`: an RTC UPDATE carries the ORIGIN attribute like any
other (RFC 4760 section 3), and `origin igp` keeps its meaning here.

Created for issue #1109.
"""

from __future__ import annotations

from exabgp.bgp.message.update.nlri import RTC
from exabgp.bgp.message.update.nlri.settings import RTCSettings
from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Error, Parser, Scope, Tokeniser
from exabgp.configuration.l2vpn.parser import next_hop
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Leaf, RouteBuilder, ValueType
from exabgp.configuration.static.rtc import rtc_default, rtc_origin_as, rtc_route_target
from exabgp.configuration.validator import LegacyParserValidator
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.route import Route

# attributes of an IP route which mean nothing for route target membership; next-hop is
# replaced, as the IP route's also adds a NEXT_HOP attribute, which an UPDATE whose only NLRI is
# in MP_REACH_NLRI SHOULD NOT carry (RFC 4760 section 3)
_NOT_FOR_RTC = ('split', 'aigp', 'otc', 'next-hop')


class AnnounceRTC(ParseAnnounce):
    schema = RouteBuilder(
        description='RTC route target membership announcement',
        nlri_class=RTC,
        settings_class=RTCSettings,
        prefix_parser=None,  # the NLRI is built from origin-as and route-target
        assign={
            'next-hop': 'nexthop',
            'origin-as': 'origin_as',
            'route-target': 'route_target',
            'default': 'default',
        },
        children={
            'next-hop': Leaf(
                type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self", carried in MP_REACH_NLRI only',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=next_hop, name='next-hop'),
            ),
            'origin-as': Leaf(
                type=ValueType.ASN,
                description='AS originating the route target membership',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=rtc_origin_as, name='origin-as'),
            ),
            'route-target': Leaf(
                type=ValueType.EXTENDED_COMMUNITY,
                description='Route target the membership is for',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=rtc_route_target, name='route-target'),
            ),
            'default': Leaf(
                type=ValueType.BOOLEAN,
                description='Default route target: every VPN route',
                target=ActionTarget.NLRI,
                operation=ActionOperation.SET,
                key=ActionKey.FIELD,
                validator=LegacyParserValidator(parser_func=rtc_default, name='default'),
            ),
            **{name: child for name, child in AnnounceIP.schema.children.items() if name not in _NOT_FOR_RTC},
        },
    )

    name = 'rtc'
    afi: AFI | None = None

    @property
    def syntax(self) -> str:
        defn = '  '.join(self.schema.definition)
        return f'rtc {defn}\n'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass


@ParseAnnounce.register_family(AFI.ipv4, SAFI.rtc, ActionTarget.SCOPE, ActionOperation.EXTEND, ActionKey.NAME)
def rtc_ipv4(tokeniser: Tokeniser) -> list[Route]:
    return _build_route(tokeniser, AnnounceRTC.schema, AFI.ipv4, SAFI.rtc)
