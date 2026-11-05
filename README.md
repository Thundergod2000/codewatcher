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

## Example output

```
FAIL  codewatch/app.py
       ✗  secrets
              ERROR   line 12: Password assignment detected — move to environment variable
       ✓  complexity
       ⚠  docstrings
              warn    line 8: Public function 'connect' has no docstring

✗  1 error(s), 2 total violation(s) across 1 file(s) — push blocked
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

✗  1 error(s), 2 total violation(s) across 1 file(s) — push blocked
```

## How the checks work

### Secrets (blocks)

Runs regex patterns over added lines only. Flags likely hardcoded
passwords, API keys, tokens, AWS credentials, JWTs, private key blocks and
non-local IPs. Placeholders (`<your-key>`, `dummy`, `fake`) and
environment lookups (`process.env.X`, `import.meta.env.X`, `getenv`) are
not flagged. Comments are skipped.

### Complexity (blocks above 20, warns above 10)

Parses the full file with tree-sitter and measures each function,
arrow function, and method. The metric is a cyclomatic complexity count:
a base of 1 plus one for each `if`, loop, `catch`, `case`, ternary, and
`&&` / `||` / `??`. This is close enough to radon's Python metric that the same
thresholds apply. Nested functions are scored separately. Only functions
that intersect added lines are reported.

### Dead code (warns)

Warns only about newly added declarations whose names never appear
elsewhere in the file. Exported declarations (`export ...` or
`export { name }`), React-style capitalized component names, and
destructuring patterns are skipped. This is deliberately conservative:
an occasional missed dead declaration is better than noisy false
positives.

### Test presence (warns)

Recognizes common JS/TS conventions:

- `name.test.js`, `name.spec.ts`, and JSX/TSX equivalents
- colocated test files next to the source file
- `test_*` / `test/` conventions
- `tests/`, `test/`, `__tests__/`, `src/tests/`, `src/__tests__/`

Test files themselves, `*.d.ts` type definitions, and Jest/Vitest config
files are skipped instead of warned about.

### Documentation (warns)

Requires a JSDoc block (`/** ... */`) directly above exported functions
and classes, including arrow-function and class-expression values
assigned to exported declarations. Private/internal declarations,
interfaces, type aliases, enums, and individual class methods are not
flagged. Decorators are accounted for, so JSDoc goes above the decorator.
TypeScript type annotations do not exempt an export.

## Requirements

- Python 3.9+
- A Git repository (Git is only needed to push/run the hook)
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
- Only added lines are checked; pre-existing issues are not reported.

## Configuration

Add a `.codewatch.yml` to your repo root to customise thresholds:

```yaml
# .codewatch.yml
complexity:
  warn_above: 10
  block_above: 20

checks:
  skip:
    - dead_code      # disable a check entirely
```

_(config file support coming in v0.2)_
