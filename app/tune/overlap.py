"""Proof b: how many characters do consecutive chunks on one page actually share?

Does: longest common suffix/prefix between chunk n and n+1 on the same page, over 200 pages.
Does not: edit the chunker. A gap against config.CHUNK_OVERLAP is reported, not fixed.
"""
import json

from app import config


def shared_chars(left: str, right: str) -> int:
    """Longest L such that the last L chars of left equal the first L chars of right."""
    for length in range(min(len(left), len(right)), 0, -1):
        if left[-length:] == right[:length]:
            return length
    return 0


def consecutive_pairs(ids: list[str], metas: list[dict], texts: list[str], max_pages: int) -> list[tuple[str, str]]:
    """(chunk n, chunk n+1) text pairs from the same source and locator, first max_pages pages."""
    by_page: dict[tuple[str, str], dict[int, str]] = {}
    for meta, text in zip(metas, texts):
        by_page.setdefault((meta["source"], meta["locator"]), {})[meta["chunk_on_page"]] = text
    pairs = []
    pages_used = 0
    for page in by_page.values():
        if len(page) < 2:
            continue
        pages_used += 1
        for n in range(len(page) - 1):
            pairs.append((page[n], page[n + 1]))
        if pages_used >= max_pages:
            break
    return pairs


def prove_overlap(max_pages: int = 200) -> dict:
    """Mean and min shared characters against the configured overlap."""
    with open(config.BM25_PATH) as f:
        saved = json.load(f)
    pairs = consecutive_pairs(saved["ids"], saved["metas"], saved["texts"], max_pages)
    if not pairs:
        raise ValueError("no page has two chunks; overlap cannot be measured")
    measured = [shared_chars(a, b) for a, b in pairs]
    mean = sum(measured) / len(measured)
    exact = sum(1 for m in measured if m == config.CHUNK_OVERLAP)
    if mean < 0.8 * config.CHUNK_OVERLAP:
        diagnosis = "far under the config value; see app/ingest/chunk.py window step"
    else:
        diagnosis = "the chunker carries the configured overlap"
    return {"pages": max_pages, "pairs": len(pairs), "configured": config.CHUNK_OVERLAP,
            "mean_shared": round(mean, 1), "min_shared": min(measured), "max_shared": max(measured),
            "pairs_exactly_configured": exact, "diagnosis": diagnosis}
