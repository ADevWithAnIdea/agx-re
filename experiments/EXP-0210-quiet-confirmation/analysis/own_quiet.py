#!/usr/bin/env python3
"""EXP-0210 -- summarise a SOURCE EXPERIMENT's OWN concurrency measurement for a run.

    python3 analysis/own_quiet.py <run_dir> [<run_dir> ...]

Each of the seven experiments shipped its own busy-machine instrument
(`gpuwatch.jsonl`, `concurrency.jsonl`, `procs.jsonl`, or `env.json`'s
`concurrent_gpu_procs`).  Reading it back for the NEW quiet runs gives a second, independent
statement about quiet, taken by the same instrument that recorded "never quiet" during the
fan-out -- so the before/after comparison is like-for-like and not an artefact of my own
sampler's definitions.
"""
import json
import os
import sys


def summarise(d):
    out = {"run": os.path.basename(d.rstrip("/"))}
    for name in ("gpuwatch.jsonl", "concurrency.jsonl", "procs.jsonl",
                 "03_procsample.jsonl"):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            continue
        recs = []
        for ln in open(p, errors="replace"):
            ln = ln.strip()
            if ln:
                try:
                    recs.append(json.loads(ln))
                except ValueError:
                    pass
        if not recs:
            continue
        counts = []
        for r in recs:
            for k in ("n_foreign", "n", "foreign", "n_procs", "count"):
                if isinstance(r.get(k), int):
                    counts.append(r[k])
                    break
            else:
                for k in ("procs", "rows", "processes"):
                    if isinstance(r.get(k), list):
                        counts.append(len([x for x in r[k]
                                           if not (isinstance(x, dict)
                                                   and x.get("ours"))]))
                        break
        out[name] = {"samples": len(recs),
                     "max": max(counts) if counts else None,
                     "zero_samples": sum(1 for c in counts if c == 0),
                     "nonzero_samples": sum(1 for c in counts if c > 0)}
    p = os.path.join(d, "env.json")
    if os.path.exists(p):
        try:
            e = json.load(open(p))
            if "concurrent_gpu_procs" in e:
                v = e["concurrent_gpu_procs"]
                out["env.json:concurrent_gpu_procs"] = (
                    "EMPTY (no foreign GPU process at run start)" if not str(v).strip()
                    else str(v)[:300])
            if "utc" in e:
                out["env.json:utc"] = e["utc"]
        except Exception:                                          # noqa: BLE001
            pass
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(json.dumps(summarise(d), indent=1, sort_keys=True))
