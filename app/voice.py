from __future__ import annotations

from dataclasses import dataclass, asdict
import re


@dataclass(frozen=True)
class VoiceProfile:
    """Local, user-editable writing preferences."""

    avoid_terms: tuple[str, ...] = (
        "leverage", "leveraging", "streamline", "harness", "delve",
        "unlock", "foster", "game-changing", "revolutionary",
    )
    max_em_dash_per_100_words: float = 1.0
    comment_min_chars: int = 200
    comment_max_chars: int = 350
    post_min_chars: int = 900
    post_max_chars: int = 1300


DEFAULT_VOICE = VoiceProfile()


def metrics(text: str) -> dict:
    words = re.findall(r"\b\w+[\w'-]*\b", text)
    word_count = len(words)
    em_dashes = text.count("—")
    emojis = sum(1 for ch in text if ord(ch) > 0x1F300)
    sentences = [x for x in re.split(r"[.!?]+", text) if x.strip()]
    repeated = len(re.findall(r"\b(\w+)\s+\1\b", text, flags=re.I))
    density = (em_dashes / max(word_count, 1)) * 100
    return {
        "chars": len(text),
        "words": word_count,
        "em_dashes": em_dashes,
        "em_dash_per_100_words": round(density, 2),
        "emoji_count": emojis,
        "sentence_count": len(sentences),
        "repeated_word_pairs": repeated,
    }


def audit_voice(text: str, profile: VoiceProfile = DEFAULT_VOICE) -> dict:
    m = metrics(text)
    lower = text.lower()
    hits = [term for term in profile.avoid_terms if re.search(rf"\b{re.escape(term)}\b", lower)]
    return {
        "metrics": m,
        "avoid_term_hits": sorted(set(hits)),
        "em_dash_ok": m["em_dash_per_100_words"] <= profile.max_em_dash_per_100_words,
        "specificity_hint": bool(re.search(r"\b\d+(?:\.\d+)?%?\b", text)),
    }


def apply_light_cleanup(text: str, profile: VoiceProfile = DEFAULT_VOICE) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def profile_dict(profile: VoiceProfile = DEFAULT_VOICE) -> dict:
    return asdict(profile)
