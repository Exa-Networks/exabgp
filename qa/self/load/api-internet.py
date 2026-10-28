#!/usr/bin/env python3

import random
import sys
import time


def write(data):
    sys.stdout.write(data + '\n')
    sys.stdout.flush()


def main():
    if len(sys.argv) < 2:
        sys.stdout.write('%s <number of routes> <updates per second thereafter>\n')
        sys.exit(1)

    initial = sys.argv[1]
    thereafter = sys.argv[2]

    if not initial.isdigit() or not thereafter.isdigit():
        write('please give valid numbers')
        sys.exit(1)

    # Limit to sane numbers :-)
    number = int(initial) & 0x00FFFFFF
    after = int(thereafter) & 0x0000FFFF

    range1 = (number >> 16) & 0xFF
    range2 = (number >> 8) & 0xFF
    range3 = (number) & 0xFF

    ip = {}
    nexthop = [
        f'{random.randint(1, 200):d}.{random.randint(0, 255):d}.{random.randint(0, 255):d}.{random.randint(0, 255):d}'
        for _ in range(200)
    ]

    for ip1 in range(range1):
        for ip2 in range(256):
            for ip3 in range(256):
                generated = f'{random.randint(1, 200):d}.{ip1:d}.{ip2:d}.{ip3:d}'
                ip[generated] = random.choice(nexthop)

    for ip2 in range(range2):
        for ip3 in range(256):
            generated = f'{random.randint(1, 200):d}.{range1:d}.{ip2:d}.{ip3:d}'
            ip[generated] = random.choice(nexthop)

    for ip3 in range(range3):
        generated = f'{random.randint(1, 200):d}.{range1:d}.{range2:d}.{ip3:d}'
        ip[generated] = random.choice(nexthop)

    count = 0

    # initial table dump
    for k, v in ip.iteritems():
        count += 1
        write(
            f'announce route {k} next-hop {v} med 1{len(k):02d} as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]',
        )
        if count % 10000 == 0:
            sys.stderr.write(f'initial : announced {count:d}\n')

    count &= 0xFFFFFFFE

    # modify routes forever
    while True:
        now = time.time()
        changed = {}

        for k, v in ip.iteritems():
            changed[k] = v
            if not random.randint(0, after):
                break

        for k, v in changed.iteritems():
            count += 2
            write(
                f'withdraw route {k} next-hop {v} med 1{len(k):02d} as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]',
            )
            ip[k] = random.choice(nexthop)
            write(
                f'announce route {k} next-hop {ip[k]} med 1{len(k):02d} as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]',
            )
            if count % 100 == 0:
                sys.stderr.write(f'updates : announced {count:d}\n')

        time.sleep(time.time() - now + 1.0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
