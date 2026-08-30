#!/usr/bin/env python3
"""EXP-0161 verdict builder (FIELD-SWEEP-PROTOCOL section 5).

  python3 analysis/verdicts.py

Reads the two gated runs, applies the pre-registered gates, cross-run-gates
every case, applies the lease adjudication (section 7A) where one exists, fits
a semantic model per field, and writes `analysis/field_verdicts.json`.

Nothing here consults `tools/agx-isa/validation.json` in the repo: labels are
compared against the FROZEN copy in `work/frozen/`, which is the one the
hardware ran against (the repo copy drifts while sibling experiments land).

CLEAN-ROOM: analysis of our own captured observations only.
"""
from __future__ import print_function

import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H   # noqa: E402
import cases as CM        # noqa: E402

# Each entry is a GATED PAIR: the same frozen matrix executed twice, in
# opposite arm order. A case counts only if both members agree and neither was
# victim-class.
PAIRS = [("g17p_20260829_run01", "g17p_20260829_run02"),      # the main matrix
         ("g17p_20260830_supp02", "g17p_20260830_supp03"),    # 2nd-carrier arms
         ("g17p_20260830_supp04", "g17p_20260830_supp05")]    # the floor arm
ADJ = EXP / "analysis" / "adjudication.json"
DANGER = sorted((EXP / "raw").glob("g17p_*_danger*/sweep.jsonl"))

VAL = json.loads((H.ISA_DIR / "validation.json").read_text())["instructions"]
GOOD = ("hardware-run", "isolated-byte-diff")
EMIT_GRADE = set(GOOD)


def load(p):
    return [json.loads(l) for l in open(str(p))] if Path(p).exists() else []


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# packings a value can use to name a register (project-standard set)
# ---------------------------------------------------------------------------
PACKINGS = [
    ("(reg<<1)|size  reg=v>>1", lambda v: v >> 1),
    ("reg<<2         reg=v>>2", lambda v: v >> 2),
    ("reg=v&0x7F", lambda v: v & 0x7F),
    ("reg=(v>>1)&0x3F", lambda v: (v >> 1) & 0x3F),
    ("reg=v&0x0F", lambda v: v & 0x0F),
    ("reg=v (identity)", lambda v: v),
]


def fit_packing(obs):
    """obs: {value -> register}. Returns the best packing name + fit count."""
    best = (None, -1, 0)
    for name, fn in PACKINGS:
        hit = sum(1 for v, r in obs.items() if fn(v) == r)
        if hit > best[1]:
            best = (name, hit, len(obs))
    return {"packing": best[0], "fit": best[1], "of": best[2]}


def fit_mask(accepted, universe):
    """Smallest (mask, const) with (v & mask) == const fitting `accepted`
    EXACTLY over `universe`. Returns None if no such rule exists."""
    acc = set(accepted)
    if not acc or acc == set(universe):
        return None
    best = None
    for mask in range(256):
        cs = set(v & mask for v in acc)
        if len(cs) != 1:
            continue
        c = cs.pop()
        if all((v & mask) != c for v in universe if v not in acc):
            nbits = bin(mask).count("1")
            if best is None or nbits < best[0]:
                best = (nbits, mask, c)
    if best is None:
        return None
    return {"rule": "(v & 0x%02X) == 0x%02X" % (best[1], best[2]),
            "dont_care_bits": [i for i in range(8) if not (best[1] >> i) & 1],
            "n_accepted": len(acc)}


