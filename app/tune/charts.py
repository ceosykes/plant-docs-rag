"""One PNG and one CSV per sweep, in charts/.

Does: a line chart of hit rate against the setting, and the raw rows beside it.
Does not: pick the winner. That is app/tune/sweeps.py.
"""
import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app import config


def write_csv(name: str, rows: list[dict]) -> str:
    """Raw rows for the chart, one file per sweep."""
    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CHARTS_DIR / f"{name}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return str(path.relative_to(config.ROOT))


def plot_sweep(name: str, rows: list[dict], x_key: str, title: str, chosen=None) -> str:
    """Page and doc hit rate against the setting; the chosen point gets a marker."""
    xs = [r[x_key] for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(xs, [r["page_hit_rate"] for r in rows], marker="o", color="#1f5f8b", label="page hit rate")
    ax.plot(xs, [r["doc_hit_rate"] for r in rows], marker="s", color="#8a8a8a", label="doc hit rate")
    if chosen is not None:
        ax.axvline(chosen, color="#c85a2a", linestyle="--", linewidth=1, label=f"chosen {chosen}")
    # label each page-level point with its value so the chart reads without the csv
    for r in rows:
        ax.annotate(f"{r['page_hit_rate']:.2f}", (r[x_key], r["page_hit_rate"]), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)
    ax.set_xlabel(x_key)
    ax.set_ylabel("hit rate")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(xs)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()
    path = config.CHARTS_DIR / f"{name}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return str(path.relative_to(config.ROOT))
