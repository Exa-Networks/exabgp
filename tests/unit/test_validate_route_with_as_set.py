"""`configuration validate` takes a route whose AS_PATH holds an AS_SET.

The validator packs each route and decodes the bytes again to compare them. It decoded
them as a receiver would, and RFC 9774 has a receiver treat a route with an AS_SET as
withdrawn, so the route came back with no next-hop, and re-encoding it raised
`ValueError: announce requires nexthop` out of the validator. Sending one is the operator's
choice (qa/rfc/rfc9774.toml), so the bytes are decoded as what we send.
"""

import pytest

from exabgp.configuration.check import check_generation
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def _configured(as_path: str) -> Configuration:
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65000;
            peer-as 65001;
            family {{ ipv4 unicast; }}
            static {{ route 10.0.0.0/24 next-hop 192.0.2.2 as-path {as_path}; }}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return config


def test_a_route_with_an_as_set_validates() -> None:
    assert check_generation(_configured('[ 65000 ] ( 65002 65003 )').neighbors)


def test_a_route_with_an_as_sequence_still_validates() -> None:
    assert check_generation(_configured('[ 65000 65002 ]').neighbors)
