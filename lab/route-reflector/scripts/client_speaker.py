#!/usr/bin/env python3
"""
Client BGP Speaker

Connects to ExaBGP route reflector and receives filtered routes.
Two instances run simultaneously:
  - Client1 (AS 65002) - receives Google routes (AS 15169)
  - Client2 (AS 65003) - receives Microsoft routes (AS 8075)

Uses ExaBGP's native message decoding library for parsing BGP UPDATEs.
"""

import sys
import os
import socket
import argparse
import time

# Add ExaBGP src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
sys.path.insert(0, os.path.join(repo_root, 'src'))

# Add lib directory to path for BGP connection helpers
sys.path.insert(0, os.path.join(script_dir, '..', 'lib'))

from bgp_helpers import BGPMessage, connect_to_peer, send_bgp, recv_bgp  # noqa: E402

# Import ExaBGP's message decoding
from exabgp.bgp.message.open.capability.negotiated import Negotiated  # noqa: E402


def log(prefix: str, message: str) -> None:
    """Log to stdout with custom prefix"""
    print(f'[{prefix}] {message}')
    sys.stdout.flush()


def receive_routes(sock: socket.socket, name: str, keepalive_interval: int = 60) -> None:
    """
    Receive and display routes from ExaBGP using ExaBGP's message decoder

    Args:
        sock: Connected BGP socket
        name: Client name for logging
        keepalive_interval: Keepalive interval in seconds
    """
    log(name, 'Waiting for routes...')
    log(name, 'Press Ctrl+C to exit')

    received_count = 0
    last_keepalive = time.time()

    # Create negotiated capabilities (used by ExaBGP's decoder)
    negotiated = Negotiated(None)

    try:
        while True:
            # Send KEEPALIVE if needed
            now = time.time()
            if now - last_keepalive >= keepalive_interval:
                keepalive = BGPMessage.keepalive()
                send_bgp(sock, keepalive)
                last_keepalive = now

            # Wait for incoming message (with timeout)
            msg_data = recv_bgp(sock, timeout=2)
            if msg_data is None:
                continue

            msg_type = msg_data[18] if len(msg_data) > 18 else 0

            if msg_type == BGPMessage.UPDATE:
                # Use ExaBGP's message decoder
                try:
                    # Extract message body (skip 19-byte header)
                    msg_body = msg_data[19:]

                    # Decode using ExaBGP's Update.unpack
                    from exabgp.bgp.message.update import Update
                    update_msg = Update.unpack_message(msg_body, negotiated)

                    # Extract announced routes
                    if hasattr(update_msg, 'nlris') and update_msg.nlris:
                        for nlri in update_msg.nlris:
                            received_count += 1

                            # Get prefix
                            prefix = str(nlri)

                            # Get AS-PATH from attributes
                            as_path = []
                            next_hop = '0.0.0.0'

                            if hasattr(update_msg, 'attributes') and update_msg.attributes:
                                # Extract AS-PATH
                                if hasattr(update_msg.attributes, 'aspath'):
                                    aspath_attr = update_msg.attributes.aspath
                                    if aspath_attr and hasattr(aspath_attr, 'as_seq'):
                                        as_path = [int(asn) for asn in aspath_attr.as_seq]

                                # Extract NEXT-HOP
                                if hasattr(update_msg.attributes, 'nexthop'):
                                    next_hop = str(update_msg.attributes.nexthop)

                            # Format AS-PATH for display
                            as_path_str = ' → '.join(f'AS{asn}' for asn in as_path) if as_path else 'empty'

                            log(name, f'RECEIVED #{received_count}: {prefix:20s} AS-PATH: {as_path_str:45s} NH: {next_hop}')

                except Exception as e:
                    log(name, f'Error decoding UPDATE with ExaBGP decoder: {e}')
                    # Fallback: just log that we received an UPDATE
                    log(name, f'RECEIVED #{received_count + 1}: UPDATE (decode failed)')

            elif msg_type == BGPMessage.KEEPALIVE:
                # Peer sent KEEPALIVE - session is alive
                pass

            elif msg_type == BGPMessage.NOTIFICATION:
                log(name, 'Received NOTIFICATION - peer closed session')
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        log(name, 'Interrupted by user')
    except Exception as e:
        log(name, f'Error receiving routes: {e}')
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='BGP client speaker for route reflector lab'
    )
    parser.add_argument(
        '--name',
        required=True,
        help='Client name (e.g., CLIENT1, CLIENT2)'
    )
    parser.add_argument(
        '--port',
        type=int,
        required=True,
        help='ExaBGP listen port to connect to'
    )
    parser.add_argument(
        '--asn',
        type=int,
        required=True,
        help='Local AS number'
    )
    parser.add_argument(
        '--router-id',
        default=None,
        help='Router ID (default: derived from ASN)'
    )

    args = parser.parse_args()

    # Configuration
    exabgp_host = '127.0.0.1'
    exabgp_port = args.port
    local_asn = args.asn
    peer_asn = 65000  # ExaBGP's ASN
    router_id = args.router_id or f'1.2.3.{local_asn % 256}'

    log(args.name, '='*70)
    log(args.name, f'BGP Client Speaker: {args.name}')
    log(args.name, '='*70)

    # Connect to ExaBGP
    log(args.name, f'Connecting to ExaBGP at {exabgp_host}:{exabgp_port}')
    log(args.name, f'Local ASN: {local_asn}, Peer ASN: {peer_asn}, Router-ID: {router_id}')

    try:
        sock = connect_to_peer(
            exabgp_host,
            exabgp_port,
            local_asn=local_asn,
            peer_asn=peer_asn,
            router_id=router_id,
            timeout=10
        )
        log(args.name, 'BGP session established successfully')

    except Exception as e:
        log(args.name, f'ERROR: Failed to establish BGP session: {e}')
        return 1

    # Wait briefly for session to stabilize
    time.sleep(1)

    # Receive routes
    try:
        receive_routes(sock, args.name, keepalive_interval=60)
    except Exception as e:
        log(args.name, f'ERROR: {e}')
    finally:
        log(args.name, 'Closing BGP session')
        sock.close()
        log(args.name, 'Exited')

    return 0


if __name__ == '__main__':
    sys.exit(main())
