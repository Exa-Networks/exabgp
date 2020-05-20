#!/usr/bin/env python
# encoding: utf-8
"""
tojson.py

Created by Thomas Mangin on 2014-12-22.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import print_function

import os
import sys
import time
import signal
import thread
import subprocess
from collections import deque

from exabgp.reactor.api.transcoder import Transcoder
from exabgp.reactor.api.processes import preexec_helper

from exabgp.configuration.setup import environment

environment.setup('')

# test = """\
# { "exabgp": "3.5.0", "time": 1430238962.74, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "state", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "state": "down", "reason": "out loop, peer reset, message [closing connection] error[the TCP connection was closed by the remote end]"} }
# { "exabgp": "3.5.0", "time": 1430238928.75, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "state", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "state": "up"} }
# { "exabgp": "3.5.0", "time": 1430293452.31, "host" : "mangin.local", "pid" : 57788, "ppid" : 57779, "type": "open", "neighbor": { "address": { "local": "172.20.10.6", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "send", "message": { "category": 1, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00AF01", "body": "04FFFE00B4800000009202060104000100010206010400010002020601040001000402060104000100800206010400010085020601040001008602060104000200010206010400020080020601040002008502060104000200860206010400190041020641040000FFFE0230402E84B00001018000010280000104800001808000018580000186800002018000028080000285800002868000194180" } } }
# { "exabgp": "3.5.0", "time": 1430293452.32, "host" : "mangin.local", "pid" : 57788, "ppid" : 57779, "type": "open", "neighbor": { "address": { "local": "172.20.10.6", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 1, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00AF01", "body": "04FFFD00B47F0000009202060104000100010206010400010002020601040001000402060104000100800206010400010085020601040001008602060104000200010206010400020080020601040002008502060104000200860206010400190041020641040000FFFD0230402E84B00001018000010280000104800001808000018580000186800002018000028080000285800002868000194180" } } }
# { "exabgp": "3.5.0", "time": 1430238928.75, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF005002", "body": "0000002740010100400212020400000001000000020000000300000004400304010101018004040000006408630858084D08420837082C08210816080B" } } }
# { "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003001941" } } }
# { "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003000286" } } }
# { "exabgp": "3.5.0", "time": 1430238928.76, "host" : "mangin.local", "pid" : 37912, "ppid" : 37903, "type": "update", "neighbor": { "address": { "local": "82.219.212.34", "peer": "127.0.0.1" }, "asn": { "local": "65534", "peer": "65533" }, "direction": "receive", "message": { "category": 2, "header": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E02", "body": "00000007900F0003000285" } } }
# """.split('\n')


# XXX: We do not accept input from the forked application


class Application(object):
    Q = deque()
    running = True

    @staticmethod
    def _signal(_, __):
        Application.running = False

    def process(self):
        run = sys.argv[1:]
        if not run:
            print(sys.stderr, 'no consummer program provided')
            sys.exit(1)

        # Prevent some weird termcap data to be created at the start of the PIPE
        # \x1b[?1034h (no-eol) (esc)
        os.environ['TERM'] = 'dumb'

        try:
            sub = subprocess.Popen(
                run,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                preexec_fn=preexec_helper
                # This flags exists for python 2.7.3 in the documentation but on on my MAC
                # creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        except (subprocess.CalledProcessError, OSError, ValueError):
            print('could not start subprocess', file=sys.stderr)
            sys.exit(1)

        return sub

    def __init__(self):
        thread.start_new_thread(self.reader, (os.getpid(),))
        signal.signal(signal.SIGTERM, Application._signal)
        self.sub = self.process()
        self.transcoder = Transcoder('json', 'json')
        self.main()

    # def test_reader (self,myself):
    # 	while len(test):
    # 		# line = sys.stdin.readline().strip()
    # 		line = test.pop(0)
    # 		if line:
    # 			self.Q.append(line)
    # 	time.sleep(2)
    # 	os.kill(myself,signal.SIGTERM)

    def reader(self, myself):
        ok = True
        line = ''
        while True:
            line = sys.stdin.readline().strip()
            if ok:
                if not line:
                    ok = False
                    continue
            elif not line:
                break
            else:
                ok = True
            self.Q.append(line)
        os.kill(myself, signal.SIGTERM)

    def main(self):
        while self.running or len(self.Q):
            try:
                line = self.Q.popleft()
                self.sub.stdin.write(self.transcoder.convert(line))
                self.sub.stdin.flush()
            except IndexError:
                # no data on the Q to read
                time.sleep(0.1)
            except IOError:
                # subprocess died
                print('subprocess died', file=sys.stderr)
                sys.exit(1)


if __name__ == '__main__':
    try:
        Application()
    except KeyboardInterrupt:
        pass
