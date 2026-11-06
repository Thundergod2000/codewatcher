"""Read git diffs in-process. No git executable is ever launched."""

from __future__ import annotations
import io
import os
import re

from dulwich import porcelain
from dulwich.errors import (
    CommitError,
    NotCommitError,
    NotGitRepository,
    ObjectMissing,
    RefFormatError,
    WrongObjectException,
)
from dulwich.graph import find_merge_base
from dulwich.objects import Commit, Tag
from dulwich.objectspec import AmbiguousShortId, parse_commit, parse_object
from dulwich.repo import Repo

# Added line numbers discovered while parsing a diff, keyed by filename.
# Checks use these for exact line mapping in real scans; unit tests that
# call checks directly fall back to matching content against the file.
_LINE_NUMBER_CACHE: dict[str, list[int]] = {}

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

_SUPPORTED_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx")

ZERO_SHA = "0" * 40
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

# Dulwich raises a variety of errors for bad refs, missing objects, or
# repositories without a usable merge base. All of them mean the same
# thing here: fall back to the staged diff.
_DIFF_ERRORS = (
    AmbiguousShortId,
    CommitError,
    KeyError,
    NotCommitError,
    NotGitRepository,
    ObjectMissing,
    OSError,
    RefFormatError,
    ValueError,
    WrongObjectException,
)


def clear_line_number_cache() -> None:
    """Clear cached diff line numbers (used between test cases)."""
    _LINE_NUMBER_CACHE.clear()


def _open_repo() -> Repo | None:
    """Open the repository containing the current directory."""
    try:
        return Repo.discover(".")
    except _DIFF_ERRORS:
        return None


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="surrogateescape")


def _parse_range(ref: str) -> tuple[str, str, bool]:
    """Split `a..b` / `a...b` into refs. Single refs diff against HEAD."""
    if "..." in ref:
        left, _, right = ref.partition("...")
        return left or "HEAD", right or "HEAD", True
    if ".." in ref:
        left, _, right = ref.partition("..")
        return left or "HEAD", right or "HEAD", False
    return ref or "HEAD", "HEAD", True


def _resolve_commit(repo: Repo, ref: str) -> Commit:
    """Resolve branch names, hashes, and syntax like HEAD~1 to a commit."""
    obj = parse_object(repo, ref)
    if isinstance(obj, Tag):
        return parse_commit(repo, obj)
    if not isinstance(obj, Commit):
        raise ValueError(f"{ref} is not a commit")
    return obj


def _diff_commits(repo: Repo, base_sha: bytes, head_sha: bytes) -> str:
    out = io.BytesIO()
    porcelain.diff(repo, commit=base_sha, commit2=head_sha, outstream=out)
    return _decode(out.getvalue())


def _staged_diff(repo: Repo) -> str:
    out = io.BytesIO()
    porcelain.diff(repo, staged=True, outstream=out)
    return _decode(out.getvalue())


def get_diff(ref: str = "HEAD~1") -> str:
    """Return a unified diff for `ref`, read directly from `.git`.

    A range (`a..b` / `a...b`) is used as-is. A single ref becomes
    `ref...HEAD` so a pre-push hook can pass the remote SHA.
    If the ref cannot be resolved, fall back to the staged diff.
    """
    repo = _open_repo()
    if repo is None:
        return ""

    try:
        try:
            left_ref, right_ref, triple_dot = _parse_range(ref)
            left_commit = _resolve_commit(repo, left_ref)
            right_commit = _resolve_commit(repo, right_ref)

            if triple_dot:
                bases = find_merge_base(repo, [left_commit.id, right_commit.id])
                if not bases:
                    raise ValueError(f"no merge base for {ref}")
                base_sha = bases[0]
            else:
                base_sha = left_commit.id

            return _diff_commits(repo, base_sha, right_commit.id)
        except _DIFF_ERRORS:
            try:
                return _staged_diff(repo)
            except _DIFF_ERRORS:
                return ""
    finally:
        repo.close()


def is_valid_sha(sha: str) -> bool:
    """Return True when `sha` is a full 40-character hexadecimal object id."""
    return isinstance(sha, str) and bool(_SHA_RE.fullmatch(sha))


def is_zero_sha(sha: str) -> bool:
    """Return True for the all-zero SHA git uses for a deleted/new ref."""
    return sha == ZERO_SHA


def _default_branch_commit(repo: Repo) -> Commit | None:
    """Return the first resolvable default branch commit, or None."""
    for name in ("origin/main", "origin/master", "main", "master"):
        try:
            return _resolve_commit(repo, name)
        except _DIFF_ERRORS:
            continue
    return None


def _merge_base(repo: Repo, first: bytes, second: bytes) -> bytes | None:
    try:
        bases = find_merge_base(repo, [first, second])
    except _DIFF_ERRORS:
        return None
    return bases[0] if bases else None


def _capped_base(repo: Repo, local: Commit, limit: int = 3) -> bytes | None:
    """Walk first-parent history up to `limit` commits.

    Returns None when the branch is shorter than the limit. None means
    "diff against the empty tree", which reviews the whole (short) branch
    including its root commit.
    """
    node = local
    for _ in range(limit):
        if not node.parents:
            return None
        try:
            parent = repo.get_object(node.parents[0])
        except _DIFF_ERRORS:
            return None
        if not isinstance(parent, Commit):
            return None
        node = parent
    return node.id


def get_push_diff(local_sha: str, remote_sha: str) -> str:
    """Return the diff for one pre-push ref, or raise on unusable input.

    A normal push diffs from the merge-base with the remote SHA. A new
    branch diffs from its merge-base with the default branch. When no
    default branch exists, only the last three commits are reviewed.
    """
    local_sha = (local_sha or "").lower()
    remote_sha = (remote_sha or "").lower()

    if not is_valid_sha(local_sha):
        raise ValueError("invalid local SHA")
    if not is_valid_sha(remote_sha):
        raise ValueError("invalid remote SHA")

    repo = _open_repo()
    if repo is None:
        raise RuntimeError("not a git repository")

    try:
        local = _resolve_commit(repo, local_sha)

        if is_zero_sha(remote_sha):
            default = _default_branch_commit(repo)
            if default is not None:
                base = _merge_base(repo, default.id, local.id)
                if base is not None:
                    return _diff_commits(repo, base, local.id)

            capped = _capped_base(repo, local)
            if capped is None:
                out = io.BytesIO()
                porcelain.diff(repo, commit2=local.id, outstream=out)
                return _decode(out.getvalue())
            return _diff_commits(repo, capped, local.id)

        remote = _resolve_commit(repo, remote_sha)
        base = _merge_base(repo, remote.id, local.id)
        return _diff_commits(repo, base if base is not None else remote.id, local.id)
    finally:
        repo.close()


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
    repo = _open_repo()
    if repo is None:
        return []

    try:
        out = io.BytesIO()
        porcelain.diff(repo, commit=ref, outstream=out)
        raw_diff = _decode(out.getvalue())
    except _DIFF_ERRORS:
        return []
    finally:
        repo.close()

    files = []
    for line in raw_diff.splitlines():
        if not line.startswith("+++ "):
            continue
        path = line[4:]
        if path.startswith("b/"):
            path = path[2:]
        if path != "/dev/null" and path.endswith(_SUPPORTED_EXTENSIONS):
            files.append(path)
    return files
