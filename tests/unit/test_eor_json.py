"""The EOR an API process is told about has to be JSON it can parse.

EOR_NLRI.json() used to return a bare '"eor": {...}' key and value. The
caller puts every NLRI rendering into a list, so the line an API process
received for an end of RIB marker could not be parsed at all.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.update.eor import EOR
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


def test_eor_nlri_json_is_an_object():
    nlri = EOR.EOR_NLRI(AFI.ipv4, SAFI.unicast)

    rendered = json.loads(nlri.json())

    assert rendered == {'eor': {'afi': 'ipv4', 'safi': 'unicast'}}


def test_eor_nlri_json_survives_being_put_in_a_list():
    # this is what the API response builder does with every NLRI
    nlris = [EOR.EOR_NLRI(AFI.ipv6, SAFI.unicast).json()]

    rendered = json.loads('[ {} ]'.format(', '.join(nlris)))

    assert rendered == [{'eor': {'afi': 'ipv6', 'safi': 'unicast'}}]
