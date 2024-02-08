import os
import sys
from datetime import datetime

commit = "99de31e8"
release = "5.0.0dev%s" % datetime.now().strftime('%Y%m%d%H%M%S')
json = "5.0.0"
text = "5.0.0"
version = os.environ.get('EXABGP_VERSION', release)

# Do not change the first line as it is parsed by scripts

if sys.version_info.major < 3:
    sys.exit('exabgp requires python3.7 or later')
if sys.version_info.major == 3 and sys.version_info.minor < 7:
    sys.exit('exabgp requires python3.7 or later')


def latest_github():
    import json as json_lib
    import urllib.request

    latest = json_lib.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                'https://api.github.com/repos/exa-networks/exabgp/releases',
                headers={'Accept': 'application/vnd.github.v3+json'},
            )
        ).read()
    )
    return latest[0]['tag_name']


def time_based():
    import datetime

    return datetime.date.today().isoformat().replace('-', '.')


if __name__ == '__main__':
    if version == release:
        version = time_based()
    sys.stdout.write(version)
