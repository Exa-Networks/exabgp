"""The EOR an API process is told about has to be JSON it can parse.

EOR_NLRI.json() used to return a bare '"eor": {...}' key and value. The
caller puts every NLRI rendering into a list, so the line an API process
received for an end of RIB marker could not be parsed at all.
"""

from __future__ import annotations

import json

import pytest

from exabgp.bgp.message.update.eor import EOR
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.reactor.api.response.json import JSON


def test_eor_nlri_json_is_an_object():
    nlri = EOR.EOR_NLRI(AFI.ipv4, SAFI.unicast)

    rendered = json.loads(nlri.json())

    assert rendered == {'eor': {'afi': 'ipv4', 'safi': 'unicast'}}


def test_eor_nlri_json_survives_being_put_in_a_list():
    # this is what the API response builder does with every NLRI
    nlris = [EOR.EOR_NLRI(AFI.ipv6, SAFI.unicast).json()]

    rendered = json.loads('[ {} ]'.format(', '.join(nlris)))

    assert rendered == [{'eor': {'afi': 'ipv6', 'safi': 'unicast'}}]


@pytest.mark.parametrize('v4', [False, True])
@pytest.mark.parametrize('afi,safi', [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast), (AFI.l2vpn, SAFI.evpn)])
def test_an_eor_is_its_own_message(v4: bool, afi: AFI, safi: SAFI) -> None:
    # 5.x and 4.2 told a helper `"message": { "eor": {...} }`. Filed as an announced route
    # with a "null" next-hop, a helper written for them never saw its End-of-RIB.
    encoder = JSON('test')
    encoder.use_v4_json = v4

    message = json.loads(encoder._update(EOR.make_eor(afi, safi).data)['message'])

    assert message == {'eor': {'afi': str(afi), 'safi': str(safi)}}
