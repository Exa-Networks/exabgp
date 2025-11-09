#!/usr/bin/env python3
# encoding: utf-8
"""
cache.py

Created by David Farrar on 2012-12-27.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import unittest

import time
from exabgp.util.cache import Cache


class TestCache(unittest.TestCase):
    def test_speed(self):
        class klass1:
            def __init__(self, data):
                pass

        class klass2(object):
            def __init__(self, data):
                pass

        class klass3:
            def __init__(self, data):
                self.a = data[0]
                self.b = data[1]
                self.c = data[2]
                self.d = data[3]
                self.e = data[4]

        class klass4:
            def __init__(self, data):
                self.a = data[0]
                self.b = data[1]
                self.c = data[2]
                self.d = data[3]
                self.e = data[4]

        class _kparent1:
            def __init__(self, data):
                self.a = data[0]
                self.b = data[1]

        class _kparent2(object):
            def __init__(self, data):
                self.a = data[0]
                self.b = data[1]

        class klass5(_kparent1):
            def __init__(self, data):
                _kparent1.__init__(self, data)
                self.c = data[2]
                self.d = data[3]
                self.e = data[4]

        class klass6(_kparent2):
            def __init__(self, data):
                _kparent2.__init__(self, data)
                self.c = data[2]
                self.d = data[3]
                self.e = data[4]

        class klass7(klass6):
            pass

        class klass8(klass6):
            def __init__(self, data):
                klass6.__init__(self, data)
                self.s = self.a + self.b + self.c + self.d + self.e

        class klass9(klass6):
            def __init__(self, data):
                klass6.__init__(self, data)
                self.s1 = self.a + self.b + self.c + self.d + self.e
                self.s2 = self.b + self.c + self.d + self.e
                self.s3 = self.c + self.d + self.e
                self.s4 = self.d + self.e
                self.s5 = self.a + self.b + self.c + self.d
                self.s6 = self.a + self.b + self.c
                self.s7 = self.a + self.b

        COUNT = 100000
        UNIQUE = 5000

        samples = set()
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:"|;<>?,./[]{}-=_+!@£$%^&*()'

        from random import choice

        while len(samples) != UNIQUE:
            samples.add(choice(chars) + choice(chars) + choice(chars) + choice(chars) + choice(chars))

        samples = list(samples)

        for klass in [klass1, klass2, klass3, klass4, klass5, klass6, klass7, klass8, klass9]:
            cache = {}

            start = time.time()
            for val in range(COUNT):
                val %= UNIQUE
                _ = klass(samples[val])
            end = time.time()
            time1 = end - start

            print(COUNT, 'iterations of', klass.__name__, 'with', UNIQUE, 'uniques classes')
            print('time instance %d' % time1)

            cache = Cache()
            start = time.time()
            for val in range(COUNT):
                val %= UNIQUE

                if val in cache:
                    _ = cache.retrieve(val)
                else:
                    _ = cache.cache(val, klass(samples[val]))

            end = time.time()
            time2 = end - start

            print(f'time cached  {time2}')
            print(f'speedup {time1 / time2:.3f}')
            print()
