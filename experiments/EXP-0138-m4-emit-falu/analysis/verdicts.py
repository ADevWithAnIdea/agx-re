#!/usr/bin/env python3
"""EXP-0138 analysis: two gated runs -> analysis/field_verdicts.json.

  analysis/verdicts.py raw/<run_a> raw/<run_b>

Applies the promotion rule frozen in PRE_REGISTRATION.md section 7. Nothing here
invents a label: a field reaches `hardware-run` only when its sweep is dense over
the claimed range, IDENTICAL in both independent runs, executed (integrity
sentinel intact) in every case that was not a structural re-length, and free of
unresolved victim cases.

Three reclassifications are applied to the raw outcomes, each declared here:

  * `undecodable` -- a case whose swept value changes the instruction's own
    LENGTH (`isadb.instr_length(bytes) != len(bytes)`). The program after it is
    a different program, so its sentinel failure is a STRUCTURAL observation
    about the field, not a broken measurement.
  * `sentinel_by_design` -- a `dst` sweep whose value names the sentinel
    register r11 or the store-index register r15. Destroying the readout is the
    predicted consequence of the field working.
  * `victim` cases are dropped from the evidence set entirely (they are
    evidence about the machine, not about the encoding).
"""
import json, math, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb                       # noqa: E402  (read-only)
import families as F               # noqa: E402

POISON_F = -6.259853398707798e+18
R_CTL, R_IDX = F.R_CTL, 15

DB = json.load(open(REPO / "tools" / "agx-isa" / "db.json"))
WIDTH = {i["mnemonic"]: {f["name"]: f["width"] for f in i.get("fields", [])}
         for i in DB["instructions"]}

# Fields whose value->behaviour map is complete and deterministic, but whose
# REGISTER mapping could only be exercised at fewer than three distinct live
# registers because the MODE-B carrier had that few live operands. An emitter
# cannot generalise from that, so these are capped at `isolated-byte-diff`
# no matter how clean the sweep is. Declared here rather than inferred.
CAP_ISOLATED = {
    ("fspecial", "src"), ("fspecial", "src_ext"), ("fspecial", "src_cache"),
    ("fspecial_est", "srcA"), ("falu2_uni", "usrc"), ("falu2_uni", "srcA_reg"),
}
REG_BOUNDARY = "0..15 dense + boundaries {16,24,31,32,40,48,63,64,66,67,95,96,112,120,125,126,127}"


def load(p):
    return [json.loads(l) for l in open(Path(p) / "sweep.jsonl")]


def obsval(r):
    o = r["observed"]
    return o.get("w0", o.get("o0"))


