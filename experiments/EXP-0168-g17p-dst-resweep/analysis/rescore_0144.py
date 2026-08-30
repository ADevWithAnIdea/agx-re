#!/usr/bin/env python3
"""EXP-0168 offline re-scoring of EXP-0164's UNSTABLE verdict on EXP-0144's
pack/unpack/convert fields.

NO HARDWARE. Every number below is recomputed from the append-only `raw/` trees
of `experiments/EXP-0144-m4-emit-pack/`, which ran on the **Apple M4 / G16G**.
Nothing here is a G17P claim, and nothing here is promoted by this script -- it
produces a measurement and a recommendation for the orchestrator.

THE CLAIM UNDER TEST
--------------------
`EXP-0164/analysis/withhold_unstable.json` withheld

    pack_convert.b7        "256 values, 2 carrier(s), 273 moved, but the movement
                            does not reproduce across the two gated runs"
    unpack_convert.dst     "256 values, 2 carrier(s), 210 moved, ... "
    cvt_f2h.op             "256 values, 1 carrier, 320 moved, ..."
    cvt_f2i.dst            "256 values, 1 carrier, 176 moved, ..."

Two things about that are checkable offline.

1. **Which two runs were compared.** `EXP-0164/analysis/audit.py:78-80` picks the
   two gated runs with the most distinct attributed values, **ties broken
   alphabetically**. `m4_20260828_run03` < `m4_20260828_run05` <
   `m4_20260828_rv01__*`, so for the pack/unpack fields the comparison used
   `run03` -- a capture `EXP-0144/RESULTS.md:28-33` explicitly disowns ("the
   earlier captures run01-run05 are retained as append-only history and **back no
   label**"); everything EXP-0144 promoted comes from the `rv01__*` revalidation.

2. **Whether run03's records are measurements at all.** After two hangs in an
   area, `EXP-0144/harness/run.py` wrote SKIP PLACEHOLDERS carrying
   `outcome:"hang"`. `EXP-0164/analysis/collect_raw.py:42` treats only
   `{invalid_run, victim, skipped}` as contamination, so those placeholders were
   scored as observations.

This script recomputes the cross-run agreement for each field over EVERY pair of
runs that actually dispatched the value, and separately reports how many of each
run's records are placeholders. If the fields agree once the placeholders are
excluded, the UNSTABLE verdict is an artifact of the analysis, not a property of
the hardware -- and that is a different repair from the one the audit prescribed
(it needs a re-scoring, not a third gated run).

CLEAN-ROOM: derived analysis of our own committed raw observations. No Apple
binary is introspected; no device is touched.

Usage:
    python3 analysis/rescore_0144.py [--repo /path/to/agx-re] [--json OUT]
"""
from __future__ import print_function

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

# (field key, EXP-0144 carrier, instruction, byte index inside the instruction)
TARGETS = [
    ("pack_convert.b7",     "c_pack",   "pack_convert",   7),
    ("unpack_convert.dst",  "c_unpack", "unpack_convert", 3),
    ("cvt_f2h.op",          "c_f2h",    "cvt_f2h",        2),
    ("cvt_f2i.dst",         "c_f2i",    "cvt_f2i",        3),
    ("cvt_f2i.b9",          "c_f2i",    "cvt_f2i",        9),
]

# EXP-0164's own contamination set, quoted so the difference is explicit.
AUDIT_CONTAM = {"invalid_run", "victim", "skipped"}
# What this script additionally refuses to score: a record with no attempt at
# all is a placeholder, whatever its `outcome` string says.
PLACEHOLDER_OUTCOMES = {"skipped", "not_run", "skipped_after_hangs",
                        "skipped_after_cascade"}


def is_placeholder(rec):
    """True iff the record documents a case that was never dispatched.

    EXP-0144 wrote skip placeholders with `outcome:"hang"` and no attempts, so
    `outcome` alone cannot separate them from a real hang. The discriminator is
    that a real dispatch always leaves at least one attempt and an `observed`
    string; a placeholder leaves neither.
    """
    if rec.get("validity") in ("skipped", "skipped_after_hangs",
                               "skipped_after_cascade", "not_run"):
        return True
    if rec.get("outcome") in PLACEHOLDER_OUTCOMES:
        return True
    att = rec.get("attempts")
    if not att:
        return True
    if isinstance(att, list) and len(att) == 0:
        return True
    return False


