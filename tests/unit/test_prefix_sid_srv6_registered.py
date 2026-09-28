"""An SRv6 service TLV of the Prefix-SID attribute is decoded whatever was imported first.

The package which registers the TLVs of the Prefix-SID (attribute/sr) imported the label
index and SRGB ones, not the SRv6 services: they were registered by whatever imported
attribute/sr/srv6, the legacy configuration parser. Once it was gone, a received SRv6 L3
service was shown as an attribute not implemented.
"""

from __future__ import annotations

import subprocess
import sys

# a Prefix-SID attribute holding an SRv6 L3 service TLV (type 5), from qa/decoding/vpnv4-extended-nexthop-1
PREFIX_SID = '05001900010015002001000100000000000000000000000000000000'


def test_the_prefix_sid_package_registers_the_srv6_services() -> None:
    """In a fresh interpreter, where nothing has imported the srv6 package already."""
    probe = (
        'from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid\n'
        f'attribute = PrefixSid.unpack_attribute(bytes.fromhex({PREFIX_SID!r}), None)\n'
        'print(attribute.json())\n'
    )
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, check=True)
    assert 'l3-service' in result.stdout, result.stdout + result.stderr
    assert 'not-implemented' not in result.stdout
