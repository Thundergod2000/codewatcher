# CodeWatch — Stress Tests & Demo Scripts

These files are designed to trigger every check dramatically so you can
show the tool working in a demo or interview. Copy these files into a
test git repo and run `codewatch scan --diff HEAD~1`.

---

## The all-violations file

Create a file called `nightmare_code.py` with this content.
It deliberately violates every single check.

```python
# nightmare_code.py
# This file exists purely to show what CodeWatch catches.
# Never write code like this in a real project.

import os
import sys

# ============================================================
# VIOLATION 1: Hardcoded secrets (BLOCKS push — ERROR)
# ============================================================
DATABASE_PASSWORD = "admin123"
AWS_SECRET_KEY = "sk-abc123xyz789longkeyvalue"
api_key = "AKIAIOSFODNN7EXAMPLE123456"

# ============================================================
# VIOLATION 2: Overly complex function (WARNS — complexity 12+)
# ============================================================
def process_order(order, user, config, inventory, flags, mode, retries, cache):
    result = []
    if order:
        if user:
            if user.get("active"):
                if config:
                    if inventory:
                        for item in order.get("items", []):
                            if item in inventory:
                                if flags.get("discount"):
                                    if mode == "bulk":
                                        result.append(item * 0.8)
                                    elif mode == "vip":
                                        result.append(item * 0.5)
                                    else:
                                        result.append(item * 0.9)
                                else:
                                    result.append(item)
                            else:
                                if retries > 0:
                                    result.append(None)
    return result


# ============================================================
# VIOLATION 3: Dead code — function defined but never used (WARNS)
# ============================================================
def _helper_that_nobody_calls(x, y):
    return x + y


def another_unused_util(data):
    return sorted(data, reverse=True)


# ============================================================
# VIOLATION 4 & 5: Public functions with no docstring (WARNS)
# ============================================================
def get_user(user_id):
    return {"id": user_id, "name": "Unknown"}


def save_record(record, path):
    with open(path, "w") as f:
        f.write(str(record))


class DataProcessor:
    def process(self, data):
        return data

    def validate(self, data):
        return bool(data)
```

### How to run it

```bash
# Create a test repo if you don't have one
mkdir demo-repo && cd demo-repo
git init
git config user.email "demo@example.com"
git config user.name "Demo"

# First commit (needed so HEAD~1 works)
echo "# Demo repo" > README.md
git add . && git commit -m "initial"

# Add the bad file
# (paste nightmare_code.py into the folder)
git add nightmare_code.py
git commit -m "add code"

# Run the scan
codewatch scan --diff HEAD~1
```

### What you will see

```
FAIL  nightmare_code.py
       ✗  secrets
              ERROR   line 8: Password assignment detected — move to environment variable
              ERROR   line 9: API key assignment detected — move to environment variable
              ERROR   line 10: AWS access key detected — move to environment variable
       ✓  complexity
              warn    line 13: process_order() has complexity 13 (threshold 10) — consider simplifying
       ⚠  dead_code
              warn    line 34: Unused function '_helper_that_nobody_calls' — remove it or add a usage
              warn    line 38: Unused function 'another_unused_util' — remove it or add a usage
       ⚠  test_presence
              warn    line 1: No test file found for nightmare_code.py
       ⚠  docstrings
              warn    line 13: Public function 'process_order' has no docstring
              warn    line 43: Public function 'get_user' has no docstring
              warn    line 47: Public function 'save_record' has no docstring
              warn    line 52: Public class 'DataProcessor' has no docstring

✗  3 error(s), 10 total violation(s) across 1 file(s) — push blocked
```

Push is blocked. Exit code 1. Exactly what you want to show.

---

## The fix — clean version of the same code

Create `clean_code.py` to show the "after" state:

