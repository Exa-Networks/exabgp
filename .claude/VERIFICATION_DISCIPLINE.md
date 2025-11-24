# Verification Discipline

NEVER claim success without running tests first.

## Forbidden Phrases (Without Verification)

❌ "Perfect!" ❌ "All tests pass!" ❌ "Config is correct"
❌ "Everything works" ❌ "This is what you requested"

## Verification Rule

1. Run the actual command/test
2. Paste exact output
3. Let output prove success/failure
4. Say nothing else

## Stop Signals (You Haven't Verified)

**Defensive phrases:**
- "The config is correct because..."
- "As you can see..." (with no output)
- "This is exactly what..." (no proof)
- Multi-paragraph explanations of correctness

**False confidence:**
- ✅ checkmarks before running tests
- "All tests pass" without pasting output
- "Working correctly" without demonstration
- Listing what you think you did

## When User Says Something is Wrong

✅ **Right:** Ask what's broken OR just test it
❌ **Wrong:** Defend your work, re-explain, re-read files

## Verification Checklist

| Claim | Command | Paste |
|-------|---------|-------|
| "Config works" | `./sbin/exabgp -t <config>` | Output |
| "Test passes" | `./qa/bin/functional encoding <id>` | Full output |
| "Code works" | Run actual scenario | Output proof |

**Rule:** No pasted output = not verified.

---

## ENFORCEMENT

Before claiming success:
- [ ] Command: `<paste command>`
- [ ] Output: `<paste full output>`
- [ ] Exit code: 0

**If can't paste: HAVEN'T VERIFIED. STOP.**

---

## VIOLATION DETECTION

**If I write these, I'm violating:**
- "✅" without output immediately after
- "All tests pass" without command + output
- "Fixed" without proof
- Explanations instead of proof
- Defending instead of testing

**Auto-fix:** Stop. Run test. Paste output. One line.
