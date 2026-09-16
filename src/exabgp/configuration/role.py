"""RFC 9234 local role and outbound OTC policy configuration."""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.core import Section, Tokeniser
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType


def local_role(tokeniser: Tokeniser) -> RoleValue:
    return RoleValue.from_string(tokeniser())


def role_boolean(tokeniser: Tokeniser) -> bool:
    value = tokeniser()
    if value not in ('enable', 'disable'):
        raise ValueError('role setting requires enable or disable')
    return value == 'enable'


def role_otc(tokeniser: Tokeniser) -> bool:
    value = tokeniser()
    if value in ('receive', 'send/receive', 'send-receive'):
        raise ValueError('OTC ingress marking is not implemented; use send or disable')
    if value not in ('send', 'disable'):
        raise ValueError('role otc requires send or disable')
    return value == 'send'


class ParseRole(Section):
    name = 'role'
    syntax = 'role { local provider|customer|peer|rs|rs-client; strict enable|disable; otc send|disable; add-meta enable|disable; }'
    schema = Container(
        description='RFC 9234 local role and outbound OTC policy',
        children={
            name: Leaf(
                type=ValueType.ENUMERATION,
                description=description,
                choices=choices,
                mandatory=name == 'local',
                target=ActionTarget.SCOPE,
                operation=ActionOperation.SET,
                key=ActionKey.COMMAND,
            )
            for name, description, choices in (
                ('local', 'Our local role', [str(role) for role in RoleValue.assigned()]),
                ('strict', 'Require the remote Role capability', ['enable', 'disable']),
                ('otc', 'Automatic OTC marking direction', ['send', 'disable']),
                ('add-meta', 'Include API metadata', ['enable', 'disable']),
            )
        },
    )
    known = {'local': local_role, 'strict': role_boolean, 'otc': role_otc, 'add-meta': role_boolean}

    @staticmethod
    def apply(neighbor: Neighbor, local: dict[str, Any]) -> str:
        """Validate the effective inherited configuration before ASN inference can hide auto."""
        if 'role' not in local:
            return ''
        role = local['role']
        if 'local' not in role:
            return 'incomplete role, missing local'
        if local.get('local-as') is None or local.get('peer-as') is None:
            return 'role requires explicit local-as and peer-as; auto is not allowed'
        if not local['local-as'] or not local['peer-as']:
            return 'role requires nonzero explicit local-as and peer-as'
        if local['local-as'] == local['peer-as']:
            return 'role requires unequal local-as and peer-as (eBGP only)'
        neighbor.session.role = role['local']
        neighbor.session.role_strict = role.get('strict', False)
        neighbor.session.role_otc = role.get('otc', True)
        neighbor.session.role_add_meta = role.get('add-meta', True)
        return ''
