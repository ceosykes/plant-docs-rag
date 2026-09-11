"""Phase 2 entry point: python -m app.ingest.run. Reads data/raw, writes store/.

Does: read every file through the router, chunk, tag with corpus and date, write both indexes,
quarantine anything unreadable or undated, print the gate numbers.
Does not: touch the network unless a urls.txt is present in data/raw.
"""
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from app import config
from app.ingest.chunk import chunk_units
from app.ingest.index import write_store
from app.ingest.readers import READERS, read_file, read_url


def load_manifest() -> dict[str, dict]:
    """File name -> row. The manifest is where the human titles and dates live."""
    with open(config.MANIFEST_PATH) as f:
        return {Path(r["file"]).name: r for r in csv.DictReader(f)}


def corpus_of(path: Path) -> str:
    """The folder under data/raw is the corpus tag. Anything else is an error, not a default."""
    name = path.parent.name
    if name not in config.CORPORA:
        raise ValueError(f"{path} is not under one of {config.CORPORA}")
    return name


def ingest_files(manifest: dict) -> tuple[list[dict], list[dict]]:
    """Every readable, dated file becomes chunks. Everything else is quarantined with a reason."""
    chunks, quarantine = [], []
    files = sorted(p for p in config.RAW_DIR.rglob("*") if p.is_file() and p.name != "manifest.csv")
    for path in files:
        if path.suffix.lower() not in READERS:
            quarantine.append({"file": path.name, "reason": f"no reader for {path.suffix}"})
            continue
        row = manifest.get(path.name)
        if not row or not row.get("published"):
            quarantine.append({"file": path.name, "reason": "no publication date in manifest"})
            continue
        try:
            units = read_file(path)
        except Exception as e:
            quarantine.append({"file": path.name, "reason": f"parse failed: {e}"})
            continue
        meta = {"source": path.name, "title": row["title"], "doc_date": row["published"],
                "corpus": corpus_of(path), "publisher": row["publisher"], "source_url": row["source_url"]}
        chunks.extend(chunk_units(units, meta))
    return chunks, quarantine


def ingest_urls(manifest: dict) -> tuple[list[dict], list[dict]]:
    """Optional data/raw/urls.txt: one 'corpus,url' per line. Fetched, routed on content-type."""
    path = config.RAW_DIR / "urls.txt"
    if not path.exists():
        return [], []
    chunks, quarantine = [], []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        corpus, url = line.split(",", 1)
        try:
            locator_prefix, units = read_url(url.strip())
        except Exception as e:
            quarantine.append({"file": url, "reason": f"fetch failed: {e}"})
            continue
        row = next((r for r in manifest.values() if r["source_url"] == url.strip()), None)
        if not row or not row.get("published"):
            quarantine.append({"file": url, "reason": "no publication date in manifest"})
            continue
        meta = {"source": url.strip(), "title": row["title"], "doc_date": row["published"],
                "corpus": corpus.strip(), "publisher": row["publisher"], "source_url": url.strip()}
        chunks.extend(chunk_units([(f"{locator_prefix} | {loc}", t) for loc, t in units], meta))
    return chunks, quarantine


def gate_report(chunks: list[dict], quarantine: list[dict]) -> dict:
    """The numbers the phase 2 gate asks for, saved so the flowchart and self-check can reread them."""
    lengths = [len(c["text"]) for c in chunks]
    per_source = Counter(c["source"] for c in chunks)
    per_corpus = Counter(c["corpus"] for c in chunks)
    report = {"chunks": len(chunks), "per_corpus": dict(per_corpus), "per_source": dict(per_source),
              "min_len": min(lengths), "max_len": max(lengths), "mean_len": round(statistics.mean(lengths)),
              "quarantined": quarantine, "chunk_size": config.CHUNK_SIZE, "chunk_overlap": config.CHUNK_OVERLAP,
              "samples": [{k: v for k, v in c.items()} for c in (chunks[0], chunks[len(chunks) // 2], chunks[-1])]}
    config.RUNS_DIR.mkdir(exist_ok=True)
    with open(config.RUNS_DIR / "ingest_report.json", "w") as f:
        json.dump(report, f, indent=1)
    return report


def main() -> None:
    manifest = load_manifest()
    chunks, quarantine = ingest_files(manifest)
    url_chunks, url_quarantine = ingest_urls(manifest)
    chunks, quarantine = chunks + url_chunks, quarantine + url_quarantine
    write_store(chunks)
    r = gate_report(chunks, quarantine)
    print(f"{r['chunks']} chunks; per corpus {r['per_corpus']}; length min/max/mean {r['min_len']}/{r['max_len']}/{r['mean_len']}")
    print(f"quarantined: {len(quarantine)} {quarantine}")
    for s in r["samples"]:
        print(f"  [{s['corpus']}] {s['source']} {s['locator']} ({s['doc_date']}): {s['text'][:120]!r}")


if __name__ == "__main__":
    main()
