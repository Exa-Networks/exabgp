# encoding: utf-8
"""
sr/__init__.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

# draft-ietf-idr-bgp-prefix-sid

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
