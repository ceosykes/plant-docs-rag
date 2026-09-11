# Stack and why

The stack is decided. Only a measured fact overrides a line in it, and if you drop one,
say which fact forced it. Verified on Python 3.13 with no torch installed.

## Two things verified, not assumed

**Chroma's default distance is squared L2, not cosine.** Measured on the same document:
default returned 1.581, cosine returned 0.7905. Cosine must be set explicitly at collection
creation: `metadata={"hnsw:space": "cosine"}`. Get this wrong and every distance number
means something other than what you say it means.

**BM25 returns 0.0 on a tiny corpus, and that is arithmetic, not a bug.** With 2 documents
where a term appears in 1, Robertson IDF is exactly log(1.5) − log(1.5) = 0. Measured:
2 docs → 0.0000, 3 docs → 0.4778, 12 docs → 1.8500. Do not debug this on three fixtures.

## The stack

| Tool | Why it is here | At a client, this becomes |
|---|---|---|
| **anthropic** | The one model call. Reads policy prose and writes findings with quotes. | Bedrock or Foundry, inside the client's tenant, under their BAA. |
| **chromadb** | Vector store. Embedded, zero ops, metadata filters applied before ranking so date-of-service filtering is not left to similarity. | pgvector on the same Postgres already holding state, or Azure AI Search. |
| **Chroma default embeddings** | `all-MiniLM-L6-v2` on onnxruntime. Runs in-process, so the corpus never leaves the machine, and no second API key. Chosen over sentence-transformers specifically to avoid dragging torch in. | A larger embedding model inside the client's tenant, if retrieval quality is the constraint. Note: changing it means re-embedding the whole corpus. |
| **rank-bm25** | Keyword retrieval, fused with dense. Not optional here: measured on an earlier corpus (life insurance), a worked example on page 8 was never retrieved while prose on page 6 ranked first twice. Numeric tables embed badly; BM25 catches exact tokens. | A managed hybrid index (AI Search) or a reranker, which subsumes both. |
| **pypdf** | Page-level text extraction. Page number is the citation, so chunks are pages. | Same, plus OCR for scans. |
| **langgraph** | Orchestration. Explicit state object, deterministic edges, the model in exactly one node. Chosen because routing you can read beats routing you have to trust, and because it is named in the requirements. | Unchanged. That is the point: the graph is portable, the adapters under it are not. |
| **langgraph-checkpoint-sqlite** | Durable state after every node, keyed by thread id. Proven by killing the process mid-run and resuming: retrieval time came back from disk at the identical value rather than being recomputed. | The Postgres checkpointer. SQLite cannot be shared across instances and a container's disk is ephemeral, so this is the first thing that breaks on deploy. |
| **langsmith** | Tracing and eval. LangGraph emits automatically with three env vars and zero instrumentation code, which makes it the cheapest way to answer "how do you know it works." | Self-hosted Langfuse when trace data cannot leave the client's perimeter. Traces carry the full prompt, so they carry whatever was in the context. Same telemetry, different trust boundary. |
| **pydantic** | The interface contract. Validation raises instead of passing silently, and the same models are the HTTP schema. Agents build against it concurrently without guessing a name. | Unchanged. |
| **fastapi** | HTTP layer for the React front end. Request and response models come straight off the contract. | Unchanged. |
| **uvicorn** | ASGI server. | Behind a load balancer, multiple workers. |
| **httpx** | URL and API ingestion, alongside PDFs from disk, so all three corpus paths exist. | Unchanged, plus retries with backoff and a circuit breaker. |
| **python-dotenv** | Local secrets. | Railway variables, then a secrets manager. Never in the image. |
| **pytest** | Makes the gates real. A gate is a test you look at, not a claim that it worked. | Unchanged, in CI. |
| **React + Vite + TypeScript** | The front end, graded equally with the backend. No component library, no router, no Tailwind: two hours has no room and a plain table reads fine. | A design system, auth, role-scoped views. |

## Deliberately not installed

**sentence-transformers** — pulls torch, multiple gigabytes, for the same model Chroma already
runs on onnxruntime.

**Docker** — Railway builds the image remotely from the Dockerfile. A local daemon is only
needed to build and run it yourself.

**Doppler or any secrets manager** — Railway has environment variables built in. Learning a
new tool the day before is risk with no rubric point behind it.

**LangChain itself** — LangGraph is used directly. Nothing needs the chain abstractions.

## Environment

```
ANTHROPIC_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=<project name>
```

Verify tracing appears in the LangSmith UI after one graph node runs, before building
anything on top of it.
