#!/usr/bin/python
"""
flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# based on the blog at: http://blog.sflow.com/2017/07/bgp-flowspec-on-white-box-switch.html

from __future__ import annotations

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
        except Exception as e:
            sys.stderr.write(f'Warning: Failed to delete ACL file {filename}: {e}\n')
            sys.stderr.flush()

    @classmethod
    def _commit(cls):
        if cls.dry:
            cls.show()
            return
        try:
            return subprocess.Popen(
                ['cl-acltool', '-i'], stderr=subprocess.STDOUT, stdout=subprocess.PIPE
            ).communicate()[0]
        except Exception as e:
            sys.stderr.write(f'Warning: Failed to commit ACL rules: {e}\n')
            sys.stderr.flush()

    @staticmethod
    def _validate_port(value):
        """Validate port/port-range value for iptables.

        Args:
            value: Port value as string (e.g., "80", "80:443", "=80")

        Returns:
            Sanitized port value safe for iptables

        Raises:
            ValueError: If value contains invalid characters
        """
        if not value:
            raise ValueError('Empty port value')

        # Remove BGP flowspec operators (=, !, <, >, &, |) - keep only valid iptables syntax
        cleaned = re.sub('[!<>=&|]', '', value)

        # Validate: only digits, colon (for ranges), and comma (for lists)
        if not re.match(r'^[\d:,]+$', cleaned):
            raise ValueError(f'Invalid port value: {value}')

        return cleaned

    @staticmethod
    def _validate_protocol(value):
        """Validate protocol value for iptables.

        Args:
            value: Protocol value as string (e.g., "tcp", "udp", "6")

        Returns:
            Sanitized protocol value safe for iptables

        Raises:
            ValueError: If value contains invalid characters
        """
        if not value:
            raise ValueError('Empty protocol value')

        # Remove BGP flowspec operators
        cleaned = re.sub('[!<>=&|]', '', value).lower()

        # Whitelist of valid protocols (names and numbers)
        valid_protocols = {
            'tcp', 'udp', 'icmp', 'icmpv6', 'esp', 'ah', 'sctp', 'all',
            '0', '1', '2', '6', '17', '41', '43', '44', '47', '50', '51', '58', '132'
        }

        if cleaned not in valid_protocols and not re.match(r'^\d+$', cleaned):
            raise ValueError(f'Invalid protocol: {value}')

        return cleaned

    @staticmethod
    def _build(flow, action):
        """Build iptables ACL rule from flowspec data.

        Args:
            flow: Flowspec flow dictionary
            action: Extended community action

        Returns:
            ACL rule string for iptables

        Raises:
            ValueError: If flow contains invalid data
        """
        acl = '[iptables]\n-A FORWARD --in-interface swp+'

        try:
            if 'protocol' in flow:
                proto = ACL._validate_protocol(flow['protocol'][0])
                acl += f' -p {proto}'

            if 'source-ipv4' in flow:
                # IP addresses are already validated by BGP parser
                acl += f' -s {flow["source-ipv4"][0]}'

            if 'destination-ipv4' in flow:
                # IP addresses are already validated by BGP parser
                acl += f' -d {flow["destination-ipv4"][0]}'

            if 'source-port' in flow:
                port = ACL._validate_port(flow['source-port'][0])
                acl += f' --sport {port}'

            if 'destination-port' in flow:
                port = ACL._validate_port(flow['destination-port'][0])
                acl += f' --dport {port}'

        except (ValueError, KeyError, IndexError) as e:
            raise ValueError(f'Invalid flow data: {e}')

        acl = acl + ' -j DROP\n'
        return acl

    @classmethod
    def insert(cls, flow, action):
        key = flow['string']
        if key in cls._known:
            return
        uid = cls._uid()
        try:
            acl = cls._build(flow, action)
        except ValueError as e:
            sys.stderr.write(f'Error: Invalid flow specification: {e}\n')
            sys.stderr.flush()
            return

        cls._known[key] = (uid, acl)
        try:
            with open(cls._file(uid), 'w') as f:
                f.write(acl)
            cls._commit()
        except (OSError, IOError) as e:
            sys.stderr.write(f'Error: Failed to write ACL rule: {e}\n')
            sys.stderr.flush()
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
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        sys.stderr.write(f'Error: Failed to process flow message: {e}\n')
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f'Unexpected error: {e}\n')
        sys.stderr.flush()
