# encoding: utf-8
"""
hashtable.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


class HashTable(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key.replace('_', '-'))

    def __setitem__(self, key, value):
        return dict.__setitem__(self, key.replace('_', '-'), value)

    def __getattr__(self, key):
        return dict.__getitem__(self, key.replace('_', '-'))

    def __setattr__(self, key, value):
        return dict.__setitem__(self, key.replace('_', '-'), value)
