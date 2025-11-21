import os
import sys


def get_zipapp():
    return os.path.abspath(os.path.sep.join(__file__.split(os.path.sep)[:-2]))


def get_root():
    if os.path.isfile(get_zipapp()):
        return get_zipapp()
    return os.path.abspath(os.path.sep.join(__file__.split(os.path.sep)[:-1]))


commit = "078e4ef2"
release = "5.0.0"
json = "5.0.0"
text = "5.0.0"
version = os.environ.get('exabgp_version',release)

# Do not change the first line as it is parsed by scripts

if sys.version_info.major < 3:
    sys.exit('exabgp requires python3.6 or later')
if (sys.version_info.major == 3 and sys.version_info.minor < 6):
    sys.exit('exabgp requires python3.6 or later')

if __name__ == '__main__':
    sys.stdout.write(version)
