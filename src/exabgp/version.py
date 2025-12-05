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


try:
    file = os.path.abspath(__file__)
    modification_time = modification_time = os.path.getmtime(file)
except NotADirectoryError:
    zipapp = get_zipapp()
    modification_time = modification_time = os.path.getmtime(zipapp)

date = datetime.fromtimestamp(modification_time)

commit = 'unset'
release = '6.0.0-{}+uncontrolled'.format(date.strftime('%Y%m%d'))
json = '6.0.0'
json_v4 = '4.0.1'  # Legacy API v4 version string
text = '6.0.0'
text_v4 = '4.0.1'  # Legacy API v4 version string
version = os.environ.get('exabgp_version', release)

# Do not change the first line as it is parsed by scripts

# Python version requirements
REQUIRED_PYTHON_MAJOR = 3  # Minimum Python major version
REQUIRED_PYTHON_MINOR = 6  # Minimum Python minor version for Python 3.x

if sys.version_info.major < REQUIRED_PYTHON_MAJOR:
    sys.exit('exabgp requires python3.6 or later')
if sys.version_info.major == REQUIRED_PYTHON_MAJOR and sys.version_info.minor < REQUIRED_PYTHON_MINOR:
    sys.exit('exabgp requires python3.6 or later')


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
    if version == release:
        version = time_based()
    sys.stdout.write(version)
