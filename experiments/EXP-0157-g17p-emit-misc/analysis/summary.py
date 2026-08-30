#!/usr/bin/env python3
"""EXP-0157: render the RESULTS.md verdict tables from the committed JSON, so
the numbers in the prose are generated, never typed."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOOD = {"hardware-run", "isolated-byte-diff"}
ORDER = ("sr_read_wide ray_move ray_move_copy6 ray_move_zero6 rtq_state_move n2_op6 "
         "n3_mov sfu_marker h_coord_hi h_coord_hi_ext scoreboard_fence op04_len8 "
         "mesh_out_src n2_op10 compute_fence_scoped ray_move_zinit rtq_dualsrc "
         "rtq_pred n2_op8 coord_madf").split()

em = json.load(open(HERE / "emittability.json"))
v = json.load(open(HERE / "field_verdicts_by_carrier.json"))
g = v.get("_gates", {})

print("### Captures actually on disk")
print()
print("| run | records | role |")
print("|---|---:|---|")
ROLE = {
 "g17p_run01": "gated capture 1 (arms R, S, H) — complete",
 "g17p_run02": "gated capture 2 — RETAINED PARTIAL, stopped, not reused",
 "g17p_run03": "targeted gated capture 2 for the carriers run02 never reached",
 "g17p_reval01": "fault/hang confirmation, ATTEMPT 1 -- never ran, the shared gpulease.sh was mid-rewrite (section 10.8)",
 "g17p_reval03": "fault/hang confirmation RETRY over all three gated captures, 5x per case, UNDER THE GPU LEASE",
 "g17p_raymove01": "arm B2 capture 1 (ray_move in the 25 kB carrier)",
 "g17p_raymove02": "arm B2 capture 2",
 "g17p_bbox01": "bounding-box carriers (single capture, reported not promoted)",
 "g17p_reach01": "reachability control",
 "g17p_fence01": "fence litmus, inert filler",
 "g17p_fence02": "fence litmus, zero filler",
 "g17p_lenmap01": "arms L/M/N — hardware length probe",
 "g17p_qlen01": "arm Q — length vs byte+1 x byte+2",
 "g17p_qlen02": "arm Q2 — length vs byte+2",
 "g17p_census01": "own-MSL compile census (no dispatches)",
}
RAW = HERE.parent / "raw"
for name, role in ROLE.items():
    d = RAW / name
    sw = d / "sweep.jsonl"
    n = sum(1 for _ in open(sw)) if sw.exists() else 0
    if not d.exists():
        print("| `%s` | — | **NOT PRESENT** — %s |" % (name, role))
    else:
        print("| `%s` | %d | %s |" % (name, n, role))
missing = [n for n in ("g17p_run03", "g17p_reval03") if not (RAW / n).exists()]
if missing:
    print()
    print("> ⚠ **%s not on disk at the time this table was generated.** Those captures were "
          "queued behind other agents on `~/agxre/gpulease.sh`. Any claim in this report "
          "that depends on them is marked as such; nothing was promoted on their assumed "
          "content." % ", ".join("`%s`" % m for m in missing))
print()
print("### Gate")
for name, rep in g.items():
    if not rep:
        continue
    print("* **%s** — %s: %d common cases, **%d agree**, %d disagree; %d of %d "
          "scanned anchors live." % (name, " + ".join(Path(p).name for p in rep["runs"]),
          rep["common_cases"], rep["agreeing"], rep["disagreeing"],
          rep["anchors_live"], rep["anchors_scanned"]))
print()
print("### Per-descriptor verdict")
print()
print("| descriptor | fields | status | operand fields an emitter can still not choose | blocking |")
print("|---|---:|---|---|---|")
for m in ORDER:
    r = em[m]
    st = ("**EMITTABLE**" if r["emittable"] else
          ("no fields in db.json" if not r["n_fields"] else "not yet"))
    print("| `%s` | %d | %s | %s | %s |" % (
        m, r["n_fields"], st, ", ".join("`%s`" % f for f in r["single_value_only"]) or "—",
        ", ".join("`%s`" % f for f in r["blocking"]) or "—"))
n_em = sum(1 for m in ORDER if em[m]["emittable"])
n_clean = sum(1 for m in ORDER if em[m]["operand_choice_available"])
nf = sum(1 for k, e in v.items() if k not in ("db_defects", "_gates")
         and e["label"] in GOOD)
merge = json.load(open(HERE / "field_verdicts.json"))
nm = sum(1 for k, e in merge.items() if k != "db_defects" and e["label"] in GOOD)
print()
print("**%d of 20 dispatched descriptors are EMITTABLE** under the DOC-02 rule "
      "(%d of them with full operand choice). %d per-carrier field entries reached emitter "
      "grade, which reduce to **%d merge-ready `<mnemonic>.<field>` entries** in "
      "`analysis/field_verdicts.json` (the form `work/merge_verdicts.py` accepts); the "
      "per-carrier detail stays in `analysis/field_verdicts_by_carrier.json`."
      % (n_em, n_clean, nf, nm))
