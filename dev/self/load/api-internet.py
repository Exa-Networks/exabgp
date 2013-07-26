#!/usr/bin/env python

import sys
import time
import random

def write (data):
	sys.stdout.write(data + '\n')
	sys.stdout.flush()

def main ():
	default = '65536'
	param = (sys.argv + [default,])[1]

	if not param.isdigit():
		write('please give a valid number')
		sys.exit(1)

	number = int(param) & 0x00FFFFFF

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


	# initial table dump
	for k,v in ip.iteritems():
		write('announce route %s next-hop %s' % (k,v))

	# modify routes forever
	while True:
		now = time.time()
		changed = {}

		for k,v in ip.iteritems():
			changed[k] = v
			if not random.randint(0,100):
				break

		for k,v in changed.iteritems():
			write('withdraw route %s next-hop %s' % (k,v))
			ip[k] = random.choice(nexthop)
			write('announce route %s next-hop %s' % (k,ip[k]))

		time.sleep(time.time()-now+1.0)

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
