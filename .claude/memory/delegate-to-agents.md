# Delegate the work to agents, do not do it yourself

Thomas corrected this twice in one session (2026-09-24). The first time:
"use agents". The second, after a single further agent was launched:
"use as many as practical".

**Why:** agents run in parallel and their tool output stays out of the main
context, so the session can hold far more work in flight than one worker doing
edits inline. Doing a fix by hand costs the same tokens as reviewing an agent's
fix, and delivers one instead of eight.

**How to apply:**

- Default to fanning out. Carve the work into DISJOINT FILE SETS and launch one
  agent per set, several in a single message. Name the files each agent may
  touch and name the files other agents hold, so they stop and report rather
  than widening.
- Keep for yourself only: verifying findings against the source, committing, and
  anything touching a shared ratchet (`qa/exa_style.json`,
  `qa/rfc_compliance.json`). Tell agents explicitly not to run
  `--update-baseline` or any mutating git command.
- Agents must not commit. Reports come back, you verify the interesting claims
  yourself, then you stage file-by-file. That also keeps another live session's
  edits out of your commits.
- Nine concurrent agents worked fine in this repository. Collisions came from
  shared TEST files and shared `qa/rfc/*.toml`, not from source files, so assign
  test-file ownership as carefully as source-file ownership.

Related: [[verify-agent-findings-before-relaying]]
