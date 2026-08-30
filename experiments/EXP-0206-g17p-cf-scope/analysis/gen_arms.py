#!/usr/bin/env python3
"""EXP-0206 arm generator -- applies the FROZEN selection rule of
PRE_REGISTRATION.md section 4 and nothing else, and writes harness/arms206.json.

Runs on the neo (it must compile the carriers to find the offsets). The resulting
`arms206.json` is pulled back, hashed into CAPTURE_CONTRACT.json by amendment,
and then NEVER edited -- both gated runs dispatch exactly this file.

The rule, restated:
 1. locate occurrences by both methods (`locate206.occurrences`, which now also
    accepts a BOUNDED RESYNC past an instruction the pinned DB cannot decode --
    without it the only non-leaf returns in the corpus are invisible);
 2. record the compiled target-field value and the occurrence's DIMENSION value;
 3. per carrier, keep at most `max_occ_per_carrier`, MAXIMISING THE SPREAD of the
    dimension value (one occurrence per distinct dimension value first, then by
    ascending offset);
 4. emit one TARGET arm and one CONTROL arm per selected occurrence.

Per-value PREDICTIONS (`expect`) are attached here, so every case carries a
host-computed, pre-registered expectation rather than a constant oracle. Where no
prediction is registered (`call.tail`), `expect` is null and stays null.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is inspected.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(HERE))

import carriers206 as C          # noqa: E402
import locate206 as L            # noqa: E402
import targets206 as T           # noqa: E402
import models206 as M            # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work"


def select_regions(regions, how):
    code = L.code_regions(regions)
    if how == "main":
        return [n for n in code if n == "_agc.main"]
    if how == "callee":
        return [n for n in code if not n.startswith("_agc.main")]
    return code


def spread(rows, k):
    """Keep at most k rows, maximising the spread of `dim`: one row per distinct
    dimension value first (ascending offset within a value), then fill by
    ascending offset. Two occurrences identical in the dimension the field
    controls are ONE occurrence."""
    by = {}
    for r in rows:
        by.setdefault(r.get("dim"), []).append(r)
    for v in by:
        by[v].sort(key=lambda r: (r["region"], r["off"]))
    out, seen = [], set()
    for v in sorted(by, key=lambda x: (x is None, x)):
        out.append(by[v][0])
        seen.add((by[v][0]["region"], by[v][0]["off"]))
        if len(out) >= k:
            return out[:k]
    rest = sorted([r for r in rows if (r["region"], r["off"]) not in seen],
                  key=lambda r: (r["region"], r["off"]))
    return (out + rest)[:k]


def expect_map(t, row):
    """The per-value, host-computed, PRE-REGISTERED expectation. `True` = the
    program must still produce the oracle vector; `False` = it must not; `None` =
    no prediction registered (and none is invented later)."""
    key, vals = t["key"], t["values"]
    dim = row.get("dim")
    cf = row.get("compiled_field")
    if key == "if_push.scope":
        # H1: at a LOOP-ITERATION push (scope_kind 0x1a = 26) the program is
        # correct iff bit 1 of `scope` is set. Basis: EXP-0188's pre-freeze
        # hazard probe, cited as a PRIOR observation and re-measured here.
        if dim == 26:
            return {str(v): bool(v & 0x02) for v in vals}
        return {str(v): True for v in vals}
    if key == "pop_reconverge.scope":
        # H2: only the compiled value is predicted correct; no rule is claimed
        # for the rest, so no expectation is invented for them.
        return {str(v): True for v in vals if v == cf}
    if key in ("pop_reconverge.reserved", "stop.reserved", "stop.reserved@synth_mid"):
        # H3/H6: predicted INERT -- every sampled value must still match. This is
        # a constant expectation ON PURPOSE: for a bit that is supposed to be
        # inert, "the observable did not move" IS the predicted effect. It is why
        # these verdicts additionally require a positive control (section 9).
        return {str(v): True for v in vals}
    if key == "ret.scoreboard":
        return {str(v): True for v in vals if v == cf}
    if key == "ret_luse.linkmode":
        # H5: at a NON-LEAF return (compiled linkmode 0x12) the LEAF value 0x02
        # must FAIL to restore the link; at a LEAF return (0x02) it must succeed.
        e = {str(cf): True} if cf is not None else {}
        if dim == 0x12:
            e["2"] = False
        elif dim == 0x02:
            e["2"] = True
        return e
    return {}                      # call.tail: no prediction, deliberately


def main():
    arms, meta = [], {}
    for name, spec in C.CARRIERS.items():
        arch, regions = L.compile_carrier(
            BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
        meta[name] = {rn: {"abs": r["abs"], "len": r["len"]}
                      for rn, r in regions.items()}
        meta[name]["_regions"] = regions

    for t in T.TARGETS:
        key = t["key"]
        want = t["mnemonic"]
        fallback = t.get("from_mnemonic")
        # `force_always` means the target instruction does not occur naturally and
        # is CONSTRUCTED from another one (the synthesized mid-program stop, built
        # over the optional 4-byte frame marker). Otherwise the fallback is used
        # only when the real instruction is absent from the carrier.
        order = [fallback] if (fallback and t.get("force_always")) \
            else ([want] + ([fallback] if fallback else []))
        for cname in t["carriers"]:
            regions = meta[cname]["_regions"]
            rows, src = [], None
            for mn in order:
                for rn in select_regions(regions, t["region_select"]):
                    b_ = regions[rn]["bytes"]
                    occ = L.occurrences(b_, mn)
                    for off in occ["accepted"]:
                        ln = L.DESC[mn]["length"]
                        raw = bytes(b_[off:off + ln])
                        r = {"region": rn, "off": off, "len": ln,
                             "bytes": raw.hex(), "src_mnemonic": mn}
                        try:
                            r["compiled_field"] = L.get_field(raw, want, t["field"])
                        except (KeyError, IndexError):
                            r["compiled_field"] = None
                        dimf = t.get("occ_dimension_field")
                        if dimf:
                            try:
                                r["dim"] = L.get_field(raw, mn, dimf)
                            except KeyError:
                                r["dim"] = None
                        if want == "stop" and mn == "stop":
                            fc, _rest = L.follows_code(b_, off, ln)
                            r["follows_code"] = fc
                        rows.append(r)
                if rows:
                    src = mn
                    break
            if not rows:
                arms.append({"key": key, "carrier": cname,
                             "arm": "%s@%s#NONE" % (key, cname),
                             "no_occurrence": True,
                             "note": "carrier emitted no %s (order tried: %s)"
                                     % (want, order)})
                continue
            synth = (src != want)
            force = [list(x) for x in t.get("force", [])] if synth else []
            start, width = L.field_span(want, t["field"])
            for i, row in enumerate(spread(rows, t["max_occ_per_carrier"])):
                tag = "%s.%s+%d" % (cname, row["region"][:14], row["off"])
                base = {"key": key, "group": t["group"], "carrier": cname,
                        "region": row["region"], "instr": want,
                        "off": row["off"], "len": row["len"],
                        "compiled_bytes": row["bytes"],
                        "compiled_field": row["compiled_field"],
                        "follows_code": row.get("follows_code"),
                        "occ": i, "occ_dim": row.get("dim"),
                        "src_mnemonic": row["src_mnemonic"],
                        "synthesized": synth}
                # The arm's OWN baseline bucket: for the SYNTHESIZED mid-program
                # stop the unswept program terminates and writes no value words,
                # so its baseline is `dead`, not `correct`. A model that predicted
                # `correct` there would be predicting the wrong thing.
                base["baseline_bucket"] = "dead" if key.endswith("@synth_mid") \
                    else "correct"
                arms.append(dict(base, arm="%s@%s" % (key, tag),
                                 field=t["field"], start=start, width=width,
                                 values=list(t["values"]), force=force,
                                 force_note=t.get("force_note", ""),
                                 expect=expect_map(t, row), role="target",
                                 models=M.predict(key, base, t["values"]),
                                 note=t["dimension"][:220]))
                # ---- detection-power control at the SAME occurrence ----
                ctl = t["control"]
                cfield = ctl.get("field")
                if cfield == "_synth_word":
                    arms.append(dict(base, arm="CTRL:synth_word@%s" % tag,
                                     field="_synth_word", start=0, width=32,
                                     values=list(ctl["values"]), force=[],
                                     expect={}, role="control_termination",
                                     note="TERMINATION dimension: " + ctl["why"][:200]))
                elif "byte0" in ctl:
                    arms.append(dict(base, arm="CTRL:byte0@%s" % tag,
                                     field="_byte0", start=0, width=8,
                                     values=list(ctl["byte0"]), force=force,
                                     expect={}, role="control_termination",
                                     note="TERMINATION dimension. A MATCH byte, "
                                          "control ONLY, never a field verdict: "
                                          + ctl["why"][:180]))
                elif cfield:
                    cs, cw = L.field_span(want, cfield)
                    arms.append(dict(base, arm="CTRL:%s@%s" % (cfield, tag),
                                     field=cfield, start=cs, width=cw,
                                     values=list(ctl["values"]), force=force,
                                     expect={}, role="control",
                                     note="detection power: " + ctl["why"][:200]))
                # ---- second control: call.offset perturbation ----
                c2 = t.get("control2")
                if c2:
                    os_, ow = L.field_span(want, c2["field"])
                    cur = L.get_field(bytes.fromhex(row["bytes"]), want, c2["field"])
                    vals = [(cur + d) & ((1 << ow) - 1) for d in c2["deltas"]]
                    arms.append(dict(base, arm="CTRL:%s@%s" % (c2["field"], tag),
                                     field=c2["field"], start=os_, width=ow,
                                     values=vals, force=force, expect={},
                                     role="control",
                                     note="detection power: " + c2["why"][:200]))

    # ---- FROZEN ARM SELECTION (contract amendment 5) --------------------------
    # Keep only the target arms named in targets206.SELECT, and every CONTROL arm
    # sitting at one of those same occurrences. Nothing else about an arm changes:
    # value coverage per arm is untouched.
    keep_occ = set()
    kept = []
    for a in arms:
        if a.get("no_occurrence"):
            continue
        if a.get("role") == "target":
            sel = T.SELECT.get(a["key"])
            if sel is not None and (a["carrier"], a["off"]) not in sel:
                continue
            keep_occ.add((a["carrier"], a["region"], a["off"]))
            kept.append(a)
    seen_ctl = set()
    for a in arms:
        if a.get("role") in ("control", "control_termination") and \
                (a["carrier"], a["region"], a["off"]) in keep_occ:
            # De-duplicate: two targets at the SAME occurrence (e.g.
            # pop_reconverge.scope and pop_reconverge.reserved) name the same
            # control field, and dispatching it twice buys nothing.
            if a["arm"] in seen_ctl:
                continue
            seen_ctl.add(a["arm"])
            kept.append(a)
    dropped = [a["arm"] for a in arms
               if not a.get("no_occurrence") and a not in kept]
    arms_all, arms = arms, kept

    doc = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "selection": "targets206.SELECT (contract amendment 5)",
           "arms_before_selection": len(arms_all),
           "dropped_arms": dropped,
           "rule": "PRE_REGISTRATION.md section 4 (amended after census: bounded "
                   "resync acceptance, see CAPTURE_CONTRACT.json amendment 1)",
           "arms": arms,
           "no_occurrence": [a for a in arms_all if a.get("no_occurrence")]}
    out = EXP / "harness" / "arms206.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    ncase = sum(len(a["values"]) for a in doc["arms"])
    print("arms=%d cases=%d -> %s" % (len(doc["arms"]), ncase, out))
    for a in doc["arms"]:
        print("  %-58s %-16s n=%-4d occ_dim=%-5s force=%s"
              % (a["arm"][:58], a["field"], len(a["values"]),
                 a.get("occ_dim"), bool(a.get("force"))))
    for a in doc["no_occurrence"]:
        print("  NO OCCURRENCE: %s -- %s" % (a["arm"], a["note"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
