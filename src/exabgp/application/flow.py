#!/usr/bin/python
"""flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# based on the blog at: http://blog.sflow.com/2017/07/bgp-flowspec-on-white-box-switch.html

from __future__ import annotations

import ipaddress
import os
import sys
import json
import re
import subprocess
import signal


class ACL:
    dry = os.environ.get('CUMULUS_FLOW_RIB', False)

    path = '/etc/cumulus/acl/policy.d/'
    priority = '60'
    prefix = 'flowspec'
    bld = '.bld'
    suffix = '.rules'

    __uid = 0
    _known = dict()

    @classmethod
    def _uid(cls):
        cls.__uid += 1
        return cls.__uid

    @classmethod
    def _file(cls, name):
        return cls.path + cls.priority + cls.prefix + str(name) + cls.suffix

    @classmethod
    def _delete(cls, key):
        if key not in cls._known:
            return
        # removing key first so the call to clear never loops forever
        uid, acl = cls._known.pop(key)
        try:
            filename = cls._file(uid)
            if os.path.isfile(filename):
                os.unlink(filename)
        except Exception:
            pass

    @classmethod
    def _commit(cls):
        if cls.dry:
            cls.show()
            return None
        try:
            return subprocess.Popen(
                ['cl-acltool', '-i'],
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ).communicate()[0]
        except Exception:
            pass

    @staticmethod
    def _prefix(value, what):
        """Validate an IPv4 prefix before it goes into an ACL rule."""
        if not isinstance(value, str):
            raise ValueError('%s is not a string' % what)
        return str(ipaddress.IPv4Network(value, strict=False))

    @staticmethod
    def _number(value, what, maximum):
        """Validate a numeric flow component before it goes into an ACL rule.

        FlowSpec numbers arrive with their comparison operator attached (">=1024"),
        which iptables can not express, so the operator is dropped as it always was.
        Only a plain decimal number is accepted once it is gone.
        """
        if not isinstance(value, str):
            raise ValueError('%s is not a string' % what)
        number = re.sub('[!<>=]', '', value)
        if not number.isascii() or not number.isdigit():
            raise ValueError('%s "%s" is not a number' % (what, value))
        if int(number) > maximum:
            raise ValueError('%s "%s" is larger than %d' % (what, value, maximum))
        return number

    @classmethod
    def _build(cls, flow, action):
        """Render an iptables rule from a flow.

        Every component is validated and re-rendered from the parsed value, so no
        part of the flow can inject anything into the rule which is not a number
        or a prefix.
        """
        acl = '[iptables]\n-A FORWARD --in-interface swp+'
        if 'protocol' in flow:
            acl += ' -p ' + cls._number(flow['protocol'][0], 'protocol', 255)
        if 'source-ipv4' in flow:
            acl += ' -s ' + cls._prefix(flow['source-ipv4'][0], 'source-ipv4')
        if 'destination-ipv4' in flow:
            acl += ' -d ' + cls._prefix(flow['destination-ipv4'][0], 'destination-ipv4')
        if 'source-port' in flow:
            acl += ' --sport ' + cls._number(flow['source-port'][0], 'source-port', 65535)
        if 'destination-port' in flow:
            acl += ' --dport ' + cls._number(flow['destination-port'][0], 'destination-port', 65535)
        acl = acl + ' -j DROP\n'
        return acl

    @classmethod
    def insert(cls, flow, action):
        key = flow['string']
        if key in cls._known:
            return
        try:
            acl = cls._build(flow, action)
        except (ValueError, IndexError, KeyError, TypeError) as exc:
            sys.stderr.write('ignoring a flow which can not be turned into an ACL: %s\n' % exc)
            sys.stderr.flush()
            return
        uid = cls._uid()
        cls._known[key] = (uid, acl)
        try:
            with open(cls._file(uid), 'w') as f:
                f.write(acl)
            cls._commit()
        except Exception:
            cls.end()

    @classmethod
    def remove(cls, flow):
        key = flow['string']
        if key not in cls._known:
            return
        uid, _ = cls._known[key]
        cls._delete(key)

    @classmethod
    def clear(cls):
        # iterate over a copy of the keys: _delete pops the entry it is given
        for key in list(cls._known.keys()):
            cls._delete(key)
        cls._commit()

    @classmethod
    def end(cls, signum=0, frame=None):  # pylint: disable=W0613
        # signum and frame are what python passes a signal handler, and are unused:
        # they are here so ACL.end can be installed as one and still be called bare
        cls.clear()
        sys.exit(1)

    @classmethod
    def show(cls):
        for key, (uid, _) in cls._known.items():
            sys.stderr.write(f'{uid} {key}\n')
        for _, acl in cls._known.values():
            sys.stderr.write(acl)
        sys.stderr.flush()


def main():
    signal.signal(signal.SIGTERM, ACL.end)

    opened = 0
    buffered = ''

    while True:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            ACL.end()
            return
        except OSError as exc:
            # a broken stdin never recovers: without this the handler below would
            # swallow the error and the loop would spin without ever making progress
            sys.stderr.write('flow: can not read from stdin: %s\n' % exc)
            sys.stderr.flush()
            ACL.end()
            return

        try:
            if not line or 'shutdown' in line:
                ACL.end()
            buffered += line
            opened += line.count('{')
            opened -= line.count('}')
            if opened:
                continue
            line, buffered = buffered, ''
            message = json.loads(line)

            if message['type'] == 'state' and message['neighbor']['state'] == 'down':
                ACL.clear()
                continue

            if message['type'] != 'update':
                continue

            update = message['neighbor']['message']['update']

            if 'announce' in update:
                flow = update['announce']['ipv4 flow']
                # The RFC allows both encoding
                flow = flow['no-nexthop'][0] if 'no-nexthop' in flow else flow[0]

                community = update['attribute']['extended-community'][0]
                ACL.insert(flow, community)
                continue

            if 'withdraw' in update:
                flow = update['withdraw']['ipv4 flow'][0]
                ACL.remove(flow)
                continue

        except KeyboardInterrupt:
            ACL.end()
        except Exception:
            pass


if __name__ == '__main__':
    main()
