# encoding: utf-8
"""
ordereddict.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


# ================================================================== OrderedDict
# This is only an hack until we drop support for python version < 2.7


class OrderedDict(dict):
    def __init__(self, args):
        dict.__init__(self, args)
        self._order = [_ for _, __ in args]

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._order.remove(key)

    def keys(self):
        return self._order

    def __iter__(self):
        return self.__next__()

    def __next__(self):
        for order in self._order:
            yield order


if __name__ == '__main__':
    d = OrderedDict(((10, 'ten'), (8, 'eight'), (6, 'six'), (4, 'four'), (2, 'two'), (0, 'boom')))
    for k in d:
        print(k)
