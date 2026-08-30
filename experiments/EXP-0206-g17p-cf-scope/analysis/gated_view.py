#!/usr/bin/env python3
"""EXP-0206 -- build a GATED-ONLY view of raw/ for `tools/agx-isa/wave_audit.py`.

wave_audit globs `raw/**/*.jsonl` recursively and pools EVERY run it finds. This
experiment retains, by protocol, four non-gated captures -- the census, a pilot, a
36-case smoke test, and the 152-case run01 that was killed for throughput. Pooled
with the gated pair they corrupt exactly the two numbers wave_audit exists to
report:

  * V is inflated, because different CARRIERS have different oracles, so the same
    field shows several "distinct valid payloads" that are really several correct
    answers to several different programs;
  * cross-run agreement collapses to ~0%, because the audit pairs the two
    alphabetically-first run directories and those are a partial run and a pilot
    with disjoint arm sets.

This writes `work/gated_view/` containing ONLY the two gated runs and the verdicts,
so `wave_audit.py work/gated_view` reports the pair. Both outputs are kept in
RESULTS.md; neither is hidden.

Nothing under raw/ is modified: raw is append-only evidence.
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
GATED = ["g17p_20260830_run03", "g17p_20260830_run04"]


def main():
    dst = os.path.join(EXP, "work", "gated_view")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "raw"))
    os.makedirs(os.path.join(dst, "analysis"))
    for r in GATED:
        src = os.path.join(EXP, "raw", r)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, "raw", r))
    shutil.copy(os.path.join(HERE, "field_verdicts.json"),
                os.path.join(dst, "analysis", "field_verdicts.json"))
    # Per-ARM view too: wave_audit keys on (instr, field) and therefore pools all
    # carriers of a field. Splitting by arm is what makes V meaningful.
    per_arm = os.path.join(dst, "per_arm")
    os.makedirs(per_arm)
    seen = {}
    for r in GATED:
        f = os.path.join(EXP, "raw", r, "sweep.jsonl")
        if not os.path.exists(f):
            continue
        for ln in open(f):
            try:
                rec = json.loads(ln)
            except Exception:                                   # noqa: BLE001
                continue
            a = rec.get("arm")
            if not a or rec.get("role") != "target":
                continue
            k = a.replace("/", "_").replace(":", "_")
            d = os.path.join(per_arm, k, "raw", r)
            if (k, r) not in seen:
                os.makedirs(d, exist_ok=True)
                seen[(k, r)] = open(os.path.join(d, "sweep.jsonl"), "w")
            seen[(k, r)].write(ln)
    for fh in seen.values():
        fh.close()
    # give every per-arm view its own field_verdicts.json so wave_audit can be run
    # per ARM, which is the only keying under which V is meaningful for this
    # experiment (it pools carriers, and different carriers have different oracles)
    fv = json.load(open(os.path.join(HERE, "field_verdicts.json")))
    for k in {k for k, _ in seen}:
        one = {kk: vv for kk, vv in fv.items() if kk.startswith("_")}
        for kk, vv in fv.items():
            if kk.startswith("_"):
                continue
            one[kk] = vv
        with open(os.path.join(per_arm, k, "field_verdicts.json"), "w") as fh:
            json.dump(one, fh, indent=1)
        os.makedirs(os.path.join(per_arm, k, "analysis"), exist_ok=True)
        shutil.copy(os.path.join(per_arm, k, "field_verdicts.json"),
                    os.path.join(per_arm, k, "analysis", "field_verdicts.json"))
    print("wrote %s (%d arm views)" % (dst, len({k for k, _ in seen})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