```python
"""Order processing module — handles order validation and pricing."""
import os


DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
API_KEY = os.environ.get("API_KEY")


def process_order(order: dict, user: dict, inventory: list) -> list:
    """
    Process an order and return priced items.

    Applies discount rules based on user type.
    Returns empty list if order or user is invalid.
    """
    if not order or not user or not user.get("active"):
        return []

    items = order.get("items", [])
    available = [item for item in items if item in inventory]
    return _apply_pricing(available, user)


def _apply_pricing(items: list, user: dict) -> list:
    """Apply pricing rules to a list of available items."""
    discount = _get_discount(user)
    return [item * discount for item in items]


def _get_discount(user: dict) -> float:
    """Return the discount multiplier for a given user type."""
    user_type = user.get("type", "standard")
    discounts = {"bulk": 0.8, "vip": 0.5, "standard": 1.0}
    return discounts.get(user_type, 1.0)


def get_user(user_id: str) -> dict:
    """Fetch a user record by ID. Returns a dict with id and name."""
    return {"id": user_id, "name": "Unknown"}


def save_record(record: dict, path: str) -> None:
    """Write a record to disk at the given path."""
    with open(path, "w") as f:
        f.write(str(record))


class DataProcessor:
    """Handles validation and processing of incoming data payloads."""

    def process(self, data: list) -> list:
        """Run processing pipeline on data and return results."""
        return data

    def validate(self, data: list) -> bool:
        """Return True if data is non-empty and valid."""
        return bool(data)
```

```bash
git add clean_code.py
git commit -m "fix: clean code with env vars and docstrings"
codewatch scan --diff HEAD~1
```

### What you will see

```
WARN  clean_code.py
       ✓  secrets
       ✓  complexity
       ✓  dead_code
       ⚠  test_presence
              warn    line 1: No test file found for clean_code.py
       ✓  docstrings

⚠  1 warning(s) across 1 file(s) — push allowed
```

Exit code 0. Push goes through.

---

## Demo script for interviews (2 minutes)

Use this as a script when showing the tool live:

```
"So the problem I'm solving is that AI generates code fast
but often leaves behind hardcoded secrets, overly complex
functions, and missing docstrings. Here's what that looks like."

[show nightmare_code.py on screen]

"When this developer tries to push..."

git add nightmare_code.py && git commit -m "add code"
git push   # or: codewatch scan --diff HEAD~1

[show the FAIL output — 3 errors, push blocked]

"The push is blocked. 3 errors, 10 violations, exact line numbers.
No hallucination — pure static analysis, works offline."

[pause for effect]

"Now they fix it — move secrets to environment variables,
split the complex function, add docstrings."

[show clean_code.py briefly]

git add clean_code.py && git commit -m "fix: clean version"
codewatch scan --diff HEAD~1

[show the PASS output]

"Passes. Push goes through."

[pause]

"The AI version does everything this does plus calls Claude
to check if the architecture makes sense — but this offline
version already catches the things that cost teams the most
debugging time."
```

---

## Stress test: secrets only

For a focused demo of just the secrets check:

```python
# secrets_nightmare.py
password = "hunter2"
db_pass = "mysecretpassword123"
SECRET_KEY = "django-insecure-abc123xyz789"
access_token = "ghp_abc123xyz789longtoken"
private_key = "-----BEGIN RSA PRIVATE KEY-----"
```

Expected: 5 errors, all blocked.

---

## Stress test: complexity only

```python
# complex_nightmare.py
def do_everything(a, b, c, d, e, f, g):
    if a:
        if b:
            if c:
                for x in d:
                    if e:
                        if f == 1:
                            return x
                        elif f == 2:
                            return x * 2
                        elif f == 3:
                            return x * 3
                        else:
                            if g:
                                return x * 4
                            else:
                                return x * 5
    return None
```

Expected: complexity ~15, warned. If above 20, blocked.

---

## Stress test: dead code only

Create a file where functions are defined but never used:

```python
# dead_nightmare.py
def _internal_helper(x, y):
    return x + y


def legacy_cleanup_job(user_id, payload):
    return payload
```

Expected: dead code warnings for both the unused private helper and the
unused public function. Dead code only warns (never blocks the push).

The check uses vulture under the hood and only reports items whose
definition line is part of the current diff, so dead code you did not
touch is not flagged.

---

## Checking exit codes (for CI integration demo)

```bash
codewatch scan --diff HEAD~1
echo "Exit code: $?"
# Bad code: Exit code: 1
# Clean code: Exit code: 0
```

Exit code 1 is what CI systems use to fail a pipeline.
This means codewatch integrates with GitHub Actions, Jenkins,
or any other CI system automatically.
