"""Live view of a build in progress. Reads the project folder on every request and
renders one page. Standard library only, no dependencies, no build step.

    python3 buildview.py [project_dir] [port]

Then open http://localhost:8099. The page refreshes itself every 5 seconds.
It reads. It never writes anything into the project.
"""
from __future__ import annotations

import csv
import html
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8099

# Artifacts worth showing, in the order a build produces them. Label, path, what it proves.
GATES = [
    ("survey",      "store/survey.json",       "corpus counted, readers confirmed"),
    ("ingest",      "store/ingest_gate.json",  "chunks indexed, metric set"),
    ("quarantine",  "store/quarantine.jsonl",  "nothing silently skipped"),
    ("memory",      "store/memory.sqlite",     "long term store exists"),
    ("threads",     "store/threads.sqlite",    "conversation state"),
    ("checkpoints", "store/checkpoints.sqlite","short term state, resumable"),
    ("eval",        "store/eval_results.json", "scored against a baseline"),
    ("flowchart",   "flowchart.html",          "generated from the compiled graph"),
    ("dockerfile",  "Dockerfile",              "deployable"),
]


def read_text(rel: str, limit: int | None = None) -> str:
    """Return a file's text, or an empty string if it is not there yet."""
    p = ROOT / rel
    if not p.is_file():
        return ""
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return t[-limit:] if limit else t


def read_json(rel: str):
    """Parse a JSON artifact, or None if missing or half-written."""
    t = read_text(rel)
    if not t:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None  # a build mid-write; next refresh will get it


def elapsed() -> str:
    """Wall clock since .clock_start if the build wrote one, else since the oldest artifact."""
    marker = ROOT / ".clock_start"
    start = None
    if marker.is_file():
        try:
            start = float(marker.read_text().strip())
        except ValueError:
            start = marker.stat().st_mtime
    if start is None:
        times = [(ROOT / rel).stat().st_mtime for _, rel, _ in GATES if (ROOT / rel).exists()]
        if not times:
            return "not started"
        start = min(times)
    secs = int(time.time() - start)
    return f"{secs // 60}m {secs % 60}s"


def recent_files(seconds: int = 90, cap: int = 12) -> list[tuple[str, str]]:
    """Files touched in the last window. Skips the noise that would drown the signal."""
    skip = (".venv", "node_modules", "data/raw", "__pycache__", ".git", "dist")
    now, out = time.time(), []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not any(s in str(Path(dirpath, d)) for s in skip)]
        if any(s in dirpath for s in skip):
            continue
        for fn in filenames:
            if fn == ".DS_Store":
                continue
            p = Path(dirpath, fn)
            try:
                age = now - p.stat().st_mtime
            except OSError:
                continue
            if age < seconds:
                out.append((age, str(p.relative_to(ROOT))))
    out.sort()
    return [(f"{int(a)}s ago", r) for a, r in out[:cap]]


def csv_table(rel: str) -> str:
    """Render a sweep CSV as a small table. Charts are the artifact; this is the number."""
    t = read_text(rel)
    if not t:
        return ""
    rows = list(csv.reader(io.StringIO(t)))
    if not rows:
        return ""
    head, body = rows[0], rows[1:]
    th = "".join(f"<th>{html.escape(c)}</th>" for c in head)
    tr = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c[:12])}</td>" for c in r) + "</tr>" for r in body
    )
    return f"<h4>{html.escape(Path(rel).stem)}</h4><table><tr>{th}</tr>{tr}</table>"


def last_reports(n: int = 3) -> str:
    """The tail of BUILD_LOG.md, which is where the decisions live."""
    t = read_text("runs/BUILD_LOG.md", limit=6000)
    if not t:
        return ('<p class="none">No <code>runs/BUILD_LOG.md</code> yet. Tell the build to append '
                'every three-minute report to it, verbatim.</p>')
    blocks = [b for b in t.split("\n\n") if b.strip()]
    return "".join(f"<pre>{html.escape(b.strip())}</pre>" for b in blocks[-n:][::-1])


def eval_block() -> str:
    """Headline eval numbers, each next to the floor or ceiling that gives it meaning."""
    d = read_json("store/eval_results.json")
    if not d:
        return '<p class="none">No eval yet.</p>'
    out = []
    ceiling = d.get("text_hit_ceiling")
    base = d.get("retrieval_baseline") or {}
    for key, label in (("doc_hit", "document hit"), ("text_hit", "exact text hit")):
        by = (d.get("retrieval_by_bucket") or {}).get(key) or {}
        val = next(iter(by.values()), None)
        bits = []
        if val is not None:
            bits.append(f"<b>{val:.3f}</b>")
        if base.get(key) is not None:
            bits.append(f"floor {base[key]:.3f}")
        if key == "text_hit" and ceiling is not None:
            bits.append(f"ceiling {ceiling:.3f}")
        if bits:
            out.append(f"<div class='kv'><span>{label}</span><span>{' · '.join(bits)}</span></div>")
    worst = (d.get("retrieval_by_type") or {}).get("text_hit") or {}
    if worst:
        lo = sorted(worst.items(), key=lambda kv: kv[1])[:3]
        out.append("<div class='kv'><span>weakest query types</span><span>"
                   + ", ".join(f"{k} {v:.2f}" for k, v in lo) + "</span></div>")
    return "".join(out)


