"""Pre-push hook runtime: read pushed refs from stdin and scan them."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from codewatch.baseline import Baseline, BaselineError, load_baseline
from codewatch.config import Config, ConfigError, load_config
from codewatch.diff import (
    get_blob_text,
    get_push_base,
    get_push_diff,
    is_valid_sha,
    is_zero_sha,
    parse_diff,
)
from codewatch.reporter import print_results, print_stale_baseline
from codewatch.scanner import run_checks, should_block

EXIT_OK = 0
EXIT_BLOCK = 1
EXIT_ERROR = 2


@dataclass(frozen=True)
class PushRef:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str


def parse_push_input(text: str) -> list[PushRef]:
    """Parse git's pre-push stdin: one ref per line, four fields."""
    refs: list[PushRef] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"malformed pre-push input on line {lineno}")

        local_ref, local_sha, remote_ref, remote_sha = parts
        if not is_valid_sha(local_sha) or not is_valid_sha(remote_sha):
            raise ValueError(f"invalid SHA on line {lineno}")

        refs.append(PushRef(
            local_ref=local_ref,
            local_sha=local_sha.lower(),
            remote_ref=remote_ref,
            remote_sha=remote_sha.lower(),
        ))

    return refs


def _collect_base_sources(
    ref: PushRef,
    changed: dict[str, list[str]],
) -> dict[str, str]:
    """Read each changed file as it was before the push.

    Delta comparison is best-effort: if the base cannot be resolved, the
    absolute complexity thresholds still apply.
    """
    try:
        base_sha = get_push_base(ref.local_sha, ref.remote_sha)
    except Exception:
        return {}

    if not base_sha:
        return {}

    sources: dict[str, str] = {}
    for filename in changed:
        text = get_blob_text(base_sha, filename)
        if text is not None:
            sources[filename] = text
    return sources


def _scan_ref(ref: PushRef, config: Config, baseline: Baseline) -> bool:
    """Scan one push ref. Return True when an ERROR should block the push."""
    diff = get_push_diff(ref.local_sha, ref.remote_sha)
    changed = parse_diff(diff)

    if not changed:
        print(f"codewatch: no supported files changed in {ref.local_ref}")
        return False

    print(f"\ncodewatch: reviewing {ref.local_ref} -> {ref.remote_ref}")
    base_sources = _collect_base_sources(ref, changed)
    results = run_checks(
        changed,
        config=config,
        baseline=baseline,
        base_sources=base_sources,
    )
    print_results(
        results, mode="check", files_scanned=len(results)
    )
    print_stale_baseline(baseline.stale(set(changed)))
    return should_block(results)


def run_hook(stdin_text: str) -> int:
    """Run the hook contract and return 0 (pass), 1 (block), or 2 (error)."""
    try:
        refs = parse_push_input(stdin_text)
    except ValueError as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        config = load_config()
        baseline = load_baseline()
    except (ConfigError, BaselineError) as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return EXIT_ERROR

    blocked = False
    reviewed = 0

    for ref in refs:
        if is_zero_sha(ref.local_sha):
            continue

        reviewed += 1
        try:
            if _scan_ref(ref, config, baseline):
                blocked = True
        except Exception as exc:  # fail closed on any tool error
            print(
                f"codewatch: could not review {ref.local_ref}: {exc}",
                file=sys.stderr,
            )
            return EXIT_ERROR

    if reviewed == 0:
        print("codewatch: no refs to review")
        return EXIT_OK

    return EXIT_BLOCK if blocked else EXIT_OK
