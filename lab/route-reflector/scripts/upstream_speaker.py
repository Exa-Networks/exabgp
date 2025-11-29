#!/usr/bin/env python3
"""
Upstream BGP Speaker

Connects to ExaBGP route reflector and announces routes with various AS-PATHs:
  - Google routes (AS 15169)
  - Microsoft routes (AS 8075)
  - Other routes (Cloudflare AS 13335, Quad9 AS 19281)

All routes include local AS (65001) at the end of the path.

Uses custom BGP message construction (BGP helpers) for sending,
as ExaBGP's message construction requires more complex setup.
"""

import sys
import os
import socket
import json
import time

# Add lib directory to path for BGP helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from bgp_helpers import BGPMessage, connect_to_peer, send_bgp, recv_bgp


def log(message: str) -> None:
    """Log to stdout with [UPSTREAM] prefix"""
    print(f'[UPSTREAM] {message}')
    sys.stdout.flush()


def load_routes(routes_file: str) -> list:
    """
    Load routes from JSON file

    Args:
        routes_file: Path to routes.json

    Returns:
        Combined list of all routes
    """
    with open(routes_file, 'r') as f:
        data = json.load(f)

    all_routes = []
    all_routes.extend(data.get('google_routes', []))
    all_routes.extend(data.get('microsoft_routes', []))
    all_routes.extend(data.get('other_routes', []))

    return all_routes


def announce_routes(sock: socket.socket, routes: list) -> None:
    """
    Send UPDATE messages announcing routes

    Args:
        sock: Connected BGP socket
        routes: List of route dicts with prefix, next_hop, as_path
    """
    for route in routes:
        prefix = route['prefix']
        next_hop = route['next_hop']
        as_path = route['as_path']
        description = route.get('description', '')

        # Build UPDATE message
        update = BGPMessage.update(
            withdrawn=[],
            attributes={
                'origin': 'igp',
                'as_path': as_path,
                'next_hop': next_hop,
            },
            announced=[prefix]
        )

        # Send UPDATE
        send_bgp(sock, update)

        # Log announcement
        as_path_str = ' → '.join(f'AS{asn}' for asn in as_path)
        log(f'ANNOUNCED: {prefix:20s} AS-PATH: {as_path_str:35s} NH: {next_hop:12s} ({description})')

        # Small delay to avoid overwhelming receiver
        time.sleep(0.2)


def keepalive_loop(sock: socket.socket, interval: int = 60) -> None:
    """
    Send periodic KEEPALIVE messages and check for incoming messages

    Args:
        sock: Connected BGP socket
        interval: Keepalive interval in seconds
    """
    log(f'Entering keepalive loop (interval: {interval}s)')
    log('Press Ctrl+C to exit')

    last_keepalive = time.time()

    try:
        while True:
            # Send KEEPALIVE if needed
            now = time.time()
            if now - last_keepalive >= interval:
                keepalive = BGPMessage.keepalive()
                send_bgp(sock, keepalive)
                log('Sent KEEPALIVE')
                last_keepalive = now

            # Check for incoming messages (with short timeout)
            msg = recv_bgp(sock, timeout=1)
            if msg:
                msg_type = msg[18] if len(msg) > 18 else 0
                if msg_type == BGPMessage.KEEPALIVE:
                    log('Received KEEPALIVE from peer')
                elif msg_type == BGPMessage.UPDATE:
                    log('Received UPDATE from peer (unexpected in upstream role)')
                elif msg_type == BGPMessage.NOTIFICATION:
                    log('Received NOTIFICATION from peer - session closed')
                    break

            time.sleep(0.5)

    except KeyboardInterrupt:
        log('Interrupted by user')
    except Exception as e:
        log(f'Error in keepalive loop: {e}')


def main():
    """Main entry point"""
    log('='*70)
    log('Upstream BGP Speaker')
    log('='*70)

    # Configuration
    exabgp_host = '127.0.0.1'
    exabgp_port = 1790
    local_asn = 65001
    peer_asn = 65000
    router_id = '1.2.3.100'

    # Determine routes file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    routes_file = os.path.join(script_dir, '..', 'data', 'routes.json')

    # Load routes
    try:
        routes = load_routes(routes_file)
        log(f'Loaded {len(routes)} routes from {routes_file}')
    except Exception as e:
        log(f'ERROR: Failed to load routes: {e}')
        return 1

    # Connect to ExaBGP
    log(f'Connecting to ExaBGP at {exabgp_host}:{exabgp_port}')
    log(f'Local ASN: {local_asn}, Peer ASN: {peer_asn}, Router-ID: {router_id}')

    try:
        sock = connect_to_peer(
            exabgp_host,
            exabgp_port,
            local_asn=local_asn,
            peer_asn=peer_asn,
            router_id=router_id,
            timeout=10
        )
        log('BGP session established successfully')

    except Exception as e:
        log(f'ERROR: Failed to establish BGP session: {e}')
        return 1

    # Wait briefly for session to stabilize
    time.sleep(1)

    # Announce all routes
    try:
        log(f'Announcing {len(routes)} routes...')
        log('-'*70)
        announce_routes(sock, routes)
        log('-'*70)
        log(f'Successfully announced {len(routes)} routes')

    except Exception as e:
        log(f'ERROR: Failed to announce routes: {e}')
        sock.close()
        return 1

    # Keep session alive
    try:
        keepalive_loop(sock, interval=60)
    except Exception as e:
        log(f'ERROR: {e}')
    finally:
        log('Closing BGP session')
        sock.close()
        log('Exited')

    return 0


if __name__ == '__main__':
    sys.exit(main())
