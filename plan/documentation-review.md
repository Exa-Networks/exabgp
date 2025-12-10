# Plan: Review and Update .claude/exabgp/ Documentation

## Status: ⏸️ On Hold

## Objective
Review and update the existing `.claude/exabgp/` documentation files to ensure they are:
- Up to date with current codebase
- Exhaustive in coverage
- Accurate in technical details

## Files to Review (21 total)

### Architecture & Structure
1. `CODEBASE_ARCHITECTURE.md` - Directory structure, module purposes
2. `DATA_FLOW_GUIDE.md` - Inbound/outbound data pipelines
3. `CRITICAL_FILES_REFERENCE.md` - Key files for modification

### Design Patterns
4. `REGISTRY_AND_EXTENSION_PATTERNS.md` - Adding NLRI, attributes, commands
5. `PACKED_BYTES_FIRST_PATTERN.md` - Wire format storage pattern
6. `WIRE_SEMANTIC_SEPARATION.md` - Wire vs semantic containers
7. `COLLECTION_PATTERN.md` - Collection pattern reference
8. `NLRI_CLASS_HIERARCHY.md` - NLRI inheritance and slots
9. `PEP688_BUFFER_PROTOCOL.md` - Buffer protocol reference
10. `BUFFER_SHARING_AND_CACHING.md` - Caching patterns

### BGP Concepts
11. `BGP_CONCEPTS_TO_CODE_MAP.md` - RFC concepts to code locations

### CLI & API
12. `CLI_COMMANDS.md` - CLI command reference
13. `CLI_SHORTCUTS.md` - CLI shortcut reference
14. `CLI_IMPLEMENTATION.md` - CLI internal architecture
15. `UNIX_SOCKET_API.md` - Unix socket API protocol
16. `API_FORMAT_VERSIONS.md` - API v4 vs v6 formats
17. `NEIGHBOR_SELECTOR_SYNTAX.md` - Neighbor selector grammar

### Configuration & Environment
18. `ENVIRONMENT_VARIABLES.md` - All exabgp_* variables

### Testing
19. `FUNCTIONAL_TEST_RUNNER.md` - Test runner documentation

### Other
20. `LOGGING_STYLE_GUIDE.md` - Logging conventions
21. `TOKENISER_USAGE.md` - Tokeniser usage patterns

## Review Process

For each file:
1. Read current content
2. Compare against actual codebase
3. Identify outdated information
4. Identify gaps in coverage
5. Update content as needed
6. Update "Updated:" timestamp

## Review Criteria

### Accuracy
- [ ] File paths are correct
- [ ] Line counts are approximate (not exact)
- [ ] Code examples compile/work
- [ ] Function signatures match actual code
- [ ] Class hierarchies are accurate

### Completeness
- [ ] All relevant modules/files covered
- [ ] All patterns documented
- [ ] All edge cases mentioned
- [ ] Cross-references to related docs included

### Currency
- [ ] Uses Python 3.12+ syntax
- [ ] Reflects current design patterns (packed-bytes-first, etc.)
- [ ] Mentions asyncio dual-mode support
- [ ] Updated timestamp is recent

## Implementation Strategy

**Phase 1: Quick audit**
- Read each file header and structure
- Note obvious outdated content
- Prioritize files needing most updates

**Phase 2: Deep review**
- Update each file systematically
- Verify against codebase
- Add missing information

**Phase 3: Verification**
- Cross-reference between docs
- Ensure consistency
- Update cross-links

## Files Modified
Will update: `.claude/exabgp/*.md` (21 files)

## Progress

- [ ] Phase 1: Quick audit
- [ ] Phase 2: Deep review
- [ ] Phase 3: Verification

---

**Created:** 2025-12-10
**Last Updated:** 2025-12-10
