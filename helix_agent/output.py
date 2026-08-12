from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any


class Palette:
    def __init__(self, enabled: bool | None = None) -> None:
        if enabled is None:
            enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self.enabled = enabled

    def paint(self, text: str, code: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self.paint(text, "1")

    def dim(self, text: str) -> str:
        return self.paint(text, "2")

    def green(self, text: str) -> str:
        return self.paint(text, "32")

    def yellow(self, text: str) -> str:
        return self.paint(text, "33")

    def red(self, text: str) -> str:
        return self.paint(text, "31")

    def cyan(self, text: str) -> str:
        return self.paint(text, "36")

    def magenta(self, text: str) -> str:
        return self.paint(text, "35")


def json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__fspath__"):
        return os.fspath(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=json_default))


def format_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], *, empty: str = "No rows.") -> str:
    if not rows:
        return empty

    widths: dict[str, int] = {}
    for key, heading in columns:
        values = [str(row.get(key, "")) for row in rows]
        widths[key] = max([len(heading), *[len(value) for value in values]])

    header = "  ".join(heading.ljust(widths[key]) for key, heading in columns)
    line = "  ".join("-" * widths[key] for key, _ in columns)
    body = [
        "  ".join(str(row.get(key, "")).ljust(widths[key]) for key, _ in columns)
        for row in rows
    ]
    return "\n".join([header, line, *body])