def page() -> str:
    gates = ""
    for label, rel, why in GATES:
        p = ROOT / rel
        ok = p.exists()
        detail = ""
        if ok:
            try:
                sz = p.stat().st_size
                detail = f"{sz/1024:.0f} KB" if sz > 2048 else f"{sz} B"
            except OSError:
                pass
        gates += (f"<div class='gate {'on' if ok else 'off'}'>"
                  f"<span class='dot'></span><b>{label}</b>"
                  f"<span class='why'>{why}</span><span class='det'>{detail}</span></div>")

    survey = read_json("store/survey.json") or {}
    ing = read_json("store/ingest_gate.json") or {}
    facts = []
    if survey.get("formats"):
        f = survey["formats"]
        tot = sum(v.get("files", 0) for v in f.values())
        fail = sum(v.get("failed", 0) for v in f.values())
        facts.append(("files seen", f"{tot} across {len(f)} formats, {fail} failed to parse"))
    if ing:
        facts.append(("indexed", f"{ing.get('chunk_count','?')} chunks from "
                                 f"{ing.get('documents','?')} documents"))
        facts.append(("metric", str(ing.get("distance_metric", "?"))))
    qn = len([l for l in read_text("store/quarantine.jsonl").splitlines() if l.strip()])
    if qn:
        facts.append(("quarantined", f"{qn} document(s), with a reason each"))
    factrows = "".join(f"<div class='kv'><span>{k}</span><span>{html.escape(v)}</span></div>"
                       for k, v in facts) or '<p class="none">Nothing indexed yet.</p>'

    sweeps = "".join(csv_table(f"charts/{n}.csv")
                     for n in ("top_k", "dense_weight", "chunk_size", "chunk_overlap"))
    recent = "".join(f"<div class='kv'><span>{a}</span><span>{html.escape(r)}</span></div>"
                     for a, r in recent_files()) or '<p class="none">Quiet.</p>'

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>Build view — {html.escape(ROOT.name)}</title>
<style>
 :root {{ --bg:#0e1116; --card:#161a21; --ink:#e6e9ee; --dim:#8e959f;
          --line:#2a313c; --on:#74bc97; --off:#3a4150; --hot:#de9560; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 ui-monospace,
         SFMono-Regular,Menlo,monospace; padding:20px }}
 h1 {{ font-size:17px; margin:0 0 2px }}
 .sub {{ color:var(--dim); font-size:12px; margin-bottom:18px }}
 .grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)) }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:5px; padding:12px 14px }}
 h3 {{ font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--hot);
       margin:0 0 10px }}
 h4 {{ font-size:11px; color:var(--dim); margin:12px 0 4px; text-transform:uppercase;
       letter-spacing:.08em }}
 .gate {{ display:flex; align-items:center; gap:8px; padding:3px 0 }}
 .dot {{ width:8px; height:8px; border-radius:50%; background:var(--off); flex:none }}
 .gate.on .dot {{ background:var(--on) }}
 .gate.off b, .gate.off .why {{ color:var(--off) }}
 .why {{ color:var(--dim); font-size:11px; flex:1 }}
 .det {{ color:var(--dim); font-size:11px }}
 .kv {{ display:flex; justify-content:space-between; gap:10px; padding:2px 0;
        border-bottom:1px dotted var(--line) }}
 .kv span:first-child {{ color:var(--dim) }}
 .clock {{ font-size:26px; color:var(--on) }}
 pre {{ background:#0b0e12; border:1px solid var(--line); border-left:2px solid var(--hot);
        padding:8px 10px; margin:0 0 8px; white-space:pre-wrap; font-size:12px }}
 table {{ border-collapse:collapse; width:100% }}
 th,td {{ text-align:left; padding:2px 6px; border-bottom:1px solid var(--line); font-size:12px }}
 th {{ color:var(--dim); font-weight:400 }}
 .none {{ color:var(--off); font-size:12px; margin:0 }}
</style></head><body>
<h1>{html.escape(ROOT.name)}</h1>
<div class="sub">{html.escape(str(ROOT))} · refreshes every 5s ·
  {datetime.now(timezone.utc).strftime('%H:%M:%SZ')}</div>
<div class="grid">
  <div class="card"><h3>Clock</h3><div class="clock">{elapsed()}</div></div>
  <div class="card"><h3>Gates</h3>{gates}</div>
  <div class="card"><h3>Corpus</h3>{factrows}</div>
  <div class="card"><h3>Eval</h3>{eval_block()}</div>
  <div class="card"><h3>Latest reports</h3>{last_reports()}</div>
  <div class="card"><h3>Sweeps</h3>{sweeps or '<p class="none">No sweeps yet.</p>'}</div>
  <div class="card"><h3>Just touched</h3>{recent}</div>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a) -> None:
        pass  # a refresh every 5s would bury the terminal


if __name__ == "__main__":
    if not ROOT.is_dir():
        raise SystemExit(f"not a directory: {ROOT}")
    print(f"build view for {ROOT}\n  http://localhost:{PORT}   (ctrl-c to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
