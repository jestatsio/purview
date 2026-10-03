"""Extract nonempty changelog notes for an exact, validated release tag."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def release_notes(tag: str, changelog: str) -> str:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", tag):
        raise ValueError(f"Expected a version tag such as v0.3.1 or v0.4.0rc1, got {tag!r}")
    heading = re.search(rf"^## \[{re.escape(tag[1:])}\](?:[^\n]*)\n", changelog, re.MULTILINE)
    if heading is None:
        raise ValueError(f"No changelog section for {tag}")
    notes = re.split(r"^## \[", changelog[heading.end() :], maxsplit=1, flags=re.MULTILINE)[0]
    notes = re.split(r"^\[Unreleased\]:", notes, maxsplit=1, flags=re.MULTILINE)[0].strip()
    if not notes:
        raise ValueError(f"Empty changelog section for {tag}")
    return notes + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    changelog_path = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    args.output.write_text(release_notes(args.tag, changelog_path.read_text()), encoding="utf-8")
