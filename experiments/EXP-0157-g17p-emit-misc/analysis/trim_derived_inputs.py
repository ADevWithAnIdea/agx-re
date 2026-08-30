#!/usr/bin/env python3
"""EXP-0157: replace oversized `00_cases.json` files with CODEX section 6 manifests.

`00_cases.json` is a DERIVED INPUT -- `harness/cases.py` regenerates it exactly
from the carriers and the resolved anchors, and every case's spliced bytes are
also recorded in that run's own `sweep.jsonl`. Some of them are 20-30 MB. This
replaces any over 2 MB with a manifest carrying its size, sha256, generation
command, retention location on the test target, its resolved anchors, and a
first-record excerpt.

`sweep.jsonl` -- the actual observations -- is never touched. Run this after
`work/pull.sh`.
"""
import hashlib
import json
from pathlib import Path

LIMIT = 2 * 1024 * 1024


def main():
    root = Path(__file__).resolve().parent.parent / "raw"
    for p in sorted(root.rglob("00_cases.json")):
        n = p.stat().st_size
        if n <= LIMIT:
            continue
        b = p.read_bytes()
        cases = json.loads(b)
        man = {"_doc": __doc__.strip(), "origin": str(p), "size_bytes": n,
               "sha256": hashlib.sha256(b).hexdigest(),
               "retention_location": "users-MacBook-Neo.local:~/agxre/EXP-0157/" + str(p),
               "generation_command": "python3 -B harness/run.py --run-id <id> ...",
               "n_groups_or_cases": len(cases) if isinstance(cases, list) else None}
        if isinstance(cases, list) and cases and isinstance(cases[0], dict) \
                and "anchor" in cases[0]:
            man["resolved_anchors"] = [
                {k: g[k] for k in ("arm", "carrier", "instr", "anchor_idx", "anchor")}
                for g in cases]
        elif isinstance(cases, list) and cases:
            man["excerpt_first_record"] = {
                k: (v[:120] if isinstance(v, str) else v) for k, v in cases[0].items()}
        p.with_name("00_cases_MANIFEST.json").write_text(
            json.dumps(man, indent=1, sort_keys=True) + "\n")
        p.unlink()
        print("trimmed %-44s %6.1f MB" % (str(p), n / 1048576))


if __name__ == "__main__":
    main()
