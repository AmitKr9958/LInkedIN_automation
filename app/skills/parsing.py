from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class LinkItem:
    text: str
    href: str

def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())

def dedupe_by(items: Iterable[T], key: Callable[[T], str]) -> list[T]:
    """Keep the first item for each non-empty key, preserving order."""
    seen: set[str] = set()
    out: list[T] = []
    for item in items:
        item_key = key(item)
        if item_key and item_key not in seen:
            seen.add(item_key)
            out.append(item)
    return out

def unique_items(items: Iterable[LinkItem]) -> list[LinkItem]:
    return dedupe_by(items, lambda item: item.href or item.text)
