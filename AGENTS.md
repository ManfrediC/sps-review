# AGENTS.md

## Scope
This repo uses AI for:
- Python coding/refactoring
- debugging
- literature extraction/summarisation
- systematic review tooling
- reproducibility/documentation work

Optimise for:
1. correctness
2. reproducibility
3. non-hallucination
4. publication-quality output

Read and follow `doc/repo_rules.md` for repo-specific workflow, pipeline, output, and runtime rules.

## Working style
- Be concise, structured, and explicit about what you are doing.
- Use British English consistently in comments, docs, prose, commit messages, and user-facing text unless a file, dependency, API, citation, or quoted source requires otherwise.
- Make reasonable low-risk assumptions and proceed.
- Ask at once if ambiguity materially affects correctness.
- When no single path is clearly best, give options with pros/cons.
- Prefer small, reviewable patches over rewrites.
- Never make irreversible changes without approval.
- Use senior judgement: do not preserve weak architecture, duplicated logic, or inconsistent patterns by default.

## Modes
### Tutor
- Explain approach before code.
- Teach concepts explicitly.
- Do not do too much at once.

### Builder
- Read relevant files first.
- Preserve existing architecture unless change is justified.
- Propose a plan before multi-file edits.
- Prefer patch-style edits.
- For larger tasks, work in phases and stop after each verified phase for review.

### Debugger
- State the most likely root cause first.
- Propose the 2-3 most informative checks.
- Isolate with the smallest possible test.
- Do not broaden into rewrites before localising the issue.

### Reviewer
- Separate must-fix issues from optional improvements.
- Focus on correctness, reproducibility, and clarity.

### Repo steward
- Inspect README, config, tests, and entry points first.
- Keep docs and workflow descriptions aligned with behaviour.

## Workflow and refactoring
- Before any structural refactor on a file >300 LOC, first remove dead code where practical: unused imports, unused code, obsolete comments, debug prints/logging.
- Keep cleanup separate from the main refactor whenever possible.
- Do not attempt large multi-file refactors in one pass; break them into explicit phases.
- Prefer each phase to touch at most 5 files before verification.
- If work spans many unrelated files, split into smaller batches or parallel sub-agents where supported.
- If architecture is weak, naming/patterns inconsistent, or logic duplicated, propose and implement a justified structural fix.

## Context and edit discipline
- Re-read relevant files before editing; do not trust memory after long exchanges or context compaction.
- For large files, read in chunks rather than assuming one read captured everything.
- If tool output looks suspiciously short, rerun with narrower scope and note possible truncation.
- Re-read files after editing to confirm the intended change actually applied.
- Do not make repeated blind edits to the same file without verification in between.

## Editing rules
- Read relevant files before suggesting changes.
- Do not touch unrelated files without reason.
- Do not do giant rewrites without warning.
- If a rewrite is needed, explain why a patch is insufficient.
- Do not silently change interfaces, file locations, or side effects.
- Before changing a public function, CLI, schema, or data contract, search for downstream uses first.
- Keep edits small and reviewable.
- British English is preferred.

## Coding conventions
- Prioritise readability.
- Prefer small functions and clear names.
- Comment only where comments add value.
- Use relative paths, not machine-specific absolute paths.
- Avoid unnecessary dependencies.
- Keep I/O separate from core logic where practical.
- Use type hints when practical.
- Prefer deterministic, testable functions over implicit state.
- Do not mix unrelated refactors with behaviour changes unless clearly explained.

## Search discipline for Python changes
Search is not semantic. When renaming or changing any Python symbol, search separately for:
- direct calls/references
- imports/re-exports
- type annotations/protocols
- string literals containing the name
- dynamic imports, `getattr()`, `globals()`, `locals()`, registry patterns
- CLI entry points and config references
- tests, fixtures, mocks
- documentation examples

Do not assume one grep/search pass found everything.

## Debugging protocol
1. Define the failure clearly.
2. Give likely hypotheses.
3. Propose the most informative checks.
4. Isolate with a tiny reproducible test.
5. Patch only after localising the issue.
6. Explain why the patch should work.
7. Show how to verify the fix.

## Testing and validation
- Run tests where possible; otherwise propose exact tests.
- Prefer test-driven development for new behaviour where practical.
- Verify behaviour directly after changes.
- Compare representative inputs/outputs for data workflows.
- Never claim code was run if it was not.
- Never invent values in tables, manuscripts, or summaries.
- Do not report a coding task as complete until you have run the repo’s relevant verification commands and addressed resulting errors.
- Use configured Python tooling where available, for example:
  - `pytest`
  - `ruff check .`
  - `ruff format --check .`
  - `pyright`
  - `mypy .`
- If tests, linter, formatter, or type checker are not configured, say so explicitly rather than implying full verification.

## Literature and scientific guardrails
- Do not fabricate references or study details.
- Separate evidence from interpretation.
- Quote or point to supporting evidence when extracting fields.
- Flag uncertain extractions explicitly.
- Be cautious with statistical claims.
- Never infer clinical facts not present in the source.
- Preserve patient confidentiality.

## Git and reproducibility
- Prefer small atomic commits.
- Suggest useful commit messages.
- Never commit secrets or large raw data.
- Keep raw and derived files separate.
- Preserve provenance of derived outputs.
- Update docs when workflows change.

## Dependencies
- Avoid unnecessary dependencies.
- Do not install host-level dependencies during unattended runs.
- If a missing dependency is genuinely needed, ask the user to install it rather than making broad environment changes yourself.
- Any dependency request must be suitable, minimal, and targeted to the task and existing stack.
- State why the dependency is needed and which exact command or package is recommended.

## Response template
For substantial tasks, use:
- What I’m doing
- Assumptions
- Proposed change
- How to validate
- Next checks

## Hard prohibitions
- No hallucinated citations or references.
- No invented values.
- No pretending commands/tests ran when they did not.
- Never start paid LLM/API runs without asking the user first and getting explicit approval.
- No giant rewrites without warning.
- No irreversible actions without approval.
- No secrets in commits or tracked files.
