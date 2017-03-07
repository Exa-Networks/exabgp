# encoding: utf-8
"""
test.py

"""

import sys

def data_from_body(body):
    if sys.version_info[0]<3:
        return ''.join(chr(_) for _ in body)
    else: # python3
        return bytes(body)
