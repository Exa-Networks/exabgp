#!/usr/bin/env python

import sys
import time
import random

def write (data):
	sys.stdout.write(data + '\n')
	sys.stdout.flush()

def main ():
	if len(sys.argv) < 2:
		print "%s <number of routes> <updates per second thereafter>"
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
	range2 = (number >>  8) & 0xFF
	range3 = (number      ) & 0xFF

	ip = {}
	nexthop = ['%d.%d.%d.%d' % (random.randint(1,200),random.randint(0,255),random.randint(0,255),random.randint(0,255)) for _ in range(200)]

	for ip1 in range(0,range1):
		for ip2 in range(0,256):
			for ip3 in range(0,256):
				generated = '%d.%d.%d.%d' % (random.randint(1,200),ip1,ip2,ip3)
				ip[generated] = random.choice(nexthop)

	for ip2 in range (0,range2):
		for ip3 in range (0,256):
			generated = '%d.%d.%d.%d' % (random.randint(1,200),range1,ip2,ip3)
			ip[generated] = random.choice(nexthop)

	for ip3 in range (0,range3):
		generated = '%d.%d.%d.%d' % (random.randint(1,200),range1,range2,ip3)
		ip[generated] = random.choice(nexthop)

	count = 0

	# initial table dump
	for k,v in ip.iteritems():
		count += 1
		write('announce route %s next-hop %s med 1%02d as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]' % (k,v,len(k)))
		if count % 100 == 0:
			sys.stderr.write('initial : announced %d\n' % count)

	count &= 0xFFFFFFFe

	# modify routes forever
	while True:
		now = time.time()
		changed = {}

		for k,v in ip.iteritems():
			changed[k] = v
			if not random.randint(0,after):
				break

		for k,v in changed.iteritems():
			count += 2
			write('withdraw route %s next-hop %s med 1%02d as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]' % (k,v,len(k)))
			ip[k] = random.choice(nexthop)
			write('announce route %s next-hop %s med 1%02d as-path [ 100 101 102 103 104 105 106 107 108 109 110 ]' % (k,ip[k],len(k)))
			if count % 100 == 0:
				sys.stderr.write('updates : announced %d\n' % count)


		time.sleep(time.time()-now+1.0)

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
