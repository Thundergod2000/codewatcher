# CodeWatch — Local Testing Guide

How to set up, run, and test CodeWatch Lite on your machine.
Written for developers who are new to the project.

---

## First time setup

Do this once when you first clone the project.

```bash
# 1. Go into the project folder
cd codewatch-lite

# 2. Install the project in "dev mode"
#    This means changes you make to the code take effect immediately
#    without needing to reinstall
#    It also installs the tree-sitter JS/TS grammars used for parsing.
pip install -e ".[dev]"

# 3. Confirm it installed
codewatch --help
```

If you see the help text, setup is done.

**What "-e" means:** Editable mode. Instead of copying your code into
Python's packages folder, it just points there. So when you edit
`codewatch/cli.py`, the `codewatch` command immediately uses the new code.

**Node.js is not required.** JavaScript, TypeScript, JSX, and TSX are
parsed inside Python by tree-sitter. Nothing is downloaded or executed at
scan time.

---

## Running the automated tests

```bash
# Run all tests
pytest tests/

# Run with verbose output (shows each test name)
pytest tests/ -v

# Run just one test file
pytest tests/test_secrets.py -v

# Run just one specific test
pytest tests/test_secrets.py::test_hardcoded_password_flagged -v

# Run all JavaScript/TypeScript tests
pytest tests/test_js_*.py tests/test_scanner.py tests/test_cli_js.py -v
```

**What to expect:** All tests should pass. If a test fails, the output
tells you which line failed and what the actual vs expected value was.

The JS/TS tests cover diff parsing, secrets, complexity, dead code, test
presence, JSDoc, language dispatch, parser failures, JSON/text output and
`--no-block`. They run without Node.js or network access.

---

## Testing the CLI manually (the most useful kind of testing)

This is how you check the tool actually works end to end.

### Step 1 — Create a test repo

```bash
# Create a temporary folder for testing
mkdir ~/codewatch-test
cd ~/codewatch-test

# Turn it into a git repo
git init
git config user.email "you@example.com"
git config user.name "Your Name"

# Create a first commit (needed so HEAD~1 exists)
echo "# test repo" > README.md
git add .
git commit -m "initial commit"
```

### Step 2 — Create a file with problems

Create a file called `bad_code.py` with this content:

```python
import os

# This will trigger the secrets check (ERROR - blocks push)
password = "supersecret123"
api_key = "sk-abc123xyz789longkeyvalue"

# This will trigger the docstrings check (WARNING)
def process_user_data(user, config, items, flags, mode, retries):
    result = []
    if user:
        if config:
            if items:
                for item in items:
                    if flags:
                        if mode == "fast":
                            result.append(item)
                        elif mode == "slow":
                            result.append(item * 2)
                        else:
                            result.append(item * 3)
                    else:
                        result.append(None)
    return result
```

### Step 3 — Commit and scan

```bash
git add bad_code.py
git commit -m "add bad code"
codewatch scan --diff HEAD~1
```

**What you should see:**
```
FAIL  bad_code.py
       ✗  secrets
              ERROR   line 4: Password assignment detected...
              ERROR   line 5: API key assignment detected...
       ⚠  complexity
              warn    line 8: process_user_data() has complexity 11...
       ✓  dead_code
       ⚠  test_presence
              warn    line 1: No test file found for bad_code.py...
       ⚠  docstrings
              warn    line 8: Public function 'process_user_data' has no docstring...

✗  2 error(s), 5 total violation(s) — push blocked
```

### Step 4 — Fix the errors and test again

Create `good_code.py`:

```python
"""Module for processing user data."""
import os


def process_user_data(user: dict, items: list) -> list:
    """Process items for a given user and return filtered results."""
    if not user or not items:
        return []
    return [item for item in items if item is not None]
```

```bash
git add good_code.py
git commit -m "add clean code"
codewatch scan --diff HEAD~1
```

**What you should see:**
```
WARN  good_code.py
       ✓  secrets
       ✓  complexity
       ✓  dead_code
       ⚠  test_presence
              warn    line 1: No test file found...
       ✓  docstrings

⚠  1 warning(s) — push allowed
```

