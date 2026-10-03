"""Verify that the rendered quickstart contains and runs the maintained example."""

from __future__ import annotations

import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path


class CodeBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._in_pre = False
        self._in_code = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            self._in_pre = True
        elif tag == "code" and self._in_pre:
            self._in_code = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "code" and self._in_code:
            self.blocks.append("".join(self._parts).strip())
            self._in_code = False
        elif tag == "pre":
            self._in_pre = False

    def handle_data(self, data: str) -> None:
        if self._in_code:
            self._parts.append(data)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parser = CodeBlocks()
    parser.feed((root / "site/quickstart/index.html").read_text(encoding="utf-8"))
    source = (root / "examples/quickstart.py").read_text(encoding="utf-8").strip()
    if source not in parser.blocks:
        raise RuntimeError(
            "Built quickstart is missing the complete example. Check snippet syntax."
        )
    rendered = parser.blocks[parser.blocks.index(source)]
    result = subprocess.run(  # noqa: S603 - rendered code must equal the maintained example above
        [sys.executable, "-c", rendered], check=True, capture_output=True, text=True, timeout=30
    )
    if result.stdout.splitlines() != ["['My draft']", "None", "True"]:
        raise RuntimeError(f"Unexpected quickstart output: {result.stdout!r}")
    print("Rendered quickstart matches the source and runs successfully")
