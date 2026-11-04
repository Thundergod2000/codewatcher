"""Parse git diff output into per-file changed lines."""

from __future__ import annotations
import os
import re
import subprocess

# Added line numbers discovered while parsing a diff, keyed by filename.
# Checks use these for exact line mapping in real scans; unit tests that
# call checks directly fall back to matching content against the file.
_LINE_NUMBER_CACHE: dict[str, list[int]] = {}

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

_SUPPORTED_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx")


def clear_line_number_cache() -> None:
    """Clear cached diff line numbers (used between test cases)."""
    _LINE_NUMBER_CACHE.clear()


def get_diff(ref: str = "HEAD~1") -> str:
    """Return unified diff of commits in `ref`, not the working tree.

    A range (`a..b` / `a...b`) is used as-is. A single ref becomes
    `ref...HEAD` so a pre-push hook can pass the remote SHA.
    """
    range_spec = ref if ".." in ref else f"{ref}...HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", range_spec, "--unified=0"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=0"],
            capture_output=True,
            text=True,
        )
        return result.stdout


def parse_diff(raw_diff: str) -> dict[str, list[str]]:
    """
    Parse a unified diff string into a mapping of filename → added lines.

    Returns only .py, .js, .jsx, .ts, .tsx files. Skips binary files and deleted files.
    Uses the new filename for renamed files.
    """
    result: dict[str, list[str]] = {}
    current_file: str | None = None
    current_lineno = 0
    in_hunk = False
    remaining_old = 0
    remaining_new = 0

    _LINE_NUMBER_CACHE.clear()

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            current_file = None
            continue

        if in_hunk:
            if line.startswith("\\"):
                # "\ No newline at end of file" is not a hunk line.
                continue

            if line.startswith("+"):
                if current_file:
                    result[current_file].append(line[1:])
                    _LINE_NUMBER_CACHE.setdefault(current_file, []).append(current_lineno)
                current_lineno += 1
                remaining_new -= 1
            elif line.startswith("-"):
                remaining_old -= 1
            else:
                # Context line. An empty line can appear when a diff producer
                # omits the leading space, so treat it as context too.
                current_lineno += 1
                remaining_old -= 1
                remaining_new -= 1

            if remaining_old <= 0 and remaining_new <= 0:
                in_hunk = False
            continue

        if line.startswith("+++ "):
            path = line[4:]
            if path.startswith("b/"):
                path = path[2:]
            if path != "/dev/null" and path.endswith(_SUPPORTED_EXTENSIONS):
                current_file = path
                result.setdefault(current_file, [])
            else:
                current_file = None
            continue

        if line.startswith("@@"):
            match = _HUNK_HEADER.match(line)
            if match:
                current_lineno = int(match.group(3))
                remaining_old = int(match.group(2)) if match.group(2) is not None else 1
                remaining_new = int(match.group(4)) if match.group(4) is not None else 1
                in_hunk = remaining_old > 0 or remaining_new > 0
            continue

        # Outside hunks: index lines, mode changes, binary markers, etc.

    return result


def added_file_linenos(filename: str, added_lines: list[str]) -> list[int]:
    """Map each added line to its 1-based line number in `filename`.

    Uses exact line numbers from the most recent parse_diff call when the
    counts match. Otherwise falls back to content matching (unit tests).
    When the file is missing, falls back to 1, 2, 3...
    Duplicate lines consume the next unused match in file order.
    """
    if not added_lines:
        return []

    cached = _LINE_NUMBER_CACHE.get(filename)
    if cached is not None and len(cached) == len(added_lines):
        return list(cached)

    if not os.path.exists(filename):
        return list(range(1, len(added_lines) + 1))

    try:
        source = open(filename, encoding="utf-8").read().splitlines()
    except (OSError, UnicodeDecodeError):
        return list(range(1, len(added_lines) + 1))

    used: set[int] = set()
    linenos: list[int] = []
    for i, added in enumerate(added_lines, start=1):
        found = 0
        for n, src in enumerate(source, start=1):
            if n in used:
                continue
            if src == added:
                found = n
                used.add(n)
                break
        linenos.append(found or i)
    return linenos


def get_changed_files(ref: str = "HEAD~1") -> list[str]:
    """Return list of changed .py, .js, .jsx, .ts, .tsx filenames (relative paths)."""
    try:
        result = subprocess.run(
            ["git", "diff", ref, "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.splitlines() if f.endswith((".py", ".js", ".jsx", ".ts", ".tsx"))]
    except subprocess.CalledProcessError:
        return []