Exit code is 0 — push would be allowed.

---

## Testing JavaScript / TypeScript support

You can use the same temporary git repo from above. No Node.js or npm
install is needed.

### Step 1 — Add a bad TypeScript file

Create `src/api.ts`:

```ts
const apiKey = "sk-abc123xyz789longkeyvalue";

export function fetchUser(id: string): string {
    return process.env.BASE_URL + id;
}
```

Create `src/api.test.ts` only if you want to check the passing test-presence
path. Without it you should see a test-presence warning.

```bash
git add src/api.ts
git commit -m "add bad TypeScript code"
codewatch scan --diff HEAD~1
```

**What you should see:**

```
FAIL  src/api.ts
       ✗  secrets
              ERROR   line 1: API key assignment detected — move to environment variable or secrets manager
       ✓  complexity
       ⚠  dead_code
              warn    line 1: Unused variable declarator 'apiKey' — remove it or add a usage
       ⚠  test_presence
              warn    line 1: No test file found for api.ts — expected api.test.ts or __tests__/ variant
       ⚠  docstrings
              warn    line 3: Exported function 'fetchUser' has no JSDoc comment — add a description for API documentation
```

### Step 2 — Fix it

```ts
/** Fetch a user by id. */
export function fetchUser(id: string): string {
    return process.env.BASE_URL + id;
}
```

```bash
git add src/api.ts
git commit -m "fix TypeScript issues"
codewatch scan --diff HEAD~1
```

The secrets and JSDoc findings should be gone. Exit code is 0 when only
warnings remain.

### Step 3 — Mixed-language diff

Commit a Python file and a JS/TS file together. CodeWatch lists both and
runs only the matching language's checks for each file.

### JSX / TSX

The same checks apply to `.jsx` and `.tsx`. React components with
capitalized names are treated as public API, so they are not reported as
dead code. Exported components still need JSDoc:

```tsx
/** Renders a button. */
export const Button = ({ label }: { label: string }) => <button>{label}</button>;
```

---

## Testing the pre-push hook

```bash
# Inside your test repo
codewatch install-hook

# Now try to push (will fail because no remote, but hook fires first)
git push origin main
```

You should see "codewatch: reviewing changes..." before the git error.

---

## Testing with JSON output (useful for CI integration)

```bash
codewatch scan --diff HEAD~1 --format json
```

You should see a JSON object with each file and its violations.

---

## Testing the --no-block flag (warn-only mode)

```bash
# Even with errors, exit code will be 0
codewatch scan --diff HEAD~1 --no-block
echo "Exit code: $?"
```

Exit code should be 0 even if there are errors.

---

## Common problems and fixes

**"codewatch: command not found"**
→ PATH is not set correctly. See the PATH setup in the main README.
On Windows, add Python's Scripts folder to your PATH.

**"No diff found — nothing to review"**
→ You are on the first commit. There is no previous commit to compare
against. Create a second commit first.

**"radon not installed"**
→ Run `pip install radon` then try again.

**"vulture not installed"**  
→ Run `pip install vulture` then try again.

**"tree-sitter grammar for javascript not installed" or similar**
→ Run `pip install tree-sitter-javascript tree-sitter-typescript` then try
again. A normal `pip install -e ".[dev]"` installs these automatically.

**JS/TS checks show `skip` with a syntax error reason**
→ The tree-sitter parser found invalid JS/TS syntax. Fix the syntax error
and scan again. Skipped is not a pass.

**Tests fail with import error**
→ Run `pip install -e ".[dev]"` again from inside the project folder.

---

## What good test coverage looks like

Before the demo, these should all pass:

```bash
pytest tests/ -v
# Should show: X passed, 0 failed

codewatch scan --diff HEAD~1  # on a repo with bad Python code
# Should show: FAIL with errors

codewatch scan --diff HEAD~1  # on a repo with bad JS/TS code
# Should show: FAIL with errors

codewatch scan --diff HEAD~1  # on a repo with clean code  
# Should show: PASS or WARN (no errors)

codewatch install-hook
# Should show: ✓ pre-push hook installed
```

If all five of these work, the demo is ready.