def value_of(rec, byte_index):
    """The swept byte's value, taken from the RECORDED INSTRUCTION BYTES rather
    than from the `value` column.

    This matters: EXP-0144's `field` label strings have since moved in
    `tools/agx-isa/db.json` (byte 7 of pack_convert was `fmt_word`, is now `b7`;
    byte 3 of unpack_convert was `convert_desc`, is now `dst`), so a re-run's
    labels no longer join against the committed raw. Bytes are stable; labels
    are not. EXP-0168's own sweep records bytes for the same reason.
    """
    h = rec.get("bytes")
    if not h:
        return None
    try:
        b = bytes.fromhex(h)
    except Exception:
        return None
    if len(b) <= byte_index:
        return None
    return b[byte_index]


def anchor_byte(recs, byte_index):
    """The most common value of the swept byte across baseline/control records."""
    c = Counter()
    for r in recs:
        if r.get("arm") == "C" and r.get("name", "").startswith("baseline"):
            v = value_of(r, byte_index)
            if v is not None:
                c[v] += 1
    return c.most_common(1)[0][0] if c else None


def load_run(rundir):
    out = []
    p = rundir / "sweep.jsonl"
    if not p.exists():
        return out
    with p.open() as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def collect(exp144, carrier, instr, byte_index):
    """run_id -> {value: (outcome, observed)} for real dispatches, plus counts."""
    per_run = {}
    stats = {}
    for rundir in sorted((exp144 / "raw").iterdir()):
        if not rundir.is_dir():
            continue
        recs = load_run(rundir)
        if not recs:
            continue
        mine = [r for r in recs
                if r.get("carrier") == carrier and r.get("instr") == instr]
        if not mine:
            continue
        anch = anchor_byte(mine, byte_index)
        vals = {}
        n_ph = 0
        n_contam = 0
        n_other_byte = 0
        for r in mine:
            # Only records that sweep THIS byte: every other byte of the
            # instruction must equal the anchor's.
            v = value_of(r, byte_index)
            if v is None:
                continue
            if r.get("arm") not in ("F", "W", "C"):
                continue
            if r.get("arm") == "C":
                continue          # controls/falsifiers are not sweep values
            hb = bytes.fromhex(r["bytes"])
            ab = None
            for rr in mine:
                if rr.get("arm") == "C" and rr.get("name", "").startswith("baseline"):
                    ab = bytes.fromhex(rr["bytes"])
                    break
            if ab is not None and len(ab) == len(hb):
                differing = [i for i in range(len(hb)) if hb[i] != ab[i]]
                if differing and differing != [byte_index]:
                    n_other_byte += 1
                    continue
            if is_placeholder(r):
                n_ph += 1
                continue
            if r.get("validity") not in (None, "valid"):
                n_contam += 1
                continue
            vals[v] = (r.get("outcome"), r.get("observed"))
        if vals or n_ph:
            per_run[rundir.name] = vals
            stats[rundir.name] = {
                "measured": len(vals), "placeholders": n_ph,
                "contaminated": n_contam, "other_byte_records": n_other_byte,
                "anchor_byte": anch,
                "outcomes": dict(Counter(o for o, _ in vals.values())),
            }
    return per_run, stats


def agreement(a, b):
    common = sorted(set(a) & set(b))
    if not common:
        return None
    dis = [v for v in common if a[v][0] != b[v][0]]
    return {
        "common": len(common),
        "disagreements": len(dis),
        "agree_pct": round(100.0 * (len(common) - len(dis)) / len(common), 2),
        "disagreeing_values": dis[:40],
        "disagreement_classes": dict(Counter(
            "%s->%s" % (a[v][0], b[v][0]) for v in dis)),
    }


