#!/usr/bin/env python3
"""
BGP Protocol Helpers
Simplified BGP message construction/parsing for lab use
Based on ExaBGP's qa/sbin/bgp test infrastructure
"""

import socket
import struct
from typing import List, Dict, Optional, Tuple, Any

class BGPMessage:
    """BGP message construction"""

    MARKER = b'\xff' * 16

    # Message types
    OPEN = 1
    UPDATE = 2
    NOTIFICATION = 3
    KEEPALIVE = 4

    @staticmethod
    def _pack_msg(msg_type: int, payload: bytes) -> bytes:
        """Pack BGP message with header (marker + length + type)"""
        length = 19 + len(payload)
        return BGPMessage.MARKER + struct.pack('!HB', length, msg_type) + payload

    @classmethod
    def open(cls, my_asn: int, router_id: str, hold_time: int = 180) -> bytes:
        """
        Construct OPEN message

        Args:
            my_asn: Local AS number
            router_id: Router ID (IPv4 address format)
            hold_time: Hold timer in seconds (default 180)

        Returns:
            Packed BGP OPEN message
        """
        version = 4
        router_id_bytes = socket.inet_aton(router_id)

        # Build capabilities
        capabilities = b''

        # Capability: ASN4 (RFC 6793) - Code 65, Length 4
        cap_asn4 = struct.pack('!BBI', 65, 4, my_asn)
        capabilities += cap_asn4

        # Capability: Route Refresh (RFC 2918) - Code 2, Length 0
        cap_rr = struct.pack('!BB', 2, 0)
        capabilities += cap_rr

        # Capability: Multiprotocol Extensions (RFC 4760) - Code 1
        # AFI=1 (IPv4), SAFI=1 (Unicast)
        cap_mp = struct.pack('!BBHBB', 1, 4, 1, 0, 1)
        capabilities += cap_mp

        # Optional Parameters (Type 2 = Capabilities)
        opt_params = struct.pack('!BB', 2, len(capabilities)) + capabilities

        # OPEN payload
        payload = (
            struct.pack('!B', version) +
            struct.pack('!H', min(my_asn, 23456)) +  # 2-byte ASN or AS_TRANS
            struct.pack('!H', hold_time) +
            router_id_bytes +
            struct.pack('!B', len(opt_params)) +
            opt_params
        )

        return cls._pack_msg(cls.OPEN, payload)

    @classmethod
    def keepalive(cls) -> bytes:
        """Construct KEEPALIVE message (no payload)"""
        return cls._pack_msg(cls.KEEPALIVE, b'')

    @classmethod
    def update(cls, withdrawn: List[str], attributes: Dict[str, Any], announced: List[str]) -> bytes:
        """
        Construct UPDATE message

        Args:
            withdrawn: List of withdrawn prefixes (e.g., ['1.0.0.0/8'])
            attributes: Dict of path attributes {
                'origin': 'igp' | 'egp' | 'incomplete',
                'as_path': [asn1, asn2, ...],
                'next_hop': '10.0.0.1'
            }
            announced: List of announced prefixes

        Returns:
            Packed BGP UPDATE message
        """
        # Encode withdrawn routes
        withdrawn_data = b''
        for prefix in withdrawn:
            withdrawn_data += cls._encode_nlri(prefix)

        # Encode path attributes
        attr_data = b''

        # ORIGIN (well-known mandatory) - Type Code 1
        origin_map = {'igp': 0, 'egp': 1, 'incomplete': 2}
        origin = origin_map.get(attributes.get('origin', 'igp'), 0)
        attr_data += struct.pack('!BBB', 0x40, 1, 1) + bytes([origin])

        # AS_PATH (well-known mandatory) - Type Code 2
        as_path = attributes.get('as_path', [])
        as_path_bytes = b''
        if as_path:
            # AS_SEQUENCE segment (type 2)
            as_path_bytes = struct.pack('!BB', 2, len(as_path))
            for asn in as_path:
                as_path_bytes += struct.pack('!I', asn)  # 4-byte ASN

        attr_flags = 0x40  # Transitive
        if len(as_path_bytes) > 255:
            attr_flags |= 0x10  # Extended length
            attr_data += struct.pack('!BBH', attr_flags, 2, len(as_path_bytes)) + as_path_bytes
        else:
            attr_data += struct.pack('!BBB', attr_flags, 2, len(as_path_bytes)) + as_path_bytes

        # NEXT_HOP (well-known mandatory) - Type Code 3
        next_hop = socket.inet_aton(attributes.get('next_hop', '0.0.0.0'))
        attr_data += struct.pack('!BBB', 0x40, 3, 4) + next_hop

        # Encode announced routes
        announced_data = b''
        for prefix in announced:
            announced_data += cls._encode_nlri(prefix)

        # Assemble UPDATE message
        payload = (
            struct.pack('!H', len(withdrawn_data)) + withdrawn_data +
            struct.pack('!H', len(attr_data)) + attr_data +
            announced_data
        )

        return cls._pack_msg(cls.UPDATE, payload)

    @staticmethod
    def _encode_nlri(prefix: str) -> bytes:
        """
        Encode IPv4 prefix as NLRI (Network Layer Reachability Information)

        Args:
            prefix: IPv4 prefix in CIDR notation (e.g., '192.168.0.0/24')

        Returns:
            Encoded NLRI bytes
        """
        ip, cidr = prefix.split('/')
        cidr = int(cidr)
        octets = [int(x) for x in ip.split('.')]

        # Determine how many octets are needed based on prefix length
        if cidr > 24:
            length = 4
        elif cidr > 16:
            length = 3
        elif cidr > 8:
            length = 2
        elif cidr > 0:
            length = 1
        else:
            length = 0

        # Pack: prefix_length + significant octets
        return bytes([cidr]) + bytes(octets[:length])


