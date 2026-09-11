"""Generate flowchart.html from the running system. Never hand-drawn.

Does: read the compiled graph, node docstrings, config guardrails, ingest stats, eval and
tuning results, installed versions, and write one self-contained HTML file.
Does not: ship. flowchart.html is gitignored and excluded from the image.
"""
import html
import importlib
import inspect
import json
from datetime import datetime, timezone
from importlib.metadata import version

from app import config

STACK = ["anthropic", "chromadb", "rank-bm25", "pypdf", "langgraph", "langgraph-checkpoint-sqlite",
         "langsmith", "pydantic", "fastapi", "uvicorn", "httpx"]


def load_json(name: str) -> dict:
    """A runs/ file if it exists, else an empty dict so the page says 'not yet run'."""
    path = config.RUNS_DIR / name
    return json.loads(path.read_text()) if path.exists() else {}


def graph_section() -> tuple[str, list[dict]]:
    """Mermaid text from the compiled graph, plus one row per node from its docstring."""
    try:
        build = importlib.import_module("app.graph.build")
        nodes = importlib.import_module("app.graph.nodes")
        nodes_answer = importlib.import_module("app.graph.nodes_answer")
    except Exception as e:
        return f"flowchart TD\n  X[\"graph not built yet: {html.escape(str(e))}\"]", []
    compiled = build.build_graph()
    mermaid = compiled.get_graph().draw_mermaid()
    rows = []
    for name in compiled.get_graph().nodes:
        fn = getattr(nodes, name, None) or getattr(nodes_answer, name, None)
        if fn is None or not callable(fn):
            continue
        src = inspect.getsource(fn)
        rows.append({"node": name, "job": (inspect.getdoc(fn) or "").splitlines()[0] if inspect.getdoc(fn) else "",
                     "kind": "model call" if "call_model(" in src else "code, deliberately"})
    return mermaid, rows


def table(rows: list[dict]) -> str:
    """A plain HTML table from a list of dicts. Empty list renders a one-line note."""
    if not rows:
        return "<p class=note>not yet run</p>"
    heads = list(rows[0])
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(r.get(h, '')))}</td>" for h in heads) + "</tr>" for r in rows)
    return f"<table><tr>{''.join(f'<th>{h}</th>' for h in heads)}</tr>{body}</table>"


def kv(d: dict) -> str:
    """Key/value pairs as a table."""
    return table([{"setting": k, "value": v} for k, v in d.items()]) if d else "<p class=note>not yet run</p>"


def main() -> None:
    mermaid, node_rows = graph_section()
    ingest, ev, proofs, sweeps = load_json("ingest_report.json"), load_json("eval_results.json"), load_json("proofs.json"), load_json("sweeps.json")
    guardrails = {"refusal string (specialist emits)": config.REFUSAL_STRING, "what the supervisor sees on refusal": config.ESCALATION_TEXT,
                  "forbidden phrases (checked in code)": ", ".join(config.FORBIDDEN_PATTERNS), "model": config.MODEL,
                  "top_k": config.TOP_K, "dense weight": config.DENSE_WEIGHT, "chunk size / overlap": f"{config.CHUNK_SIZE} / {config.CHUNK_OVERLAP}",
                  "chroma space": config.CHROMA_SPACE}
    memory = [{"kind": "short term", "where": str(config.CHECKPOINT_DB.relative_to(config.ROOT)),
               "stores": "graph state after every node, keyed by thread id: question, corpora chosen, reports, dropped quotes, answer. Lets a refresh reopen the thread and a killed run resume."},
              {"kind": "long term", "where": str(config.MEMORY_DB.relative_to(config.ROOT)),
               "stores": "ManagerDecision rows: question, answer, reason, who, when. Fed into later runs as delimited data, never as a citation."}]
    corpus = {k: ingest.get(k) for k in ("chunks", "per_corpus", "min_len", "max_len", "mean_len")} if ingest else {}
    corpus["quarantined"] = len(ingest.get("quarantined", [])) if ingest else None
    stack = [{"package": p, "version": version(p)} for p in STACK]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Plant docs RAG: flowchart</title>
<style>body{{font:15px/1.45 -apple-system,Helvetica,Arial;margin:32px;max-width:1100px;color:#222}}h1{{font-size:22px}}h2{{font-size:17px;margin-top:32px;border-bottom:1px solid #ddd;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px}}td,th{{border:1px solid #ddd;padding:5px 8px;text-align:left;vertical-align:top}}th{{background:#f4f4f4}}
.note{{color:#777}}.mermaid{{background:#fafafa;padding:12px;border:1px solid #eee}}pre{{white-space:pre-wrap}}</style></head><body>
<h1>Plant docs RAG for the floor supervisor</h1><p class=note>Generated from the running system at {now}. If this page is wrong, the code is wrong.</p>
<h2>The graph, read from the compiled LangGraph</h2><pre class="mermaid">{html.escape(mermaid)}</pre>
<h2>Nodes: one line each, from the function docstring</h2>{table(node_rows)}
<h2>Memory, two kinds</h2>{table(memory)}
<h2>Guardrails, read from config</h2>{kv(guardrails)}
<h2>Corpus, from the last ingest</h2>{kv(corpus)}
<h2>Eval, from the last run</h2>{kv({k: v for k, v in ev.items() if not isinstance(v, (list, dict))}) if ev else '<p class=note>not yet run</p>'}
{kv(ev.get('retrieval', {})) if isinstance(ev.get('retrieval'), dict) else ''}
<h2>Proofs</h2>{kv({k: (v if not isinstance(v, (list, dict)) else json.dumps(v)[:200]) for k, v in proofs.items()}) if proofs else '<p class=note>not yet run</p>'}
<h2>Sweeps</h2>{kv({k: (v if not isinstance(v, (list, dict)) else json.dumps(v)[:200]) for k, v in sweeps.items()}) if sweeps else '<p class=note>not yet run</p>'}
<h2>Stack, installed versions</h2>{table(stack)}
<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";mermaid.initialize({{startOnLoad:true}});</script>
</body></html>"""
    (config.ROOT / "flowchart.html").write_text(page)
    print(f"flowchart.html written; graph nodes: {len(node_rows)}; eval: {'yes' if ev else 'not yet'}; proofs: {'yes' if proofs else 'not yet'}")


if __name__ == "__main__":
    main()
