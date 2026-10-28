"""The healthcheck reads its options from a file as it reads them from its command line.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from ipaddress import ip_network
from pathlib import Path
from unittest.mock import patch

from exabgp.application.healthcheck import parse


def test_a_configuration_file_is_read_as_options(tmp_path: Path) -> None:
    config = tmp_path / 'healthcheck.conf'
    config.write_text('# the interval, then an address\ninterval = 7\n\n ip=192.0.2.0/24 \ncommand=true\n')

    with patch('sys.argv', ['healthcheck', '--config', str(config)]):
        options = parse()

    assert options.interval == 7
    assert options.ips == [ip_network('192.0.2.0/24')]
    assert options.command == 'true'


def test_the_command_line_is_read_after_the_file(tmp_path: Path) -> None:
    config = tmp_path / 'healthcheck.conf'
    config.write_text('interval=7\n')

    with patch('sys.argv', ['healthcheck', '--config', str(config), '--interval', '3']):
        options = parse()

    assert options.interval == 3
