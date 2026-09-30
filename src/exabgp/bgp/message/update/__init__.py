"""exabgp.bgp.message.update

The package: its code is in update.py, where mypyc can compile it (plan/wip-mypyc.md).
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.update import (
    MPNLRICollection,
    NLRICollection,
    Update,
    UpdateCollection,
    UpdateWire,
)

# EOR is an Update, so it is imported once Update is
from exabgp.bgp.message.update.eor import EOR  # noqa: E402

__all__ = [
    'AttributeCollection',
    'EOR',
    'MPNLRICollection',
    'NLRICollection',
    'Update',
    'UpdateCollection',
    'UpdateWire',
]
