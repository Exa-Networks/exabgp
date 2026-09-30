# http://teethgrinder.co.uk/perm.php?a=Python-memory-leak-detector
from __future__ import annotations

import gc
import inspect

# How much of the str() of a garbage object is printed before it is cut short.
MAX_DESCRIPTION_LENGTH = 80


def dump() -> None:
    # force collection
    print('\nCollecting GARBAGE:')
    gc.collect()
    # prove they have been collected
    print('\nCollecting GARBAGE:')
    gc.collect()

    print('\nGARBAGE OBJECTS:')
    for x in gc.garbage:
        s = str(x)
        if len(s) > MAX_DESCRIPTION_LENGTH:
            s = '%s...' % s[:MAX_DESCRIPTION_LENGTH]

        print('::', s)
        print('		type:', type(x))
        print('   referrers:', len(gc.get_referrers(x)))
        _print_source(x)
        print()


def _print_source(x: object) -> None:
    print('	is class:', inspect.isclass(type(x)))
    print('	  module:', inspect.getmodule(x))
    try:
        lines, line_num = inspect.getsourcelines(type(x))
    except (OSError, TypeError):
        # A builtin or C class has no Python source (TypeError), and a class defined
        # somewhere the source is not kept, an interpreter prompt or a zip, has none to
        # read (OSError). The rest of the dump is still worth having.
        return
    print('	line num:', line_num)
    for line in lines:
        print('		line:', line.rstrip('\n'))
