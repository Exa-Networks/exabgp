# ERROR RECOVERY PROTOCOL

After mistakes: rushed to fix faster, created more errors.

---

## MANDATORY RULES

**1. NEVER rush after mistake**
- Slow down, not speed up
- Mistakes compound when rushing

**2. ALWAYS follow protocols after errors**
- Read GIT_VERIFICATION_PROTOCOL.md before git ops
- Read MANDATORY_REFACTORING_PROTOCOL.md before changes
- Check `pwd` before operations
- Verify with `ls` before/after moves

**3. NEVER fear upsetting user**
- User prefers slow + correct over fast + broken
- Ask clarifying questions vs make assumptions
- Quality > Speed

**4. When you make mistake:**
1. STOP
2. Acknowledge clearly
3. SLOW DOWN
4. Read relevant protocol
5. Verify state (`pwd`, `ls`, `git status`)
6. Plan fix
7. Execute methodically
8. Verify fix

**5. CRITICAL: When user corrects you**
- User correction = protocol gap
- IMMEDIATELY offer: "Should I update [PROTOCOL].md to prevent this?"
- If yes: Update protocol with specific rule
- Do NOT just apologize - FIX THE PROTOCOL

**6. Common mistake patterns:**
- Working in wrong directory → check `pwd` first
- Creating in wrong place → verify path before `mkdir`
- Moving non-existent files → verify with `ls` first
- Batch without verification → verify each step

**7. Git with pre-existing changes:**
- NEVER run `git add -A` without explicit confirmation
- NEVER assume "commit" means "commit all files"
- ALWAYS ask which files when multiple modified
- Even if user says "commit", STOP and ask: "Which files?"
- List: "[my changes] + [pre-existing]"
- WAIT for explicit answer

---

## Recovery Checklist

After ANY mistake:
- [ ] Stop and breathe
- [ ] Acknowledge mistake
- [ ] Identify protocol violated
- [ ] Re-read that protocol
- [ ] Verify current state
- [ ] Plan fix step-by-step
- [ ] Execute methodically
- [ ] Verify each step

After user corrects you:
- [ ] ALWAYS offer to update protocol
- [ ] Add rule to prevent exact error
- [ ] Verify protocol captures lesson

**User's patience > Your speed**
**Protocol improvements > Apologies**

---

## ENFORCEMENT

After making ANY mistake:
- [ ] STOPPED immediately
- [ ] Acknowledged mistake clearly
- [ ] Identified which protocol violated
- [ ] Re-read that protocol (paste name)
- [ ] Verified current state: `<paste git status / pwd / ls output>`
- [ ] Planned fix in numbered steps
- [ ] Executed methodically (one step at a time)

**If ANY unchecked: SLOW DOWN MORE.**

After user corrects me:
- [ ] Offered to update protocol
- [ ] User said yes/no: `<paste response>`
- [ ] If yes: Updated protocol with specific rule

**If ANY unchecked: OFFER NOW.**

---

## VIOLATION DETECTION

**If I do these after mistake, I'm violating:**
- Speed up instead of slow down
- Skip re-reading protocol
- Batch multiple fixes together
- Make assumptions without verification
- Apologize without offering protocol update

**Auto-fix:** Stop. Breathe. Re-read protocol. One step at a time.
