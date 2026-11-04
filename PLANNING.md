# CodeWatch — Build Plan

This is the single source of truth for what we are building, in what order,
and why. Read this before starting any feature.

---

## The one-line goal

Ship a working CLI tool that catches bad Python and JavaScript/TypeScript
code before it gets pushed to git, impressive enough to demo in a job
interview for an AI/GenAI role.

---

## What is in scope RIGHT NOW

These are the only things being built. Nothing else.

### ✅ Already built
- [x] Project scaffold (folders, pyproject.toml, entry point)
- [x] git diff parser — reads changed files from git
- [x] 5 static checks: secrets, complexity, dead_code, tests, docstrings
- [x] Terminal reporter — coloured output, PASS/WARN/FAIL
- [x] pre-push hook installer (`codewatch install-hook`)
- [x] JSON output mode (`--format json`)
- [x] 10 passing tests
- [x] JavaScript, TypeScript, JSX, and TSX support (offline via tree-sitter)
- [x] 107 passing tests

### 🔨 Building next (in this order)

**Step 1 — Make the demo impressive**
- Stress test file that triggers every check dramatically
- Clean demo script that shows before/after in 60 seconds
- README with a GIF or screenshot of it working

**Step 2 — Multi-account key rotation**
- Read a list of API keys from environment or .env
- Try key 1, if rate-limited or out of tokens → try key 2
- If all keys fail → fall back to static-only mode silently

**Step 3 — Token reduction (RTK)**
- Strip unchanged lines from diff before any API call
- Cache system prompt between calls
- Bundle all AI checks into one call, not many

**Step 4 — Package and distribute**
- Push to PyPI so anyone can `pip install codewatch-lite`
- Write a one-page landing page (can be GitHub README)
- Tag v0.1.0 release on GitHub

**Step 5 — Deploy (for the AI version)**
- Simple FastAPI server that accepts webhook from GitHub
- One endpoint: POST /review — takes a diff, returns verdict
- Deploy to Railway or Render (free tier, no credit card needed)

---

## What is OUT of scope (skip these for now)

| Feature | Why skipped |
|---|---|
| Web dashboard | Takes weeks, adds no demo value right now |
| Database / history | Not needed until there are paying users |
| Java / other languages | JS/TS shipped; other languages are not needed for the demo |
| Config file support | Hard-coded defaults work fine for MVP |
| GitHub Actions integration | Webhook deploy covers this later |
| Architecture checks | Needs RAG + embeddings — Phase 2 |
| Scalability work | Premature — get users first |

---

## Phase map — big picture

```
Phase 1 (NOW)    → CodeWatch Lite CLI — working, installable, demo-ready
Phase 2 (Next)   → CodeWatch AI — adds Claude API layer on top of Lite
Phase 3 (Later)  → CodeWatch SaaS — web dashboard, teams, billing
```

We are in Phase 1. Do not build Phase 2 or 3 features right now.

---

## Demo flow (what the interviewer will see)

The demo should take under 2 minutes and show this sequence:

```
1. Developer adds bad code (hardcoded password, no docstring, complex function)
2. Developer tries to push: git push
3. codewatch fires automatically (pre-push hook)
4. Terminal shows FAIL with exact line numbers and explanations
5. Push is blocked
6. Developer fixes the password (moves to env var)
7. Developer pushes again
8. codewatch shows PASS
9. Push goes through
```

This is the entire demo. Keep it to this. Do not show config files,
dashboards, or anything else.

---

## Why this is good for an AI/GenAI job application

- Shows you understand how to wrap an AI API in a real product
- Shows you understand token costs and how to reduce them
- Shows you built something end-to-end, not just a notebook
- The multi-account key rotation shows practical LLM operations knowledge
- The static-first, AI-second architecture shows you think about cost

When asked in an interview: "What would you do differently?"
Answer: "I'd add RAG to give the AI context about the project's existing
architecture so it gives project-specific feedback, not generic feedback."
That answer shows depth.

---

## Decisions still open (things to choose before building)

### Decision 1: Where to store API keys for multi-account rotation?

**Option A: .env file** (simpler)
- Keys go in a .env file, loaded with python-dotenv
- Tradeoff: developer has to manage the file manually, easy to accidentally commit it

**Option B: Environment variables** (safer)
- Keys set in the shell: `export CLAUDE_KEY_1=sk-ant-...`
- Tradeoff: harder to set up for non-technical users, but safer

