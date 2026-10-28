#!/usr/bin/python
"""flow.py

Created by Thomas Mangin on 2017-07-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# based on the blog at: http://blog.sflow.com/2017/07/bgp-flowspec-on-white-box-switch.html

from __future__ import annotations

import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
from types import FrameType
from typing import Any, ClassVar

from exabgp.environment.parsing import boolean
from exabgp.util.isolated import isolated


class ACL:
    dry: ClassVar[bool] = boolean(os.environ.get('CUMULUS_FLOW_RIB', 'false'))

    path: ClassVar[str] = '/etc/cumulus/acl/policy.d/'
    priority: ClassVar[str] = '60'
    prefix: ClassVar[str] = 'flowspec'
    bld: ClassVar[str] = '.bld'
    suffix: ClassVar[str] = '.rules'

    __uid: ClassVar[int] = 0
    _known: ClassVar[dict[str, tuple[int, str]]] = dict()

    @classmethod
    def _uid(cls) -> int:
        cls.__uid += 1
        return cls.__uid

    @classmethod
    def _file(cls, name: int) -> str:
        return cls.path + cls.priority + cls.prefix + str(name) + cls.suffix

    @classmethod
    def _delete(cls, key: str) -> None:
        if key not in cls._known:
            return
        # removing key first so the call to clear never loops forever
        uid, _acl = cls._known.pop(key)
        filename = cls._file(uid)
        try:
            if os.path.isfile(filename):
                os.unlink(filename)
        except OSError as exc:
            # The rule file is still in the policy directory and cl-acltool will install it
            # again, so this flow keeps dropping traffic while exabgp believes it is gone.
            sys.stderr.write(f'flow: {key} is withdrawn but its rule file remains, {filename}: {exc}\n')
            sys.stderr.flush()

    @classmethod
    def _commit(cls) -> bytes:
        if cls.dry:
            cls.show()
            return b''
        try:
            # Any: the stub says communicate() gives two bytes, and a compiled caller checks
            # that, but stderr goes to stdout and comes back None
            acltool: Any = subprocess.Popen(
                ['cl-acltool', '-i'],
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            )
            output: bytes = acltool.communicate()[0]
        except (OSError, subprocess.SubprocessError):
            return b''
        return output

    @staticmethod
    def _text(flow: dict[str, Any], what: str) -> str:
        """The first value of a flow component, as text, whatever JSON type it arrived as.

        Its type is not checked: _prefix and _number accept only the text of a prefix or of
        a number, so a list or a boolean, as text, is refused there with everything else.
        """
        return str(flow[what][0])

    @staticmethod
    def _prefix(value: str, what: str) -> str:
        """Validate an IPv4 prefix before it goes into an ACL rule."""
        return str(ipaddress.IPv4Network(value, strict=False))

    @staticmethod
    def _number(value: str, what: str, maximum: int) -> str:
        """Validate a numeric flow component before it goes into an ACL rule.

        FlowSpec numbers arrive with their comparison operator attached (">=1024"),
        which iptables can not express, so the operator is dropped as it always was.
        Only a plain decimal number is accepted once it is gone.
        """
        number = re.sub('[!<>=]', '', value)
        if not number.isascii() or not number.isdigit():
            raise ValueError(f'{what} "{value}" is not a number')
        if int(number) > maximum:
            raise ValueError(f'{what} "{value}" is larger than {maximum}')
        return number

    @classmethod
    def _build(cls, flow: dict[str, Any], action: str) -> str:
        """Render an iptables rule from a flow.

        Every component is validated and re-rendered from the parsed value, so no
        part of the flow can inject anything into the rule which is not a number
        or a prefix.
        """
        acl = '[iptables]\n-A FORWARD --in-interface swp+'
        if 'protocol' in flow:
            acl += ' -p ' + cls._number(cls._text(flow, 'protocol'), 'protocol', 255)
        if 'source-ipv4' in flow:
            acl += ' -s ' + cls._prefix(cls._text(flow, 'source-ipv4'), 'source-ipv4')
        if 'destination-ipv4' in flow:
            acl += ' -d ' + cls._prefix(cls._text(flow, 'destination-ipv4'), 'destination-ipv4')
        if 'source-port' in flow:
            acl += ' --sport ' + cls._number(cls._text(flow, 'source-port'), 'source-port', 65535)
        if 'destination-port' in flow:
            acl += ' --dport ' + cls._number(cls._text(flow, 'destination-port'), 'destination-port', 65535)
        acl = acl + ' -j DROP\n'
        return acl

    @classmethod
    def insert(cls, flow: dict[str, Any], action: str) -> None:
        key: str = flow['string']
        if key in cls._known:
            return
        try:
            acl = cls._build(flow, action)
        except (ValueError, IndexError, KeyError, TypeError) as exc:
            sys.stderr.write(f'ignoring a flow which can not be turned into an ACL: {exc}\n')
            sys.stderr.flush()
            return
        uid = cls._uid()
        cls._known[key] = (uid, acl)
        try:
            with open(cls._file(uid), 'w') as f:
                f.write(acl)
            cls._commit()
        except OSError:
            cls.end()

    @classmethod
    def remove(cls, flow: dict[str, Any]) -> None:
        key: str = flow['string']
        if key not in cls._known:
            return
        cls._delete(key)
        # Deleting the rule file does not unprogram the switch: insert() and clear() both
        # reload the policy directory after changing it, and a withdraw which does not keeps
        # dropping traffic for a flow exabgp has already forgotten.
        cls._commit()

    @classmethod
    def clear(cls) -> None:
        for key in list(cls._known.keys()):
            cls._delete(key)
        cls._commit()

    @classmethod
    def end(cls, signum: int = 0, frame: FrameType | None = None) -> None:
        cls.clear()
        sys.exit(1)

    @classmethod
    def show(cls) -> None:
        for key, (uid, _) in cls._known.items():
            sys.stderr.write(f'{uid} {key}\n')
        for _, acl in cls._known.values():
            sys.stderr.write(acl)
        sys.stderr.flush()


def _unprocessed(exc: Exception) -> None:
    """A message the helper could not act on: said, and the next one read."""
    print(f'flow: error processing message: {exc}', file=sys.stderr)


def main() -> None:
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
            print(f'flow: can not read from stdin: {exc}', file=sys.stderr)
            ACL.end()
            return

        with isolated(_unprocessed):
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


if __name__ == '__main__':
    main()