def connect_to_peer(host: str, port: int, local_asn: int, peer_asn: int,
                   router_id: Optional[str] = None, timeout: int = 10) -> socket.socket:
    """
    Connect to BGP peer and complete OPEN handshake

    Args:
        host: Peer IP address
        port: Peer TCP port
        local_asn: Local AS number
        peer_asn: Peer AS number (for validation)
        router_id: Local router ID (default: derived from ASN)
        timeout: Connection timeout in seconds

    Returns:
        Connected socket with established BGP session

    Raises:
        ConnectionError: If connection or handshake fails
        ValueError: If OPEN handshake fails
    """
    if router_id is None:
        # Generate router-id from local_asn
        router_id = f'1.2.3.{local_asn % 256}'

    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    try:
        # Connect to peer
        sock.connect((host, port))

        # Send OPEN message
        open_msg = BGPMessage.open(local_asn, router_id, hold_time=180)
        sock.sendall(open_msg)

        # Receive OPEN message from peer
        recv_open = sock.recv(4096)
        if len(recv_open) < 19 or recv_open[18] != BGPMessage.OPEN:
            raise ValueError(f'Expected OPEN message, got type {recv_open[18] if len(recv_open) > 18 else "unknown"}')

        # Send KEEPALIVE to complete handshake
        keepalive = BGPMessage.keepalive()
        sock.sendall(keepalive)

        # Receive KEEPALIVE from peer
        recv_ka = sock.recv(4096)
        if len(recv_ka) < 19 or recv_ka[18] != BGPMessage.KEEPALIVE:
            raise ValueError(f'Expected KEEPALIVE message, got type {recv_ka[18] if len(recv_ka) > 18 else "unknown"}')

        # BGP session established
        return sock

    except Exception as e:
        sock.close()
        raise ConnectionError(f'Failed to establish BGP session: {e}')


def send_bgp(sock: socket.socket, message: bytes) -> None:
    """
    Send BGP message over socket

    Args:
        sock: Connected socket
        message: BGP message bytes
    """
    sock.sendall(message)