**Recommendation:** Start with .env, add a .gitignore entry for it.

### Decision 2: What to do when all API keys are exhausted?

**Option A: Fail open** — run static checks only, skip AI checks
- Tradeoff: developer gets partial feedback, doesn't know AI was skipped unless they read logs

**Option B: Fail with warning** — show a clear message that AI checks were skipped
- Tradeoff: slightly more friction but developer always knows what ran

**Recommendation:** Option B — transparency builds trust.

### Decision 3: Deploy target for the AI version

**Option A: Railway** — free tier, deploys from GitHub, zero config
- Tradeoff: free tier sleeps after inactivity (30s cold start for demo)

**Option B: Render** — similar to Railway, slightly more reliable free tier
- Tradeoff: same cold start problem

**Option C: Fly.io** — more control, stays awake on free tier
- Tradeoff: slightly more setup

**Recommendation:** Railway for speed. Upgrade to Fly.io if cold starts
become a demo problem.

---

## Next language plan — JavaScript, TypeScript, and React

**Status: implemented and tested.** Python remains fully supported with
unchanged behavior and exit codes. This section records the plan and the
decisions made during implementation.

### Implementation summary

- **Diff and dispatch:** `.js`, `.jsx`, `.ts`, and `.tsx` are parsed from
  the same git diff as `.py`. Files are dispatched by extension; Python
  files run the original Python checks and JS/TS files run the new
  tree-sitter-based checks. Deleted, renamed, binary, and repeated-line
  cases are preserved, including exact added-line numbers from diff hunk
  headers.
- **Parser/dependency choice:** `tree-sitter` with
  `tree-sitter-javascript` and `tree-sitter-typescript`. These are normal
  Python dependencies (not optional), install on Python 3.9+ from wheels,
  and require no Node.js, npm, project scripts, or network at scan time.
  The code supports both the `Parser(language)` API and older
  `Language(capsule)` packages.
- **Secrets:** same severity and reporter conventions as Python. Added
  lines only. Supports camelCase/snake_case JS/TS assignments, placeholders,
  comments, `process.env`, and `import.meta.env` allowlists. Hardcoded
  credentials are `ERROR`.
- **Complexity:** cyclomatic-style metric (base 1 + `if`, loops, `catch`,
  `case`, ternary, `&&`/`||`/`??`). Nested functions are scored separately and
  only functions intersecting added lines are reported. The metric is
  comparable to radon's, so the existing thresholds are used unchanged:
  warn above 10, block above 20. Any parse or syntax failure returns an
  explicit skipped result.
- **Dead code:** warnings only, for newly added declarations whose names are
  never used elsewhere in the file. Exports, `export { name }` declarations,
  capitalized React component names, and destructuring patterns are
  skipped. Conservative to avoid false positives.
- **Test presence:** recognizes `*.test.*`, `*.spec.*`, `test_*`, and
  `tests/`, `test/`, `__tests__/`, `src/tests/`, `src/__tests__/`, plus
  colocated tests. Test files, `*.d.ts` files, and Jest/Vitest configs are
  skipped.
- **Documentation:** JSDoc required for exported functions and classes,
  including arrow-function/class-expression values assigned to exports.
  Interfaces, type aliases, enums, class methods, private/internal
  declarations, and pre-existing code are not flagged. Decorators and
  TypeScript types are handled.
- **CLI/output:** automatic language detection (no new flag), unchanged
  text/JSON shapes, and unchanged `--no-block` behavior.
- **Verification:** 107 unit and integration tests pass. No Node/npm or
  subprocess is invoked by checks (covered by a regression test). E2E
  testing in a live repo remains a manual developer step.

### Known limitations

- Dead-code detection only inspects the changed file and is deliberately
  conservative.
- Test discovery covers common conventions; unusual monorepo layouts may
  need a test file in a recognized location.
- No framework-specific semantics (Next.js entry points, NestJS, etc.).
- Static analysis only; not a type checker or ESLint replacement.

### Goal

Extend CodeWatch Lite to review changed `.js`, `.jsx`, `.ts`, and `.tsx` files
in the same offline, diff-focused workflow as Python, including mixed-language
repositories. Do not require Node.js, npm, or a network connection at scan
time.

### POC goals

1. Recognize JavaScript, TypeScript, JSX, and TSX files in a git diff while
   continuing to scan Python files exactly as before.
2. Reuse the existing result and reporting model so findings have a check
   name, severity, line number, message, and skipped status.
