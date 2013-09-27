#!/usr/bin/env python

import sys
import time
import random

def write (data):
	sys.stdout.write(data + '\n')
	sys.stdout.flush()

def main ():
	count = 0

	ip = {}
	nexthop="1.2.3.4"

	for ip1 in range(0,223):
		generated = '%d.0.0.0/8' % (ip1)
		ip[generated] = nexthop

	for ip1 in range(0,223):
		for ip2 in range(0,256):
			generated = '%d.%d.0.0/16' % (ip1,ip2)
			ip[generated] = nexthop

	# initial table dump
	for k,v in ip.iteritems():
		count += 1
		write('announce route %s next-hop %s med 100 as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]' % (k,v))
		if count % 100 == 0:
			sys.stderr.write('initial : announced %d\n' % count)

	count &= 0xFFFFFFFe
	time.sleep(10000)

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
