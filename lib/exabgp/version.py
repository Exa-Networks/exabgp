import os

commit = "bbe42ac9"
release = "4.2.15"
json = "4.0.1"
text = "4.0.1"
version = os.environ.get('EXABGP_VERSION',release)

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
    import sys
    sys.stdout.write(version)
