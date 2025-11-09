#!/usr/bin/env python3

import sys

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 0

while True:
    try:
        line = sys.stdin.readline().strip()
        if line == '':
            counter += 1
            if counter > 100:
                break
            continue

        counter = 0

        send = '\n{} {} {}\n'.format('-' * 10, line, '-' * 10)
        sys.stderr.write(f'{send}\n')
        sys.stderr.flush()
    except KeyboardInterrupt:
        pass
    except OSError:
        # most likely a signal during readline
        pass
