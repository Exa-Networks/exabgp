#!/usr/bin/env python3

import sys

count = 0

while True:
    line = sys.stdin.readline()
    if ' route' in line:
        count += 1
        if count % 100 == 0:
            sys.stderr.write(f'received {count:<10d}\n')
            sys.stderr.flush()
