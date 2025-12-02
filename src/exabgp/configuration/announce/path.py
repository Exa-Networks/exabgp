"""announce/path.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.inet import INET

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP
from exabgp.configuration.announce.route_builder import _build_route
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error
from exabgp.configuration.schema import RouteBuilder, Leaf, ValueType

from exabgp.configuration.static.parser import prefix


class AnnouncePath(AnnounceIP):
    # Schema extends AnnounceIP with path-information using RouteBuilder
    schema = RouteBuilder(
        description='IP route announcement with path information',
        nlri_factory=INET,
        prefix_parser=prefix,
        assign={
            'path-information': 'path_info',
        },
        children={
            **AnnounceIP.schema.children,
            'path-information': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Path information (path ID for ADD-PATH)',
                action='nlri-set',
            ),
        },
    )

    name = 'path'

    afi: AFI | None = None

    @property
    def syntax(self) -> str:
        """Syntax generated from schema."""
        return self.schema.syntax

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        AnnounceIP.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnounceIP.check(change, afi):
            return False

        return True


@ParseAnnounce.register('unicast', 'extend-name', 'ipv4')
def unicast_v4(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnouncePath.schema, AFI.ipv4, SAFI.unicast, AnnouncePath.check)


@ParseAnnounce.register('unicast', 'extend-name', 'ipv6')
def unicast_v6(tokeniser: Tokeniser) -> list[Change]:
    return _build_route(tokeniser, AnnouncePath.schema, AFI.ipv6, SAFI.unicast, AnnouncePath.check)
