"""Tests for bgp.neighbor.session module."""

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.neighbor.session import Session
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPv4, IPv6


class TestSessionDefaults:
    """Test Session default values."""

    def test_default_session(self) -> None:
        """Test Session has correct default values."""
        session = Session()

        assert session.peer_address is IP.NoNextHop
        assert session.local_address is IP.NoNextHop
        assert session.local_as == ASN(0)
        assert session.peer_as == ASN(0)
        assert session.router_id is None
        assert session.md5_password == ''
        assert session.md5_base64 is False
        assert session.md5_ip is None
        # TCP-AO defaults
        assert session.tcp_ao_keyid is None
        assert session.tcp_ao_algorithm == ''
        assert session.tcp_ao_password == ''
        assert session.tcp_ao_base64 is False
        assert session.connect == 0
        assert session.listen == 0
        assert session.passive is False
        assert session.source_interface == ''
        assert session.outgoing_ttl is None
        assert session.incoming_ttl is None

    def test_auto_discovery_default(self) -> None:
        """Test auto_discovery is True when local_address is NoNextHop."""
        session = Session()
        assert session.auto_discovery is True

    def test_auto_discovery_when_local_set(self) -> None:
        """Test auto_discovery is False when local_address is set."""
        session = Session(local_address=IPv4.from_string('192.168.1.1'))
        assert session.auto_discovery is False


class TestSessionMissing:
    """Test Session.missing() validation."""

    def test_missing_peer_address(self) -> None:
        """Test missing returns 'peer-address' when not set."""
        session = Session()
        assert session.missing() == 'peer-address'

    def test_missing_router_id_auto_discovery(self) -> None:
        """Test missing returns 'router-id' in auto_discovery mode."""
        session = Session(peer_address=IPv4.from_string('192.168.1.2'))
        assert session.missing() == 'router-id'

    def test_missing_router_id_ipv6(self) -> None:
        """Test missing returns 'router-id' for IPv6 peer."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::1'),
            local_address=IPv6.from_string('2001:db8::2'),
        )
        assert session.missing() == 'router-id'

    def test_missing_local_address_listen(self) -> None:
        """Test missing returns 'local-address' when listen set with auto_discovery."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            listen=179,
            router_id=RouterID('1.2.3.4'),
        )
        assert session.missing() == 'local-address'

    def test_complete_session(self) -> None:
        """Test missing returns '' for complete session."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
            router_id=RouterID('1.2.3.4'),
        )
        assert session.missing() == ''


class TestSessionInfer:
    """Test Session.infer() for derived values."""

    def test_infer_md5_ip_from_local(self) -> None:
        """Test infer sets md5_ip from local_address."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
        )
        assert session.md5_ip is None

        session.infer()

        assert session.md5_ip == IPv4.from_string('192.168.1.1')

    def test_infer_no_md5_ip_auto_discovery(self) -> None:
        """Test infer does not set md5_ip in auto_discovery mode."""
        session = Session(peer_address=IPv4.from_string('192.168.1.2'))

        session.infer()

        assert session.md5_ip is None


class TestSessionIpSelf:
    """Test Session.ip_self() for next-hop self resolution."""

    def test_ip_self_ipv4(self) -> None:
        """Test ip_self returns local_address for matching AFI."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
        )
        assert session.ip_self(AFI.ipv4) == IPv4.from_string('192.168.1.1')

    def test_ip_self_ipv6(self) -> None:
        """Test ip_self returns local_address for IPv6."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::2'),
            local_address=IPv6.from_string('2001:db8::1'),
        )
        assert session.ip_self(AFI.ipv6) == IPv6.from_string('2001:db8::1')

    def test_ip_self_fallback_to_router_id(self) -> None:
        """Test ip_self returns router_id for IPv4 when peer is IPv6."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::2'),
            local_address=IPv6.from_string('2001:db8::1'),
            router_id=RouterID('1.2.3.4'),
        )
        # IPv4 route with IPv6 session - use router_id
        assert session.ip_self(AFI.ipv4) == RouterID('1.2.3.4')

    def test_ip_self_error_mismatch(self) -> None:
        """Test ip_self raises TypeError for AFI mismatch."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
        )
        with pytest.raises(TypeError, match='next-hop self'):
            session.ip_self(AFI.ipv6)


class TestSessionValidateMd5:
    """Test Session.validate_md5() for MD5 password validation."""

    def test_validate_md5_empty_password(self) -> None:
        """Test validate_md5 returns empty for no password."""
        session = Session()
        assert session.validate_md5() == ''

    def test_validate_md5_valid_password(self) -> None:
        """Test validate_md5 returns empty for valid password."""
        session = Session(md5_password='my-secret-password')
        assert session.validate_md5() == ''

    def test_validate_md5_valid_base64(self) -> None:
        """Test validate_md5 returns empty for valid base64 password."""
        import base64

        password = base64.b64encode(b'my-secret').decode()
        session = Session(md5_password=password, md5_base64=True)
        assert session.validate_md5() == ''

    def test_validate_md5_invalid_base64(self) -> None:
        """Test validate_md5 returns error for invalid base64."""
        session = Session(md5_password='not-valid-base64!!!', md5_base64=True)
        error = session.validate_md5()
        assert 'Invalid base64' in error

    def test_validate_md5_password_too_long(self) -> None:
        """Test validate_md5 returns error for password > 80 chars."""
        session = Session(md5_password='x' * 81)
        error = session.validate_md5()
        assert '80' in error


