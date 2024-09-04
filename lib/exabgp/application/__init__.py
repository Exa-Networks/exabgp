# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2014-12-31.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


def main():
    from exabgp.application.main import main

    main()


def run_exabgp():
    from exabgp.application.bgp import main

    main()


def run_exabmp():
    from exabgp.application.bmp import main

    main()


def run_healthcheck():
    from exabgp.application.healthcheck import main

    main()


def run_cli():
    from exabgp.application.cli import main

    main()


def run_control():
    from exabgp.application.control import main

    main()
