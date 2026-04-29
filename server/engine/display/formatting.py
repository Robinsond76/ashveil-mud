"""Shared display formatting utilities — the single source of truth for _box()."""
from __future__ import annotations


def box(title: str, lines: list[str]) -> str:
    """Format a boxed display with title."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)
