"""One reader for the `raw:` capture lines in qa/encoding/*.ci and qa/api/*.ci.

A capture is `<step>:raw:<hexadecimal>` and the hexadecimal is punctuated four different
ways across the corpus: split as MARKER:LENGTH:TYPE:PAYLOAD, split as MARKER:LENGTHTYPE:
PAYLOAD, split somewhere inside the payload, and not split at all.  The colons are a
reading aid and carry nothing; the bytes are the same either way.

Before this module each reader had its own pattern and ignored what the pattern missed.
test_json demanded the fully split form and saw 325 of the 395 captures.  test_api_encode
demanded a numeric step and saw 379, missing the A1/B1 steps of api-reload.ci and
api-teardown.ci.  qa/bin/functional splits on the first two colons and sees all of them.
Three dialects, three different answers about what is in the same files.

The damage was not the narrow pattern, it was the silence: a line which did not match fell
out of the loop with nothing counted.  test_json also GENERATES the json: expectations, so
no expectation was ever written for a capture it could not read, and the hole was self
consistent and therefore permanently green.  conf-sr-policy.ci is written entirely without
inner colons and all seven of its captures were unchecked while the summary said
`Passed: 248, Failed: 0`.

So a line which says `raw:` and which this cannot read comes back as a RawProblem, and a
caller which drops one is dropping an object rather than failing a match.
"""

from __future__ import annotations

import re

MARKER_HEX = 32  # the 16 byte all-ones marker
LENGTH_HEX = 4  # the 2 byte length
TYPE_HEX = 2  # the 1 byte message type
HEADER_HEX = MARKER_HEX + LENGTH_HEX + TYPE_HEX

# The length field is two bytes, so a capture cannot describe more than this many bytes.
# The equality check in parse_raw is what enforces the cap: a longer line disagrees with
# the largest number the field can hold.
MAX_MESSAGE_BYTES = 0xFFFF

UPDATE_TYPE = '02'

# How many skipped captures get named before the list is cut short.  Long enough that
# today's whole backlog is printed, short enough that a corpus wide regression does not
# bury the summary under it.
MAX_NAMED = 80

# The step is whatever comes before `:raw:`.  Numbers in most files, A1/B1/C1 where a
# test groups messages by connection, and nothing here cares which.
_CAPTURE = re.compile(r'^([^:\s]+):raw:(.*)$')
_HEXADECIMAL = re.compile(r'^[0-9A-Fa-f]+$')


class RawCapture:
    """One `raw:` line, read the one way every reader agrees on."""

    __slots__ = ('line_number', 'step', 'hexadecimal')

    def __init__(self, line_number: int, step: str, hexadecimal: str) -> None:
        assert len(hexadecimal) >= HEADER_HEX, 'parse_raw checked the header is present'
        assert len(hexadecimal) % 2 == 0, 'parse_raw checked the digits pair up'
        assert len(hexadecimal) <= 2 * MAX_MESSAGE_BYTES, 'parse_raw checked the declared length'
        self.line_number = line_number
        self.step = step
        self.hexadecimal = hexadecimal

    @property
    def message_type(self) -> str:
        return self.hexadecimal[MARKER_HEX + LENGTH_HEX : HEADER_HEX].upper()

    @property
    def payload(self) -> str:
        return self.hexadecimal[HEADER_HEX:]

    @property
    def is_update(self) -> bool:
        return self.message_type == UPDATE_TYPE

    @property
    def is_end_of_rib(self) -> bool:
        """An UPDATE announcing nothing: empty, or MP_UNREACH carrying only an AFI/SAFI."""
        payload = self.payload.upper()
        return payload == '00000000' or payload.startswith('00000007900F0003')


class RawProblem:
    """A line which says `raw:` and which cannot be read as one.

    Returned rather than ignored so the caller has to decide what to do with it.  There
    are none in the corpus today, which is worth keeping true.
    """

    __slots__ = ('line_number', 'text', 'reason')

    def __init__(self, line_number: int, text: str, reason: str) -> None:
        self.line_number = line_number
        self.text = text
        self.reason = reason


class Skipped:
    """A capture a reader met and did not check, and the reason it did not."""

    __slots__ = ('where', 'reason')

    def __init__(self, where: str, reason: str) -> None:
        self.where = where
        self.reason = reason


def parse_raw(line: str, line_number: int) -> RawCapture | RawProblem | None:
    """Read one line of a .ci file.

    Returns None when the line is not a capture at all, a RawCapture when it reads, and a
    RawProblem when it claims to be a capture and does not.  A caller must account for
    every RawCapture and every RawProblem it is handed: that accounting is the point.
    """
    text = line.strip()
    if ':raw:' not in text or text.startswith('#'):
        return None

    match = _CAPTURE.match(text)
    if match is None:
        return RawProblem(line_number, text, 'not <step>:raw:<hexadecimal>')

    hexadecimal = match.group(2).replace(':', '')
    if not _HEXADECIMAL.match(hexadecimal):
        return RawProblem(line_number, text, 'the capture is not hexadecimal')
    if len(hexadecimal) % 2:
        return RawProblem(line_number, text, f'{len(hexadecimal)} hexadecimal digits do not pair up into bytes')
    if len(hexadecimal) < HEADER_HEX:
        held = len(hexadecimal) // 2
        return RawProblem(line_number, text, f'{held} bytes is shorter than a {HEADER_HEX // 2} byte BGP header')

    declared = int(hexadecimal[MARKER_HEX : MARKER_HEX + LENGTH_HEX], 16)
    held = len(hexadecimal) // 2
    if declared != held:
        return RawProblem(line_number, text, f'the header declares {declared} bytes and the line holds {held}')

    return RawCapture(line_number, match.group(1), hexadecimal)


def where(relative_path: object, capture: RawCapture | RawProblem) -> str:
    """How a capture is named in a report: the file, the line, and the step."""
    step = capture.step if isinstance(capture, RawCapture) else '?'
    return f'{relative_path}:{capture.line_number} step {step}'


def report_skipped(skipped: list[Skipped], named: set[str]) -> None:
    """Print what was met and not checked: every reason counted, some also named.

    A bare count is what let the hole hide, so the reasons which mean missing coverage
    are printed line by line rather than folded into a number.
    """
    counts: dict[str, int] = {}
    for entry in skipped:
        counts[entry.reason] = counts.get(entry.reason, 0) + 1
    for reason in sorted(counts, key=lambda name: (-counts[name], name)):
        print(f'  {counts[reason]:4}  {reason}')

    loud = [entry for entry in skipped if entry.reason in named]
    if not loud:
        return
    print()
    print(f'{len(loud)} capture line(s) this run looked at and checked nothing about:')
    for entry in loud[:MAX_NAMED]:
        print(f'  {entry.where}  ({entry.reason})')
    if len(loud) > MAX_NAMED:
        print(f'  ... and {len(loud) - MAX_NAMED} more')


def report_problems(problems: list[tuple[str, RawProblem]]) -> None:
    """Print the lines no reader could make sense of.  There should never be any."""
    if not problems:
        return
    print()
    print(f'{len(problems)} line(s) say raw: and cannot be read as a capture:')
    for location, problem in problems[:MAX_NAMED]:
        print(f'  {location}: {problem.reason}')
        print(f'    {problem.text[:100]}')
    if len(problems) > MAX_NAMED:
        print(f'  ... and {len(problems) - MAX_NAMED} more')
