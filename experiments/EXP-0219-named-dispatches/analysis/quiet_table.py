#!/usr/bin/env python3
"""EXP-0219 -- "the machine was quiet" as a MEASUREMENT, per capture.

Reads each capture's own procs.jsonl (harness/quietsample.py, byte-identical
copy of EXP-0213's) and gpu_pre/gpu_post snapshots.  recoveryCount is REPORTED,
NOT GATED (PRE_REGISTRATION section 6).
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
rows = []
for d in sorted((EXP / "raw").iterdir()):
    if not d.is_dir():
        continue
    e = {"run": d.name}
    p = d / "procs.jsonl"
    if p.exists():
        samples = []
        for ln in p.open():
            try:
                samples.append(json.loads(ln))
            except Exception:
                pass
        samples = [s for s in samples if isinstance(s, dict)]
        def mx(k):
            v = [s.get(k) for s in samples if isinstance(s.get(k), int)]
            return max(v) if v else None

        def gmx(k):
            v = [s["gpu"].get(k) for s in samples
                 if isinstance(s.get("gpu"), dict) and isinstance(s["gpu"].get(k), int)]
            return (min(v), max(v)) if v else (None, None)
        e.update(n_samples=len(samples),
                 max_foreign_runner=mx("n_foreign_runner"),
                 max_foreign_runner_strict=mx("n_foreign_runner_strict"),
                 max_compiler_svc=mx("n_compiler_svc"),
                 max_busy_count=gmx("busy_count")[1],
                 rc_min=gmx("recovery_count")[0], rc_max=gmx("recovery_count")[1],
                 submitters=sorted({s["gpu"].get("last_submission_pid")
                                    for s in samples
                                    if isinstance(s.get("gpu"), dict)
                                    and s["gpu"].get("last_submission_pid") is not None}))
    for tag in ("gpu_pre", "gpu_post"):
        f = d / (tag + ".json")
        if f.exists():
            try:
                j = json.loads(f.read_text().strip().splitlines()[-1])
                e[tag + "_recoveryCount"] = j.get("recovery_count", j.get("recoveryCount"))
            except Exception as ex:
                e[tag + "_error"] = str(ex)[:60]
    s = d / "02_summary.json"
    if s.exists():
        j = json.loads(s.read_text())
        e["records"] = j.get("cases", j.get("records"))
        e["counters"] = j.get("counters", j.get("counts"))
        e["elapsed_s"] = j.get("elapsed_s")
        for k in ("recoveryCount_pre", "recoveryCount_post", "hangs_total", "cascade"):
            if k in j:
                e[k] = j[k]
    rows.append(e)
print(json.dumps(rows, indent=1))
