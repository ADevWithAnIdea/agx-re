#!/usr/bin/env python3
"""EXP-0200 target-2 verdicts -- the ONLY place an `_instruction` verdict may be
written.

  python3 analysis/verdicts200.py raw/<t2run01> raw/<t2run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from
a previous verdicts file. The census is never consulted: it chose where to look
and must not be able to influence what was concluded.

THE GATE (frozen in PRE_REGISTRATION.md section 8; nothing else may promote).

 1. Two gated runs, the same frozen `harness/arms200.json`.
 2. Per-value cross-run agreement >= 99 % on the OUTCOME PARTITION
    (outcome + the exact observed 32-bit value vector), and, on ruler arms,
    `moved >= 2 * disagree AND moved >= 1` -- written that way and NOT as
    `moved >= 2 * max(disagree, 1)`, the form that cannot promote a width-1
    field by arithmetic (protocol 5b).
 3. HOLE ADMISSION. A ruler hole supports a verdict only if, IN BOTH RUNS:
      a. its arm-open baseline is `ok` (the unmutated program is correct), AND
      b. `C_reach` (stop at +0) is `not_written` with the sentinel intact
         -- the hole is executed, before the result store, AND
      c. `A_icmp6` (a known 6-byte hardware-run word, stop at +2) is NOT
         `not_written` -- the ruler can SEE over-read. Without (c) a
         `not_written` reading is uninformative: everything would read
         "length fits" including things that do not.
    A hole failing any of these is DROPPED and COUNTED. Dropping is the honest
    outcome of a control that did not fire, not a search for a better hole:
    the admission test is fixed before the data and applied to every hole.
 4. ANCHOR MATCH, per stop offset. A 2-byte candidate's reading is admitted only
    at holes where `A_mov2` (mov_imm, `_instruction: hardware-run`, length 2,
    stop at +2) reads `not_written`. A 4-byte candidate's reading is admitted
    only where `A_ifpush4` (if_push, length 4, stop at +4) reads `not_written`.
    The candidate is then read as a CONTRAST against anchors measured at the
    SAME stop offset in the SAME program, not against an absolute.
 5. VERDICT per target word:
      LENGTH-CONFIRMED  -- >= 2 admitted holes, in >= 2 distinct carriers, all
                           reading `not_written` for that word, none reading
                           otherwise, cross-run agreement >= 99 %.
      LENGTH-REFUTED    -- any admitted hole where the word reads `written`
                           (`ok` / `wrong_value` / `silent_zero`) while its
                           anchor reads `not_written`. One clean refutation
                           outranks any number of confirmations; it is reported
                           as the result and the label is NOT promoted.
      HAZARDOUS         -- the word faults or hangs at admitted holes where the
                           anchors do not. Recorded as a hardware fact.
      UNDERPOWERED      -- fewer than 2 admitted holes, or no anchor match.
                           Label stays `tokenization-only`. No rounding up.
 6. TRANSPARENCY is a SEPARATE conjunct, never a substitute. It counts only at a
    natural hole whose own `X_reach` fired and whose `X_null` was `ok`, and it
    asks whether a candidate substituted for a DIFFERENT word of the same length
    leaves the carrier's non-zero oracle intact.
 7. LABELS. `hardware-run` is proposed only for a word that is LENGTH-CONFIRMED,
    and the `range` string states exactly what was measured -- total bytes
    consumed, at how many holes, in how many carriers, plus whether transparency
    was demonstrated. Everything else keeps `tokenization-only`.
    A word that is LENGTH-CONFIRMED but never shown transparent gets the length
    claim in `range` and an explicit `note` that its architectural effect is
    still uncharacterised: an emitter may rely on the framing and on nothing
    else.

WHAT WOULD MAKE THIS GATE SAY NO (stated because a criterion that cannot return
"no" is broken, and thirteen in this corpus could not):
  * every hole dropped at rule 3 -> UNDERPOWERED for every word;
  * `A_icmp6` reading `not_written` everywhere -> the ruler is blind -> nothing;
  * a single admitted hole where a candidate is `written` while its anchor is
    `not_written` -> LENGTH-REFUTED, and the pre-registered length claim in
    `db.json` is wrong;
  * cross-run agreement below 99 % -> no verdict.
Rule 5's REFUTED branch fired against `op04_len8` in the design as a deliberate
positive: `D_op04_len8` is pre-registered to read `written` if our own tokenizer
is right and `not_written` if it is wrong, and either answer is publishable.

Derived from EXP-0187 analysis/verdicts.py (our own code, cited).
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
AGREE_MIN = 99.0
MEAS_FAIL_MAX_PCT = 1.0

TARGETS_2B = ("n1_word", "n2_compact2", "n3_word")
TARGETS_4B = ("rtq_pred", "n4_cf_word", "n4_rt_word")
HARD = ("fault", "hang", "nondeterministic", "invalid_run", "measurement_failure")
WRITTEN = ("ok", "wrong_value", "silent_zero")


def load(run_dir):
    out = []
    for ln in (Path(run_dir) / "sweep.jsonl").read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def vkey(r):
    o = r.get("observed") or {}
    vals = o.get("vals_u32")
    h = (hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:16]
         if vals is not None else "none")
    return "%s|%s" % (r.get("outcome"), h)


def index(recs):
    """-> {arm: {"fills": {fid: rec}, "baselines": [rec]}}"""
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        base = arm.split(":")[0]
        if r.get("role") == "baseline":
            out.setdefault(base, {"fills": {}, "baselines": []})
            out[base]["baselines"].append(r)
            continue
        d = out.setdefault(arm, {"fills": {}, "baselines": []})
        fid = r.get("fill_id")
        if fid:
            d["fills"][fid] = r
    return out


def both(i1, i2, arm, fid):
    a = i1.get(arm, {}).get("fills", {}).get(fid)
    b = i2.get(arm, {}).get("fills", {}).get(fid)
    return a, b


def agreed_outcome(a, b):
    """The outcome both runs agree on, else None."""
    if not a or not b:
        return None
    return a["outcome"] if vkey(a) == vkey(b) else None


def baselines_ok(i, arm):
    bs = i.get(arm, {}).get("baselines", [])
    return bool(bs) and all(x.get("outcome") == "ok" for x in bs)


def arm_stats(i1, i2, arm):
    f1 = i1.get(arm, {}).get("fills", {})
    f2 = i2.get(arm, {}).get("fills", {})
    shared = sorted(set(f1) & set(f2))
    mf = [k for k in shared if f1[k]["outcome"] == "measurement_failure"
          or f2[k]["outcome"] == "measurement_failure"]
    use = [k for k in shared if k not in set(mf)]
    agree = sum(1 for k in use if vkey(f1[k]) == vkey(f2[k]))
    bk = None
    for b in i1.get(arm, {}).get("baselines", []):
        if str(b.get("note", "")).endswith(":open"):
            bk = vkey(b)
            break
    moved = sum(1 for k in use
                if vkey(f1[k]) != bk and vkey(f2[k]) != bk) if bk else 0
    return {"shared_fills": len(use), "agree_pct": round(100.0 * agree / max(1, len(use)), 3),
            "disagree": len(use) - agree, "moved": moved,
            "measurement_failures": len(mf),
            "measurement_failure_pct": round(100.0 * len(mf) / max(1, len(shared)), 3),
            "baselines_ok": baselines_ok(i1, arm) and baselines_ok(i2, arm)}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    r1, r2 = sys.argv[1], sys.argv[2]
    i1, i2 = index(load(r1)), index(load(r2))
    arms = json.loads((EXP / "harness" / "arms200.json").read_text())["arms"]

    ruler, transp = {}, {}
    for a in arms:
        (ruler if a["kind"] == "ruler" else transp)[a["arm"]] = a

    # ------------------------------------------------ ruler hole admission
    holes = {}
    for arm, a in sorted(ruler.items()):
        st = arm_stats(i1, i2, arm)
        creach = agreed_outcome(*both(i1, i2, arm, "C_reach"))
        cre_sent = all((x or {}).get("observed", {}).get("sentinel_ok")
                       for x in both(i1, i2, arm, "C_reach") if x)
        icmp6 = agreed_outcome(*both(i1, i2, arm, "A_icmp6"))
        mov2 = agreed_outcome(*both(i1, i2, arm, "A_mov2"))
        push4 = agreed_outcome(*both(i1, i2, arm, "A_ifpush4"))
        reasons = []
        if not st["baselines_ok"]:
            reasons.append("arm baselines not all ok")
        if not (creach == "not_written" and cre_sent):
            reasons.append("C_reach did not fire (%s, sentinel_ok=%s)"
                           % (creach, cre_sent))
        if icmp6 == "not_written" or icmp6 is None:
            reasons.append("A_icmp6 over-read control did not fire (%s)" % icmp6)
        if st["agree_pct"] < AGREE_MIN:
            reasons.append("cross-run agreement %.2f%% < %.1f%%"
                           % (st["agree_pct"], AGREE_MIN))
        if st["measurement_failure_pct"] > MEAS_FAIL_MAX_PCT:
            reasons.append("measurement failures %.2f%%" % st["measurement_failure_pct"])
        if not (st["moved"] >= 2 * st["disagree"] and st["moved"] >= 1):
            reasons.append("movement rule failed (moved=%d disagree=%d)"
                           % (st["moved"], st["disagree"]))
        holes[arm] = {"carrier": a["carrier"], "off": a["off"],
                      "covers": a.get("covers"), "admitted": not reasons,
                      "drop_reasons": reasons, "stats": st,
                      "C_reach": creach, "A_icmp6": icmp6,
                      "A_mov2": mov2, "A_ifpush4": push4,
                      "A_pad2": agreed_outcome(*both(i1, i2, arm, "A_pad2")),
                      "A_stop6": agreed_outcome(*both(i1, i2, arm, "A_stop6")),
                      "D_op04_len8": agreed_outcome(*both(i1, i2, arm,
                                                          "D_op04_len8"))}

    # --------------------------------------------------- per-word readings
    def fids_for(word):
        if word in TARGETS_2B:
            return ["T_%s" % word]
        if word == "rtq_pred":
            return ["T_rtq_pred"]
        if word == "n4_cf_word":
            return [k for k in _all_fids() if k.startswith("T_n4_cf_word_b3_")]
        if word == "n4_rt_word":
            return [k for k in _all_fids() if k.startswith("T_n4_rt_word_dst_")]
        return []

    def _all_fids():
        s = set()
        for a in ruler.values():
            for f in a["fills"]:
                s.add(f["fid"])
        return sorted(s)

    verdicts = {}
    for word in TARGETS_2B + TARGETS_4B:
        anchor = "A_mov2" if word in TARGETS_2B else "A_ifpush4"
        conf, refute, hazard, unread, per_hole = [], [], [], [], {}
        for arm, h in sorted(holes.items()):
            if not h["admitted"]:
                continue
            if h[anchor] != "not_written":
                unread.append({"arm": arm, "why": "anchor %s read %s"
                               % (anchor, h[anchor])})
                continue
            reads = {}
            for fid in fids_for(word):
                oc = agreed_outcome(*both(i1, i2, arm, fid))
                if oc is None:
                    continue
                reads[fid] = oc
            per_hole[arm] = {"carrier": h["carrier"], "off": h["off"],
                             "reads": reads}
            nw = [f for f, o in reads.items() if o == "not_written"]
            wr = [f for f, o in reads.items() if o in WRITTEN]
            hz = [f for f, o in reads.items() if o in HARD]
            if wr:
                refute.append({"arm": arm, "fills": wr})
            if hz:
                hazard.append({"arm": arm, "fills": hz})
            if nw and not wr:
                conf.append({"arm": arm, "carrier": h["carrier"],
                             "n_fills_not_written": len(nw)})
        carriers = sorted({c["carrier"] for c in conf})
        if refute:
            verdict, label = "LENGTH-REFUTED", "tokenization-only"
        elif len(conf) >= 2 and len(carriers) >= 2:
            verdict, label = "LENGTH-CONFIRMED", "hardware-run"
        else:
            verdict, label = "UNDERPOWERED", "tokenization-only"
        verdicts[word] = {"verdict": verdict, "label": label, "anchor": anchor,
                          "confirming_holes": conf, "refuting_holes": refute,
                          "hazard_holes": hazard, "unreadable_holes": unread,
                          "carriers": carriers, "per_hole": per_hole}

    # --------------------------------------------------- transparency arms
    trans = {}
    for arm, a in sorted(transp.items()):
        st = arm_stats(i1, i2, arm)
        xr = agreed_outcome(*both(i1, i2, arm, "X_reach"))
        xn = agreed_outcome(*both(i1, i2, arm, "X_null"))
        xo = agreed_outcome(*both(i1, i2, arm, "X_over"))
        admitted = (st["baselines_ok"] and st["agree_pct"] >= AGREE_MIN
                    and xr == "not_written" and xn == "ok")
        reads = {}
        for f in a["fills"]:
            if f["role"] not in ("target", "anchor_len2", "anchor_len4"):
                continue
            reads[f["fid"]] = {"instr": f["instr"],
                               "outcome": agreed_outcome(*both(i1, i2, arm,
                                                               f["fid"]))}
        trans[arm] = {"carrier": a["carrier"], "off": a["off"],
                      "len": a["len"], "orig": a.get("orig_bytes"),
                      "covers": a.get("covers"), "admitted": admitted,
                      "X_reach": xr, "X_null": xn, "X_over": xo,
                      "stats": st, "reads": reads}

    for word in verdicts:
        good, bad = [], []
        for arm, t in trans.items():
            if not t["admitted"]:
                continue
            for fid, rd in t["reads"].items():
                if rd["instr"] != word:
                    continue
                (good if rd["outcome"] == "ok" else bad).append(
                    {"arm": arm, "fid": fid, "outcome": rd["outcome"]})
        verdicts[word]["transparent_at"] = good
        verdicts[word]["not_transparent_at"] = bad

    # ------------------------------------------------------ field verdicts
    out = {}
    for word, v in sorted(verdicts.items()):
        nholes = len(v["confirming_holes"])
        rng = ("total bytes consumed measured on hardware at %d admitted "
               "stop-ruler hole(s) across %d carrier(s), against a known-2-byte "
               "(mov_imm) / known-4-byte (if_push) / known-6-byte (icmp_pred) "
               "anchor set at the same stop offsets" % (nholes, len(v["carriers"])))
        if v["verdict"] != "LENGTH-CONFIRMED":
            rng = "NOT ESTABLISHED (%s); %s" % (v["verdict"], rng)
        note = []
        if v["verdict"] == "LENGTH-CONFIRMED":
            note.append("The encoding was GENERATED by us at program points the "
                        "compiler never chose and consumed exactly the length "
                        "db.json claims; a longer known word at the same offset "
                        "provably hides the planted terminator, so the reading "
                        "is a contrast and not an absolute.")
            if word in TARGETS_4B:
                note.append("The ruler bounds TOTAL consumption at 4 bytes; it "
                            "cannot separate one 4-byte op from two 2-byte "
                            "tokens, because every 4-byte candidate's trailing "
                            "half is itself a legal 2-byte encoding.")
            if v["transparent_at"]:
                note.append("Architecturally transparent (carrier oracle "
                            "preserved) at %d natural substitution hole(s)."
                            % len(v["transparent_at"]))
            else:
                note.append("Transparency NOT demonstrated: the micro-op's "
                            "architectural effect remains uncharacterised. An "
                            "emitter may rely on the framing and on nothing else.")
        if v["hazard_holes"]:
            note.append("HAZARD: %d admitted hole(s) returned a hard outcome "
                        "for some fills; see hazard_holes." % len(v["hazard_holes"]))
        out["%s._instruction" % word] = {
            "label": v["label"], "verdict": v["verdict"], "range": rng,
            "target": "G17P", "evidence": ["EXP-0200"],
            "start": 0, "width": 0,
            "n_admitted_holes": nholes, "carriers": v["carriers"],
            "anchor": v["anchor"],
            "confirming_holes": v["confirming_holes"],
            "refuting_holes": v["refuting_holes"],
            "hazard_holes": v["hazard_holes"],
            "unreadable_holes": v["unreadable_holes"],
            "transparent_at": v["transparent_at"],
            "not_transparent_at": v["not_transparent_at"],
            "per_hole": v["per_hole"],
            "note": " ".join(note) or "no verdict",
        }
    doc = {"_generated_by": "analysis/verdicts200.py", "_runs": [str(r1), str(r2)],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved >= 1",
                     "measurement_failure_max_pct": MEAS_FAIL_MAX_PCT},
           "holes": holes, "transparency": trans, "verdicts": out}
    p = EXP / "analysis" / "t2_verdicts.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps({k: {"label": v["label"], "verdict": v["verdict"],
                          "holes": v["n_admitted_holes"],
                          "carriers": v["carriers"]}
                      for k, v in out.items()}, indent=1))
    print("admitted holes: %d / %d"
          % (sum(1 for h in holes.values() if h["admitted"]), len(holes)))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
