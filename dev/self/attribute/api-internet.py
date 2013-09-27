#!/usr/bin/env python

import sys
import time

def write (data):
	sys.stdout.write(data + '\n')
	sys.stdout.flush()

def main ():
	msg = 'announce attribute next-hop 1.2.3.4 med 100 as-path [ 100 101 102 103 104 105 106 107 108 109 110 ] nlri %s'
	write(msg % ' '.join('%d.0.0.0/8' % ip for ip in range(0,224)))
	write(msg % ' '.join('10.%d.0.0/16' % ip for ip in range(0,256)))

	time.sleep(2)

	write('withdraw attribute next-hop 1.2.3.4 med 100 as-path [ 100 101 102 103 104 105 106 107 108 109 110 ] nlri 0.0.0.0/8 1.0.0.0/8')

	time.sleep(10000)

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		pass
