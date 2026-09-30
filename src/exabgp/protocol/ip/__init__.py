"""exabgp.protocol.ip

The package: its code is in address.py, where mypyc can compile it (plan/wip-mypyc.md).
"""

from __future__ import annotations

from exabgp.protocol.ip.address import (
    IP,
    IPBase,
    IPFactory,
    IPRange,
    IPSelf,
    IPT,
    IPv4,
    IPv6,
)

__all__ = [
    'IP',
    'IPBase',
    'IPFactory',
    'IPRange',
    'IPSelf',
    'IPT',
    'IPv4',
    'IPv6',
]
