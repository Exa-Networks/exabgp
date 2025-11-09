from __future__ import annotations

import sys
import pdb  # noqa: T100

from exabgp.environment import getenv


class Error(Exception):
    def __init__(self):
        self.message = ''
        self.debug = getenv().debug.configuration

    def set(self, message):
        self.message = message
        if self.debug:
            error = False
            sys.stdout.write('\n{}\n'.format(self.message))
            pdb.set_trace()  # noqa: T100
            return error
        return False

    def throw(self, message):
        self.message = message
        if self.debug:
            sys.stdout.write('\n{}\n'.format(message))
            pdb.set_trace()  # noqa: T100
        else:
            raise self

    def clear(self):
        self.message = ''

    def __repr__(self):
        return self.message

    def __str__(self):
        return self.message
