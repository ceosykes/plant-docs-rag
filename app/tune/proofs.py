"""Phase 7 proofs: distance metric, real overlap, refusal separability. Prints one line each.

Does: python -m app.tune.proofs -> runs/proofs.json and a report in runs/BUILD_LOG.md.
Does not: change any config value. Proofs only produce evidence.
"""
import json

from app import config
from app.ingest.index import Store
from app.tune.clock import append_report
from app.tune.norms import prove_metric
from app.tune.overlap import prove_overlap
from app.tune.refusal import prove_refusal, wait_for_golden


def evidence_lines(metric: dict, overlap: dict, refusal: dict) -> list[str]:
    """One line of evidence per proof, in the words the log will carry."""
    return [
        f"metric: norms {metric['norms']}, same order under cosine and l2 = {metric['same_order']}, "
        f"l2/cosine distance ratio {metric['l2_over_cosine']}; {metric['verdict']}",
        f"overlap: {overlap['pairs']} consecutive pairs on {overlap['pages']} pages share mean {overlap['mean_shared']} "
        f"min {overlap['min_shared']} chars against config {overlap['configured']} "
        f"({overlap['pairs_exactly_configured']} pairs exact); {overlap['diagnosis']}",
        f"refusal: max answerable dense {refusal['max_answerable_dense']}, min unanswerable dense "
        f"{refusal['min_unanswerable_dense']}, gap {refusal['gap']}; {refusal['verdict']}",
    ]


def main() -> None:
    """Run the three proofs in order and write runs/proofs.json."""
    store = Store()
    metric = prove_metric(store.collection)
    print("PROOF a:", metric["verdict"], metric["norms"], flush=True)
    overlap = prove_overlap()
    print("PROOF b:", overlap["mean_shared"], "mean shared vs", overlap["configured"], flush=True)
    golden = wait_for_golden()
    refusal = prove_refusal(store, golden)
    print("PROOF c:", refusal["verdict"], flush=True)
    lines = evidence_lines(metric, overlap, refusal)
    for line in lines:
        print(line)
    with open(config.RUNS_DIR / "proofs.json", "w") as f:
        json.dump({"metric": metric, "overlap": overlap, "refusal": refusal, "evidence": lines}, f, indent=1)
    append_report("proofs", {
        "CLOCK": "see heading",
        "DONE": " | ".join(lines),
        "NOW": "sweeps: top_k, dense_weight at stored chunking; chunk size and overlap on a subset",
        "DECIDED": "cosine stays; overlap finding reported not fixed; refusal mechanism per the gap above",
        "SAY": f"The store's vectors have norm {metric['norms'][0]} and consecutive chunks share {overlap['mean_shared']} "
               f"characters on average against a setting of {overlap['configured']}.",
        "IF BEHIND": "shrink the chunk size and overlap grids to two points each",
    })


if __name__ == "__main__":
    main()
