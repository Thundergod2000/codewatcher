# CodeWatch Lite

**A pre-push gate that blocks hardcoded secrets and overly complex code before they reach your repo.**
Offline, deterministic, no LLM, no network, no Node.js.

![CodeWatch blocking a push that contains an API key](demo.gif)
<!-- TODO: add demo.gif when ready -->

```bash
pip install codewatch-lite
python -m codewatch install-hook
git push        # CodeWatch reviews the commits being pushed, then lets them through or blocks them
```

---

## Why CodeWatch

Leaked keys and 200-line, 40-branch functions both tend to reach the remote because nobody was looking at that moment. Code review misses them, and by the time CI flags them the secret is already in your Git history.

CodeWatch runs on your machine, at push time, on only the commits you are about to push:

- **Offline and private.** Nothing leaves your machine. No tokens, no API calls, no telemetry. Git data is read directly from `.git`, and the scanner never launches `git` or any other executable.
- **Deterministic.** The same code gives the same result every time, which is what you want from something that can block a push.
- **One install, one report.** Secrets, complexity, dead code, test presence, and documentation in a single tool with a single output format, instead of five tools with five configs.
- **Fast on pushes.** It reviews only the pushed range and only the lines that changed, not your whole repository.

### How is this different from gitleaks, git-secrets, ESLint, or Ruff?

Those are good tools, and if you only need one of those jobs, use them. CodeWatch is for teams that want a single, offline pre-push gate covering Python and JS/TS, with a consistent severity policy: **secrets and extreme complexity block; everything else warns**. It does not try to beat dedicated secret scanners on detection breadth.

---

## What it checks

| Check | Blocks push | Python | JS / TS / JSX / TSX | What it catches |
|---|---|---|---|---|
| Secrets | ✅ Yes | ✅ | ✅ | Hardcoded passwords, API keys, AWS credentials, tokens, JWTs, private key blocks |
| Complexity | ✅ Yes (>20) / ⚠ Warn (>10) | ✅ | ✅ | Functions too complex to maintain |
| Dead code | ⚠ Warn | ✅ | ✅ | Unused functions, classes, variables |
| Test presence | ⚠ Warn | ✅ | ✅ | Source files with no matching test file |
| Documentation | ⚠ Warn | ✅ Docstrings | ✅ JSDoc | Public APIs without documentation |

Supported extensions: `.py`, `.js`, `.jsx`, `.ts`, `.tsx`. Language is detected automatically, and mixed Python + JS/TS repositories are scanned file by file.

---

## Install

```bash
pip install codewatch-lite
```

Requires Python 3.9+. On recent Linux and macOS systems that block global `pip install`, use `pipx install codewatch-lite` or a virtual environment.

## Usage

Run with `python -m codewatch`, so no PATH changes are needed. The `codewatch` command is also installed as a shortcut.

```bash
# Scan your latest commit
python -m codewatch scan

# Scan against a specific ref
python -m codewatch scan --diff main

# Install the pre-push hook (runs on every push)
python -m codewatch install-hook

# JSON output for scripts and CI
python -m codewatch scan --format json
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Pass, or warnings only |
| `1` | At least one ERROR: push blocked |
| `2` | Tool or config error (fails closed) |

Use `--no-block` to always exit `0`.

## Example output

```
codewatch: reviewing refs/heads/main -> refs/heads/main
codewatch: check — 1 file(s) scanned

FAIL  badcodeinTS.ts
       ✗  secrets
              ERROR   line 1: API key assignment detected — move to environment variable or secrets manager  [CW-SECRET-005]
       ✓  complexity
       ⚠  dead_code
              warn    line 1: Unused variable declarator 'apikey' — remove it or add a usage  [CW-DEAD-001]
       ⚠  test_presence
              warn    line 1: No test file found for badcodeinTS.ts — expected badcodeinTS.test.ts or __tests__/ variant  [CW-TEST-001]
       ✓  docstrings

