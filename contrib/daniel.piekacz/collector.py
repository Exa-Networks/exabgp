#!/usr/bin/env python
"""
Created by Daniel Piekacz on 2012-01-14.
Last update on 2012-02-06.
Copyright (c) 2012 Daniel Piekacz. All rights reserved.
Copyright (c) 2012 Thomas Mangin. All rights reserved.
Project website: gix.net.pl, e-mail: daniel@piekacz.tel
"""

# standard include - will always be there
import sys
import os
import time
import syslog
import string

# just to test, run ./collector.py print | ./collector.py <db settings>
def print_debug():
 	print '''\
neighbor 192.168.127.130 down
neighbor 192.168.127.130 up
neighbor 192.168.127.130 announce IPv4 unicast 1.2.3.4/32 next-hop 192.168.127.130 origin igp as-sequence [ 123456 64 128 256 1234567 ] med 20 community 65000:1 extended-community [ target:65000:0.0.0.1 origin:1.2.3.4:5678 ]
neighbor 192.168.127.130 announce IPv4 unicast 8.9.0.0/16 next-hop 192.168.127.130 origin igp as-sequence [ 123456 64 128 256 1234567 ] med 20 community 65000:1 extended-community [ target:65000:0.0.0.1 origin:1.2.3.4:5678 ]
neighbor 192.168.127.130 announce IPv4 unicast 5.6.7.0/24 next-hop 192.168.127.130 origin igp as-sequence [ 123456 64 128 256 1234567 ] med 20 community 65000:1 extended-community [ target:65000:0.0.0.1 origin:1.2.3.4:5678 ]
neighbor 192.168.127.130 announce IPv6 unicast 1234:5678::/32 next-hop :: origin igp as-sequence [ 123456 ] med 0
neighbor 192.168.127.130 withdraw IPv4 unicast 5.6.7.0/24
'''
	sys.exit(0)

def routes ():
	# When the parent dies we are seeing continual newlines, so we only access so many before stopping
	counter = 0

	# currently supported route keys
	route_keys = ['neighbor','announce','withdraw','unicast','next-hop','med','local-preference','as-path','community','extended-community','origin','as-sequence']
	# as-path is called as-sequence when routes are generated
	replace = {'as-sequence':'as-path'}

	line = ''

	while True:
		try:
			# As any Keyboard Interrupt will force us back here, we are only reading line if we could yield the route to the parent un-interrupted.
			if not line:
				line = sys.stdin.readline().strip()
			if line == "":
				counter += 1
				if counter > 100:
					raise StopIteration()
				continue
			counter = 0

			# local-preference default is 100
			# med default is 100

			route = dict(zip(route_keys,['',]*len(route_keys)))
			route['time'] = time.strftime('%Y-%m-%d  %H:%M:%S',time.localtime())

			tokens = line.split(' ')

			while len(tokens) >= 2:
				key = tokens.pop(0)
				value = tokens.pop(0)

				if key not in route_keys:
					print >> sys.stderr, 'unknown route attributes %s' % (key)
					if value == '[':
						while tokens and value != ']':
							value = tokens.pop(0)
						continue

				if value == '[':
					values = []
					while tokens:
						value = tokens.pop(0)
						if value == ']': break
						values.append(value)
					if value != ']':
						print >> sys.stderr, 'problem parse the values of attribute %s' % (key)
						line = ''
						continue
					value = ' '.join(values)

				route[replace.get(key,key)] = value

			if tokens:
				token = tokens.pop(0)
				if token in ('up','down'):
					route['state'] = token
			else:
				route['state'] = ''

			yield route
			line = ''
		except KeyboardInterrupt:
			pass

def _prefixed (level,message):
	now = time.strftime('%a, %d %b %Y %H:%M:%S',time.localtime())
	return "%s %-8s %-6d %s" % (now,level,os.getpid(),message)

