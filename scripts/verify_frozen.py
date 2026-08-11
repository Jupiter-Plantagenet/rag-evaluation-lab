"""Verify that the frozen held-out artefacts still hash to their recorded values.

The checksums are parsed out of ``docs/frozen-held-out-result.md`` rather than
duplicated here. One source of truth: if the document and the artefacts disagree,
that is exactly the condition this script exists to detect, and there is no third
copy that could quietly agree with the wrong one.

Exit status is 0 when every recorded file matches, 1 otherwise. Run it directly or
via ``tests/unit/test_frozen_artefacts.py``.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD = REPO_ROOT / "docs" / "frozen-held-out-result.md"

# One line of `sha256␠␠path`, exactly as `sha256sum` writes it.
_LINE = re.compile(r"^([0-9a-f]{64})\s\s(\S+)$")


def recorded_checksums(record: Path = RECORD) -> dict[str, str]:
    """Parse {path: sha256} out of the fenced checksum block."""
    text = record.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _LINE.match(line.strip())
        if m:
            out[m.group(2)] = m.group(1)
    if not out:
        raise SystemExit(f"no checksum lines found in {record} -- has the format changed?")
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(repo_root: Path = REPO_ROOT) -> list[str]:
    """Return a list of human-readable problems. Empty means everything matches."""
    problems: list[str] = []
    for rel, expected in sorted(recorded_checksums().items()):
        path = repo_root / rel
        if not path.exists():
            problems.append(f"MISSING   {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            problems.append(
                f"CHANGED   {rel}\n            recorded {expected}\n            actual   {actual}"
            )
    return problems


def main() -> int:
    problems = verify()
    n = len(recorded_checksums())
    if problems:
        print(f"FROZEN ARTEFACTS DIFFER ({len(problems)} of {n} files):\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nThese files are closed scientific evidence. If you regenerated one, restore it\n"
            "with `git checkout -- <path>`. A genuinely re-issued result must be written to a\n"
            "NEW path and recorded as a new report version -- never by overwriting these.",
            file=sys.stderr,
        )
        return 1
    print(f"all {n} frozen artefacts match their recorded SHA-256 checksums")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
