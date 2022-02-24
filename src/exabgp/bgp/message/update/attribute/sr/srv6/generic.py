# encoding: utf-8
"""
srv6/generic.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

class GenericSrv6ServiceSubTlv:
    def __init__(self, code, packed):
        self.code = code
        self.packed = packed

    def __repr__(self):
        return "SRv6 Service Sub-TLV type %d not implemented" % self.code

    def json(self, compact=None):
        # TODO:
        return ""

    def pack(self):
        return self.packed

class GenericSrv6ServiceDataSubSubTlv:
    def __init__(self, code, packed):
        self.code = code
        self.packed = packed

    def __repr__(self):
        return "SRv6 Service Data Sub-Sub-TLV type %d not implemented" % self.code

    def json(self, compact=None):
        # TODO:
        return ""

    def pack(self):
        return self.packed
