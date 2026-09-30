"""exabgp current version"""

from __future__ import annotations

import sys
import argparse
import platform

from exabgp.version import version, get_root


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    pass
    # fmt:on


def build() -> str:
    """'mypyc' when the message code runs compiled (doc/user/compiled-build.md), else 'python'."""
    from exabgp.bgp.message.update.nlri import inet

    # .pyc: a frozen tree (the PyInstaller executable) holds the byte code without the source
    return 'python' if (inet.__file__ or '').endswith(('.py', '.pyc')) else 'mypyc'


def main() -> None:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> None:
    python_version = sys.version.replace('\n', ' ')
    sys.stdout.write(f'ExaBGP : {version}\n')
    sys.stdout.write(f'Python : {python_version}\n')
    sys.stdout.write(f'Build  : {build()}\n')
    uname_str = ' '.join(platform.uname()[:5])
    sys.stdout.write(f'Uname  : {uname_str}\n')
    sys.stdout.write(f'From   : {get_root()}\n')
    sys.stdout.flush()


if __name__ == '__main__':
    main()