# ---------------------------------------------------------------------------
def main():
    adj = json.loads(ADJ.read_text()) if ADJ.exists() else {}
    adjmap = dict((int(k), v) for k, v in adj.get("cases", {}).items())

    gates, agreed, disagree = {}, {}, []
    victims = 0
    used_pairs, n_cases = [], 0
    for (n1, n2) in PAIRS:
        r1 = load(EXP / "raw" / n1 / "sweep.jsonl")
        r2 = load(EXP / "raw" / n2 / "sweep.jsonl")
        if not r1 or not r2:
            continue
        used_pairs.append([n1, n2])
        n_cases += len(r1)
        i1 = dict((r["idx"], r) for r in r1)
        i2 = dict((r["idx"], r) for r in r2)
        for arm in sorted(set(r["arm"] for r in r1)):
            g = {}
            for r in r1:
                if r["arm"] == arm and (r["field"].startswith("__falsifier")
                                        or r["field"] == "__baseline"):
                    o2 = i2[r["idx"]]["outcome"]
                    g[r["field"]] = {"runA": r["outcome"], "runB": o2,
                                     "victim": r["victim"] or i2[r["idx"]]["victim"]}
            g["pair"] = [n1, n2]
            g["baseline_ok"] = g.get("__baseline", {}).get("runA") == "ok" and \
                g.get("__baseline", {}).get("runB") == "ok"
            fals = [k for k in g if k.startswith("__falsifier")]
            g["falsifiers_fired"] = all(
                g[k]["runA"] != "ok" and g[k]["runB"] != "ok" for k in fals)
            g["USABLE"] = bool(g["baseline_ok"] and g["falsifiers_fired"] and fals)
            gates[arm] = g
        for idx, a in i1.items():
            b = i2.get(idx)
            if b is None:
                continue
            key = (n1, idx)
            if a["victim"] or b["victim"]:
                victims += 1
                continue
            if a["outcome"] != b["outcome"]:
                disagree.append({"pair": n1, "idx": idx, "arm": a["arm"],
                                 "field": a["field"], "value": a["value"],
                                 "runA": a["outcome"], "runB": b["outcome"]})
                continue
            oc = a["outcome"]
            if n1 == PAIRS[0][0] and idx in adjmap:
                oc = adjmap[idx]["final"]
            agreed[key] = (a, oc)
    meta = {"gated_pairs": used_pairs, "cases_per_run": n_cases, "target": "G17P",
            "fault_adjudication": (ADJ.name if ADJ.exists() else "NOT RUN"),
            "n_adjudicated": adj.get("_meta", {}).get("n_adjudicated"),
            "n_adjudication_changed": adj.get("_meta", {}).get("n_changed")}
    meta["gates"] = gates
    meta["cross_run"] = {"agreed": len(agreed), "victim_excluded": victims,
                         "disagreements": len(disagree)}
    meta["cross_run_disagreements"] = disagree[:200]

    # ---- per-field statistics -------------------------------------------
    stats = defaultdict(lambda: defaultdict(dict))     # arm -> field -> value -> (rec,oc)
    for idx, (rec, oc) in agreed.items():
        stats[rec["arm"]][rec["field"]][rec["value"]] = (rec, oc)

    ARM = dict((a["arm"], a) for a in
               list(CM.ARMS) + list(CM.SUPP_ARMS) + list(CM.SUPP2_ARMS)
               + [CM.DANGER_ARM])
    out = {}
    notes = {}

    # semantic recovery, per arm, from the SYNTH 16-register dumps
    sem = {}
    for arm in stats:
        if ARM.get(arm, {}).get("style") != "synth":
            continue
        bl = stats[arm].get("__baseline", {}).get(0)
        if not bl or not bl[0].get("observed"):
            continue
        base = bl[0]["observed"]["regs"]
        seeds = H.seeds_for(ARM[arm]["kind"])
        for field, vals in stats[arm].items():
            if field.startswith("__"):
                continue
            released, destmap = {}, {}
            for v, (rec, oc) in sorted(vals.items()):
                o = rec.get("observed")
                if not o or not o.get("regs"):
                    continue
                rg = o["regs"]
                # register the mutated instruction RELEASED (read): non-zero in
                # the baseline dump, zero here, and not zero in the baseline
                rel = [i for i in range(15)
                       if rg[i] == 0 and base[i] != 0]
                # register that RECEIVED the baseline's result value
                res = base[0]
                dst = [i for i in range(1, 15)
                       if rg[i] == res and base[i] != res]
                if len(rel) == 1:
                    released[v] = rel[0]
                if len(dst) == 1:
                    destmap[v] = dst[0]
            s = {}
            if len(released) >= 6:
                s["released_register_map"] = fit_packing(released)
                s["released_examples"] = dict(list(sorted(released.items()))[:8])
            if len(destmap) >= 6:
                s["destination_register_map"] = fit_packing(destmap)
                s["destination_examples"] = dict(list(sorted(destmap.items()))[:8])
            if s:
                sem["%s.%s" % (arm, field)] = s
    meta["semantic_maps"] = sem

    # ---- verdict per (instr, field) -------------------------------------
    perfield = defaultdict(lambda: defaultdict(dict))   # instr -> field -> arm -> info
    for arm in stats:
        instr = ARM[arm]["instr"]
        for field, vals in stats[arm].items():
            if field.startswith("__base") or field.startswith("__falsifier"):
                continue
            cnt = Counter(oc for (_, oc) in vals.values())
            accepted = sorted(v for v, (_, oc) in vals.items() if oc == "ok")
            universe = sorted(vals.keys())
            info = {"arm": arm, "style": ARM.get(arm, {}).get("style", "inplace"),
                    "n": len(vals), "outcomes": dict(cnt),
                    "n_accepted": len(accepted),
                    "accepted": accepted if len(accepted) <= 40 else
                                accepted[:40] + ["...(%d)" % len(accepted)],
                    "range_lo": universe[0], "range_hi": universe[-1]}
            m = fit_mask(accepted, universe)
            if m:
                info["accept_rule"] = m
            k = "%s.%s" % (arm, field)
            if k in sem:
                info["semantics"] = sem[k]
            perfield[instr][field][arm] = info

    # the DANGER arm is single-run by design (each case resets the device, so a
    # second full run is not a proportionate cost); it is reported separately
    # and never enters the cross-run-gated verdicts.
    danger = {}
    for p in DANGER:
        rs = load(p)
        cnt = Counter(r["outcome"] for r in rs)
        oshang = sum(1 for r in rs for a in r["attempts"]
                     if a["error"] and "ErrorHang" in a["error"])
        first_att = Counter(
            ("ErrorHang" if (r["attempts"][0]["error"] or "").find("ErrorHang") >= 0
             else ("InnocentVictim" if r["attempts"][0]["victim"]
                   else r["attempts"][0]["status"]))
            for r in rs if r["attempts"])
        danger[p.parent.name] = {
            "cases": len(rs), "outcomes": dict(cnt),
            "os_ErrorHang_attempts": oshang,
            "first_attempt_classification": dict(first_att),
            "values": sorted(r["value"] for r in rs if r["field"] == "src"),
            "watchdog_hangs": cnt.get("hang", 0)}
    meta["danger_arm"] = danger

    for instr in sorted(perfield):
        for field in sorted(perfield[instr]):
            arms = perfield[instr][field]
            usable = dict((a, v) for a, v in arms.items() if gates[a]["USABLE"])
            key = "%s.%s" % (instr, field)
            fdef = [f for f in CM.INS[instr]["fields"] if f["name"] == field]
            width = fdef[0]["width"] if fdef else None
            prior = VAL.get(instr, {}).get(field, {})
            if not usable:
                out[key] = {"label": "untested", "target": "G17P",
                            "evidence": ["EXP-0161"],
                            "range": "swept, but no carrier passed its gate",
                            "note": "arms %s all failed the pre-registered "
                                    "falsifier/baseline gate; per PRE_REGISTRATION "
                                    "section 6 nothing is promoted from them"
                                    % sorted(arms), "arms": arms,
                            "prior_label": prior.get("label", "untested")}
                continue
            # coverage: dense over the whole encodable range?
            dense = all(v["n"] >= (1 << width) * 0.75 for v in usable.values()) \
                if width else False
            full = all(v["range_lo"] == 0 and v["range_hi"] == (1 << width) - 1
                       for v in usable.values()) if width else False
            # discrimination: does ANY usable arm see more than one outcome?
            multi = any(len(v["outcomes"]) > 1 for v in usable.values())
            inert = all(set(v["outcomes"]) == {"ok"} for v in usable.values())
            semk = [k for k in sem if k.split(".", 1)[1] == field
                    and k.split(".", 1)[0] in usable]
            has_sem = any("released_register_map" in sem[k]
                          or "destination_register_map" in sem[k] for k in semk)
            if multi and dense:
                label = "hardware-run"
            elif inert and len(usable) >= 2 and dense:
                label = "hardware-run"      # inert confirmed in >=2 carriers
            elif multi:
                label = "isolated-byte-diff"
            else:
                label = "untested"
            rng = " / ".join("%s: %d..%d (%d values%s)"
                             % (a, v["range_lo"], v["range_hi"], v["n"],
                                ", dense" if width and v["n"] == (1 << width) else "")
                             for a, v in sorted(usable.items()))
            note = []
            if inert:
                note.append("HW-TESTED INERT over the whole swept range in %d "
                            "independent carriers (%s): every value reproduces "
                            "the unmutated result exactly. Role UNKNOWN -- an "
                            "emitter may use any value, but must NOT synthesize "
                            "a meaning for it." % (len(usable), ", ".join(sorted(usable))))
            for a, v in sorted(usable.items()):
                if "accept_rule" in v:
                    note.append("%s: accepted set fits %s (%d of %d values)"
                                % (a, v["accept_rule"]["rule"],
                                   v["accept_rule"]["n_accepted"], v["n"]))
            for k in semk:
                s = sem[k]
                for nm in ("released_register_map", "destination_register_map"):
                    if nm in s and s[nm]["fit"] >= max(6, int(0.8 * s[nm]["of"])):
                        note.append("%s: %s -> %s, fit %d/%d"
                                    % (k, nm.replace("_", " "),
                                       s[nm]["packing"], s[nm]["fit"], s[nm]["of"]))
            out[key] = {"label": label, "target": "G17P",
                        "evidence": ["EXP-0161"], "range": rng,
                        "note": " | ".join(note), "arms": arms,
                        "prior_label": prior.get("label", "untested"),
                        "prior_target": prior.get("target", "")}

    # ---- emittability ----------------------------------------------------
    emit = {}
    for instr in sorted(set(list(perfield.keys()))):
        fields = [f["name"] for f in CM.INS[instr]["fields"]]
        rows = {}
        for f in fields:
            k = "%s.%s" % (instr, f)
            new = out.get(k, {}).get("label")
            old = VAL.get(instr, {}).get(f, {}).get("label", "untested")
            rows[f] = {"prior": old, "this_exp": new,
                       "best": new if (new in EMIT_GRADE) else old}
        blocking = [f for f, v in rows.items() if v["best"] not in EMIT_GRADE]
        emit[instr] = {"fields": rows, "blocking_before":
                       [f for f in fields
                        if VAL.get(instr, {}).get(f, {}).get("label", "untested")
                        not in EMIT_GRADE],
                       "blocking_after": blocking,
                       "EMITTABLE_AFTER": not blocking}
    meta["emittability"] = emit

    doc = {"_meta": meta, "verdicts": out}
    (EXP / "analysis" / "field_verdicts_raw.json").write_text(
        json.dumps(doc, indent=1, sort_keys=True))

    # protocol section 5 shape
    slim = {}
    for k, v in out.items():
        slim[k] = {"label": v["label"], "range": v["range"], "target": "G17P",
                   "evidence": ["EXP-0161"], "note": v["note"]}
    print("== gates")
    for a in sorted(gates):
        print("  %-18s baseline_ok=%-5s falsifiers_fired=%-5s USABLE=%s"
              % (a, gates[a]["baseline_ok"], gates[a]["falsifiers_fired"],
                 gates[a]["USABLE"]))
    print("== cross-run:", meta["cross_run"])
    print("== verdict labels:", dict(Counter(v["label"] for v in out.values())))
    for instr in sorted(emit):
        print("  %-14s blocking %d -> %d  EMITTABLE=%s"
              % (instr, len(emit[instr]["blocking_before"]),
                 len(emit[instr]["blocking_after"]),
                 emit[instr]["EMITTABLE_AFTER"]))
    return doc, slim


if __name__ == "__main__":
    main()
