from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, is_dataclass
from typing import Any


class Palette:
    def __init__(self, enabled: bool | None = None) -> None:
        if enabled is None:
            color_mode = os.environ.get("HELIX_COLOR", "").lower()
            forced = bool(os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE") or color_mode == "always")
            disabled = bool(os.environ.get("NO_COLOR") or color_mode == "never")
            enabled = (sys.stdout.isatty() or forced) and not disabled
        self.enabled = enabled

    def paint(self, text: str, code: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def style(self, text: str, *codes: str) -> str:
        return self.paint(text, ";".join(codes))

    def bold(self, text: str) -> str:
        return self.paint(text, "1")

    def dim(self, text: str) -> str:
        return self.paint(text, "2")

    def green(self, text: str) -> str:
        return self.paint(text, "32")

    def blue(self, text: str) -> str:
        return self.paint(text, "34")

    def yellow(self, text: str) -> str:
        return self.paint(text, "33")

    def red(self, text: str) -> str:
        return self.paint(text, "31")

    def cyan(self, text: str) -> str:
        return self.paint(text, "36")

    def magenta(self, text: str) -> str:
        return self.paint(text, "35")


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def pad_visible(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


def banner(title: str, subtitle: str, palette: Palette, *, width: int = 76) -> str:
    inner = max(20, width - 4)
    top = palette.cyan("+" + "-" * (inner + 2) + "+")
    bottom = palette.cyan("+" + "-" * (inner + 2) + "+")
    title_line = "| " + pad_visible(palette.bold(title), inner) + " |"
    subtitle_line = "| " + pad_visible(palette.dim(subtitle), inner) + " |"
    return "\n".join([top, title_line, subtitle_line, bottom])


def status_badge(label: str, state: str, palette: Palette) -> str:
    padded = f"[{label}]"
    if state == "ok":
        return palette.green(padded)
    if state == "warn":
        return palette.yellow(padded)
    if state == "error":
        return palette.red(padded)
    return palette.dim(padded)


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
        widths[key] = max([visible_len(heading), *[visible_len(value) for value in values]])

    header = "  ".join(pad_visible(heading, widths[key]) for key, heading in columns)
    line = "  ".join("-" * widths[key] for key, _ in columns)
    body = [
        "  ".join(pad_visible(str(row.get(key, "")), widths[key]) for key, _ in columns)
        for row in rows
    ]
    return "\n".join([header, line, *body])
