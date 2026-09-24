from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class LinkItem:
    text: str
    href: str

def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())

def unique_items(items: Iterable[LinkItem]) -> list[LinkItem]:
    seen: set[str] = set()
    out: list[LinkItem] = []
    for item in items:
        key = item.href or item.text
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out