3. Implement equivalents of the five Python checks where meaningful:
   - **Secrets:** inspect added lines and block on likely hardcoded credentials.
   - **Complexity:** inspect complete source and report only functions touched
     by the diff; use the existing warning/block thresholds only if the
     selected metric is comparable.
   - **Dead code:** warn conservatively about newly added, clearly unused
     declarations. Avoid treating exports, framework entry points, or
     conventionally discovered components as dead without evidence.
   - **Test presence:** recognize common JavaScript/TypeScript test naming and
     directories; skip test files themselves.
   - **Documentation:** warn on newly added public APIs that lack JSDoc where
     the language and project conventions make that check applicable.
4. Keep checks offline and usable from the Python package installation alone.
   Prefer a Python-accessible JavaScript/TypeScript syntax parser over
   invoking Node-based tools. Evaluate parser and grammar package compatibility
   with the project's Python 3.9+ floor before choosing dependencies.
5. Add focused unit tests and a mixed-language CLI test; document the
   supported extensions, dependency behavior, limitations, and examples.

### Acceptance tests

- Diff parsing includes `.js`, `.jsx`, `.ts`, and `.tsx` additions, excludes
  unrelated extensions, and preserves rename/deletion behavior.
- A mixed Python/JS/TS diff returns results for each supported changed file;
  unchanged Python-only scans produce the same results and exit codes as
  before.
- Added-line secret fixtures cover representative JS/TS assignments and
  safe placeholders/environment lookups; only likely secrets block.
- Complexity fixtures cover functions and arrow functions, warning and
  blocking thresholds, and edits outside a function; findings map to the
  function's source line.
- Dead-code fixtures cover unused local declarations and exported/public or
  framework-convention declarations that must not be reported.
- Test-presence fixtures cover common `*.test.*` / `*.spec.*` naming and
  typical `test` / `tests` directories, plus files that should be skipped.
- Documentation fixtures cover exported functions/classes and React
  components with and without JSDoc, while ignoring private/internal
  declarations according to the agreed policy.
- Parser failures, missing files, and unsupported syntax produce an explicit
  skipped result rather than crashing or silently passing.
- CLI text and JSON output include JS/TS findings, preserve the current JSON
  shape where possible, and block only for ERROR-level findings.
- Tests run without Node/npm installed and without network access.

### Suggested implementation sequence

1. Confirm parser/dependency choice and the conventions/thresholds below.
2. Extend diff parsing and file dispatch, keeping Python paths unchanged.
3. Add JS/TS check modules using the existing `CheckResult` and `Violation`
   types; map findings to added lines.
4. Add unit fixtures for each check and mixed-language regression tests.
5. Validate from a clean Python 3.9+ installation without Node, then update
   README and TESTING instructions.

### Questions for the scaffolding / implementation AI

- Which Python-accessible parser and JS/TS/JSX/TSX grammars support Python
  3.9+, install reliably on supported platforms, and work offline at scan
  time? Are they required dependencies or an optional extra?
- How should the scanner identify exported APIs, React components, framework
  entry points, and other declarations that are intentionally unused?
- What exact JS/TS cyclomatic-complexity metric and thresholds are equivalent
  enough to Python's current radon thresholds? If not comparable, what policy
  should apply?
- Which test file patterns and directories should count (for example,
  `*.test.*`, `*.spec.*`, colocated tests, and `__tests__`)?
- Should JSDoc be required for all exports, React components only, or follow
  existing project conventions? How should TypeScript types affect this?
- How should unsupported syntax or parser errors be reported, and should
  `--no-block` and JSON output behave identically for both languages?

### Out of scope for this POC

- Requiring or installing Node/npm, running ESLint or arbitrary project
  scripts, network-based analysis, configuration-file support, and
  framework-specific semantic rules beyond checks above.
- Changing Python check behavior, thresholds, or supported Python versions.



## Phase 2 Plan: Next Steps

Read the whole section before starting. Work through the milestones in order. Do not start a milestone until the previous one passes its acceptance checks. Where this plan conflicts with how the existing code is structured, follow the existing structure and note the deviation in your summary.

### Goals

1. Installation needs no `.exe`, no installer and no environment variable or PATH changes.
2. Two scan modes: `check` (committed/changed files only) and `scan` (whole project).
3. AI agents run the check before pushing code, backed by enforcement that does not rely on the agent remembering.
4. The project is ready to open source, so contributors can add rules easily.

