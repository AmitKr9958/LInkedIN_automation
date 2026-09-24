from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")

_DEGREE_SPLIT = re.compile(r"\s*[\u2022]\s*")


@dataclass(frozen=True)
class LinkItem:
    text: str
    href: str


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def strip_degree(value: str) -> str:
    """Drop LinkedIn connection-degree suffixes like '• 2nd' from labels."""
    return clean_text(_DEGREE_SPLIT.split(value or "", maxsplit=1)[0])


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
