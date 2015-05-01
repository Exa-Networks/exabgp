#!/usr/bin/env python
# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2014-12-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.reactor.api.transcoder import Transcoder

from exabgp.configuration.setup import environment
env = environment.setup('')


test = """\
{ "exabgp": "3.5.0", "time": 1430238962.74, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "state", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "state": "down", "reason": "out loop, peer reset, message [closing connection] error[the TCP connection was closed by the remote end]"} }
{ "exabgp": "3.5.0", "time": 1430238928.75, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "state", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "state": "up"} }
{ "exabgp": "3.5.0", "time": 1430293452.31, "host" : "mangin.local", "pid" : 57788, "ppid" : 57779, "type": "open", "neighbor": { "address": { "local": "172.20.10.6", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "send", "message": { "category": 1, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00AF01", "body": "04FFFE00B4800000009202060104000100010206010400010002020601040001000402060104000100800206010400010085020601040001008602060104000200010206010400020080020601040002008502060104000200860206010400190041020641040000FFFE0230402E84B00001018000010280000104800001808000018580000186800002018000028080000285800002868000194180" } } }
{ "exabgp": "3.5.0", "time": 1430293452.32, "host" : "mangin.local", "pid" : 57788, "ppid" : 57779, "type": "open", "neighbor": { "address": { "local": "172.20.10.6", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 1, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00AF01", "body": "04FFFD00B47F0000009202060104000100010206010400010002020601040001000402060104000100800206010400010085020601040001008602060104000200010206010400020080020601040002008502060104000200860206010400190041020641040000FFFD0230402E84B00001018000010280000104800001808000018580000186800002018000028080000285800002868000194180" } } }
{ "exabgp": "3.5.0", "time": 1430238928.75, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF005002", "body": "0000002740010100400212020400000001000000020000000300000004400304010101018004040000006408630858084D08420837082C08210816080B" } } }
{ "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003001941" } } }
{ "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003000286" } } }
{ "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003000285" } } }
""".split('\n')

def main ():
	transcoder = Transcoder('json','json')

	running = 50
	while running:

		if not test:
			break

		# line = sys.stdin.readline().strip()
		line = test.pop(0)

		if not line:
			running -= 1
			continue
		running = 50

		print transcoder.convert(line)

if __name__ == '__main__':
	main()
