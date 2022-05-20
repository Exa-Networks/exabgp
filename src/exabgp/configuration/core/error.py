import pdb

from exabgp.environment import getenv


class Error(Exception):
    def __init__(self):
        self.message = ''
        self.debug = getenv().debug.configuration

    def set(self, message):
        self.message = message
        if self.debug:
            error = False
            print('\n%s\n' % self.message)
            pdb.set_trace()
            return error
        return False

    def throw(self, message):
        self.message = message
        if self.debug:
            print('\n%s\n' % message)
            pdb.set_trace()
        else:
            raise self

    def clear(self):
        self.message = ''

    def __repr__(self):
        return self.message

    def __str__(self):
        return self.message
