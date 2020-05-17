#!/usr/bin/env python

import sys
import json
import pprint

exit = False

while True:
    line = sys.stdin.readline().strip()

    if not line:
        if exit:
            sys.exit(0)
        exit = True
    else:
        exit = False

    sys.sterr.write(f'\n=====\n{line}\n---\n')
    sys.stderr.write(pprint.pformat(json.loads(line), indent=3).replace("u'", "'"))
    sys.sterr.write('\n')
    sys.stderr.flush()
