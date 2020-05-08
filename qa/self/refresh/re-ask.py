#!/usr/bin/env python

from __future__ import print_function
import sys
import signal


class TimeError(Exception):
    pass


def handler(signum, frame):
    raise TimeError()


count = 0

while True:
    try:
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(4)

        line = sys.stdin.readline()
        sys.stderr.write('received %s\n' % line.strip())
        sys.stderr.flush()
    except TimeError:
        print('announce route-refresh ipv4 unicast')
        sys.stdout.flush()
        print('announce route-refresh ipv4 unicast', file=sys.stderr)
        sys.stderr.flush()
