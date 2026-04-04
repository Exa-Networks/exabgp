#!/usr/bin/env python3

import sys
import signal


class TimeError(Exception):
    pass


def handler(signum, frame):
    raise TimeError


count = 0

while True:
    try:
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(4)

        line = sys.stdin.readline()
        sys.stderr.write('received {}\n'.format(line.strip()))
        sys.stderr.flush()
    except TimeError:
        sys.stdout.write('announce route-refresh ipv4 unicast\n')
        sys.stdout.flush()
        sys.stderr.write('announce route-refresh ipv4 unicast\n')
        sys.stderr.flush()
