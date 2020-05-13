# encoding: utf-8
"""
od.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


def od(value):
    def spaced(value):
        even = None
        for v in value:
            if even is False:
                yield ' '
            yield '%02X' % v
            even = not even

    return ''.join(spaced(value))
