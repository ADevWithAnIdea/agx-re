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
    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
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
    # gen03 uses a DIFFERENT record schema: the per-case result is `verdict`, not
    # `outcome`.  Reading `outcome` here returns None for every record and would make
    # a "20/20 pass" claim look like 0/20.
    gen = [r for r in R["g17p_20260830_gen03"] if r.get("gen") == "fspecial"]
    gen_pass = [r for r in gen if r.get("verdict") == "pass"]
    gen_info = {"fspecial_generated_records": len(gen), "pass": len(gen_pass),
                "verdicts": dict(collections.Counter(r.get("verdict") for r in gen)),
                "descs": sorted({r.get("desc") for r in gen})[:6]}

    # ---------- cited scripts exist ---------------------------------------
    cited = ["analysis/rederive_def1_fspecial.py", "analysis/def1_summary.py",
             "analysis/rederive_gen03.py", "analysis/rederive_def3_fnclass.py",
             "analysis/rederive_def4_roundmode.py"]
    exists = {c: os.path.exists(os.path.join(E165, c)) for c in cited}

    def note(k):
        m, f = k.split(".", 1)
        return val["instructions"][m][f].get("note") or ""

    def N(k, rx, n=1):
        """Claimed numbers are parsed OUT OF THE NOTE, never transcribed by hand,
        so a changed note changes the verdict (see analysis/negative_control.py)."""
        mo = re.search(rx, note(k))
        if not mo:
            return None if n == 1 else (None,) * n
        return int(mo.group(1)) if n == 1 else tuple(int(g) for g in mo.groups())

    def add(k, claims):
        out[k] = {"label": val["instructions"][k.split(".")[0]][k.split(".", 1)[1]].get("label"),
                  "note": note(k), "claims": claims,
                  "verdict": "SUPPORTED" if all(c["ok"] for c in claims) else "CONTRADICTED"}

    dN = N("fspecial.dst", r"Destination map from the 16-register dump: (\d+)/(\d+) fit", 2)
    dHang, dTot, dVic = N("fspecial.dst",
        r"(\d+) of those (\d+) values gave a genuine kIOGPUCommandBufferCallbackErrorHang, "
        r"(\d+) were only ever observed as innocent victims", 3)
    add("fspecial.dst", [
        {"claim": "N/N fit, 0 misfits, in BOTH gated runs (v=0..29 -> r0..r14)",
         "claimed": list(dN), "raw": dst_fit,
         "ok": (dN[0] == dN[1]
                and all(dst_fit[r]["fits"] == dN[0] and not dst_fit[r]["misfits"]
                        for r in GATED))},
        {"claim": "v=12/13 write r6 and are invisible (seed aliasing)",
         "raw": {r: dst_fit[r]["invisible_seed_alias"] for r in GATED},
         "ok": all(dst_fit[r]["invisible_seed_alias"] == [12, 13] for r in GATED)},
        {"claim": "v>=192: N hangs, M victim-only, none worked (K values)",
         "claimed": {"hang": dHang, "of": dTot, "victim_only": dVic},
         "raw": danger,
         "ok": (danger["n_cases"] == dTot and danger["hang"] == dHang
                and danger["victim_only"] == dVic and danger["worked"] == 0)},
        {"claim": "N/N GENERATED `r_i = rsqrt(r_j)` encodings pass",
         "claimed": N("fspecial.dst", r"(\d+)/(\d+) GENERATED `r_i = rsqrt\(r_j\)` "
                                      r"encodings pass", 2),
         "raw": gen_info,
         "ok": (lambda c: c[0] == c[1] and gen_info["pass"] == c[0]
                          and gen_info["fspecial_generated_records"] == c[1])(
                 N("fspecial.dst", r"(\d+)/(\d+) GENERATED `r_i = rsqrt\(r_j\)` "
                                   r"encodings pass", 2))},
        {"claim": "cited EXP-0165 scripts exist", "raw": exists,
         "ok": all(exists.values())}])

    sN = N("fspecial.src", r"Source map from the 16-register dump: (\d+)/(\d+) fit", 2)
    sRel = N("fspecial.src", r"\((\d+)/\d+ where src != dst\)")
    add("fspecial.src", [
        {"claim": "N/N fit, 0 misfits, in BOTH gated runs (v=0..59 -> r0..r14)",
         "claimed": list(sN), "raw": src_fit,
         "ok": (sN[0] == sN[1]
                and all(src_fit[r]["fits"] == sN[0] and not src_fit[r]["misfits"]
                        for r in GATED))},
        {"claim": "M/M where src != dst are released to zero", "claimed": sRel,
         "raw": {r: src_fit[r]["released_to_zero"] for r in GATED},
         "ok": all(src_fit[r]["released_to_zero"] == sRel for r in GATED)},
        {"claim": "N/N GENERATED encodings pass",
         "claimed": N("fspecial.src", r"(\d+)/(\d+) GENERATED encodings pass", 2),
         "raw": gen_info,
         "ok": (lambda c: c[0] == c[1] and gen_info["pass"] == c[0]
                          and gen_info["fspecial_generated_records"] == c[1])(
                 N("fspecial.src", r"(\d+)/(\d+) GENERATED encodings pass", 2))}])

    ro, re_ = (N("fspecial.roundmode", r"(\d+)/(\d+) odd values all-NaN", 2),
               N("fspecial.roundmode", r"(\d+)/(\d+) even values bit-matching the baseline", 2))
    add("fspecial.roundmode", [
        {"claim": "N/N odd all-NaN and M/M even bit-matching baseline, "
                  "two carriers x two gated runs",
         "claimed": {"odd": list(ro), "even": list(re_)}, "raw": rm,
         "ok": (ro[0] == ro[1] and re_[0] == re_[1]
                and all(v["odd"] == ro[1] and v["odd_all_nan"] == ro[0]
                        and v["even"] == re_[1] and v["even_bitmatch_baseline"] == re_[0]
                        for v in rm.values()))}])

    WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    _mo = re.search(r"identical in all (\d+) pairs, (\w+) carriers", note("fspecial.fnclass"))
    fp = (int(_mo.group(1)), WORDNUM.get(_mo.group(2), -1)) if _mo else (None, None)
    add("fspecial.fnclass", [
        {"claim": "bit 3 DON'T-CARE: v and v+8 identical in all N pairs, M carriers",
         "claimed": list(fp), "raw": fn,
         "ok": (all(v["pairs"] == fp[0] and v["identical"] == fp[0] for v in fn.values())
                and len({k.split("|")[1] for k in fn}) == fp[1])}])

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
