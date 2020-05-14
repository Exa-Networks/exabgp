# encoding: utf-8
"""
hashtable.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


def _(key):
    return key.replace('_', '-')


class HashTable(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, _(key))

    def __setitem__(self, key, value):
        return dict.__setitem__(self, _(key), value)

    def __getattr__(self, key):
        return dict.__getitem__(self, _(key))

    def __setattr__(self, key, value):
        return dict.__setitem__(self, _(key), value)


class GlobalHashTable(HashTable):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalHashTable, cls).__new__(cls)
        return cls._instance
