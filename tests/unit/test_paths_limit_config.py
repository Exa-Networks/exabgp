#!/usr/bin/env python3
# encoding: utf-8
"""test_paths_limit_config.py

Comprehensive tests for PATHS-LIMIT configuration parsing.

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


def _neighbor_template(extra_capability: str = '', extra_neighbor: str = '', families: str = 'ipv4 unicast;') -> str:
    return f"""neighbor 127.0.0.1 {{
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as 65500;
    peer-as 65500;
    capability {{
        add-path send/receive;
        {extra_capability}
    }}
    family {{ {families} }}
    {extra_neighbor}
}}"""


class TestSugarForm:
    def test_sugar_sets_default(self) -> None:
        ok, c = _parse(_neighbor_template('paths-limit 10;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 10
        assert n.capability.paths_limit_per_family == {}

    def test_sugar_zero_allowed(self) -> None:
        ok, c = _parse(_neighbor_template('paths-limit 0;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 0

    def test_sugar_max_uint16(self) -> None:
        ok, c = _parse(_neighbor_template('paths-limit 65535;'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 65535

    def test_sugar_negative_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit -1;'))
        assert not ok

    def test_sugar_overflow_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit 70000;'))
        assert not ok

    def test_sugar_non_numeric_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit foo;'))
        assert not ok


class TestBlockForm:
    def test_block_with_all_only(self) -> None:
        ok, c = _parse(_neighbor_template('paths-limit { all 7; }'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 7
        assert n.capability.paths_limit_per_family == {}

    def test_block_with_all_and_override(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { all 7; ipv4 unicast 32; }',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 7
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 32}

    def test_block_per_family_only_no_default(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { ipv4 unicast 5; ipv6 unicast 0; }',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 0  # untouched
        assert n.capability.paths_limit_per_family == {
            (AFI.ipv4, SAFI.unicast): 5,
            (AFI.ipv6, SAFI.unicast): 0,
        }

    def test_block_empty(self) -> None:
        ok, c = _parse(_neighbor_template('paths-limit { }'))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 0
        assert n.capability.paths_limit_per_family == {}

    def test_block_zero_per_family_disables(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { all 10; ipv6 unicast 0; }',
                families='ipv4 unicast; ipv6 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 10
        assert n.capability.paths_limit_per_family == {(AFI.ipv6, SAFI.unicast): 0}

    def test_block_multiple_families_across_afis(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { ipv4 unicast 10; ipv6 unicast 20; l2vpn evpn 5; }',
                families='ipv4 unicast; ipv6 unicast; l2vpn evpn;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {
            (AFI.ipv4, SAFI.unicast): 10,
            (AFI.ipv6, SAFI.unicast): 20,
            (AFI.l2vpn, SAFI.evpn): 5,
        }


class TestCombinationSemantics:
    def test_sugar_then_block_block_wins_with_merge(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit 5; paths-limit { all 9; ipv4 unicast 33; }',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 9
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 33}

    def test_block_then_sugar_sugar_overwrites(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { ipv4 unicast 33; } paths-limit 5;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit == 5
        assert n.capability.paths_limit_per_family == {}


class TestValidation:
    def test_block_duplicate_all_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { all 5; all 10; }'))
        assert not ok

    def test_block_duplicate_per_family_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { ipv4 unicast 5; ipv4 unicast 10; }'))
        assert not ok

    def test_block_per_family_overflow_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { ipv4 unicast 70000; }'))
        assert not ok

    def test_block_per_family_negative_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { ipv4 unicast -1; }'))
        assert not ok

    def test_block_all_negative_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { all -1; }'))
        assert not ok

    def test_block_all_overflow_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { all 70000; }'))
        assert not ok

    def test_block_invalid_safi_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { ipv4 frobnicate 5; }'))
        assert not ok

    def test_block_missing_limit_rejected(self) -> None:
        ok, _ = _parse(_neighbor_template('paths-limit { ipv4 unicast; }'))
        assert not ok


class TestFamilyNotNegotiated:
    def test_unnegotiated_family_silently_skipped(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { ipv6 mpls-vpn 5; }',
                families='ipv4 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {}

    def test_mix_negotiated_and_unnegotiated(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { ipv4 unicast 7; ipv6 mpls-vpn 5; }',
                families='ipv4 unicast;',
            )
        )
        assert ok, c.error
        n = next(iter(c.neighbors.values()))
        assert n.capability.paths_limit_per_family == {(AFI.ipv4, SAFI.unicast): 7}


class TestEmissionIntegration:
    def test_default_only_emits_for_all_addpath_families(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit 8;',
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
        assert pl[(AFI.ipv6, SAFI.unicast)] == 8

    def test_per_family_overrides_default(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { all 8; ipv6 unicast 32; }',
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
        assert pl[(AFI.ipv6, SAFI.unicast)] == 32

    def test_zero_per_family_excludes_from_wire(self) -> None:
        ok, c = _parse(
            _neighbor_template(
                'paths-limit { all 8; ipv6 unicast 0; }',
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
        assert (AFI.ipv4, SAFI.unicast) in pl
        assert (AFI.ipv6, SAFI.unicast) not in pl

    def test_no_paths_limit_no_capability_emitted(self) -> None:
        ok, c = _parse(_neighbor_template(''))
        assert ok, c.error
        n = next(iter(c.neighbors.values()))

        from exabgp.bgp.message.open.capability import Capabilities, Capability

        caps = Capabilities()
        caps.new(n, restarted=False)
        assert caps.get(Capability.CODE.PATHS_LIMIT) is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
