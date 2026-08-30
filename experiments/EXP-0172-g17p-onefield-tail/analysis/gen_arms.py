#!/usr/bin/env python3
"""gen_arms.py -- EXP-0172: turn the PRE-FREEZE census into the frozen arm list.

Reads raw/prefreeze/census.json (CALIBRATION, not evidence) and writes
harness/arms.py.  Each arm records the carrier, stage, mnemonic, occurrence
index, the target field(s) swept on it, and the EXACT instruction bytes the
census saw there -- run.py asserts the located bytes still match, so a shifted
occurrence index is a recorded error rather than a silently wrong arm.

SELECTION RULE (frozen in PRE_REGISTRATION.md sec.7 step 4, applied here
mechanically rather than by hand-listing offsets):

  * FIELD_CARRIERS below names, per target field, the carriers that differ
    STRUCTURALLY IN THE DIMENSION THAT FIELD CONTROLS.  Two carriers identical
    in that dimension are one carrier (rule 2 / EXP-0164 iter_at.loc), so a
    carrier is listed only if `carriers.py`'s `why` states the dimension.
  * Within a carrier, occurrences are taken in program order, preferring ones
    whose OTHER decoded field values differ from those already taken -- so an
    inert verdict is not an artefact of one instruction context.
  * MAX_OCC caps occurrences per carrier: 2 for a field wider than 1 bit
    (a 256-value sweep), 3 for a 1-bit field (a 2-value sweep is nearly free).

CLEAN-ROOM: OWN-SHADER.  Every byte named here is compiled from kernels/*.metal.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import carriers as CA                                   # noqa: E402

CEN = json.load(open(os.path.join(EXP, "raw", "prefreeze", "census.json")))

# field -> carriers, ordered best-first.  The dimension each carrier adds is
# stated in carriers.py `why`; this list is the frozen selection.
FIELD_CARRIERS = {
    # ---- TIER 1 ----
    "falu2i.imm_flag":              ["fimm", "fimm2"],
    "get_sr.form":                  ["srwide", "srnarrow"],
    "tex_sample.coord":             ["texread", "texmix"],
    "vary_slot.slot":               ["vmany", "vhalf", "vflat", "vsrc"],
    "tex_deriv.dstsrc":             ["deriv"],
    # ---- TIER 2 ----
    "imageblock_store.src":         ["ibsamp", "ibhalf", "ibmrt", "ibms4"],
    "irotate.b2":                   ["rot", "rot2", "deadsrc"],
    "simd_ballot.cache":            ["deadsrc", "sball", "scache", "sdiv"],
    "simd_shuffle.cache":           ["deadsrc", "scache", "stype", "sdiv"],
    "frame_marker_compact.b1":      ["rot", "srnarrow", "scache", "vhalf", "vsrc"],
    "n4_cf_word.b3":                ["cfdiv", "tgat", "sdiv"],
    # ---- TIER 3 (swept for the record; promotion declined in advance) ----
    "ret.scoreboard":               ["cfdiv"],
    # dev_scoreboard_fence.scope_flag is NOT here: the pre-freeze census found
    # ZERO occurrences of dev_scoreboard_fence in any of the 24 carriers, in any
    # stage.  Recorded as a measured decline in RESULTS.md rather than swept on a
    # carrier that does not emit it.
}

TIER = {}
for f in ("falu2i.imm_flag", "get_sr.form", "tex_sample.coord",
          "vary_slot.slot", "tex_deriv.dstsrc"):
    TIER[f] = 1
for f in ("imageblock_store.src", "irotate.b2", "simd_ballot.cache",
          "simd_shuffle.cache", "frame_marker_compact.b1", "n4_cf_word.b3"):
    TIER[f] = 2
for f in ("ret.scoreboard", "dev_scoreboard_fence.scope_flag"):
    TIER[f] = 3

sys.path.insert(0, os.path.join(EXP, "work", "frozen"))
import isadb                                            # noqa: E402
WIDTH = {}
for ins in isadb.DB:
    for fl in ins.get("fields", []):
        WIDTH[f"{ins['mnemonic']}.{fl['name']}"] = (fl["start"], fl["width"])


def main():
    arms, missing, notes = [], [], []
    for key, clist in FIELD_CARRIERS.items():
        mnem, field = key.rsplit(".", 1)
        if key not in WIDTH:
            missing.append((key, "no such field in the PINNED db.json"))
            continue
        start, width = WIDTH[key]
        # cases per occurrence: 2^w for w<=8, ~40 sampled for w>8.  Budget more
        # occurrences where each is cheap.
        max_occ = 4 if (width == 1 or width > 8) else 2
        for carrier in clist:
            e = CEN.get(carrier)
            if e is None or e.get("build_rc") not in (0,):
                missing.append((key, f"{carrier}: carrier did not build"))
                continue
            for stage, st in sorted(e.get("stages", {}).items()):
                lst = st.get("targets", {}).get(mnem, [])
                if not lst:
                    continue
                # Program order, capped at max_occ, under two preferences:
                #
                #   (1) SPAN THE TARGET FIELD'S OWN BASELINE VALUES.  Added after
                #       the smoke02 calibration, which exposed the gap: all six
                #       chosen get_sr arms happened to have form==0 natively, so
                #       every control flipped 0->1 and the 1->0 direction was
                #       never tested. Two arms that agree on the field's own
                #       baseline value cannot bound its effect in both
                #       directions -- the same rule-2 mistake one level down
                #       (EXP-0164 / iter_at.loc). Occurrences are therefore
                #       bucketed by their baseline value of the target field and
                #       taken round-robin across buckets.
                #   (2) within a bucket, prefer occurrences whose OTHER decoded
                #       field values differ from those already taken.
                buckets = {}
                for occ, r in enumerate(lst):
                    buckets.setdefault(r["fields"].get(field), []).append((occ, r))
                chosen, seen_ctx = [], []
                order = sorted(buckets)
                while len(chosen) < max_occ and any(buckets[b] for b in order):
                    took = False
                    for b in order:
                        if not buckets[b] or len(chosen) >= max_occ:
                            continue
                        # first occurrence in this bucket with a fresh context
                        pick = None
                        for i, (occ, r) in enumerate(buckets[b]):
                            ctx = {k: v for k, v in r["fields"].items()
                                   if k != field}
                            if ctx not in seen_ctx:
                                pick = i
                                seen_ctx.append(ctx)
                                break
                        if pick is None:
                            buckets[b] = []
                            continue
                        chosen.append(buckets[b].pop(pick))
                        took = True
                    if not took:
                        break
                if not chosen:                     # all contexts identical
                    chosen = [(0, lst[0])]
                for occ, r in chosen:
                    arms.append(dict(
                        id=f"{mnem}.{field}@{carrier}/{stage}#{occ}",
                        carrier=carrier, stage=stage, mnemonic=mnem, occ=occ,
                        fields=[field], tier=TIER[key],
                        start=start, width=width,
                        expect_hex=r["hex"], expect_off=r["off"],
                        census_fields=r["fields"], tokenized=st["tokenized"],
                        why=CA.CARRIERS[carrier]["why"]))
            if not any(a["carrier"] == carrier and a["mnemonic"] == mnem
                       for a in arms):
                missing.append((key, f"{carrier}: mnemonic not emitted"))

    # Merge arms that target the same occurrence for several fields.
    merged = {}
    for a in arms:
        k = (a["carrier"], a["stage"], a["mnemonic"], a["occ"])
        if k in merged:
            for f in a["fields"]:
                if f not in merged[k]["fields"]:
                    merged[k]["fields"].append(f)
            merged[k]["tier"] = min(merged[k]["tier"], a["tier"])
        else:
            a = dict(a)
            a["id"] = f"{a['mnemonic']}@{a['carrier']}/{a['stage']}#{a['occ']}"
            merged[k] = a
    arms = sorted(merged.values(), key=lambda a: (a["tier"], a["id"]))

    src = ['#!/usr/bin/env python3',
           '"""arms.py -- EXP-0172 FROZEN arm list.',
           '',
           'GENERATED by analysis/gen_arms.py from raw/prefreeze/census.json under the',
           'selection rule frozen in PRE_REGISTRATION.md sec.7 step 4, then FROZEN:',
           'run.py asserts that the instruction it locates still has `expect_hex` at',
           '`expect_off`, so a shifted occurrence index is a recorded error, never a',
           'silently different arm.',
           '',
           '`tier` is the pre-registered priority (1 = attempt promotion, 2 = swept for',
           'the record, 3 = swept for the record with promotion DECLINED IN ADVANCE).',
           '`start`/`width` come from the PINNED work/frozen/db.json and are carried into',
           'every verdict row, so a stale DB becomes a loud merge failure.',
           '',
           'CLEAN-ROOM: OWN-SHADER.  Every byte named here is compiled from kernels/*.metal.',
           '"""',
           'ARMS = [']
    for a in arms:
        src.append("    " + repr(a) + ",")
    src.append("]")
    src.append("")
    src.append("MISSING = %r" % (missing,))
    open(os.path.join(EXP, "harness", "arms.py"), "w").write("\n".join(src) + "\n")

    print("arms:", len(arms))
    for m, n in sorted(collections.Counter(a["mnemonic"] for a in arms).items()):
        print(f"  {m:24s} {n} arms")
    ncases = 0
    for a in arms:
        for f in a["fields"]:
            w = WIDTH[f"{a['mnemonic']}.{f}"][1]
            ncases += (1 << w) if w <= 8 else 40
    print("dense sweep cases per run (excl. ladders/baselines): ~", ncases)
    print("MISSING:")
    for m in missing:
        print("   ", m)


if __name__ == "__main__":
    main()
