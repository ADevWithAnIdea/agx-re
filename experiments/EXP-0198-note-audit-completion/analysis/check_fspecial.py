#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- reground the 4 EXP-0161/EXP-0165 `fspecial` notes and
`carry_gen.srcB` from EXP-0161's committed raw.

NAME TRAP.  DEF-0161-1 RENAMED fspecial's fields, and the raw predates the
rename: byte+3 is recorded under `field: "src"` and byte+5 under
`field: "src_ext"`, while validation.json now calls them `dst` and `src`.  A
field-name-keyed lookup therefore reads the WRONG BYTE (and, for `dst`, finds a
16-record byte+1-high-nibble sweep instead of the 192-record byte+3 sweep).  The
mapping used here is taken from EXP-0165/analysis/rederive_def1_fspecial.py's own
comments (`byte+3 (db 'src')`, `byte+5 (db 'src_ext')`), not guessed.

Claims re-derived, independently of EXP-0165's scripts:
  * the destination map     "28/28 fit, 0 misfits, in BOTH gated runs"
  * the source map          "60/60 fit, 0 misfits, in BOTH gated runs" and
                            "56/56 where src != dst"
  * the roundmode result    "128/128 odd values all-NaN and 128/128 even values
                            bit-matching the baseline, in two carriers x two runs"
  * the danger sweep        "45 of those 64 values gave a genuine
                            kIOGPUCommandBufferCallbackErrorHang, 19 were only
                            ever observed as innocent victims, and none ever worked"
  * fnclass bit 3           "v and v+8 identical in all 8 pairs, three carriers"
  * the cited script files exist (CITES-MISSING-FILE)