def recv_bgp(sock: socket.socket, timeout: Optional[int] = None) -> Optional[bytes]:
    """
    Receive complete BGP message from socket

    Args:
        sock: Connected socket
        timeout: Receive timeout in seconds (None = blocking)

    Returns:
        Complete BGP message or None on timeout/EOF
    """
    if timeout is not None:
        sock.settimeout(timeout)

    try:
        # Read BGP header (19 bytes: 16 marker + 2 length + 1 type)
        header = b''
        while len(header) < 19:
            chunk = sock.recv(19 - len(header))
            if not chunk:
                return None  # Connection closed
            header += chunk

        # Validate marker
        if header[:16] != BGPMessage.MARKER:
            raise ValueError('Invalid BGP marker')

        # Extract message length
        length = struct.unpack('!H', header[16:18])[0]

        # Read message body
        body = b''
        body_len = length - 19
        while len(body) < body_len:
            chunk = sock.recv(body_len - len(body))
            if not chunk:
                return None  # Connection closed
            body += chunk

        return header + body

    except socket.timeout:
        return None


def parse_update(message: bytes) -> List[Dict[str, Any]]:
    """
    Parse BGP UPDATE message and extract announced routes

    Args:
        message: Complete BGP UPDATE message

    Returns:
        List of route dictionaries: [
            {'prefix': '8.8.8.0/24', 'as_path': [15169, 65001], 'next_hop': '10.0.0.1'},
            ...
        ]
    """
    if len(message) < 23:
        return []

    offset = 19  # Skip BGP header

    # Withdrawn routes length
    withdrawn_len = struct.unpack('!H', message[offset:offset+2])[0]
    offset += 2 + withdrawn_len

    # Path attributes length
    attr_len = struct.unpack('!H', message[offset:offset+2])[0]
    offset += 2

    # Parse path attributes
    attributes = {}
    attr_end = offset + attr_len

    while offset < attr_end:
        flags = message[offset]
        attr_type = message[offset + 1]

        # Extended length flag?
        if flags & 0x10:
            attr_value_len = struct.unpack('!H', message[offset+2:offset+4])[0]
            attr_value = message[offset+4:offset+4+attr_value_len]
            offset += 4 + attr_value_len
        else:
            attr_value_len = message[offset + 2]
            attr_value = message[offset+3:offset+3+attr_value_len]
            offset += 3 + attr_value_len

        # Parse AS_PATH (type 2)
        if attr_type == 2:
            as_path = []
            idx = 0
            while idx < len(attr_value):
                attr_value[idx]
                seg_len = attr_value[idx + 1]
                idx += 2
                for _ in range(seg_len):
                    asn = struct.unpack('!I', attr_value[idx:idx+4])[0]
                    as_path.append(asn)
                    idx += 4
            attributes['as_path'] = as_path

        # Parse NEXT_HOP (type 3)
        elif attr_type == 3:
            next_hop_bytes = attr_value[:4]
            next_hop = socket.inet_ntoa(next_hop_bytes)
            attributes['next_hop'] = next_hop

    # Parse announced NLRIs
    routes = []
    while offset < len(message):
        cidr = message[offset]
        offset += 1

        # Calculate prefix bytes needed
        if cidr > 24:
            prefix_bytes = 4
        elif cidr > 16:
            prefix_bytes = 3
        elif cidr > 8:
            prefix_bytes = 2
        elif cidr > 0:
            prefix_bytes = 1
        else:
            prefix_bytes = 0

        # Read prefix octets
        ip_bytes = message[offset:offset+prefix_bytes]
        offset += prefix_bytes

        # Reconstruct IP address
        ip_parts = list(ip_bytes) + [0] * (4 - len(ip_bytes))
        prefix = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}/{cidr}"

        routes.append({
            'prefix': prefix,
            'as_path': attributes.get('as_path', []),
            'next_hop': attributes.get('next_hop', '0.0.0.0')
        })

    return routes


def format_prefix(prefix: str) -> Tuple[str, int]:
    """
    Split prefix into IP and CIDR

    Args:
        prefix: IPv4 prefix (e.g., '192.168.0.0/24')

    Returns:
        Tuple of (ip_address, cidr_length)
    """
    parts = prefix.split('/')
    return parts[0], int(parts[1])
