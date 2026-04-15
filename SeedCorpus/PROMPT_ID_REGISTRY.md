# Prompt ID Registry

Authoritative registry of every system prompt in Record Health.

Governed by ARCHITECTURE.md §3.3 (Prompt Identity and Versioning,
RecordHealth_App repo). Storage schema and registration endpoints
defined in GRADING_TOOL_DESIGN.md sprint GT-1.5. Initial
population is sprint GT-1.5a.

## Status

Provisional — empty until GT-1.5a audit sprint populates it from
the iOS codebase. No prompt_ids are assumed, guessed, or
pre-assigned. Every entry below will be written by GT-1.5a after
developer confirmation of the inventory.

## Registry

| prompt_id | current_version | type | location | notes |
|-----------|-----------------|------|----------|-------|
| (empty — populated by GT-1.5a) | | | | |

## Discipline

- Adding a prompt → add a registry row in the same commit that
  introduces the prompt. Register the prompt_text in
  prompt_versions (Worker) in the same PR.
- Changing a prompt's text → bump the version in both the code
  location and this registry, and register the new
  (prompt_id, version) in prompt_versions. Same commit.
- Removing a prompt → mark deprecated in notes. Do not delete the
  row. Do not reuse the prompt_id.
- Renaming a prompt_id is forbidden. If the purpose changes,
  assign a new prompt_id and deprecate the old one.

## Invariants

- prompt_id is permanent from first commit.
- (prompt_id, version) is append-only in prompt_versions. Text
  cannot change for an existing pair — bump the version instead.
- Every audit_fields row and grading record references a
  (prompt_id, version) pair that exists in this registry.
