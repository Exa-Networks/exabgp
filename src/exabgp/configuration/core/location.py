# encoding: utf-8
"""
location.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# ===================================================================== Location
# file location


class Location(object):
    def __init__(self, index_line=0, index_column=0, line=''):
        self.line = line
        self.index_line = index_line
        self.index_column = index_column

    def clear(self):
        self.index_line = 0
        self.index_column = 0
        self.line = ''


class Error(Exception):
    tabsize = 3
    syntax = ''

    def __init__(self, location, message, syntax=''):
        self.line = location.line.replace('\t', ' ' * self.tabsize)
        self.index_line = location.index_line
        self.index_column = location.index_column + (self.tabsize - 1) * location.line[: location.index_column].count(
            '\t'
        )

        self.message = '\n\n'.join(
            (
                'problem parsing configuration file line %d position %d'
                % (location.index_line, location.index_column + 1),
                'error message: %s' % message.replace('\t', ' ' * self.tabsize),
                '%s%s' % (self.line, '-' * self.index_column + '^'),
            )
        )
        # allow to give the right syntax in using Raised
        if syntax:
            self.message += '\n\n' + syntax

        Exception.__init__(self)

    def __repr__(self):
        return self.message
