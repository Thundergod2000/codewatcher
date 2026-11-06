# CodeWatch Lite

Offline code governance for Python, JavaScript, TypeScript, JSX and TSX — catches quality issues before they reach your repo. No LLM, no network, no Node.js, no noise.

## What it checks

| Check | Blocks push | Python | JS / TS / JSX / TSX | What it catches |
|---|---|---|---|---|
| Secrets | ✅ Yes | ✅ | ✅ | Hardcoded passwords, API keys, AWS credentials |
| Complexity | ✅ Yes (>20) / ⚠ Warn (>10) | ✅ | ✅ | Functions that are too complex to maintain |
| Dead code | ⚠ Warn | ✅ | ✅ | Unused functions, classes, variables |
| Test presence | ⚠ Warn | ✅ | ✅ | Source files with no matching test file |
| Documentation | ⚠ Warn | ✅ Docstrings | ✅ JSDoc | Public APIs without documentation |

## Supported file types

Only files with these extensions are scanned:

- `.py`
- `.js`
- `.jsx`
- `.ts`
- `.tsx`

Language is detected automatically — there is no language flag. Mixed
Python + JS/TS repositories are scanned file by file, and each file only
runs checks for its own language.

## Install

```bash
pip install codewatch-lite
```

## Usage

Run it with `python -m codewatch` — no `codewatch.exe` or PATH changes needed.
The installed `codewatch` command is still available as a shortcut.

```bash
# Scan your latest commit
python -m codewatch scan

# Scan against a specific ref
python -m codewatch scan --diff main

# Install as a pre-push hook (runs automatically on every push)
python -m codewatch install-hook

# Get JSON output (for CI integration)
python -m codewatch scan --format json
```

`scan` exits `1` when an ERROR blocks the push and `0` for pass or
warnings only. Use `--no-block` to always exit `0`.

## Pre-push hook

```bash
python -m codewatch install-hook
```

The installer writes a managed `.git/hooks/pre-push` and preserves any
existing hook by backing it up and chaining it. On every push, CodeWatch
reviews only the commits being pushed:

- **Normal push** — diff against the remote SHA (`remote...local`).
- **New branch** — merge-base with `origin/main`, `origin/master`,
  `main`, or `master`.
- **No default branch or remote** — at most the **last 3 commits**,
  clamped to the branch root. It never scans full history, which may be
  thousands of commits on a legacy project.

Exit codes: `0` for pass or warnings only, `1` when an ERROR blocks the
push, and `2` for a tool or config error (fail closed). The hook runs
with the Python interpreter that installed CodeWatch, so an inactive
virtualenv or missing PATH entry does not break it.

`install-hook --ref` and `.codewatch.yml` configuration are planned for
v0.2. The full hook contract lives in `PLANNING.md` (source of truth).

## Example output

```
FAIL  codewatch/app.py
       ✗  secrets
              ERROR   line 12: Password assignment detected — move to environment variable
       ✓  complexity
       ✓  dead_code
       ⚠  test_presence
              warn    line 1: No test file found for app.py — expected test_app.py in tests/
       ⚠  docstrings
              warn    line 8: Public function 'connect' has no docstring

✗  1 error(s), 3 total violation(s) across 1 file(s) — push blocked
```

JavaScript output uses the same format:

```
FAIL  src/api.ts
       ✗  secrets
              ERROR   line 4: API key assignment detected — move to environment variable
       ✓  complexity
       ✓  dead_code
       ⚠  test_presence
              warn    line 1: No test file found for api.ts — expected api.test.ts or __tests__/ variant
       ⚠  docstrings
              warn    line 4: Exported function 'fetchUser' has no JSDoc comment

✗  1 error(s), 3 total violation(s) across 1 file(s) — push blocked
```

## How the checks work

Python and JS/TS use separate implementations, but the severity policy is
the same for both: secrets and complexity above 20 block; everything else
warns.

### Secrets (blocks)

