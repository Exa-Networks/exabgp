# The RFC requirement ledger

"exabgp implements RFC 4271" is a claim about a few hundred separate sentences. A test
suite says nothing about which of them are covered: `test_open_rejects_bad_version`
proves something about section 6.2, but only to a reader who already knows what section
6.2 says.

This directory makes the claim checkable. It holds, per RFC:

- `<rfc>.toml` - one entry per normative sentence, quoted verbatim
- `text/<rfc>.txt` - the RFC as published, so the quotes can be verified

and tests elsewhere in the tree carry `@pytest.mark.rfc('<id>')`, naming the
requirements they prove. `./qa/bin/check_rfc_compliance` joins the two and fails when
they disagree.

## Why the quote is verbatim

Requirement lists written from memory are wrong in both directions: they invent MUSTs a
document does not contain, and they invert the ones it does. So every `text` in a ledger
is checked, whitespace-normalised, against `text/<rfc>.txt` on every run. A requirement
which is not in the RFC cannot be committed, whatever wrote it.

Two consequences when you are writing an entry:

- Do not paraphrase, do not fix the RFC's grammar, do not join two sentences which are
  not adjacent in the document. Copy the lines.
- Do not quote across a page break. The footer and header are part of the file and will
  land in the middle of your quote.

## Adding a requirement

1. Fetch the RFC if it is not here yet:

   ```
   curl -o qa/rfc/text/rfc4271.txt https://www.rfc-editor.org/rfc/rfc4271.txt
   ```

2. Add an entry to `qa/rfc/rfc4271.toml`:

   ```toml
   [[requirement]]
   id = "rfc4271#6.2-version-not-supported"
   section = "6.2"
   level = "MUST"
   status = "required"
   polarity = "both"
   text = """
   If the version number in the Version field of the received OPEN
   message is not supported, then the Error Subcode MUST be set to
   Unsupported Version Number.
   """
   ```

   `id` is `<rfc>#<section>-<slug>`. The slug says what the requirement is about, so a
   reviewer reading a test can tell what it claims without opening the ledger.

3. Write the tests and mark them:

   ```python
   @pytest.mark.rfc('rfc4271#6.2-version-not-supported')
   def test_an_open_with_version_four_is_accepted() -> None: ...

   @pytest.mark.rfc('rfc4271#6.2-version-not-supported', polarity='negative')
   def test_an_open_with_version_five_is_refused_with_subcode_one() -> None: ...
   ```

4. Lower the ceiling:

   ```
   ./qa/bin/check_rfc_compliance --update-baseline
   ```

## Both sides of a MUST

A MUST-level requirement needs a **positive** and a **negative** test unless the ledger
says otherwise.

The positive test shows we do the thing. The negative test shows we notice when the
other end does not, and that is the half which finds bugs: a decoder which accepts
everything passes every positive test ever written. For a `MUST NOT` the polarities read
the same way round, the positive test being the one where we comply.

When a requirement genuinely has only one meaningful side, say so and say why:

```toml
polarity = "positive-only"
note = """
This is a property of the identifiers we assign, so the meaningful test is that two
paths stay distinct through the RIB. There is no peer input which violates it.
"""
```

## What we do about a requirement

`status` is one of:

| status | meaning | test expected |
| --- | --- | --- |
| `required` | we implement it, and a test must prove it | yes |
| `gap` | we owe it and do not do it. An admission, with a reason | no |
| `not-applicable` | the obligation never bound exabgp at all | no |

`gap` and `not-applicable` both need a `note`. "Not applicable" with no reason is
indistinguishable from "not done yet", which is exactly what this directory exists to
stop. Be specific: *"exabgp does not manipulate the FIB, so there is no forwarding state
for this to describe"* is a reason; *"n/a"* is not.

The difference between the two matters. `not-applicable` is a decision that closes;
`gap` stays on the ledger and shows up in the generated report as something we owe.

## Demonstrating a gap instead of describing it

A test may carry both `rfc()` and `xfail`:

```python
@pytest.mark.rfc('rfc7911#5-send-requires-both-directions')
@pytest.mark.xfail(strict=True, reason='we send with send/receive 1, see plan/...')
def test_we_do_not_send_multiple_paths_without_receiving_the_capability() -> None: ...
```

That is worth more than a line in a plan file, because it runs. The requirement is
reported as a known gap rather than as proven, and the day the behaviour arrives the
`xfail` becomes an unexpected pass and the suite says so.

## Levels

Only `MUST`, `MUST NOT`, `REQUIRED`, `SHALL` and `SHALL NOT` are gated. `SHOULD` and
`MAY` are recorded and reported, because knowing which ones we follow is useful, but a
SHOULD we decline is a decision rather than a defect.

## Enrolment

An RFC is enrolled when it has a count in `qa/rfc_compliance.json`. The count is a
ceiling on untested binding requirements which may fall and may not rise, the same
ratchet `qa/exa_style.json` applies to the style rules. Adding a ledger without
enrolling it fails the check, so enrolling is a deliberate act rather than something
that happens to you.

## Commands

```
./qa/bin/check_rfc_compliance                            # the gate
./qa/bin/check_rfc_compliance --report                   # coverage per RFC
./qa/bin/check_rfc_compliance --show                     # what is untested
./qa/bin/check_rfc_compliance --markdown doc/RFC_COMPLIANCE.md
./qa/bin/check_rfc_compliance --update-baseline
```
