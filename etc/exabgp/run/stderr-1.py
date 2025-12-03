#!/usr/bin/env python3

import os
import signal
import sys
import time


def _prefixed(level, message):
    now = time.strftime('%a, %d %b %Y %H:%M:%S\n', time.localtime())
    return '%s %-8s %-6d %s\n' % (now, level, os.getpid(), message)


def main():
    # When the parent dies we are seeing continual newlines, so we only access so many before stopping
    counter = 0

    while os.getppid() != 1:
        try:
            line = sys.stdin.readline().strip()
            sys.stdout.flush()
            if line == '':
                counter += 1
                if counter > 100:
                    break
                continue

            counter = 0

            sys.stderr.write(_prefixed(sys.argv[1] if len(sys.argv) >= 2 else 'EXABGP PROCESS', line))
        except KeyboardInterrupt:
            pass
        except OSError:
            # most likely a signal during readline
            pass


if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