Runs regex patterns over added lines only. Flags likely hardcoded
passwords, API keys, tokens, AWS credentials, JWTs, private key blocks and
non-local IPs. Placeholders (`<your-key>`, `dummy`, `fake`) and
environment lookups (`os.environ`, `getenv`, `process.env.X`,
`import.meta.env.X`) are not flagged. Full-line comments are skipped.

### Complexity (blocks above 20, warns above 10)

- **Python** — uses `radon` on the full file. Only functions whose body
  intersects the added lines are reported.
- **JS/TS** — uses tree-sitter to measure each function, arrow function,
  and method with the same cyclomatic complexity style: a base of 1 plus
  one for each `if`, loop, `catch`, `case`, ternary, and `&&` / `||` /
  `??`. Nested functions are scored separately, and only functions that
  intersect added lines are reported.

Both languages use the same thresholds: warn above 10, block above 20.

### Dead code (warns)

- **Python** — uses `vulture` (minimum confidence 60). Only newly added
  definitions are reported; pre-existing dead code is ignored.
- **JS/TS** — warns only about newly added declarations whose names never
  appear elsewhere in the file. Exported declarations (`export ...` or
  `export { name }`), React-style capitalized component names, and
  destructuring patterns are skipped.

Always a warning, never a block. This is deliberately conservative: an
occasional missed dead declaration is better than noisy false positives.

### Test presence (warns)

- **Python** — looks for `test_<name>.py` or `<name>_test.py` in
  `tests/`, `test/`, `src/tests/`, or next to the source file. Skips test
  files, `__init__.py`, `setup.py`, `conftest.py`, and migration files.
- **JS/TS** — recognizes `name.test.js`, `name.spec.ts` and JSX/TSX
  equivalents, colocated tests, `test_*` / `test/` conventions, and
  `tests/`, `test/`, `__tests__/`, `src/tests/`, `src/__tests__/`. Skips
  test files, `*.d.ts` type definitions, and Jest/Vitest config files.

Always a warning, never a block.

### Documentation (warns)

- **Python** — public functions and classes (names not starting with `_`)
  added in the diff must have a docstring.
- **JS/TS** — requires a JSDoc block (`/** ... */`) directly above
  exported functions and classes, including arrow-function and
  class-expression values assigned to exported declarations.
  Private/internal declarations, interfaces, type aliases, enums, and
  individual class methods are not flagged. Decorators are accounted for,
  so JSDoc goes above the decorator. TypeScript type annotations do not
  exempt an export.

Always a warning, never a block.

## Requirements

- Python 3.9+
- A Git repository (the Git executable is only needed to push; scanning
  reads `.git` directly)
- `radon`, `vulture`, `tree-sitter`, `tree-sitter-javascript`,
  `tree-sitter-typescript`, and `dulwich` (installed automatically)

No Node.js, npm, project installation, or network access is required at
scan time. JavaScript/TypeScript parsing runs entirely in Python via
tree-sitter grammars. Git data is read directly from `.git` with the
pure-Python `dulwich` library — the scanner never launches `git.exe` or
any other executable.

## Limitations

- This is static analysis, not a type checker or a replacement for
  ESLint/TypeScript.
- Dead-code detection is conservative and only inspects the changed file.
- Test discovery checks common conventions; unusual monorepo layouts may
  need a manual test file in a recognized location.
- Framework-specific rules (Next.js entry points, NestJS decorators, etc.)
  are out of scope.
- Findings are limited to new or changed code; pre-existing issues are
  not reported.
- A new branch with no default branch or remote reviews at most the last
  3 commits, by design.

## Configuration (v0.2)

A `.codewatch.yml` in the repo root will customise thresholds and hook
behaviour:

```yaml
# .codewatch.yml
complexity:
  warn_above: 10
  block_above: 20

hook:
  default_branch: origin/main   # base used for new branches

checks:
  skip:
    - dead_code      # disable a check entirely

ignore:
  - vendor/
  - node_modules/
```

_(`.codewatch.yml` support, including the hook default branch and the
`--ref` override, is coming in v0.2. Until then the hook uses the built-in
order `origin/main` → `origin/master` → `main` → `master`, then the last
3 commits.)_
