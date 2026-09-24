from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaPrompt:
    prompt: str
    kind: str = "wide"
    alt_text: str = ""

    def to_dict(self) -> dict:
        return {"prompt": self.prompt, "kind": self.kind, "alt_text": self.alt_text}


def build_image_prompt(post_text: str, kind: str = "wide", brand_hint: str = "") -> MediaPrompt:
    excerpt = " ".join(post_text.split())[:500]
    prompt = (
        "Create a professional LinkedIn visual that supports this post without "
        "repeating the entire text. Use clean composition, strong hierarchy, "
        f"and accessible contrast. Topic: {excerpt}"
    )
    if brand_hint:
        prompt += f" Brand direction: {brand_hint}."
    return MediaPrompt(prompt, kind, f"LinkedIn visual supporting: {excerpt[:180]}")


def build_quote_card(quote: str, handle: str = "", style: str = "clean") -> MediaPrompt:
    prompt = f"Create a clean quote card using this exact quote: {quote.strip()}. Style: {style}."
    if handle:
        prompt += f" Include the handle {handle}."
    return MediaPrompt(prompt, "quote-card", quote.strip())
