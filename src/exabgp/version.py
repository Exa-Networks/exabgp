from __future__ import annotations

import os
import sys
from datetime import datetime


def get_zipapp() -> str:
    return os.path.abspath(os.path.sep.join(__file__.split(os.path.sep)[:-2]))


def get_root() -> str:
    if os.path.isfile(get_zipapp()):
        return get_zipapp()
    return os.path.abspath(os.path.sep.join(__file__.split(os.path.sep)[:-1]))


def _is_zipapp() -> bool:
    """Check if running from a zipapp."""
    return os.path.isfile(get_zipapp())


def _is_venv() -> bool:
    """Check if running inside a virtual environment."""
    return sys.prefix != sys.base_prefix


def _is_pip_install() -> bool:
    """Check if running from a pip-installed package (not editable/venv)."""
    # In a venv, it's likely an editable install for development
    if _is_venv():
        return False

    try:
        from importlib.metadata import version as pkg_version

        pkg_version('exabgp')
        return True
    except Exception:
        return False


def _get_base_version() -> str:
    """Get base version from installed package or pyproject.toml.

    Priority:
    1. importlib.metadata (installed package)
    2. pyproject.toml (dev checkout)
    3. 'unknown' fallback
    """
    # Try importlib.metadata first (installed package)
    try:
        from importlib.metadata import version as pkg_version

        return pkg_version('exabgp')
    except Exception:
        pass

    # Fall back to parsing pyproject.toml (dev checkout)
    try:
        import tomllib

        pyproject = os.path.join(os.path.dirname(__file__), '..', '..', 'pyproject.toml')
        if os.path.exists(pyproject):
            with open(pyproject, 'rb') as f:
                version: str = tomllib.load(f)['project']['version']
                return version
    except Exception:
        pass

    return 'unknown'


# Modification time for dev builds
try:
    _file = os.path.abspath(__file__)
    _modification_time = os.path.getmtime(_file)
except NotADirectoryError:
    _modification_time = os.path.getmtime(get_zipapp())

_date = datetime.fromtimestamp(_modification_time)

# Version strings - base version from pyproject.toml
_base = _get_base_version()
json = _base
json_v4 = '4.0.1'  # Legacy API v4 JSON version string (frozen)
text_v4 = '4.0.1'  # Legacy API v4 text version string (frozen)

# For pip installs or zipapps, use clean version; otherwise dev version with date suffix
_is_release = _is_pip_install() or _is_zipapp()
_default_version = _base if _is_release else f'{_base}-{_date.strftime("%Y%m%d")}+uncontrolled'
version = os.environ.get('exabgp_version', _default_version)

# Do not change the first line as it is parsed by scripts

# Python version requirements
REQUIRED_PYTHON_MAJOR = 3  # Minimum Python major version
REQUIRED_PYTHON_MINOR = 12  # Minimum Python minor version for Python 3.x

if sys.version_info.major < REQUIRED_PYTHON_MAJOR:
    sys.exit('exabgp requires python3.12 or later')
if sys.version_info.major == REQUIRED_PYTHON_MAJOR and sys.version_info.minor < REQUIRED_PYTHON_MINOR:
    sys.exit('exabgp requires python3.12 or later')


def latest_github():
    import json as json_lib
    import urllib.request

    latest = json_lib.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                'https://api.github.com/repos/exa-networks/exabgp/releases',
                headers={'Accept': 'application/vnd.github.v3+json'},
            ),
        ).read(),
    )
    return latest[0]['tag_name']


def time_based():
    import datetime

    return datetime.date.today().isoformat().replace('-', '.')


if __name__ == '__main__':
    sys.stdout.write(version)
