"""med.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.unsigned import UnsignedAttribute

# ====================================================================== MED (4)
#


@Attribute.register()
class MED(UnsignedAttribute):
    """Multi-Exit Discriminator, RFC 4271 5.1.4: four octets."""

    ID = Attribute.CODE.MED
    FLAG = Attribute.Flag.OPTIONAL
    CACHING = True
    TREAT_AS_WITHDRAW = True
    WIDTH = 4
    NAME = 'MED'

    @property
    def med(self) -> int:
        return self.value
