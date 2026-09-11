"""Rewrite the GUESS comments in app/config.py with the sweep evidence. The one edit outside app/tune.

Does: replace exactly the lines that begin with the six names; everything else stays byte-identical.
Does not: change a value unless the caller passes a new one.
"""
from app import config

SHAPE = "{name} = {value}   # {evidence}"


def rewrite_config(new_lines: dict[str, tuple[str, str]]) -> list[str]:
    """new_lines maps NAME -> (value literal, evidence). Returns the lines written."""
    path = config.ROOT / "app" / "config.py"
    with open(path) as f:
        lines = f.read().split("\n")
    written, seen = [], set()
    for n, line in enumerate(lines):
        name = line.split("=")[0].strip() if "=" in line else ""
        if name in new_lines and not line.startswith(" "):
            value, evidence = new_lines[name]
            lines[n] = SHAPE.format(name=name, value=value, evidence=evidence)
            written.append(lines[n])
            seen.add(name)
    missing = set(new_lines) - seen
    if missing:
        raise ValueError(f"config.py has no line for {sorted(missing)}; nothing written")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return written
