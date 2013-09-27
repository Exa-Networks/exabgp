#!/usr/bin/env python

import sys

count = 0

while True:
	line = sys.stdin.readline()
	if ' route' in line:
		count += 1
		if count % 100 == 0:
			sys.stderr.write('received %-10d\n' % count)
			sys.stderr.flush()
