---
name: posting-attribution
description: Any text posted to GitHub (or anywhere public) from Thomas's account must state that Claude wrote it
metadata:
  type: feedback
---

Every comment, issue, pull request body or review posted with Thomas's credentials must open with a
line making clear that Claude wrote the text, not Thomas. This applies to ALL posts, on every
repository, without exception.

**Why:** the post goes out under Thomas's name. Unattributed text reads as his own words and
opinions, which misrepresents him, and he is not the author of what Claude writes (nor the reverse).
He had to manually prefix an earlier comment of mine on issue #1407 with "Claude was asked to review
the documentation ... and it reports:" to repair exactly this.

**How to apply:** before calling `gh issue comment`, `gh pr create`, `gh pr comment` or any equivalent,
put an attribution line at the top of the body, for example:

    *Posted by Claude (AI assistant) working on Thomas's machine, not written by Thomas.*

Then the content. Ask before posting when the content is a judgement call about the project's
direction, and never post a correction of Thomas's own words without checking with him first.
