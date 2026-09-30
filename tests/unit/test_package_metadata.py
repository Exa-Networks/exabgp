"""Source builds obtain their download URL without importing runtime package state."""

import os
from pathlib import Path
import subprocess
import sys
import tomllib
from email.parser import Parser


ROOT = Path(__file__).resolve().parents[2]


def test_source_build_download_url_names_the_project_version(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.pop('EXABGP_MYPYC', None)
    result = subprocess.run(
        [sys.executable, 'setup.py', 'egg_info', '--egg-base', str(tmp_path)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert 'Traceback' not in result.stderr, result.stderr
    metadata = Parser().parsestr((tmp_path / 'exabgp.egg-info' / 'PKG-INFO').read_text())
    with (ROOT / 'pyproject.toml').open('rb') as reader:
        version = tomllib.load(reader)['project']['version']
    assert metadata['Download-URL'] == f'https://github.com/Exa-Networks/exabgp/archive/{version}.tar.gz'
