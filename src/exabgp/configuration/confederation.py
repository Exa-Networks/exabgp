"""RFC 5065 BGP confederation configuration.

    confederation {
        identifier 65000;
        members [ 65001 65002 ];
    }

`local-as` is our Member-AS Number, and `peer-as` the peer's: a peer whose AS is our own
or one of the members is inside the confederation, any other is outside it and sees only
the identifier.
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.core import Section, Tokeniser
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType

# the member list is written by hand, a real confederation has a handful of Member-ASes
MAX_MEMBERS = 1024


def identifier(tokeniser: Tokeniser) -> ASN:
    value = ASN.from_string(tokeniser())
    if not value:
        raise ValueError('the confederation identifier can not be AS 0')
    return value


def members(tokeniser: Tokeniser) -> tuple[ASN, ...]:
    """One AS number, or a list of them in brackets."""
    value = tokeniser()
    if value != '[':
        return (ASN.from_string(value),)
    found: list[ASN] = []
    while True:
        value = tokeniser()
        if value == ']':
            return tuple(found)
        if value in ('', ';'):
            raise ValueError("the confederation members are not closed with ']'")
        if value == ',':
            continue
        if len(found) == MAX_MEMBERS:
            raise ValueError(f'a confederation holds at most {MAX_MEMBERS} members')
        found.append(ASN.from_string(value))


class ParseConfederation(Section):
    name = 'confederation'
    syntax = 'confederation { identifier <asn>; members [ <asn> ... ]; }'
    schema = Container(
        description='RFC 5065 BGP confederation',
        children={
            'identifier': Leaf(
                type=ValueType.ASN,
                description='AS Confederation Identifier, the AS the world outside sees',
                mandatory=True,
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
            'members': Leaf(
                type=ValueType.STRING,
                description='Member-AS Numbers of the confederation, besides local-as',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            ),
        },
    )
    known = {'identifier': identifier, 'members': members}

    @staticmethod
    def apply(neighbor: Neighbor, local: dict[str, Any]) -> str:
        """Check the block against local-as and peer-as, and give it to the session."""
        if 'confederation' not in local:
            return ''
        confederation = local['confederation']
        if 'identifier' not in confederation:
            return 'incomplete confederation, missing identifier'
        if not local.get('local-as') or not local.get('peer-as'):
            return 'confederation requires explicit local-as and peer-as; auto is not allowed'
        confed_id = confederation['identifier']
        member_asns = tuple(confederation.get('members', ()))
        if local['local-as'] == confed_id:
            return 'local-as is the Member-AS Number, it can not be the confederation identifier'
        if confed_id in member_asns:
            return 'the confederation identifier can not also be a member'
        neighbor.session.confederation = confed_id
        neighbor.session.confederation_members = member_asns
        assert neighbor.session.confederation
        return ''
