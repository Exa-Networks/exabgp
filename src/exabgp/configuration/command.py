"""command.py

Decode BGP UPDATE messages to API command strings.
Used by `exabgp decode --command` for round-trip testing.

Created by Thomas Mangin on 2024-12-10.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.configuration.check import _hexa, _make_update
from exabgp.reactor.api.response import Response
from exabgp.version import json as json_version


def format_extended_community(ec: dict) -> str | None:
    """Format a single extended community dict to API command string."""
    if not isinstance(ec, dict) or 'string' not in ec:
        return None

    ec_string = ec['string']

    # Handle interface-set with transitive field
    if ec_string.startswith('interface-set:'):
        if 'transitive' in ec:
            trans = 'transitive' if ec['transitive'] else 'non-transitive'
            parts = ec_string.split(':', 1)
            if len(parts) == 2:
                return f'interface-set:{trans}:{parts[1]}'

    return ec_string


def parse_generic_attribute_name(attr_name: str) -> tuple[int, int] | None:
    """Parse attribute-0xNN-0xNN format to (type_code, flags)."""
    if not attr_name.startswith('attribute-0x'):
        return None

    rest = attr_name[10:]  # len("attribute-") = 10
    sep_pos = rest.find('-0x', 2)
    if sep_pos == -1:
        return None

    type_hex = rest[:sep_pos]
    flags_hex = rest[sep_pos + 1 :]

    try:
        type_code = int(type_hex, 16)
        flags = int(flags_hex, 16)
        return (type_code, flags)
    except ValueError:
        return None


def format_generic_attributes(attributes: dict) -> list[str]:
    """Extract generic attributes as 'attribute [0xNN 0xNN 0xHEX]' syntax."""
    parts = []
    for attr_name, attr_value in attributes.items():
        parsed = parse_generic_attribute_name(attr_name)
        if parsed is None:
            continue
        type_code, flags = parsed
        if isinstance(attr_value, str) and attr_value.startswith('0x'):
            hex_data = attr_value[2:]
            parts.append(f'attribute [0x{type_code:02x} 0x{flags:02x} 0x{hex_data}]')
    return parts


def format_attributes(attrs: dict) -> list[str]:
    """Format attributes for API command."""
    parts = []
    if 'origin' in attrs:
        parts.append(f'origin {attrs["origin"]}')
    if 'as-path' in attrs:
        as_path = attrs['as-path']
        if as_path:
            as_nums = []
            if isinstance(as_path, list):
                as_nums = as_path
            elif isinstance(as_path, dict):
                for seg in as_path.values():
                    if isinstance(seg, dict) and 'value' in seg:
                        as_nums.extend(seg['value'])
            if as_nums:
                parts.append(f'as-path [{" ".join(str(a) for a in as_nums)}]')
    if 'local-preference' in attrs:
        parts.append(f'local-preference {attrs["local-preference"]}')
    if 'med' in attrs:
        parts.append(f'med {attrs["med"]}')
    if 'atomic-aggregate' in attrs:
        if attrs['atomic-aggregate']:
            parts.append('atomic-aggregate')
    if 'aggregator' in attrs:
        parts.append(f'aggregator {attrs["aggregator"]}')
    if 'community' in attrs:
        comms = attrs['community']
        if comms:
            comm_strs = []
            for c in comms:
                if isinstance(c, list) and len(c) == 2:
                    comm_strs.append(f'{c[0]}:{c[1]}')
                else:
                    comm_strs.append(str(c))
            parts.append(f'community [{" ".join(comm_strs)}]')
    if 'large-community' in attrs:
        lcomms = attrs['large-community']
        if lcomms:
            lcomm_strs = []
            for lc in lcomms:
                if isinstance(lc, list) and len(lc) == 3:
                    lcomm_strs.append(f'{lc[0]}:{lc[1]}:{lc[2]}')
                else:
                    lcomm_strs.append(str(lc))
            parts.append(f'large-community [{" ".join(lcomm_strs)}]')
    if 'extended-community' in attrs:
        ecomms = attrs['extended-community']
        if ecomms:
            ecomm_strs = []
            for ec in ecomms:
                if isinstance(ec, dict) and 'string' in ec:
                    ecomm_strs.append(ec['string'])
                else:
                    ecomm_strs.append(str(ec))
            parts.append(f'extended-community [{" ".join(ecomm_strs)}]')
    if 'originator-id' in attrs:
        parts.append(f'originator-id {attrs["originator-id"]}')
    if 'cluster-list' in attrs:
        cluster_list = attrs['cluster-list']
        if cluster_list:
            parts.append(f'cluster-list [{" ".join(cluster_list)}]')

    # Generic attributes (attribute-0xNN-0xNN format)
    parts.extend(format_generic_attributes(attrs))
    return parts


def family_to_api_format(family: str) -> str:
    """Convert JSON family format to API command format."""
    if family.startswith('ipv4'):
        return 'route'
    return family


def format_flow_announce(
    afi: str, nexthop: str, nlri_info: dict, attributes: dict, action: str = 'announce'
) -> str | None:
    """Format a FlowSpec NLRI as an API announce/withdraw command."""
    flow_string = nlri_info.get('string', '')
    if not flow_string:
        return None

    if flow_string.startswith('flow '):
        flow_details = flow_string[5:]
    else:
        flow_details = flow_string

    rd = nlri_info.get('rd')
    if rd and f'rd {rd}' not in flow_details:
        flow_details = f'{flow_details} rd {rd}'

    cmd_parts = [f'{action} {afi} flow {flow_details}']

    if nexthop and nexthop != 'no-nexthop':
        cmd_parts.append(f'next-hop {nexthop}')

    if 'extended-community' in attributes:
        ecomms = attributes['extended-community']
        if ecomms:
            ecomm_strs = []
            for ec in ecomms:
                formatted = format_extended_community(ec)
                if formatted:
                    ecomm_strs.append(formatted)
            if ecomm_strs:
                cmd_parts.append(f'extended-community [{" ".join(ecomm_strs)}]')

    if 'community' in attributes:
        comms = attributes['community']
        if comms:
            comm_strs = []
            for c in comms:
                if isinstance(c, list) and len(c) == 2:
                    comm_strs.append(f'{c[0]}:{c[1]}')
            if comm_strs:
                cmd_parts.append(f'community [{" ".join(comm_strs)}]')

    cmd_parts.extend(format_generic_attributes(attributes))
    return ' '.join(cmd_parts)


def format_mvpn_announce(
    afi: str, nexthop: str, nlri_info: dict, attributes: dict, action: str = 'announce'
) -> str | None:
    """Format a MCAST-VPN NLRI as an API announce/withdraw command."""
    code = nlri_info.get('code', 0)
    rd = nlri_info.get('rd', '')
    source = nlri_info.get('source', '')
    group = nlri_info.get('group', '')
    source_as = nlri_info.get('source-as', '')

    nlri_str = ''
    if code == 5:
        nlri_str = f'source-ad source {source} group {group} rd {rd}'
    elif code == 6:
        nlri_str = f'shared-join rp {source} group {group} rd {rd} source-as {source_as}'
    elif code == 7:
        nlri_str = f'source-join source {source} group {group} rd {rd} source-as {source_as}'
    else:
        return None

    cmd_parts = [f'{action} {afi} mcast-vpn {nlri_str} next-hop {nexthop}']

    if 'extended-community' in attributes:
        ecomms = attributes['extended-community']
        if ecomms:
            ecomm_strs = []
            for ec in ecomms:
                if isinstance(ec, dict) and 'string' in ec:
                    ecomm_strs.append(ec['string'])
            if ecomm_strs:
                cmd_parts.append(f'extended-community [{" ".join(ecomm_strs)}]')

    cmd_parts.extend(format_generic_attributes(attributes))
    return ' '.join(cmd_parts)


def format_mup_announce(
    afi: str, nexthop: str, nlri_info: dict, attributes: dict, action: str = 'announce'
) -> str | None:
    """Format a MUP NLRI as an API announce/withdraw command."""
    name = nlri_info.get('name', '')
    rd = nlri_info.get('rd', '')

    mup_type = None
    nlri_str = ''

    if name == 'InterworkSegmentDiscoveryRoute':
        mup_type = 'mup-isd'
        prefix_ip = nlri_info.get('prefix_ip', '')
        prefix_ip_len = nlri_info.get('prefix_ip_len', 0)
        nlri_str = f'{prefix_ip}/{prefix_ip_len} rd {rd}'

    elif name == 'DirectSegmentDiscoveryRoute':
        mup_type = 'mup-dsd'
        ip = nlri_info.get('ip', '')
        nlri_str = f'{ip} rd {rd}'

    elif name == 'Type1SessionTransformedRoute':
        mup_type = 'mup-t1st'
        prefix_ip = nlri_info.get('prefix_ip', '')
        prefix_ip_len = nlri_info.get('prefix_ip_len', 0)
        teid = nlri_info.get('teid', '0')
        qfi = nlri_info.get('qfi', '0')
        endpoint_ip = nlri_info.get('endpoint_ip', '')
        nlri_str = f'{prefix_ip}/{prefix_ip_len} rd {rd} teid {teid} qfi {qfi} endpoint {endpoint_ip}'
        source_ip = nlri_info.get('source_ip', '')
        source_ip_len = nlri_info.get('source_ip_len', 0)
        if source_ip and source_ip_len > 0 and source_ip != "b''":
            nlri_str += f' source {source_ip}'

    elif name == 'Type2SessionTransformedRoute':
        mup_type = 'mup-t2st'
        endpoint_ip = nlri_info.get('endpoint_ip', '')
        endpoint_len = nlri_info.get('endpoint_len', 0)
        teid = nlri_info.get('teid', '0')
        ip_bits = 128 if ':' in endpoint_ip else 32
        teid_len = endpoint_len - ip_bits
        nlri_str = f'{endpoint_ip} rd {rd} teid {teid}/{teid_len}'

    if not mup_type:
        return None

    cmd_parts = [f'{action} {afi} mup {mup_type} {nlri_str} next-hop {nexthop}']

    if 'extended-community' in attributes:
        ecomms = attributes['extended-community']
        if ecomms:
            ecomm_strs = []
            for ec in ecomms:
                if isinstance(ec, dict) and 'string' in ec:
                    ecomm_strs.append(ec['string'])
            if ecomm_strs:
                cmd_parts.append(f'extended-community [{" ".join(ecomm_strs)}]')

    if 'bgp-prefix-sid' in attributes:
        prefix_sid = attributes['bgp-prefix-sid']
        if 'l3-service' in prefix_sid:
            for service in prefix_sid['l3-service']:
                sid = service.get('sid', '')
                behavior = service.get('endpoint_behavior', 0)
                structure = service.get('structure', {})
                lbl = structure.get('locator-block-length', 0)
                lnl = structure.get('locator-node-length', 0)
                fl = structure.get('function-length', 0)
                al = structure.get('argument-length', 0)
                tl = structure.get('transposition-length', 0)
                to = structure.get('transposition-offset', 0)
                cmd_parts.append(
                    f'bgp-prefix-sid-srv6 ( l3-service {sid} 0x{behavior:x} [{lbl},{lnl},{fl},{al},{tl},{to}] )'
                )

    cmd_parts.extend(format_generic_attributes(attributes))
    return ' '.join(cmd_parts)


def decode_to_api_command(payload_hex: str, neighbor: 'Neighbor', generic: bool = False) -> list[str]:
    """Decode BGP UPDATE hex to API command string(s).

    Args:
        payload_hex: The BGP UPDATE payload in hex (after 19-byte header)
        neighbor: Neighbor for negotiation context
        generic: If True, output generic attributes as hex

    Returns:
        List of API command strings.
        Empty list on error.
    """
    try:
        raw = _hexa(payload_hex)
        update = _make_update(neighbor, raw)
        if not update:
            return []

        encoder = Response.JSON(json_version)
        if generic:
            encoder.generic_attribute_format = True

        json_str = encoder.update(neighbor, 'in', update, b'', b'', Negotiated.UNSET)
        data = json.loads(json_str)

        message = data.get('neighbor', {}).get('message', {}).get('update', {})
        if not message:
            return []

        announce = message.get('announce', {})
        withdraw = message.get('withdraw', {})
        attributes = message.get('attribute', {})

        commands = []

        # Process announces
        for family, nexthops in announce.items():
            # Handle FlowSpec
            if 'flow' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nexthop, nlris in nexthops.items():
                    for nlri_info in nlris:
                        cmd = format_flow_announce(afi, nexthop, nlri_info, attributes)
                        if cmd:
                            commands.append(cmd)
                continue

            # Handle MCAST-VPN
            if 'mcast-vpn' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nexthop, nlris in nexthops.items():
                    if len(nlris) > 1:
                        group_cmds = []
                        for nlri_info in nlris:
                            cmd = format_mvpn_announce(afi, nexthop, nlri_info, attributes)
                            if cmd:
                                group_cmds.append(cmd)
                        if len(group_cmds) > 1:
                            commands.append('group ' + ' ; '.join(group_cmds))
                        elif group_cmds:
                            commands.append(group_cmds[0])
                    else:
                        for nlri_info in nlris:
                            cmd = format_mvpn_announce(afi, nexthop, nlri_info, attributes)
                            if cmd:
                                commands.append(cmd)
                continue

            # Handle MUP
            if 'mup' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nexthop, nlris in nexthops.items():
                    for nlri_info in nlris:
                        cmd = format_mup_announce(afi, nexthop, nlri_info, attributes)
                        if cmd:
                            commands.append(cmd)
                continue

            # Handle VPLS
            if 'vpls' in family:
                for nexthop, nlris in nexthops.items():
                    for nlri_info in nlris:
                        rd = nlri_info.get('rd', '')
                        endpoint = nlri_info.get('endpoint', 0)
                        base = nlri_info.get('base', 0)
                        offset = nlri_info.get('offset', 0)
                        size = nlri_info.get('size', 0)
                        cmd_parts = [
                            f'announce vpls rd {rd} endpoint {endpoint} base {base} offset {offset} size {size} next-hop {nexthop}'
                        ]
                        cmd_parts.extend(format_attributes(attributes))
                        commands.append(' '.join(cmd_parts))
                continue

            # Standard families
            for nexthop, nlris in nexthops.items():
                # Check for EOR
                if nlris and isinstance(nlris, list) and len(nlris) == 1:
                    nlri_item = nlris[0]
                    if isinstance(nlri_item, str) and nlri_item == 'eor':
                        commands.append(f'announce eor {family}')
                        continue
                    if isinstance(nlri_item, dict) and 'eor' in nlri_item:
                        eor_info = nlri_item['eor']
                        if isinstance(eor_info, dict):
                            afi = eor_info.get('afi', 'ipv4')
                            safi = eor_info.get('safi', 'unicast')
                            commands.append(f'announce eor {afi} {safi}')
                        continue

                # Multi-NLRI: use 'attributes' syntax
                if len(nlris) > 1:
                    path_info = nlris[0].get('path-information') if nlris else None
                    all_same_path = all(n.get('path-information') == path_info for n in nlris)

                    cmd_parts = ['announce attributes']
                    if path_info and all_same_path:
                        cmd_parts.append(f'path-information {path_info}')
                    cmd_parts.append(f'next-hop {nexthop}')
                    cmd_parts.extend(format_attributes(attributes))
                    cmd_parts.append('nlri')
                    for nlri_info in nlris:
                        nlri = nlri_info.get('nlri', '')
                        cmd_parts.append(nlri)
                    commands.append(' '.join(cmd_parts))
                else:
                    # Single NLRI
                    for nlri_info in nlris:
                        nlri = nlri_info.get('nlri', '')
                        api_family = family_to_api_format(family)
                        cmd_parts = [f'announce {api_family} {nlri} next-hop {nexthop}']

                        if 'path-information' in nlri_info:
                            cmd_parts.append(f'path-information {nlri_info["path-information"]}')

                        if 'rd' in nlri_info:
                            cmd_parts.append(f'rd {nlri_info["rd"]}')

                        if 'label' in nlri_info:
                            labels = nlri_info['label']
                            if labels:
                                if isinstance(labels[0], list):
                                    cmd_parts.append(f'label {labels[0][0]}')
                                else:
                                    cmd_parts.append(f'label {labels[0]}')

                        cmd_parts.extend(format_attributes(attributes))
                        commands.append(' '.join(cmd_parts))

        # Process withdraws
        for family, nlris in withdraw.items():
            if 'flow' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nlri_info in nlris:
                    if isinstance(nlri_info, dict):
                        nexthop = attributes.get('next-hop', '0.0.0.0')
                        cmd = format_flow_announce(afi, nexthop, nlri_info, attributes, action='withdraw')
                        if cmd:
                            commands.append(cmd)
                continue

            if 'mup' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nlri_info in nlris:
                    if isinstance(nlri_info, dict):
                        nexthop = attributes.get('next-hop', '0.0.0.0')
                        cmd = format_mup_announce(afi, nexthop, nlri_info, attributes, action='withdraw')
                        if cmd:
                            commands.append(cmd)
                continue

            if 'mcast-vpn' in family:
                afi = 'ipv4' if 'ipv4' in family else 'ipv6'
                for nlri_info in nlris:
                    if isinstance(nlri_info, dict):
                        nexthop = attributes.get('next-hop', '0.0.0.0')
                        cmd = format_mvpn_announce(afi, nexthop, nlri_info, attributes, action='withdraw')
                        if cmd:
                            commands.append(cmd)
                continue

            if 'vpls' in family:
                for nlri_info in nlris:
                    if isinstance(nlri_info, dict):
                        rd = nlri_info.get('rd', '')
                        endpoint = nlri_info.get('endpoint', 0)
                        base = nlri_info.get('base', 0)
                        offset = nlri_info.get('offset', 0)
                        size = nlri_info.get('size', 0)
                        cmd_parts = [
                            f'withdraw vpls rd {rd} endpoint {endpoint} base {base} offset {offset} size {size} next-hop 0.0.0.0'
                        ]
                        commands.append(' '.join(cmd_parts))
                continue

            api_family = family_to_api_format(family)
            for nlri_info in nlris:
                if isinstance(nlri_info, dict):
                    nlri = nlri_info.get('nlri', '')
                    cmd_parts = [f'withdraw {api_family} {nlri}']

                    if 'rd' in nlri_info:
                        cmd_parts.append(f'rd {nlri_info["rd"]}')

                    if 'label' in nlri_info:
                        labels = nlri_info['label']
                        if labels:
                            if isinstance(labels[0], list):
                                cmd_parts.append(f'label {labels[0][0]}')
                            else:
                                cmd_parts.append(f'label {labels[0]}')

                    cmd_parts.extend(format_attributes(attributes))
                    commands.append(' '.join(cmd_parts))
                else:
                    commands.append(f'withdraw {api_family} {nlri_info}')

        return commands

    except Exception:
        return []
