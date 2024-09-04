#!/usr/bin/env python

import sys

match = {
    0: ['neighbor 127.0.0.1 update start',] * 20,
    1: [
        'neighbor 127.0.0.1 announced route %d%d.0.0.0/8 next-hop 1.1.1.1 origin igp as-path [ 1 2 3 4 ] med 100'
        % (number, number)
        for number in range(1, 10)
    ]
    + [
        'neighbor 127.0.0.1 announced route eor %d/%d (%s)' % (afi, safi, text)
        for (afi, safi, text) in (
            (1, 1, 'ipv4 unicast'),
            (1, 2, 'ipv4 multicast'),
            (1, 4, 'ipv4 nlri-mpls'),
            (1, 128, 'ipv4 mpls-vpn'),
            (1, 133, 'ipv4 flow'),
            (1, 134, 'ipv4 flow-vpn'),
            (2, 1, 'ipv6 unicast'),
            (2, 128, 'ipv6 mpls-vpn'),
            (2, 133, 'ipv6 flow'),
            (2, 134, 'ipv6 flow-vpn'),
            (25, 65, 'l2vpn vpls'),
        )
    ],
    2: ['neighbor 127.0.0.1 update end',] * 20,
    3: ['',] * 20,
}

count = 0

while True:
    line = sys.stdin.readline().strip()
    # print >> sys.stderr, '[%s]' % line.replace('\n','\\n'), start, end

    options = match[count % 4]

    if line in options:
        sys.stderr.write('%-3d ok      %s\n' % (count, line))
        sys.stderr.flush()
        count += 1
        continue

    sys.stderr.write('%-3d failed  %s\n' % (count, line))
    # sys.stderr.write("---" + line + "---\n")
    # sys.stderr.write("---" + str(options) + "---\n")
    sys.stderr.flush()
    count += 1
