"""Read any supported file or URL into (locator, text) units. One router in front.

Does: pdf, docx, pptx, html, md, txt, xlsx, csv, and a URL routed on content-type.
Does not: OCR. A PDF page with no extractable text is reported, not guessed.
"""
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import httpx

Unit = tuple[str, str]  # (locator, text)


def read_pdf(data: bytes) -> list[Unit]:
    """Page-level units so the page number is the citation."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return [(f"page {i + 1}", page.extract_text() or "") for i, page in enumerate(reader.pages)]


def read_docx(data: bytes) -> list[Unit]:
    """Paragraph index is the locator; a docx has no pages until it is printed."""
    import docx
    doc = docx.Document(io.BytesIO(data))
    return [(f"paragraph {i + 1}", p.text) for i, p in enumerate(doc.paragraphs) if p.text.strip()]


def read_pptx(data: bytes) -> list[Unit]:
    """Slide number is the locator."""
    from pptx import Presentation
    units = []
    for i, slide in enumerate(Presentation(io.BytesIO(data)).slides):
        text = "\n".join(s.text for s in slide.shapes if getattr(s, "has_text_frame", False))
        units.append((f"slide {i + 1}", text))
    return units


def read_html(data: bytes) -> list[Unit]:
    """Heading path is the locator: text under each h1/h2/h3 becomes one unit."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "lxml")
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    units, path, buf = [], ["top"], []
    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "td"]):
        if el.name in ("h1", "h2", "h3"):
            if buf:
                units.append((" > ".join(path), "\n".join(buf)))
            path, buf = [el.get_text(" ", strip=True)], []
        else:
            buf.append(el.get_text(" ", strip=True))
    if buf:
        units.append((" > ".join(path), "\n".join(buf)))
    return units


def read_markdown(data: bytes) -> list[Unit]:
    """Heading path is the locator, same idea as html."""
    units, heading, buf = [], "top", []
    for line in data.decode("utf-8", errors="replace").splitlines():
        if line.startswith("#"):
            if buf:
                units.append((heading, "\n".join(buf)))
            heading, buf = line.lstrip("#").strip(), []
        else:
            buf.append(line)
    if buf:
        units.append((heading, "\n".join(buf)))
    return units


def read_csv(data: bytes) -> list[Unit]:
    """Row number is the locator; each row becomes 'header: value' pairs, structured not prose."""
    rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))
    if not rows:
        return []
    header = rows[0]
    return [(f"row {i + 2}", "; ".join(f"{h}: {v}" for h, v in zip(header, r))) for i, r in enumerate(rows[1:])]


def read_xlsx(data: bytes) -> list[Unit]:
    """Sheet and row is the locator."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    units = []
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = [str(h) for h in next(rows, [])]
        for i, r in enumerate(rows):
            units.append((f"sheet {ws.title} row {i + 2}", "; ".join(f"{h}: {v}" for h, v in zip(header, r))))
    return units


READERS = {
    ".pdf": read_pdf, ".docx": read_docx, ".pptx": read_pptx, ".html": read_html, ".htm": read_html,
    ".md": read_markdown, ".txt": read_markdown, ".csv": read_csv, ".xlsx": read_xlsx,
}


def read_file(path: Path) -> list[Unit]:
    """Route on the file extension. Raises with the extension named when there is no reader."""
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"no reader for {path.suffix!r} ({path.name}); readers exist for {sorted(READERS)}")
    return reader(path.read_bytes())


def read_url(url: str) -> tuple[str, list[Unit]]:
    """Fetch and route on content-type. Returns (locator prefix with fetch time, units)."""
    response = httpx.get(url, timeout=30.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    kind = response.headers.get("content-type", "").split(";")[0]
    reader = read_pdf if kind == "application/pdf" else read_html if "html" in kind else read_markdown
    return f"{url} fetched {fetched}", reader(response.content)
