"""then.py

Created by Thomas Mangin on 2015-06-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Callable, Dict, Generator, List, Tuple, Union

from exabgp.configuration.core import Section
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute.community import Communities
from exabgp.bgp.message.update.attribute.community.large.communities import LargeCommunities
from exabgp.bgp.message.update.attribute.community.extended import (
    ExtendedCommunities,
    TrafficRate,
    TrafficAction,
    TrafficMark,
    TrafficRedirect,
    TrafficRedirectASN4,
    TrafficRedirectIPv6,
    TrafficNextHopIPv4IETF,
    TrafficNextHopIPv6IETF,
    TrafficNextHopSimpson,
)

from exabgp.configuration.flow.parser import accept
from exabgp.configuration.flow.parser import discard
from exabgp.configuration.flow.parser import rate_limit
from exabgp.configuration.flow.parser import redirect
from exabgp.configuration.flow.parser import redirect_next_hop
from exabgp.configuration.flow.parser import redirect_next_hop_ietf
from exabgp.configuration.flow.parser import copy
from exabgp.configuration.flow.parser import mark
from exabgp.configuration.flow.parser import action

from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community


class ParseFlowThen(Section):
    definition: List[str] = [
        'accept',
        'discard',
        'rate-limit 9600',
        'redirect 30740:12345',
        'redirect 1.2.3.4:5678',
        'redirect 1.2.3.4',
        'redirect-next-hop',
        'copy 1.2.3.4',
        'mark 123',
        'action sample|terminal|sample-terminal',
    ]

    joined: str = ';\\n  '.join(definition)
    syntax: str = f'then {{\n  {joined};\n}}'

    known: Dict[
        str,
        Callable[
            [Tokeniser],
            Generator[
                Union[
                    bool,
                    TrafficRate,
                    TrafficAction,
                    TrafficMark,
                    Tuple[
                        NextHop,
                        Union[
                            TrafficRedirect,
                            TrafficRedirectASN4,
                            TrafficRedirectIPv6,
                            TrafficNextHopIPv4IETF,
                            TrafficNextHopIPv6IETF,
                            TrafficNextHopSimpson,
                        ],
                    ],
                    Communities,
                    LargeCommunities,
                    ExtendedCommunities,
                ],
                None,
                None,
            ],
        ],
    ] = {
        'accept': accept,
        'discard': discard,
        'rate-limit': rate_limit,
        'redirect': redirect,
        'redirect-to-nexthop': redirect_next_hop,
        'redirect-to-nexthop-ietf': redirect_next_hop_ietf,
        'copy': copy,
        'mark': mark,
        'action': action,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
    }

    # 'community','extended-community'

    action: Dict[str, str] = {
        'accept': 'nop',
        'discard': 'attribute-add',
        'rate-limit': 'attribute-add',
        'redirect': 'nexthop-and-attribute',
        'redirect-to-nexthop': 'attribute-add',
        'redirect-to-nexthop-ietf': 'attribute-add',
        'copy': 'nexthop-and-attribute',
        'mark': 'attribute-add',
        'action': 'attribute-add',
        'community': 'attribute-add',
        'large-community': 'attribute-add',
        'extended-community': 'attribute-add',
    }

    name: str = 'flow/then'

    def __init__(self, tokeniser: Tokeniser, scope: Scope, error: Error) -> None:
        Section.__init__(self, tokeniser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True
