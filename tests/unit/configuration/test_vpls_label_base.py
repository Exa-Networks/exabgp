"""The VPLS label base is a twenty bit MPLS label, not a sixteen bit number.

RFC 4761 3.2.2 gives the VPLS NLRI a two octet VE ID, VE Block Offset and VE Block Size,
and a three octet field holding the Label Base, a 20 bit label. The configuration capped
all four at 0xFFFF, so a label base above 65535, which the NLRI carries and VPLSSettings
accepts, could not be configured.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.configuration.configuration import Configuration

LINE = 'vpls endpoint 3 base {base} offset 1 size 8 rd 172.30.5.4:13 next-hop 192.0.2.1'


def configure(base: int) -> tuple[bool, Configuration]:
    configuration = Configuration([''], text=True)
    return configuration.partial('l2vpn', LINE.format(base=base), 'announce'), configuration


@pytest.mark.parametrize('base', [0x10000, 0xFFFFF - 8])
def test_a_label_base_above_sixteen_bits_is_configured(base: int) -> None:
    parsed, configuration = configure(base)
    assert parsed, str(configuration.error)
    (route,) = configuration.pop_routes()
    assert isinstance(route.nlri, VPLS)
    assert route.nlri.base == base


def test_a_label_base_above_twenty_bits_is_refused() -> None:
    parsed, _ = configure(0x100000)
    assert not parsed


@pytest.mark.parametrize('keyword', ['endpoint', 'offset', 'size'])
def test_the_two_octet_fields_stay_two_octets(keyword: str) -> None:
    values = {'endpoint': 3, 'offset': 1, 'size': 8, keyword: 65536}
    line = 'vpls endpoint {endpoint} base 1000 offset {offset} size {size} rd 1:1 next-hop 192.0.2.1'
    configuration = Configuration([''], text=True)
    assert not configuration.partial('l2vpn', line.format(**values), 'announce')
