"""Build clock and log append, shared by proofs and sweeps.

Does: mm:ss since the build started, and an append-only write to runs/BUILD_LOG.md.
Does not: rewrite anything already in the log.
"""
from datetime import datetime

from app import config

# The 00:10 phase 2 entry landed at 16:57:53 on the laptop clock, so the build started here
BUILD_START = datetime(2026, 9, 11, 16, 47, 53)


def clock() -> str:
    """Minutes and seconds since the build started, for report headings."""
    elapsed = int((datetime.now() - BUILD_START).total_seconds())
    return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


def append_report(step: str, lines: dict[str, str]) -> None:
    """Six-line report appended verbatim to runs/BUILD_LOG.md under a mm:ss heading."""
    body = "\n".join(f"{key:<9} {value}" for key, value in lines.items())
    with open(config.RUNS_DIR / "BUILD_LOG.md", "a") as f:
        f.write(f"\n## {clock()}  tune agent: {step}\n\n{body}\n")
