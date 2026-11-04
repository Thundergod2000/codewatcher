---
name: "Implement JavaScript, TypeScript, and React Support"
description: "Implement the planned offline JS/TS/JSX/TSX checks in CodeWatch Lite with Python regression coverage."
argument-hint: "Optional constraints or project conventions for JS/TS support"
agent: "agent"
---

Implement the JavaScript, TypeScript, JSX, and TSX support described in
[PLANNING.md](../../PLANNING.md), including tests and related documentation.
Treat this as an implementation task, not a request to revise the plan.

## Required outcome

- Scan changed `.js`, `.jsx`, `.ts`, and `.tsx` files in the existing git-diff
  workflow, including mixed Python/JS repositories.
- Preserve existing Python behavior, results, and exit codes.
- Work with the existing Python package installation alone. Do not require
  Node.js, npm, network access, or executing scripts from the scanned project.
- Reuse CodeWatch's existing `CheckResult`, `Violation`, severity, reporter,
  and CLI conventions wherever appropriate.
- Run checks against added code only. Use complete source context when a
  check requires parsing or analyzing a function.

## Before editing

1. Read the JS/TS plan, `CLAUDE.md`, `README.md`, `TESTING.md`, and the current
   diff parser, scanner, check modules, types, reporter, CLI, and related tests.
2. Inspect the worktree and integrate around existing user changes; do not
   discard or overwrite unrelated modifications.
3. Check current dependency constraints and Python 3.9+ compatibility before
   selecting a parser. Choose a Python-accessible parser that handles the
   required JS, TS, JSX, and TSX syntax, installs on the project's supported
   platforms, and requires no runtime network or Node. Prefer a single
   well-supported parser/grammar approach over regex-based structural
   analysis.
4. If no suitable parser can meet these constraints, or a policy choice blocks
   a correct implementation, stop and ask a focused question rather than
   silently relaxing the requirements.

## Implementation requirements

### Diff and dispatch

- Extend diff parsing to include exactly `.js`, `.jsx`, `.ts`, and `.tsx`
  alongside `.py`; continue excluding unrelated extensions.
- Preserve handling of deleted files, renames, binary files, and paths.
- Dispatch each changed file to checks appropriate for its language. Do not
  run Python AST/radon/vulture checks on JS/TS files or JS/TS checks on Python.
- Preserve existing Python-only scan behavior and output. Avoid changing
  Python checks unless a change is necessary to share dispatch safely; any
  such change must have regression coverage.
- Preserve accurate source line numbers for findings on added lines, including
  repeated identical lines and edits to existing functions.

### Checks

Implement the five planned checks, using existing severity conventions:

- **Secrets:** inspect added lines, flag likely hardcoded credentials as
  `ERROR`, and avoid common placeholders and environment-variable lookups.
- **Complexity:** analyze functions and arrow functions with full syntax
  context; report only when the function intersects added lines. Use the
  existing thresholds only if the chosen metric is meaningfully comparable to
  Python's. Document any different metric or threshold. If added code cannot
  be analyzed reliably, return an explicit skipped result.
- **Dead code:** warn only on newly added, confidently unused declarations.
  Do not report exported APIs, React components, framework entry points, or
  other conventionally discovered declarations as dead without evidence.
- **Test presence:** recognize common JS/TS test naming and directories, such
  as `*.test.*`, `*.spec.*`, and `__tests__`, plus colocated tests where
  consistent with project conventions. Skip test files themselves.
- **Documentation:** warn on newly added public APIs without JSDoc only where
  that policy makes sense. Account for TypeScript type information and React
  components; avoid imposing docstrings on private/internal declarations.

Do not silently treat parser failures, missing files, or unsupported syntax
as clean passes. Use the established skipped-result mechanism and a useful
reason. Do not introduce broad exception catches or success-shaped fallbacks.
Only secrets and complexity above a justified blocking threshold should block;
dead-code, test-presence, and documentation findings are warnings.

### CLI, output, and documentation

- Keep automatic language detection; do not add a required language flag.
- Keep text and JSON output consistent with the existing result model, adding
  no unnecessary format changes.
- Preserve `--no-block` behavior.
- Update README and TESTING documentation with supported file types, setup,
  limitations, examples, and how to run the new tests.
- Keep the implementation focused on this POC. Do not add a configuration
  system, web UI, network analysis, arbitrary linter execution, or
  framework-specific semantic rules outside the plan.

## Tests and verification

Add focused tests following repository conventions. Cover:

- Diff inclusion of all four extensions; exclusion of unrelated files;
  deletion, rename, and binary handling.
- Mixed Python and JS/TS scans, plus unchanged Python behavior and exit codes.
- Secrets in JS/TS syntax, placeholders, and environment lookups.
- Complexity for declarations and arrow functions, threshold behavior, line
  mapping, and edits outside the function.
- Dead-code false-positive protections for exports, React components, and
  framework conventions.
- Test file patterns/directories and skipping test files.
- JSDoc behavior for public exports, React components, and private APIs.
- Parser errors, unsupported syntax, missing files, text/JSON reporting, and
  `--no-block`.

Run the focused tests first, then the full existing test suite. Verify the
JS/TS scan works without Node/npm and does not access the network at scan time.
Report the dependency choice, tests run, outcomes, and any known limitations.

Do not stop after editing or only provide a plan; complete implementation,
tests, documentation, and verification in this task.
