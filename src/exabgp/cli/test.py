#!/usr/bin/env python3

from vyos.xml import load_configuration
from vyos.cli.completer import VyOSCompleter
from vyos.cli.validator import VyOSValidator
from vyos.cli.validator import ValidationError
from vyos.cli.command import dispatch
from vyos.cli import msg


def test_complete():
    cmd = 'set interfaces ethernet lan0 '
    cmd = 'interfaces ethernet lan0 address 1.1.1.1/32 test'
    cmd = 'set interfaces ethernet eth0 '

    xml = load_configuration()

    completer = VyOSCompleter(xml, {})
    for _ in completer._set_complete(cmd):
        print(_)
    print()
    print(f'"{cmd}"')
    print(completer.set_help())


def test_validate():
    commands = [
        'set interfaces dummy dum0 address 1.2.',
        'set interfaces dummy dum0 address 1.2.3.4/32',
        # 'set interfaces dummy eth1 address 1.2.3.4/32',
    ]

    xml = load_configuration()
    message = msg()

    validator = VyOSValidator(xml, message)

    for cmd in commands:
        print()
        print(f'checking {cmd}')

        try:
            validator._validate_set(cmd)
        except ValidationError:
            print(message)


if __name__ == '__main__':
    try:
        # test_complete()
        test_validate()
    except KeyboardInterrupt:
        pass