### Principles

- The core stays rule-based and predictable. Do not add LLM calls to the core.
- Zero setup friction: a fresh clone should work with as few steps as possible.
- Fail = blocks the push (non-zero exit). Warning = reported but exit code 0.
- Keep default output short. It is read by AI agents, so tokens matter.

---

## Milestone 1: Install with no exe and no env vars

- Make `pip install codewatcher` the primary install path.
- Make `python -m codewatcher <command>` work for every command. Document and use this form everywhere, because it does not depend on PATH.
- All settings live in a config file inside the repo. Do not require global config or environment variables.
- Python and JS/TS/React scanning must keep working with no Node installation.
- Optional: `codewatcher init` can write a small runner (for example `.codewatcher/run.py`) so a fresh clone works without installing the package.

Acceptance checks:
- On a clean machine with only Python installed, install and a first run succeed with no PATH or env var edits.
- `python -m codewatcher --help` lists all commands.

## Milestone 2: Two scan modes

| Command | Scans | Purpose |
|---|---|---|
| `codewatcher check` | Only committed/changed files (current behavior, keep as default) | Gate for AI pushes |
| `codewatcher scan` | The whole project | Health check on any repo |

- Add `--base <branch>` to `check` to scan everything changed versus that branch (for example `--base main`).
- Respect ignore paths in both modes. Skip `node_modules`, `.venv`, `dist`, `build` and similar by default.
- The report header must state which mode ran and how many files were scanned.
- Exit codes: `0` = pass or warnings only, `1` = at least one failure, `2` = tool or config error.
- Add `--format json` alongside the default compact text report.

Acceptance checks:
- `check` output is unchanged for existing behavior.
- `scan` finds issues in files that were never committed or changed.
- Exit codes match the list above.

## Milestone 3: Make AI run it before every push

Ask layer (tell the agent):
- `codewatcher init` writes a short instruction block into whichever of these files exist or are chosen: `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`.
- The block says: run `python -m codewatcher check` before pushing and fix every failure.
- `init` must append to existing files, never overwrite them, and must not add the block twice.

Enforce layer (do not rely on the agent remembering):
- `init` installs a git **pre-push** hook that runs `python -m codewatcher check`. A failure blocks the push.
- Where an agent tool supports hooks (for example Claude Code), provide an optional hook that runs the check before `git push`.
- Ship a GitHub Actions workflow that runs the same check in CI, as a backstop for `--no-verify`.

Acceptance checks:
- A push containing a failing file is blocked locally.
- Running `init` twice does not duplicate anything.
- CI fails on the same input that fails locally.

## Milestone 4: Open-source readiness

- README: what it does, a 30-second install, a sample report, and one example rule.
- LICENSE (MIT or Apache 2.0, owner to confirm).
- CONTRIBUTING.md: run locally, add a rule, run tests, submit a PR.
- Documented rule format. Adding a new rule should take minutes. Include a template rule and a test for it.
- Config file support: enable or disable rules, override severity (fail or warn), ignore paths.
- Inline suppression that requires a reason.
- Issue and PR templates, and a basic CI workflow that runs the test suite.
- Create 5 to 10 well-described "good first issue" tasks (new rules, docs fixes, report formats).

---

## Phase 2 Feature Backlog (after Milestones 1 to 4)

Priority order:

1. **AI-mistake rules.** The main differentiator. Examples: leftover `console.log` or `print`, placeholder TODOs, imports missing from the dependency manifest, swallowed exceptions, hardcoded secrets, skipped tests (`.skip`), empty test assertions, large blocks of commented-out code.
2. **Baseline mode.** Record existing issues and fail only on new ones, so `scan` is usable on old codebases.
3. **`codewatcher explain <RULE_ID>`.** Shows why the rule exists, a bad example and a good example.
4. **Fix prompts.** End the report with a ready-to-paste instruction for an AI agent describing exactly what to fix.
5. **Performance.** Caching and parallel scanning.
6. **SARIF output** for GitHub code scanning.
7. **Rule packs** (react, python, security) that can be enabled together.
8. **Autofix** for simple rules.

Later: more languages, a VS Code extension, and an optional opt-in LLM layer using the user's own key. Keep it separate from the core.

---

## How to report back

After each milestone, give a short summary: what changed, how you tested it, anything you skipped or changed from this plan, and any open questions. Do not start the next milestone until the acceptance checks pass.