Read-only.  Writes analysis/check_fspecial.json.
"""
import collections, json, math, os, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
E161 = os.path.join(ROOT, "experiments", "EXP-0161-g17p-carry-fspecial")
E165 = os.path.join(ROOT, "experiments", "EXP-0165-db-defect-repair")
GATED = ("g17p_20260829_run01", "g17p_20260829_run02")
SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0, 0.0]


def fb(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


SEED = [fb(v) for v in SEED_F32]


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def load(run):
    p = os.path.join(E161, "raw", run, "sweep.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


R = {r: load(r) for r in (GATED[0], GATED[1], "g17p_20260830_danger01",
                          "g17p_20260830_gen03")}


def sel(run, arm, field):
    return [r for r in R[run] if r.get("instr") == "fspecial"
            and r.get("arm") == arm and r.get("field") == field
            and not r.get("victim")]


def regmap(run, arm, rawfield):
    """value -> which register received an rsqrt of which seed, and which was
    released to zero.  Uses the 16-register architectural dump only."""
    base = [r for r in R[run] if r.get("arm") == arm and r.get("field") == "__baseline"]
    b = (base[0].get("observed") or {}).get("regs") if base else None
    out = {}
    for r in sel(run, arm, rawfield):
        rg = (r.get("observed") or {}).get("regs")
        if rg is None or b is None:
            continue
        ch = [i for i in range(15) if rg[i] != SEED[i]]
        zero = [i for i in ch if rg[i] == 0]
        hits = []
        for i in ch:
            if rg[i] == 0:
                continue
            for j in range(15):
                if SEED_F32[j] <= 0:
                    continue
                want = 1.0 / math.sqrt(SEED_F32[j])
                if abs(f32(rg[i]) - want) <= 1e-5 * max(1.0, abs(want)):
                    hits.append((i, j))
        out[r["value"]] = {"changed": ch, "zeroed": zero, "rsqrt_writes": hits}
    return out


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}

    # ---------- destination map: byte+3, recorded as `src` -----------------
    dst_fit = {}
    for run in GATED:
        m = regmap(run, "D3_FSPEC_SYNTH", "src")
        fits = [v for v in range(30)
                if v in m and any(i == (v >> 1) for i, _ in m[v]["rsqrt_writes"])]
        invisible = [v for v in (12, 13) if v in m and not m[v]["rsqrt_writes"]]
        dst_fit[run] = {"n_values_0_29_present": sum(1 for v in range(30) if v in m),
                        "fits": len(fits), "fit_values": fits,
                        "invisible_seed_alias": invisible,
                        "misfits": [v for v in range(30)
                                    if v in m and v not in fits and v not in (12, 13)]}
    # ---------- source map: byte+5, recorded as `src_ext` ------------------
    src_fit = {}
    for run in GATED:
        m = regmap(run, "D3_FSPEC_SYNTH", "src_ext")
        fits, released = [], []
        for v in range(60):
            if v not in m:
                continue
            j = v >> 2
            if any(jj == j for _, jj in m[v]["rsqrt_writes"]):
                fits.append(v)
            if j in m[v]["zeroed"]:
                released.append(v)
        src_fit[run] = {"n_values_0_59_present": sum(1 for v in range(60) if v in m),
                        "fits": len(fits), "released_to_zero": len(released),
                        "misfits": [v for v in range(60) if v in m and v not in fits]}

    # ---------- roundmode -------------------------------------------------
    rm = {}
    for run in GATED:
        for arm in ("D_FSPEC_INPLACE", "D2_FSPEC_LOG2"):
            base = [r for r in R[run] if r.get("arm") == arm and r.get("field") == "__baseline"]
            bout = (base[0].get("observed") or {}).get("out") if base else None
            odd_nan = even_match = odd_n = even_n = 0
            for r in sel(run, arm, "roundmode"):
                o = (r.get("observed") or {}).get("out")
                if o is None:
                    continue
                if r["value"] & 1:
                    odd_n += 1
                    if len(o) == 12 and all(str(x).lower() == "nan" for x in o):
                        odd_nan += 1
                else:
                    even_n += 1
                    if o == bout:
                        even_match += 1
            rm["%s|%s" % (run, arm)] = {"odd": odd_n, "odd_all_nan": odd_nan,
                                        "even": even_n, "even_bitmatch_baseline": even_match}

    # ---------- danger sweep (v >= 192 on byte+3) -------------------------
    dz = [r for r in R["g17p_20260830_danger01"]
          if r.get("instr") == "fspecial" and r.get("field") == "src"]
    hangs, victims, worked = [], [], []
    for r in dz:
        att = r.get("attempts") or []
        errs = " ".join(str(a.get("error")) for a in att)
        if any(a.get("outcome") == "ok" and not a.get("victim") for a in att) \
                and r.get("outcome") == "ok":
            worked.append(r["value"])
        if "Hang" in errs:
            hangs.append(r["value"])
        elif att and all(a.get("victim") for a in att):
            victims.append(r["value"])
    danger = {"n_cases": len(dz), "hang": len(hangs),
              "victim_only": len(victims), "worked": len(worked),
              "outcomes": dict(collections.Counter(r["outcome"] for r in dz))}

    # ---------- fnclass bit 3 don't-care ----------------------------------
    fn = {}
    for run in GATED:
        for arm in ("D_FSPEC_INPLACE", "D2_FSPEC_LOG2", "D3_FSPEC_SYNTH"):
            m = {r["value"]: (r.get("observed") or {}).get("out")
                 for r in sel(run, arm, "fnclass")}
            pairs = [(v, v + 8) for v in range(8) if v in m and v + 8 in m]
            same = [p for p in pairs if m[p[0]] == m[p[1]]]
            fn["%s|%s" % (run, arm)] = {"pairs": len(pairs), "identical": len(same)}

    # ---------- gen03 GENERATED encodings ---------------------------------
    gen = [r for r in R["g17p_20260830_gen03"]]
    gen_ok = [r for r in gen if r.get("outcome") == "ok"]
    gen_info = {"records": len(gen), "ok": len(gen_ok),
                "outcomes": dict(collections.Counter(r.get("outcome") for r in gen))}

    # ---------- cited scripts exist ---------------------------------------
    cited = ["analysis/rederive_def1_fspecial.py", "analysis/def1_summary.py",
             "analysis/rederive_gen03.py", "analysis/rederive_def3_fnclass.py",
             "analysis/rederive_def4_roundmode.py"]
    exists = {c: os.path.exists(os.path.join(E165, c)) for c in cited}

    def note(k):
        m, f = k.split(".", 1)
        return val["instructions"][m][f].get("note") or ""

    def add(k, claims):
        out[k] = {"label": val["instructions"][k.split(".")[0]][k.split(".", 1)[1]].get("label"),
                  "note": note(k), "claims": claims,
                  "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}

    add("fspecial.dst", [
        {"claim": "28/28 fit, 0 misfits, in BOTH gated runs (v=0..29 -> r0..r14)",
         "raw": dst_fit,
         "ok": all(dst_fit[r]["fits"] == 28 and not dst_fit[r]["misfits"] for r in GATED)},
        {"claim": "v=12/13 write r6 and are invisible (seed aliasing)",
         "raw": {r: dst_fit[r]["invisible_seed_alias"] for r in GATED},
         "ok": all(dst_fit[r]["invisible_seed_alias"] == [12, 13] for r in GATED)},
        {"claim": "v>=192: 45 hangs, 19 victim-only, none worked (64 values)",
         "raw": danger,
         "ok": (danger["n_cases"] == 64 and danger["hang"] == 45
                and danger["victim_only"] == 19 and danger["worked"] == 0)},
        {"claim": "cited EXP-0165 scripts exist", "raw": exists,
         "ok": all(exists.values())}])

    add("fspecial.src", [
        {"claim": "60/60 fit, 0 misfits, in BOTH gated runs (v=0..59 -> r0..r14)",
         "raw": src_fit,
         "ok": all(src_fit[r]["fits"] == 60 and not src_fit[r]["misfits"] for r in GATED)},
        {"claim": "56/56 where src != dst are released to zero",
         "raw": {r: src_fit[r]["released_to_zero"] for r in GATED},
         "ok": all(src_fit[r]["released_to_zero"] == 56 for r in GATED)}])

    add("fspecial.roundmode", [
        {"claim": "128/128 odd all-NaN and 128/128 even bit-matching baseline, "
                  "two carriers x two gated runs",
         "raw": rm,
         "ok": all(v["odd"] == 128 and v["odd_all_nan"] == 128
                   and v["even"] == 128 and v["even_bitmatch_baseline"] == 128
                   for v in rm.values())}])

    add("fspecial.fnclass", [
        {"claim": "bit 3 DON'T-CARE: v and v+8 identical in all 8 pairs, three carriers",
         "raw": fn,
         "ok": all(v["pairs"] == 8 and v["identical"] == 8 for v in fn.values())}])

    out["_gen03"] = gen_info
    json.dump(out, open(os.path.join(HERE, "check_fspecial.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter(v["verdict"] for k, v in out.items() if not k.startswith("_"))
    print("fspecial family:", len(out) - 1, dict(c))
    for k, v in sorted(out.items()):
        if k.startswith("_"):
            continue
        print("  %-24s %s" % (k, v["verdict"]))
        for cl in v["claims"]:
            if not cl["ok"]:
                print("       FAILS", json.dumps(cl)[:600])
    print("  gen03:", json.dumps(gen_info))


if __name__ == "__main__":
    main()