def moved(vals, anchor_outcome_value):
    """How many swept values changed the observation away from the anchor's."""
    if anchor_outcome_value is None or anchor_outcome_value not in vals:
        return None
    base = vals[anchor_outcome_value][1]
    return sum(1 for v, (o, ob) in vals.items()
               if v != anchor_outcome_value and ob != base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    repo = Path(a.repo) if a.repo else here.parents[2]
    exp144 = repo / "experiments" / "EXP-0144-m4-emit-pack"
    if not exp144.exists():
        raise SystemExit("cannot find %s" % exp144)

    report = {
        "_meta": {
            "experiment": "EXP-0168-g17p-dst-resweep",
            "what": "offline re-scoring of EXP-0164's UNSTABLE verdict on "
                    "EXP-0144's pack/unpack/convert fields",
            "target_of_the_underlying_data": "M4 / G16G (EXP-0144 ran there)",
            "device_used_by_this_script": "NONE",
            "audit_gate": {"min_agree_pct": 99.0, "moved_over_disagree": 2.0,
                           "source": "EXP-0164/analysis/audit.py:25-27"},
            "audit_run_selection":
                "two gated runs with the most distinct attributed values, ties "
                "broken ALPHABETICALLY (EXP-0164/analysis/audit.py:78-80)",
        },
        "fields": {},
    }

    for key, carrier, instr, bidx in TARGETS:
        per_run, stats = collect(exp144, carrier, instr, bidx)
        anch = None
        for s in stats.values():
            if s["anchor_byte"] is not None:
                anch = s["anchor_byte"]
                break
        pairs = {}
        runs = sorted(per_run)
        for i in range(len(runs)):
            for j in range(i + 1, len(runs)):
                ag = agreement(per_run[runs[i]], per_run[runs[j]])
                if ag:
                    ag["moved_%s" % runs[i]] = moved(per_run[runs[i]], anch)
                    ag["moved_%s" % runs[j]] = moved(per_run[runs[j]], anch)
                    pairs["%s|%s" % (runs[i], runs[j])] = ag

        # the pair the audit would have picked, and the best measured pair
        best = None
        for name, ag in pairs.items():
            if ag["common"] < 32:
                continue
            if best is None or (ag["agree_pct"], ag["common"]) > \
                    (pairs[best]["agree_pct"], pairs[best]["common"]):
                best = name

        report["fields"][key] = {
            "instr": instr, "carrier": carrier, "byte_index": bidx,
            "anchor_byte": anch,
            "per_run": stats,
            "pairs": pairs,
            "best_measured_pair": best,
            "best_pair_result": pairs.get(best),
        }

        print("=" * 74)
        print("%s   (%s byte+%d, carrier %s, anchor 0x%02x)"
              % (key, instr, bidx, carrier,
                 anch if anch is not None else 0))
        for r in runs:
            s = stats[r]
            print("   %-34s measured=%-4d placeholders=%-4d contam=%-3d %s"
                  % (r, s["measured"], s["placeholders"], s["contaminated"],
                     json.dumps(s["outcomes"], sort_keys=True)))
        for name, ag in sorted(pairs.items()):
            print("   pair %-58s common=%-4d agree=%6.2f%% dis=%d %s"
                  % (name, ag["common"], ag["agree_pct"], ag["disagreements"],
                     json.dumps(ag["disagreement_classes"], sort_keys=True)
                     if ag["disagreements"] else ""))
        if best:
            ag = pairs[best]
            verdict = ("MEETS the >=99%% gate on the measured pair"
                       if ag["agree_pct"] >= 99.0 else
                       "STILL BELOW the >=99%% gate on its best measured pair")
            print("   -> best measured pair %s: %.2f%%  ==> %s"
                  % (best, ag["agree_pct"], verdict))

    outp = Path(a.json) if a.json else (here / "rescore_0144.json")
    outp.write_text(json.dumps(report, indent=1, sort_keys=True))
    print("\nwrote", outp)
    print("\nNOTE: this script settles ONLY whether EXP-0164's cross-run gate was "
          "computed over runs that actually dispatched the value. It does NOT "
          "promote anything: the underlying observations are M4/G16G, and "
          "EXP-0168's own G17P sweep is what carries a target-correct label.")


if __name__ == "__main__":
    main()
