"""RFC 9234 local role configuration."""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.core import Section, Tokeniser
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget, Container, Leaf, ValueType

# RFC 9234 section 5 ends with "The operator MUST NOT have the ability to modify the
# procedures defined in this section", so `otc send|disable` was removed rather than
# deprecated. An operator upgrading has the line in a working file, and an option which
# is quietly ignored changes what leaves the box without saying so; name the RFC instead.
OTC_REMOVED = (
    "'role otc' was removed in 6.0.0: RFC 9234 section 5 says the operator MUST NOT have the "
    'ability to modify the Only-to-Customer procedures. Delete the line; the egress marking is '
    'unconditional for IPv4 and IPv6 unicast.'
)


def local_role(tokeniser: Tokeniser) -> RoleValue:
    return RoleValue.from_string(tokeniser())


def role_boolean(tokeniser: Tokeniser) -> bool:
    value = tokeniser()
    if value not in ('enable', 'disable'):
        raise ValueError('role setting requires enable or disable')
    return value == 'enable'


def role_otc_removed(tokeniser: Tokeniser) -> bool:
    """Refuse the removed sub-option by name, rather than as an unknown keyword.

    The entry stays in `known` only so the parser reaches this function: it is absent from
    the schema, so it is neither offered nor documented as a choice.
    """
    tokeniser()
    raise ValueError(OTC_REMOVED)


class ParseRole(Section):
    name = 'role'
    syntax = 'role { local provider|customer|peer|rs|rs-client; strict enable|disable; add-meta enable|disable; }'
    schema = Container(
        description='RFC 9234 local role',
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
                ('add-meta', 'Include API metadata', ['enable', 'disable']),
            )
        },
    )
    known = {'local': local_role, 'strict': role_boolean, 'add-meta': role_boolean, 'otc': role_otc_removed}

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
        neighbor.session.role_add_meta = role.get('add-meta', True)
        return ''
