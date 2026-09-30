"""localpref.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.unsigned import UnsignedAttribute

# ========================================================= Local Preference (5)
#


class LocalPreference(UnsignedAttribute):
    """LOCAL_PREF, RFC 4271 5.1.5: four octets, higher is preferred."""

    ID: ClassVar = Attribute.CODE.LOCAL_PREF
    FLAG: ClassVar = Attribute.Flag.TRANSITIVE
    CACHING: ClassVar[bool] = True
    TREAT_AS_WITHDRAW: ClassVar[bool] = True
    MANDATORY: ClassVar[bool] = True
    WIDTH: ClassVar[int] = 4
    NAME: ClassVar[str] = 'LocalPreference'

    @property
    def localpref(self) -> int:
        return self.value


Attribute.register()(LocalPreference)
