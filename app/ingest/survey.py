"""Phase 1: count files, formats, pages, parse failures and readable dates before ingesting.

Does: print the numbers the gate asks for. Does not: write anything.
"""
import csv
from collections import Counter
from pathlib import Path

from app import config
from app.ingest.readers import READERS, read_file


def manifest_dates() -> dict[str, str]:
    """File name -> published date, from the manifest that came with the corpus."""
    if not config.MANIFEST_PATH.exists():
        return {}
    with open(config.MANIFEST_PATH) as f:
        return {Path(r["file"]).name: r["published"] for r in csv.DictReader(f)}


def survey(raw_dir: Path = config.RAW_DIR) -> dict:
    """The gate numbers as one dict, so the self-check page can print them again later."""
    files = sorted(p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in READERS)
    unknown = sorted(p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() not in READERS and p.name != "manifest.csv")
    dates = manifest_dates()
    formats, pages, failed, undated, scans = Counter(), 0, [], [], []
    for path in files:
        formats[path.suffix.lower()] += 1
        try:
            units = read_file(path)
        except Exception as e:
            failed.append(f"{path.name}: {e}")
            continue
        pages += len(units)
        # a page with under 20 characters of text is a scan or a blank page
        if sum(1 for _, t in units if len(t.strip()) < 20) > len(units) * 0.5:
            scans.append(path.name)
        if path.name not in dates:
            undated.append(path.name)
    return {"files": len(files), "formats": dict(formats), "pages": pages, "failed": failed,
            "scans": scans, "dated": len(files) - len(undated), "undated": undated,
            "unknown_format": [p.name for p in unknown]}


if __name__ == "__main__":
    s = survey()
    print(f"{s['files']} files, formats {s['formats']}, {s['pages']} pages")
    print(f"{len(s['failed'])} fail to parse: {s['failed']}")
    print(f"{len(s['scans'])} look like scans: {s['scans']}")
    print(f"{s['dated']} carry a date from the manifest; undated: {s['undated']}")
    print(f"unknown formats: {s['unknown_format']}")
