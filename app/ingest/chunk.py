"""Cut one page (or section) into chunks that carry their locator and date with them.

Does: fixed-size character windows with overlap, never crossing a page boundary.
Does not: sentence detection. Page is the citation, so a chunk never spans two.
"""
from app import config


def chunk_text(text: str, size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Windows of `size` chars stepping by size - overlap. Empty text gives an empty list."""
    if overlap >= size:
        raise ValueError(f"overlap {overlap} must be smaller than size {size}")
    text = " ".join(text.split())
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, max(len(text) - overlap, 1), step)]


def chunk_units(units: list[tuple[str, str]], meta: dict) -> list[dict]:
    """Every chunk carries the document metadata plus its locator and its index on that page."""
    out = []
    for locator, text in units:
        for n, piece in enumerate(chunk_text(text)):
            out.append({"text": piece, "locator": locator, "chunk_on_page": n, **meta})
    return out
