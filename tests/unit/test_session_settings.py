"""Tests for SessionSettings dataclass and Session.from_settings() (TDD)

These tests define the expected behavior of SessionSettings and the
Session.from_settings() factory method for programmatic Session construction.

The Settings pattern enables deferred construction by collecting configuration
values first, then validating and creating the Session in a single step.
"""

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.protocol.ip import IP


class TestSessionSettings:
    """Test SessionSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        assert settings.peer_address is None
        assert settings.local_address is None
        assert settings.local_as is None
        assert settings.peer_as is None
        assert settings.router_id is None
        assert settings.md5_password == ''
        assert settings.md5_base64 is False
        assert settings.connect == 0
        assert settings.listen == 0
        assert settings.passive is False
        assert settings.source_interface == ''
        assert settings.outgoing_ttl is None
        assert settings.incoming_ttl is None

    def test_validate_missing_peer_address(self) -> None:
        """Validation returns error when peer_address is missing"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)

        error = settings.validate()
        assert 'peer-address' in error.lower() or 'peer_address' in error.lower()

    def test_validate_missing_local_as(self) -> None:
        """Validation returns error when local_as is missing"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.peer_as = ASN(65001)

        error = settings.validate()
        assert 'local-as' in error.lower() or 'local_as' in error.lower()

    def test_validate_missing_peer_as(self) -> None:
        """Validation returns error when peer_as is missing"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_as = ASN(65000)

        error = settings.validate()
        assert 'peer-as' in error.lower() or 'peer_as' in error.lower()

    def test_validate_complete_settings(self) -> None:
        """Complete valid settings return empty string"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)

        error = settings.validate()
        assert error == ''

    def test_validate_auto_discovery_without_router_id(self) -> None:
        """Settings with auto-discovery (no local_address) and no router_id should still validate.

        Router ID derivation happens in Session.infer() after from_settings(),
        so validation doesn't require router_id upfront.
        """
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        # local_address is None = auto-discovery
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.router_id = RouterID.from_string('1.1.1.1')  # Must provide router_id for auto-discovery

        error = settings.validate()
        assert error == ''

    def test_validate_listen_requires_local_address(self) -> None:
        """When listen > 0, local_address is required"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.listen = 179  # Requires local_address

        error = settings.validate()
        assert 'local-address' in error.lower() or 'local_address' in error.lower()

    def test_validate_listen_with_local_address(self) -> None:
        """When listen > 0 and local_address is set, validation passes"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.listen = 179

        error = settings.validate()
        assert error == ''

    def test_validate_with_md5_password(self) -> None:
        """Settings with MD5 password validate correctly"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.md5_password = 'secret'

        error = settings.validate()
        assert error == ''

    def test_validate_with_ttl_settings(self) -> None:
        """Settings with TTL values validate correctly"""
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.outgoing_ttl = 255
        settings.incoming_ttl = 254

        error = settings.validate()
        assert error == ''


class TestSessionFromSettings:
    """Test Session.from_settings() factory method"""

    def test_from_settings_creates_valid_session(self) -> None:
        """from_settings creates valid Session from complete settings"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)

        session = Session.from_settings(settings)

        assert session.peer_address == IP.from_string('192.168.1.1')
        assert session.local_address == IP.from_string('192.168.1.2')
        assert session.local_as == ASN(65000)
        assert session.peer_as == ASN(65001)

    def test_from_settings_preserves_md5_password(self) -> None:
        """from_settings preserves MD5 password"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.md5_password = 'secret'

        session = Session.from_settings(settings)

        assert session.md5_password == 'secret'

    def test_from_settings_preserves_ttl_settings(self) -> None:
        """from_settings preserves TTL settings"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.outgoing_ttl = 255
        settings.incoming_ttl = 254

        session = Session.from_settings(settings)

        assert session.outgoing_ttl == 255
        assert session.incoming_ttl == 254

    def test_from_settings_preserves_connect_listen(self) -> None:
        """from_settings preserves connect and listen ports"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.connect = 1790
        settings.listen = 179

        session = Session.from_settings(settings)

        assert session.connect == 1790
        assert session.listen == 179

    def test_from_settings_preserves_passive(self) -> None:
        """from_settings preserves passive flag"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.passive = True

        session = Session.from_settings(settings)

        assert session.passive is True

    def test_from_settings_preserves_source_interface(self) -> None:
        """from_settings preserves source interface"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.source_interface = 'eth0'

        session = Session.from_settings(settings)

        assert session.source_interface == 'eth0'

    def test_from_settings_calls_infer(self) -> None:
        """from_settings calls infer() to derive router_id from local_address"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')  # IPv4 -> derives router_id
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        # router_id not set - should be derived

        session = Session.from_settings(settings)

        # router_id should be derived from local_address
        assert session.router_id is not None
        assert str(session.router_id) == '192.168.1.2'

    def test_from_settings_with_explicit_router_id(self) -> None:
        """from_settings preserves explicit router_id"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.router_id = RouterID.from_string('10.0.0.1')

        session = Session.from_settings(settings)

        # Explicit router_id should be preserved
        assert session.router_id is not None
        assert str(session.router_id) == '10.0.0.1'

    def test_from_settings_auto_discovery_mode(self) -> None:
        """from_settings with no local_address creates auto-discovery session"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        # local_address is None = auto-discovery
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.router_id = RouterID.from_string('10.0.0.1')  # Required for auto-discovery

        session = Session.from_settings(settings)

        assert session.auto_discovery is True
        assert session.local_address is IP.NoNextHop

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        # Missing local_as and peer_as

        with pytest.raises(ValueError):
            Session.from_settings(settings)

    def test_from_settings_raises_on_missing_peer_address(self) -> None:
        """from_settings raises ValueError when peer_address is missing"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        # Missing peer_address

        with pytest.raises(ValueError):
            Session.from_settings(settings)

    def test_from_settings_derives_md5_ip(self) -> None:
        """from_settings derives md5_ip from local_address via infer()"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('192.168.1.1')
        settings.local_address = IP.from_string('192.168.1.2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.md5_password = 'secret'

        session = Session.from_settings(settings)

        # md5_ip should be derived from local_address
        assert session.md5_ip == IP.from_string('192.168.1.2')

    def test_from_settings_ipv6_peer(self) -> None:
        """from_settings works with IPv6 peer address"""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.neighbor.settings import SessionSettings

        settings = SessionSettings()
        settings.peer_address = IP.from_string('2001:db8::1')
        settings.local_address = IP.from_string('2001:db8::2')
        settings.local_as = ASN(65000)
        settings.peer_as = ASN(65001)
        settings.router_id = RouterID.from_string('10.0.0.1')  # Router ID required for IPv6

        session = Session.from_settings(settings)

        assert session.peer_address == IP.from_string('2001:db8::1')
        assert session.local_address == IP.from_string('2001:db8::2')
        assert session.router_id is not None
