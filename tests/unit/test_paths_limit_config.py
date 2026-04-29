#!/usr/bin/env python3
# encoding: utf-8
"""test_paths_limit_config.py

Tests for PATHS-LIMIT configuration via add-path { ... limit N; } syntax.

License: 3-clause BSD
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI


def _parse(cfg: str) -> tuple[bool, Configuration]:
    c = Configuration([cfg], text=True)
    ok = c.reload()
    return ok, c


def _neighbor(addpath_body: str, families: str = 'ipv4 unicast;') -> str:
    return f"""neighbor 127.0.0.1 {{
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as 65500;
    peer-as 65500;
    capability {{
        add-path send/receive;
    }}
    family {{ {families} }}
    add-path {{
        {addpath_body}
    }}
}}"""


class TestAddPathWithLimit:
    def test_family_without_limit(self) -> None:
        ok, c = _parse(_neighbor('ipv4 unicast;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {}

    def test_family_with_limit(self) -> None:
        ok, c = _parse(_neighbor('ipv4 unicast limit 10;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 10}

    def test_mixed_limit_and_no_limit(self) -> None:
        ok, c = _parse(
            _neighbor(
                'ipv4 unicast limit 10;\n        ipv6 unicast;',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 10}

    def test_multiple_families_with_limits(self) -> None:
        ok, c = _parse(
            _neighbor(
                'ipv4 unicast limit 10;\n        ipv6 unicast limit 20;',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {
            (AFI.ipv4, SAFI.unicast): 10,
            (AFI.ipv6, SAFI.unicast): 20,
        }

    def test_max_limit_value(self) -> None:
        ok, c = _parse(_neighbor('ipv4 unicast limit 65535;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 65535}

    def test_limit_one(self) -> None:
        ok, c = _parse(_neighbor('ipv4 unicast limit 1;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 1}

    def test_l2vpn_evpn_with_limit(self) -> None:
        ok, c = _parse(
            _neighbor(
                'l2vpn evpn limit 5;',
                families='l2vpn evpn;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.l2vpn, SAFI.evpn): 5}


class TestAddPathLimitValidation:
    def test_limit_zero_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast limit 0;'))
        assert not ok

    def test_limit_negative_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast limit -1;'))
        assert not ok

    def test_limit_overflow_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast limit 70000;'))
        assert not ok

    def test_limit_non_numeric_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast limit foo;'))
        assert not ok

    def test_duplicate_family_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast limit 5;\n        ipv4 unicast limit 10;'))
        assert not ok

    def test_invalid_safi_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 frobnicate limit 5;'))
        assert not ok

    def test_unexpected_token_rejected(self) -> None:
        ok, _ = _parse(_neighbor('ipv4 unicast 10;'))
        assert not ok


class TestAddPathLimitFamilyNegotiation:
    def test_unnegotiated_family_skipped(self) -> None:
        ok, c = _parse(
            _neighbor(
                'ipv6 unicast limit 5;',
                families='ipv4 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {}

    def test_mix_negotiated_and_unnegotiated(self) -> None:
        ok, c = _parse(
            _neighbor(
                'ipv4 unicast limit 7;\n        ipv6 unicast limit 5;',
                families='ipv4 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 7}


class TestCapabilityEmission:
    def test_limit_emits_paths_limit_capability(self) -> None:
        ok, c = _parse(
            _neighbor(
                'ipv4 unicast limit 8;\n        ipv6 unicast limit 12;',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))

        from exabgp.bgp.message.open.capability import Capabilities, Capability
        from exabgp.bgp.message.open.capability.pathslimit import PathsLimit

        caps = Capabilities()
        caps.new(n, restarted=False)
        pl = caps.get(Capability.CODE.PATHS_LIMIT)
        assert isinstance(pl, PathsLimit)
        assert pl[(AFI.ipv4, SAFI.unicast)] == 8
        assert pl[(AFI.ipv6, SAFI.unicast)] == 12

    def test_no_limit_no_paths_limit_capability(self) -> None:
        ok, c = _parse(_neighbor('ipv4 unicast;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))

        from exabgp.bgp.message.open.capability import Capabilities, Capability

        caps = Capabilities()
        caps.new(n, restarted=False)
        assert caps.get(Capability.CODE.PATHS_LIMIT) is None

    def test_no_addpath_block_no_paths_limit_capability(self) -> None:
        cfg = """neighbor 127.0.0.1 {
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as 65500;
    peer-as 65500;
    capability {
        add-path send/receive;
    }
    family { ipv4 unicast; }
}"""
        ok, c = _parse(cfg)
        assert ok, c.error
        n = next(iter(c.neighbors.values()))

        from exabgp.bgp.message.open.capability import Capabilities, Capability

        caps = Capabilities()
        caps.new(n, restarted=False)
        assert caps.get(Capability.CODE.PATHS_LIMIT) is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
