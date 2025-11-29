#!/usr/bin/env python3
"""
ExaBGP API Filter Program - AS-PATH Based Route Filtering

Receives routes from ExaBGP via JSON (stdin), filters based on AS-PATH,
and sends filtered routes to specific neighbors via text commands (stdout).

Filtering Logic:
  - Routes with AS 15169 (Google) → Client1 (127.0.0.2)
  - Routes with AS 8075 (Microsoft) → Client2 (127.0.0.3)
  - All other routes → Dropped (logged)
"""

import sys
import json
from typing import List, Dict, Any

# AS-PATH to Client IP mapping
AS_FILTERS = {
    15169: '127.0.0.2',  # Google → Client1
    8075: '127.0.0.3',   # Microsoft → Client2
}

# Known AS descriptions for logging
AS_NAMES = {
    15169: 'Google',
    8075: 'Microsoft',
    13335: 'Cloudflare',
    19281: 'Quad9',
    65001: 'Upstream',
    65000: 'ExaBGP',
    65002: 'Client1',
    65003: 'Client2',
}


def log(message: str) -> None:
    """Log to stderr with [FILTER] prefix"""
    sys.stderr.write(f'[FILTER] {message}\n')
    sys.stderr.flush()


def parse_aspath(attributes: Dict[str, Any]) -> List[int]:
    """
    Extract AS numbers from AS-PATH attribute

    Args:
        attributes: ExaBGP attributes dict from JSON message

    Returns:
        List of AS numbers in path order
    """
    aspath_data = attributes.get('as-path', attributes.get('aspath', []))
    asns = []

    # Handle both formats: list of dicts or list of lists
    if isinstance(aspath_data, list):
        for segment in aspath_data:
            if isinstance(segment, dict):
                # Format: {"type": "as-sequence", "asns": [15169, 65001]}
                segment_asns = segment.get('asns', segment.get('value', []))
                if isinstance(segment_asns, list):
                    asns.extend(segment_asns)
            elif isinstance(segment, (list, tuple)):
                # Format: [[15169, 65001]]
                asns.extend(segment)

    return asns


def format_as_path_str(as_path: List[int]) -> str:
    """
    Format AS-PATH for logging

    Args:
        as_path: List of AS numbers

    Returns:
        Formatted string with AS names (e.g., "Google(15169) Upstream(65001)")
    """
    parts = []
    for asn in as_path:
        name = AS_NAMES.get(asn, f'AS{asn}')
        parts.append(f'{name}({asn})')
    return ' → '.join(parts)


def filter_route(update_msg: Dict[str, Any]) -> None:
    """
    Process UPDATE message and forward to appropriate client

    Args:
        update_msg: ExaBGP JSON update message
    """
    try:
        # Extract route information
        announce = update_msg.get('announce', {})
        attributes = update_msg.get('attributes', {})

        # Get NLRI prefixes
        prefixes = []
        for family, routes_dict in announce.items():
            if isinstance(routes_dict, dict):
                for next_hop, route_list in routes_dict.items():
                    if isinstance(route_list, list):
                        for route in route_list:
                            if isinstance(route, dict):
                                nlri = route.get('nlri')
                                if nlri:
                                    prefixes.append((nlri, next_hop))

        if not prefixes:
            # Try legacy format
            nlri = update_msg.get('nlri', '')
            next_hop = attributes.get('next-hop', '')
            if nlri and next_hop:
                prefixes = [(nlri, next_hop)]

        if not prefixes:
            log('No NLRI found in update message')
            return

        # Parse AS-PATH
        as_path = parse_aspath(attributes)

        if not as_path:
            log('No AS-PATH found in update message')
            return

        # Check if any ASN in path matches our filters
        matched_asn = None
        for asn in as_path:
            if asn in AS_FILTERS:
                matched_asn = asn
                break

        if matched_asn is None:
            # No matching AS - drop route
            as_path_str = format_as_path_str(as_path)
            for prefix, _ in prefixes:
                log(f'DROPPED:  {prefix:20s} (no filter)      | AS-PATH: {as_path_str}')
            return

        # Forward route to appropriate client
        client_ip = AS_FILTERS[matched_asn]
        as_path_str = format_as_path_str(as_path)

        for prefix, next_hop in prefixes:
            # Format AS-PATH for announce command (space-separated ASNs)
            as_path_list = ' '.join(str(asn) for asn in as_path)

            # Send announce command to ExaBGP
            announce_cmd = f'announce route {prefix} next-hop {next_hop} as-path [ {as_path_list} ]'
            sys.stdout.write(announce_cmd + '\n')
            sys.stdout.flush()

            # Log forwarding action
            as_name = AS_NAMES.get(matched_asn, f'AS{matched_asn}')
            client_name = 'Client1' if client_ip == '127.0.0.2' else 'Client2'
            log(f'FORWARD: {prefix:20s} ({as_name:10s}) → {client_name:7s} | AS-PATH: {as_path_str}')

    except Exception as e:
        log(f'ERROR processing route: {e}')
        import traceback
        traceback.print_exc(file=sys.stderr)


def main():
    """Main filter loop - read JSON from stdin, process, write commands to stdout"""
    log('Starting AS-PATH filter API')
    log(f'Filter rules: {len(AS_FILTERS)} AS filters configured')
    for asn, client_ip in AS_FILTERS.items():
        as_name = AS_NAMES.get(asn, f'AS{asn}')
        client_name = 'Client1' if client_ip == '127.0.0.2' else 'Client2'
        log(f'  {as_name} (AS{asn}) → {client_name} ({client_ip})')

    message_count = 0

    try:
        while True:
            # Read line from stdin (ExaBGP sends JSON messages one per line)
            line = sys.stdin.readline()
            if not line:
                # EOF - ExaBGP closed connection
                break

            line = line.strip()
            if not line:
                continue

            # Parse JSON message
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Not JSON - might be control message
                if 'shutdown' in line.lower():
                    log('Received shutdown signal')
                    break
                # Ignore non-JSON lines
                continue

            # Process UPDATE messages
            msg_type = msg.get('type')
            if msg_type == 'update':
                neighbor = msg.get('neighbor', {})
                peer_asn = neighbor.get('asn', {}).get('peer')

                # Only process routes from upstream (AS 65001)
                if peer_asn == 65001:
                    message_count += 1
                    filter_route(msg)

    except KeyboardInterrupt:
        log('Interrupted by user')
    except Exception as e:
        log(f'Fatal error in main loop: {e}')
        import traceback
        traceback.print_exc(file=sys.stderr)

    log(f'Exiting - processed {message_count} update messages')


if __name__ == '__main__':
    main()
