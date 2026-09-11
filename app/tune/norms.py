"""Proof a: are the stored vectors unit length, and does cosine rank the same as L2?

Does: read stored embeddings, measure norms, rebuild 200 chunks under cosine and l2 in memory.
Does not: touch the persistent collection. The temporary collections live in RAM only.
"""
import math

import chromadb


def vector_norms(collection, n: int = 5) -> list[float]:
    """L2 norm of the first n stored embeddings. 1.0 means unit length."""
    got = collection.get(limit=n, include=["embeddings"])
    if len(got["embeddings"]) == 0:
        raise ValueError("collection returned no embeddings; was the store built?")
    return [round(math.sqrt(sum(x * x for x in vec)), 6) for vec in got["embeddings"]]


def temp_collection(space: str, ids: list[str], docs: list[str], embeddings) -> object:
    """In-memory collection with the given hnsw space, loaded from stored embeddings."""
    client = chromadb.Client()
    name = f"proof_{space}"
    try:
        client.delete_collection(name)
    except Exception:
        pass
    col = client.create_collection(name, metadata={"hnsw:space": space})
    col.add(ids=ids, documents=docs, embeddings=embeddings)
    return col


def rank_under_both_spaces(collection, question: str, n_chunks: int = 200, k: int = 5) -> dict:
    """Same 200 chunks, same question, under cosine and under l2: order and distance ratio."""
    got = collection.get(limit=n_chunks, include=["embeddings", "documents"])
    cos = temp_collection("cosine", got["ids"], got["documents"], got["embeddings"])
    l2 = temp_collection("l2", got["ids"], got["documents"], got["embeddings"])
    r_cos = cos.query(query_texts=[question], n_results=k)
    r_l2 = l2.query(query_texts=[question], n_results=k)
    ids_cos, ids_l2 = r_cos["ids"][0], r_l2["ids"][0]
    d_cos, d_l2 = r_cos["distances"][0], r_l2["distances"][0]
    # for unit vectors squared L2 = 2 - 2 cos = 2 * cosine distance, so the ratio should be 2
    ratios = [round(b / a, 4) for a, b in zip(d_cos, d_l2) if a > 1e-9]
    return {"question": question, "chunks": len(got["ids"]), "same_order": ids_cos == ids_l2,
            "cosine_distances": [round(d, 5) for d in d_cos], "l2_distances": [round(d, 5) for d in d_l2],
            "l2_over_cosine": ratios}


def prove_metric(collection) -> dict:
    """Norms plus the two-space comparison, with a one-line verdict."""
    norms = vector_norms(collection)
    unit = all(abs(n - 1.0) < 1e-3 for n in norms)
    both = rank_under_both_spaces(collection, "how often should a belt drive be inspected")
    if unit:
        verdict = ("vectors are unit length so cosine, L2 and inner product rank identically; "
                   "cosine chosen because its 0..2 distance reads as a similarity")
    else:
        verdict = "NORMS ARE NOT 1.0: the spaces will NOT rank the same; cosine is a real choice here"
    return {"norms": norms, "unit_length": unit, "verdict": verdict, **both}
