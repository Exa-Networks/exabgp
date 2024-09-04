#!/usr/bin/python
"""
flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# based on the blog at: http://blog.sflow.com/2017/07/bgp-flowspec-on-white-box-switch.html

import os
import sys
import json
import re
import subprocess
import signal


class ACL(object):
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
        except KeyboardInterrupt:
            raise
        except Exception:
            pass

    @classmethod
    def _commit(cls):
        if cls.dry:
            cls.show()
            return
        try:
            return subprocess.Popen(
                ['cl-acltool', '-i'], stderr=subprocess.STDOUT, stdout=subprocess.PIPE
            ).communicate()[0]
        except KeyboardInterrupt:
            raise
        except Exception:
            pass

    @staticmethod
    def _build(flow, action):
        acl = '[iptables]\n-A FORWARD --in-interface swp+'
        if 'protocol' in flow:
            acl += ' -p ' + re.sub('[!<>=]', '', flow['protocol'][0])
        if 'source-ipv4' in flow:
            acl += ' -s ' + flow['source-ipv4'][0]
        if 'destination-ipv4' in flow:
            acl += ' -d ' + flow['destination-ipv4'][0]
        if 'source-port' in flow:
            acl += ' --sport ' + re.sub('[!<>=]', '', flow['source-port'][0])
        if 'destination-port' in flow:
            acl += ' --dport ' + re.sub('[!<>=]', '', flow['destination-port'][0])
        acl = acl + ' -j DROP\n'
        return acl

    @classmethod
    def insert(cls, flow, action):
        key = flow['string']
        if key in cls._known:
            return
        uid = cls._uid()
        acl = cls._build(flow, action)
        cls._known[key] = (uid, acl)
        try:
            with open(cls._file(uid), 'w') as f:
                f.write(acl)
            cls._commit()
        except KeyboardInterrupt:
            raise
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
        for key in cls._known:
            cls._delete(key)
        cls._commit()

    @classmethod
    def end(cls):
        cls.clear()
        sys.exit(1)

    @classmethod
    def show(cls):
        for key, (uid, _) in cls._known.items():
            sys.stderr.write('%d %s\n' % (uid, key))
        for _, acl in cls._known.values():
            sys.stderr.write('%s' % acl)
        sys.stderr.flush()


signal.signal(signal.SIGTERM, ACL.end)


opened = 0
buffered = ''

while True:
    try:
        line = sys.stdin.readline()
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
