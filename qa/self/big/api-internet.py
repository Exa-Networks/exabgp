#!/usr/bin/env python3

import sys
import time


def write(data):
    sys.stdout.write(data + '\n')
    sys.stdout.flush()


def main():
    count = 0

    ip = {}
    nexthop = '1.2.3.4'

    for ip1 in range(223):
        generated = f'{ip1:d}.0.0.0/8'
        ip[generated] = nexthop

    for ip1 in range(223):
        for ip2 in range(256):
            generated = f'{ip1:d}.{ip2:d}.0.0/16'
            ip[generated] = nexthop

    # initial table dump
    for k, v in ip.iteritems():
        count += 1
        write(
            f'announce route {k} next-hop {v} med 100 as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]'
        )
        if count % 100 == 0:
            sys.stderr.write(f'initial : announced {count:d}\n')

    count &= 0xFFFFFFFE
    time.sleep(10000)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
