"""Draws which reach the awkward values, rather than reaching them by luck.

`st.binary()` is the right draw for "arbitrary bytes must raise Notify and never crash":
every input exercises the length checks, so uniform sampling explores what matters.

It is the wrong draw when the bug lives in a *value* which only a narrow byte pattern
produces. Issue #1426 is the worked example. A `traffic-rate` extended community carries
an IEEE-754 single, and the community is only a NaN or an infinity when the float's
exponent is all ones, which needs one of two values in one byte and one of two in the
next. Measured over a hundred thousand uniform six byte draws that is 0.39% of them, so
the gate's two hundred examples per code find it 54% of the time. The first version of
`test_attribute_decoder_properties.py` was made to go red by reverting the fix, went red on
this branch, and stayed green on 5.0 with exactly the same defect present. A sweep which
finds a bug on a coin toss reads in the summary line exactly like one which finds it every
time.

`payload()` draws half its examples from uniform bytes and half from the byte values which
sit on the boundaries. It is a superset of what `st.binary()` explores, never a subset, so
swapping it in cannot narrow a sweep.
"""

from __future__ import annotations

from hypothesis import strategies as st

# 0x00 and 0xFF are the ends of the range, 0x7F and 0x80 the sign boundary, and 0x01 the
# smallest non-zero. Between them they build the all-ones exponents, the maximum lengths,
# the zero lengths and the reserved-bit patterns that decoders are gated on.
INTERESTING_BYTES = [0x00, 0x01, 0x7F, 0x80, 0xFF]


def payload(min_size_bytes: int, max_size_bytes: int) -> st.SearchStrategy[bytes]:
    """Uniform bytes or boundary bytes, so the awkward values are actually reached."""
    return st.one_of(
        st.binary(min_size=min_size_bytes, max_size=max_size_bytes),
        st.lists(st.sampled_from(INTERESTING_BYTES), min_size=min_size_bytes, max_size=max_size_bytes).map(bytes),
    )