class TestSessionValidateTcpAo:
    """Test Session.validate_tcp_ao() for TCP-AO validation."""

    def test_validate_tcp_ao_empty_password(self) -> None:
        """Test validate_tcp_ao returns empty for no password."""
        session = Session()
        assert session.validate_tcp_ao() == ''

    def test_validate_tcp_ao_valid_config(self) -> None:
        """Test validate_tcp_ao returns empty for valid config."""
        session = Session(
            tcp_ao_password='my-secret-key',
            tcp_ao_keyid=1,
            tcp_ao_algorithm='hmac-sha-256',
        )
        assert session.validate_tcp_ao() == ''

    def test_validate_tcp_ao_all_algorithms(self) -> None:
        """Test validate_tcp_ao accepts all valid algorithms."""
        for algorithm in ['hmac-sha-1-96', 'aes-128-cmac-96', 'hmac-sha-256']:
            session = Session(
                tcp_ao_password='secret',
                tcp_ao_keyid=1,
                tcp_ao_algorithm=algorithm,
            )
            assert session.validate_tcp_ao() == '', f'Algorithm {algorithm} should be valid'

    def test_validate_tcp_ao_invalid_algorithm(self) -> None:
        """Test validate_tcp_ao returns error for invalid algorithm."""
        session = Session(
            tcp_ao_password='secret',
            tcp_ao_keyid=1,
            tcp_ao_algorithm='invalid-algo',
        )
        error = session.validate_tcp_ao()
        assert 'Invalid TCP-AO algorithm' in error

    def test_validate_tcp_ao_missing_keyid(self) -> None:
        """Test validate_tcp_ao returns error when keyid missing."""
        session = Session(
            tcp_ao_password='secret',
            tcp_ao_algorithm='hmac-sha-256',
        )
        error = session.validate_tcp_ao()
        assert 'keyid is required' in error

    def test_validate_tcp_ao_missing_algorithm(self) -> None:
        """Test validate_tcp_ao returns error when algorithm missing."""
        session = Session(
            tcp_ao_password='secret',
            tcp_ao_keyid=1,
        )
        error = session.validate_tcp_ao()
        assert 'algorithm is required' in error

    def test_validate_tcp_ao_keyid_range(self) -> None:
        """Test validate_tcp_ao validates keyid 0-255."""
        # Valid keyids
        for keyid in [0, 1, 127, 255]:
            session = Session(
                tcp_ao_password='secret',
                tcp_ao_keyid=keyid,
                tcp_ao_algorithm='hmac-sha-256',
            )
            assert session.validate_tcp_ao() == '', f'keyid {keyid} should be valid'

        # Invalid keyid
        session = Session(
            tcp_ao_password='secret',
            tcp_ao_keyid=256,
            tcp_ao_algorithm='hmac-sha-256',
        )
        error = session.validate_tcp_ao()
        assert '0-255' in error

    def test_validate_tcp_ao_key_too_long(self) -> None:
        """Test validate_tcp_ao returns error for key > 80 bytes."""
        session = Session(
            tcp_ao_password='x' * 81,
            tcp_ao_keyid=1,
            tcp_ao_algorithm='hmac-sha-256',
        )
        error = session.validate_tcp_ao()
        assert '80' in error

    def test_validate_tcp_ao_valid_base64(self) -> None:
        """Test validate_tcp_ao returns empty for valid base64 key."""
        import base64

        key = base64.b64encode(b'my-secret-key').decode()
        session = Session(
            tcp_ao_password=key,
            tcp_ao_keyid=1,
            tcp_ao_algorithm='hmac-sha-256',
            tcp_ao_base64=True,
        )
        assert session.validate_tcp_ao() == ''

    def test_validate_tcp_ao_invalid_base64(self) -> None:
        """Test validate_tcp_ao returns error for invalid base64."""
        session = Session(
            tcp_ao_password='not-valid-base64!!!',
            tcp_ao_keyid=1,
            tcp_ao_algorithm='hmac-sha-256',
            tcp_ao_base64=True,
        )
        error = session.validate_tcp_ao()
        assert 'Invalid base64' in error

    def test_validate_tcp_ao_mutual_exclusion_with_md5(self) -> None:
        """Test TCP-AO and MD5 are mutually exclusive."""
        session = Session(
            md5_password='md5secret',
            tcp_ao_password='aosecret',
            tcp_ao_keyid=1,
            tcp_ao_algorithm='hmac-sha-256',
        )
        # Both validations should return mutual exclusion error
        tcp_ao_error = session.validate_tcp_ao()
        md5_error = session.validate_md5()
        assert 'mutually exclusive' in tcp_ao_error
        assert 'mutually exclusive' in md5_error


class TestSessionConnectionEstablished:
    """Test Session.connection_established() for auto-discovery."""

    def test_connection_established_auto_discovery(self) -> None:
        """Test connection_established sets local_address in auto_discovery."""
        session = Session(peer_address=IPv4.from_string('192.168.1.2'))
        assert session.auto_discovery is True

        session.connection_established('192.168.1.1')

        assert session.local_address == IPv4.from_string('192.168.1.1')
        assert session.auto_discovery is False

    def test_connection_established_sets_router_id(self) -> None:
        """Test connection_established sets router_id for IPv4."""
        session = Session(peer_address=IPv4.from_string('192.168.1.2'))

        session.connection_established('192.168.1.1')

        assert session.router_id == RouterID('192.168.1.1')

    def test_connection_established_sets_md5_ip(self) -> None:
        """Test connection_established sets md5_ip."""
        session = Session(peer_address=IPv4.from_string('192.168.1.2'))

        session.connection_established('192.168.1.1')

        assert session.md5_ip == IPv4.from_string('192.168.1.1')