def eq(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b or abs(a - b) <= 1e-6 * max(1.0, abs(b))
    return a == b


def relengthed(r):
    b = bytes.fromhex(r["bytes"])
    try:
        L = isadb.instr_length(b)
    except Exception:
        return True
    return L != len(b)


def sentinel_by_design(r):
    if r["field"] not in ("dst", "dst_lo"):
        return False
    v = r["value"]
    w = WIDTH.get(r["instr"], {}).get(r["field"], 4)
    regs = {v} if w <= 4 else {(v >> 1) & 0x3F, v & 0x3F}
    return bool(regs & {R_CTL, R_IDX})


def reclass(r):
    o = r["outcome"]
    if o == "victim":
        return "victim"
    if o == "invalid_run":
        if relengthed(r):
            return "undecodable"
        if sentinel_by_design(r):
            return "sentinel_by_design"
    return o


def compress(vs):
    vs = sorted(vs)
    if len(vs) > 10:
        return "%d values (%d..%d)" % (len(vs), vs[0], vs[-1])
    return ",".join(str(v) for v in vs)


def main():
    ra, rb = load(sys.argv[1]), load(sys.argv[2])
    A = {r["i"]: r for r in ra}
    Bm = {r["i"]: r for r in rb}
    common = sorted(set(A) & set(Bm))
    fields = collections.defaultdict(list)
    for i in common:
        fields[(A[i]["instr"], A[i]["field"])].append((A[i], Bm[i]))

    verdicts, summary = {}, collections.Counter()
    per_instr = collections.defaultdict(dict)
    for (instr, field), pairs in sorted(fields.items()):
        if field.startswith("_"):
            continue
        for a, b in pairs:
            a["_o"] = reclass(a)
            b["_o"] = reclass(b)
        # victim cases carry no encoding information -- drop them entirely
        ev = [(a, b) for a, b in pairs if a["_o"] != "victim" and b["_o"] != "victim"]
        n_victim = len(pairs) - len(ev)
        if not ev:
            continue
        vals = sorted({a["value"] for a, _ in ev})
        w = WIDTH.get(instr, {}).get(field)
        determ = all(eq(obsval(a), obsval(b)) and a["_o"] == b["_o"] for a, b in ev)
        outc = collections.Counter(a["_o"] for a, _ in ev)
        bad_sent = [a for a, _ in ev if a["_o"] == "invalid_run"]
        preds = [a for a, _ in ev if a["expect_match"]]
        n_pred_fail = sum(1 for a in preds if not a["match"])
        ok_vals = {round(obsval(a), 9) for a, _ in ev
                   if a["status"] == "OK" and obsval(a) is not None
                   and not eq(obsval(a), POISON_F)}
        live = len(ok_vals) > 1
        n_live_nonzero = len({v for v in ok_vals if v != 0.0})

        # -------- coverage ------------------------------------------------
        tail = all(a["note"].startswith("tail byte") for a, _ in ev)
        if tail:
            nb = len({a["note"][:14] for a, _ in ev})
            dense = len(vals) >= 256 * nb
            rng = ("each of the %d constituent bytes swept 0..255 dense; the %s-bit "
                   "field's full space is NOT claimed" % (nb, w))
        elif field in ("srcA_reg", "srcB_reg", "usrc", "srcA_reg7", "srcB_reg7") \
                and w and w > 4:
            dense = len(vals) >= 30
            rng = REG_BOUNDARY
        elif w is not None and w <= 8:
            dense = len(vals) >= 2 ** w
            rng = ("0..%d dense (all %d values)" % (2 ** w - 1, 2 ** w) if dense
                   else "%d of %d encodable values" % (len(vals), 2 ** w))
        else:
            dense = False
            rng = "%d sampled values" % len(vals)

        # -------- label ---------------------------------------------------
        reasons = []
        if not determ:
            reasons.append("NOT deterministic across the two gated runs")
        if bad_sent:
            reasons.append("%d cases failed the integrity sentinel without a "
                           "structural explanation" % len(bad_sent))
        if not dense:
            reasons.append("sweep not dense over the encodable range")
        if n_pred_fail:
            reasons.append("%d/%d pre-registered predictions REFUTED; the label rests on "
                           "the observed value->behaviour map, which is complete and "
                           "reproduced in both runs" % (n_pred_fail, len(preds)))
        if n_victim:
            reasons.append("%d case(s) dropped as InnocentVictim (machine evidence)" % n_victim)

        if determ and not bad_sent and dense:
            label = "hardware-run"
        elif determ and not bad_sent and live:
            label = "isolated-byte-diff"
        else:
            label = "untested"
        if (instr, field) in CAP_ISOLATED and label == "hardware-run":
            label = "isolated-byte-diff"
            reasons.append("CAPPED: the carrier held too few live source registers to "
                           "establish a register->value RULE (only %d distinct non-zero "
                           "results), so an emitter may not generalise" % n_live_nonzero)
        summary[label] += 1

        m = collections.defaultdict(list)
        for a, _ in ev:
            m[(a["_o"], None if obsval(a) is None else round(obsval(a), 6))].append(a["value"])
        sem = "; ".join("%s@%s: %s" % (o, v, compress(vs))
                        for (o, v), vs in sorted(m.items(), key=lambda kv: -len(kv[1]))[:8])
        verdicts["%s.%s" % (instr, field)] = {
            "label": label, "range": rng, "target": "M4",
            "evidence": ["EXP-0138"], "semantics": sem,
            "note": "; ".join(reasons),
            "n_cases": len(ev), "outcomes": dict(outc), "deterministic": determ,
            "live": live, "distinct_results": len(ok_vals),
        }
        per_instr[instr][field] = label

    # -------- which instructions this makes emittable ---------------------
    val = json.load(open(REPO / "tools" / "agx-isa" / "validation.json"))
    EMIT = {"hardware-run", "isolated-byte-diff"}
    emittable, blocked = [], {}
    for i in DB["instructions"]:
        mn = i["mnemonic"]
        if mn not in per_instr:
            continue
        cur = val["instructions"].get(mn, {})
        rem = []
        for f in i.get("fields", []):
            lab = per_instr[mn].get(f["name"]) or cur.get(f["name"], {}).get("label", "untested")
            if lab not in EMIT:
                rem.append("%s(%s)" % (f["name"], lab))
        (emittable.append(mn) if not rem else blocked.setdefault(mn, rem))

    out = {"_meta": {"experiment": "EXP-0138",
                     "target": "Apple M4 (G16G), local host only",
                     "runs": [sys.argv[1], sys.argv[2]],
                     "n_field_sweeps": len(verdicts),
                     "label_counts": dict(summary),
                     "would_become_emittable": sorted(emittable),
                     "still_blocked": {k: v for k, v in sorted(blocked.items())}},
           **verdicts}
    (HERE / "field_verdicts.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["_meta"], indent=1))


if __name__ == "__main__":
    main()