def tosql (cursor,route):
	try:
		if route['state'] == "up":
			cursor.execute ("DELETE FROM prefixes WHERE (neighbor = %s)", (route['neighbor']))
			cursor.execute ("UPDATE members SET time='0000-00-00 00:00:00',prefixes=0,status=1,updown=updown+1,lastup=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			return

		if route['state'] == "down":
			cursor.execute ("DELETE FROM prefixes WHERE (neighbor = %s)", (route['neighbor']))
			cursor.execute ("UPDATE members SET time='0000-00-00 00:00:00',prefixes=0,status=0,updown=updown+1,lastdown=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			return

		if route['announce']:
			cursor.execute ("SELECT '' FROM prefixes WHERE ((neighbor=%s) && (prefix=%s))", (route['neighbor'], route['unicast']))
			if cursor.rowcount == 0:
				cursor.execute ("""\
				INSERT INTO prefixes
				(
					neighbor,
					type,
					prefix,
					aspath,
					nexthop,
					community,
					extended_community,
					origin,
					time
				) VALUES
				(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
				(
					route['neighbor'],
					route['announce'][-1],
					route['unicast'],
					route['as-path'],
					route['next-hop'],
					route['community'],
					route['extended-community'],
					route['origin'],
					route['time']
				))
				cursor.execute ("UPDATE members SET prefixes=prefixes+1,time=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			else:
				cursor.execute ("UPDATE prefixes SET aspath=%s,nexthop=%s,community=%s,extended_community=%s,origin=%s,time=%s WHERE ((neighbor=%s) && (prefix=%s))", (route['as-path'], route['next-hop'], route['community'], route['extended-community'], route['origin'], route['time'], route['neighbor'], route['unicast']))
				cursor.execute ("UPDATE members SET time=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			return

		if route['withdraw']:
			cursor.execute ("SELECT '' FROM prefixes WHERE ((neighbor=%s) && (prefix=%s))", (route['neighbor'], route['unicast']))
			if cursor.rowcount == 0:
				cursor.execute ("UPDATE members SET time=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			else:
				cursor.execute ("DELETE FROM prefixes WHERE ((neighbor = %s) && (prefix = %s))", (route['neighbor'], route['unicast']))
				cursor.execute ("UPDATE members SET prefixes=prefixes-1,time=%s WHERE neighbor=%s", (route['time'], route['neighbor']))
			return

		syslog.syslog(syslog.LOG_ALERT, _prefixed('INFO', "BGP: unparsed route %s" % (str(route))))
	except KeyboardInterrupt:
		# keyboard interrupt are not for us, whatever it was we were doing, do it.
		tosql(cursor,route)


def main ():
	import MySQLdb

	syslog.openlog("ExaBGP")

	host = sys.argv[1]
	database = sys.argv[2]
	user = sys.argv[3]
	password = sys.argv[4]

	try:
		mydb = MySQLdb.connect (host = host, db = database, user = user, passwd = password, connect_timeout = 0)
		cursor = mydb.cursor ()
		mydb.ping(True)
	except MySQLdb.Error, e:
		print >> sys.stderr,"Error %d: %s" % (e.args[0], e.args[1])
		sys.exit(1)

	running = True

	while running:
		try:
			for route in routes():
				tosql(cursor,route)
				mydb.commit()
			running = False
		except KeyboardInterrupt:
			# If we are so unlucky to get the keyboard interrupt between the yield and the function call, there is no much we can do, that update will be lost
			# However this mean that ExaBGP is shutting down, and that it was not run as a deamon (so most likely not in production)
			pass
		except MySQLdb.Error, e:
			# Nothing much we can do ...
			print >> sys.stderr,"Error %d: %s" % (e.args[0], e.args[1])
			sys.exit (1)

	try:
		cursor.close ()
		mydb.close ()
	except MySQLdb.Error, e:
		# no point complaining we were on our way out anyway
		pass

if __name__ == '__main__':
	if len(sys.argv) == 2 and sys.argv[1] == 'print':
		print_debug()
	elif len(sys.argv) == 5:
		main ()
	else:
		print "wrong syntax"
		print "%s <host> <database> <user> <password>" % sys.argv[0]
		sys.exit(1)