✗  1 error(s), 3 total violation(s) across 1 file(s) — push blocked
```

Every finding has a file, a line number, a plain-language fix hint, and a stable rule ID (`CW-SECRET-005`) you can search for.

---

## Pre-push hook

```bash
python -m codewatch install-hook
```

The installer writes a managed `.git/hooks/pre-push`. If you already have a pre-push hook, it is backed up and chained, not overwritten. The hook runs with the Python interpreter that installed CodeWatch, so an inactive virtualenv or a missing PATH entry won't break it.

On every push, CodeWatch reviews only the commits being pushed:

- **Normal push:** diff against the remote SHA (`remote...local`).
- **New branch:** merge-base with `origin/main`, `origin/master`, `main`, or `master`.
- **No default branch or remote:** at most the **last 3 commits**, clamped to the branch root. It never scans full history.

### Bypassing a block

If a finding is a false positive or you need to push anyway, Git's standard escape hatch works:

```bash
git push --no-verify
```

Treat this as an exception. A hook runs on your machine and can always be skipped, so for a guarantee that matters, also run `python -m codewatch scan --diff <base> --format json` in CI. Allowlists and inline ignores are planned (see [Roadmap](#roadmap)).

---

## How the checks work

Python and JS/TS use separate implementations with the same policy: secrets and complexity above 20 block, and everything else warns.

### Secrets (blocks)

Regex patterns run over **added lines only**. They flag likely hardcoded passwords, API keys, tokens, AWS credentials, JWTs, private key blocks, and non-local IPs. Placeholders (`<your-key>`, `dummy`, `fake`) and environment lookups (`os.environ`, `getenv`, `process.env.X`, `import.meta.env.X`) are not flagged. Full-line comments are skipped.

CodeWatch is tuned to prefer a false positive over a missed secret.

### Complexity (blocks above 20, warns above 10)

- **Python:** uses `radon` on the full file. Only functions whose body intersects the added lines are reported.
- **JS/TS:** uses tree-sitter to measure each function, arrow function, and method. Score is 1 plus one for each `if`, loop, `catch`, `case`, ternary, and `&&` / `||` / `??`. Nested functions are scored separately, and only functions that intersect added lines are reported.

### Dead code (warns)

- **Python:** uses `vulture` (minimum confidence 60). Only newly added definitions are reported.
- **JS/TS:** warns about newly added declarations whose names never appear elsewhere in the file. Exports, capitalized React-style component names, and destructuring patterns are skipped.

Deliberately conservative: an occasional miss is better than noisy false positives.

### Test presence (warns)

- **Python:** looks for `test_<name>.py` or `<name>_test.py` in `tests/`, `test/`, `src/tests/`, or next to the source file. Skips test files, `__init__.py`, `setup.py`, `conftest.py`, and migrations.
- **JS/TS:** recognizes `name.test.*`, `name.spec.*`, colocated tests, and `tests/`, `test/`, `__tests__/`, `src/tests/`, `src/__tests__/`. Skips test files, `*.d.ts`, and Jest/Vitest config files.

### Documentation (warns)

- **Python:** public functions and classes (names not starting with `_`) added in the diff need a docstring.
- **JS/TS:** exported functions and classes need a JSDoc block (`/** ... */`) directly above them, including arrow functions and class expressions assigned to exported declarations. Internal declarations, interfaces, type aliases, enums, and class methods are not flagged. With decorators, put the JSDoc above the decorator.

---

## Security and privacy

- No network access at scan time. `pip install` is the only step that needs the internet.
- No LLM and no telemetry.
- Git data is read with the pure-Python `dulwich` library. The scanner never launches `git.exe` or any other executable.
- Secrets found in your code are never sent anywhere.
- The source will be published once the security review is complete, so the "no network" claim can be verified by reading the code. <!-- TODO: update when the repo is public -->

## Requirements

- Python 3.9+
- A Git repository (the Git executable is only needed to push)
- Installed automatically: `radon`, `vulture`, `tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript`, `dulwich`

No Node.js, npm, or project installation is required.

---

## Limitations

- This is static analysis. It is not a type checker or a replacement for ESLint or TypeScript.
- Findings are limited to new or changed code, so pre-existing issues are not reported.
- The secrets check reviews the added lines of the pushed range. A secret that is added and removed within the same push may not be detected, and it would still exist in the pushed commits. Per-commit scanning is planned.
- Secret detection is pattern-based and tuned to over-report. Expect some false positives, and don't treat a passing scan as proof that no secret is present.
- Dead-code detection is conservative and only inspects the changed file.
- Test discovery checks common conventions. Unusual monorepo layouts may need a test file in a recognized location.
- Framework-specific rules (Next.js entry points, NestJS decorators, etc.) are out of scope.
- A new branch with no default branch or remote reviews at most the last 3 commits, by design.
- Only Python and JavaScript/TypeScript are supported in this release.

---

## Configuration (v0.2)

A `.codewatch.yml` in the repo root will customize thresholds and hook behavior:

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

Until v0.2, the hook uses the built-in order `origin/main` → `origin/master` → `main` → `master`, then the last 3 commits.

## Roadmap

**v0.2**
- [ ] `.codewatch.yml` configuration and `install-hook --ref`
- [ ] Allowlists and inline ignore for known false positives
- [ ] Baseline file, so existing violations don't block adoption on legacy code
- [ ] Optional full-repo scan on push
- [ ] Compact summary output and a full report written to a file

**Later**
- [ ] Per-commit secrets scanning across the whole pushed range
- [ ] Scanning secrets in config files (`.env`, YAML, JSON)
- [ ] Detection of secrets exposed to the browser, such as `NEXT_PUBLIC_*`, `VITE_*`, and `REACT_APP_*` variables
- [ ] CI mode with SARIF output
- [ ] More languages

**CodeWatch AI** (separate, optional) will add AI-assisted maintainability review for teams that are comfortable sending diffs to an LLM. CodeWatch Lite will stay free, offline, and LLM-free.

---

## Support

Need help rolling CodeWatch out across your repositories, tuning rules for your stack, or adding a custom check? Get in touch: <!-- TODO: add contact email or link -->

## Contributing

Issues and feedback are welcome, especially false positives and false negatives with a minimal example. Please never paste real secrets into an issue. <!-- TODO: expand once the repo is public -->

## License

<!-- TODO: add license -->