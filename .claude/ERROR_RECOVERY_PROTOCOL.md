# ERROR RECOVERY PROTOCOL

**Why this exists:** After making mistakes, rushed to "fix" things faster, created more errors, violated protocols.

## MANDATORY RULES

**1. NEVER rush after making a mistake**
- Slow down, not speed up
- Mistakes compound when rushing
- Take time to verify each step

**2. ALWAYS follow existing protocols, especially after errors**
- Read GIT_VERIFICATION_PROTOCOL.md before git operations
- Read MANDATORY_REFACTORING_PROTOCOL.md before changes
- Check file locations with `pwd` before operations
- Verify with `ls` before and after moves

**3. NEVER fear upsetting the user**
- User prefers slow and correct over fast and broken
- Better to ask clarifying questions than make assumptions
- User will tell you when to move faster
- Quality > Speed

**4. When you make a mistake:**
1. STOP
2. Acknowledge the mistake clearly
3. SLOW DOWN (do not speed up)
4. Read relevant protocols
5. Verify current state (`pwd`, `ls`, `git status`)
6. Plan fix carefully
7. Execute fix methodically
8. Verify fix worked

**5. CRITICAL: When user corrects you - ALWAYS offer to update protocols**
- User correction = protocol gap that will cause same error in future sessions
- IMMEDIATELY offer: "Should I update [PROTOCOL_NAME].md to prevent this error in future sessions?"
- If yes: Update protocol with specific rule to prevent this exact error
- This creates self-improving system that gets better over time
- Do NOT just apologize and move on - FIX THE PROTOCOL

**Example:**
```
User: "Files in .claude/ should be UPPERCASE"
You: "You're right - I violated FILE_NAMING_CONVENTIONS.md.
     Should I update FILE_NAMING_CONVENTIONS.md to explicitly
     document that .claude/ protocol files use UPPERCASE?"
```

**6. Common mistake patterns to avoid:**
- Working in wrong directory → Always check `pwd` first
- Creating directories in wrong place → Verify path before `mkdir`
- Moving files that don't exist → Verify with `ls` first
- Batch operations without verification → Verify each step
- Skipping git verification → ALWAYS follow GIT_VERIFICATION_PROTOCOL.md

## Example: File Move Operations

**WRONG (rushed after mistake):**
```bash
mkdir -p docs/projects/foo  # didn't check pwd
mv file.md docs/...  # didn't verify file exists
```

**CORRECT (methodical):**
```bash
pwd  # verify location
ls -la | grep file.md  # verify file exists
mkdir -p docs/projects/foo  # create destination
ls docs/projects/  # verify created
mv file.md docs/projects/foo/  # move
ls docs/projects/foo/  # verify moved
```

## Recovery Checklist

After making ANY mistake:
- [ ] Stop and breathe
- [ ] Acknowledge mistake to user
- [ ] Identify which protocol was violated
- [ ] Re-read that protocol
- [ ] Verify current system state
- [ ] Plan fix step-by-step
- [ ] Execute methodically
- [ ] Verify each step

**After user corrects you:**
- [ ] ALWAYS offer to update the protocol
- [ ] Add specific rule to prevent this exact error
- [ ] Verify protocol update captures the lesson

**User's patience > Your speed**
**Protocol improvements > Apologies**
