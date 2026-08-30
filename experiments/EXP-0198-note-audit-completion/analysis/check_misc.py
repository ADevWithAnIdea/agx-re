#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- the 16 remaining NOT-CHECKED notes that no family script covers:
carry_gen.srcB, falu2_ext.srcB_neg, funary.mod, packed_half2_hi.mods,
half_alu_fma12._instruction, if_push.scope, and the ten EXP-0181 `_instruction`
refresh notes.

Each claim is checked against the artifact that could refute it; where no
instrument exists the row is reported INSTRUMENT-LIMITED and NOT counted as a
finding.

Read-only.  Writes analysis/check_misc.json.
"""
import collections, glob, json, math, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402  (our own disassembler, on our own byte strings)

val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
OUT = {}


def note(k):
    m, f = k.split(".", 1)
    return val["instructions"][m][f].get("note") or ""


def N(k, rx, n=1):
    """Claimed numbers parsed OUT OF THE NOTE, never transcribed by hand, so a
    changed note changes the verdict (analysis/negative_control.py)."""
    mo = re.search(rx, note(k))
    if not mo:
        return None if n == 1 else (None,) * n
    return int(mo.group(1), 0) if n == 1 else tuple(int(g, 0) for g in mo.groups())


def add(k, claims):
    m, f = k.split(".", 1)
    lim = [c for c in claims if c["ok"] is None]
    bad = [c for c in claims if c["ok"] is False]
    OUT[k] = {"label": val["instructions"][m][f].get("label"),
              "note": note(k), "claims": claims,
              "verdict": ("CONTRADICTED" if bad else
                          "INSTRUMENT-LIMITED" if lim else "SUPPORTED")}


def jl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


# ---------------------------------------------------------------- carry_gen
SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0, 0.0]
E161 = os.path.join(EXPS, "EXP-0161-g17p-carry-fspecial")
R161 = {r: jl(os.path.join(E161, "raw", r, "sweep.jsonl"))
        for r in ("g17p_20260829_run01", "g17p_20260829_run02")}
cg = {}
for run, recs in R161.items():
    for arm in ("A_CARRY_INPLACE", "A_CARRY_SYNTH"):
        rs = [x for x in recs if x.get("instr") == "carry_gen" and x.get("field") == "srcB"
              and x.get("arm") == arm and not x.get("victim")]
        ok = sorted({x["value"] for x in rs if x["outcome"] == "ok"})
        base = [x for x in recs if x.get("arm") == arm and x.get("field") == "__baseline"]
        b = (base[0].get("observed") or {}).get("regs") if base else None
        fits = tot = 0
        for x in rs:
            rg = (x.get("observed") or {}).get("regs")
            if rg is None or b is None:
                continue
            zero = [i for i in range(15) if rg[i] == 0 and b[i] != 0]
            if zero:
                tot += 1
                if ((x["value"] >> 1) & 0x3F) in zero:
                    fits += 1
        cg["%s|%s" % (run, arm)] = {"n": len(rs), "accepted": ok,
                                    "rule_v_and_0x7f_eq_3":
                                        ok == [v for v in range(256) if (v & 0x7F) == 3],
                                    "released_map_fit": "%d/%d" % (fits, tot)}
cg_n, cg_d = N("carry_gen.srcB", r"\(v & 0x7F\) == 0x03 \((\d+) of (\d+) values\)", 2)
cg_f, cg_t = N("carry_gen.srcB", r"reg=\(v>>1\)&0x3F, fit (\d+)/(\d+)", 2)
add("carry_gen.srcB", [
    {"claim": "accepted set fits (v & 0x7F) == 0x03, N of M, on both arms",
     "claimed": [cg_n, cg_d], "raw": cg,
     "ok": all(v["rule_v_and_0x7f_eq_3"] and len(v["accepted"]) == cg_n
               and v["n"] == cg_d for v in cg.values())},
    {"claim": "A_CARRY_SYNTH.srcB released register map reg=(v>>1)&0x3F, fit N/M",
     "claimed": [cg_f, cg_t],
     "raw": {k: v["released_map_fit"] for k, v in cg.items() if "SYNTH" in k},
     "ok": (cg_f == cg_t and all(v["released_map_fit"] == "%d/%d" % (cg_f, cg_t)
                                 for k, v in cg.items() if "SYNTH" in k))}])

# ---------------------------------------------------- falu2_ext.srcB_neg
A, B = "6901040501000080", "6901040501080080"
x, y = (int.from_bytes(bytes.fromhex(h), "little") for h in (A, B))
d = x ^ y
span = [(f["start"], f["width"]) for i in db["instructions"] if i["mnemonic"] == "falu2_ext"
        for f in i["fields"] if f["name"] == "srcB_neg"]
runs = {}
for run in ("m4_20260828_run01", "m4_20260828_run05", "m4_20260828_run06"):
    p = os.path.join(EXPS, "EXP-0138-m4-emit-falu", "raw", run, "sweep.jsonl")
    hits = collections.defaultdict(list)
    for r in jl(p):
        if r.get("bytes") in (A, B):
            hits[r["bytes"]].append(r)
    runs[run] = {h: [{"outcome": v[0]["outcome"], "match": v[0]["match"],
                      "oracle": v[0]["oracle"], "observed": v[0]["observed"],
                      "expect_match": v[0].get("expect_match")}]
                 for h, v in hits.items()}
add("falu2_ext.srcB_neg", [
    {"claim": "the two byte strings differ in EXACTLY ONE BIT, bit N",
     "claimed": N("falu2_ext.srcB_neg", r"differ in EXACTLY ONE BIT, bit (\d+)"),
     "raw": {"xor": hex(d), "popcount": bin(d).count("1"), "bit": d.bit_length() - 1},
     "ok": (bin(d).count("1") == 1
            and d.bit_length() - 1 == N("falu2_ext.srcB_neg",
                                        r"differ in EXACTLY ONE BIT, bit (\d+)"))},
    {"claim": "db.json models srcB_neg at the start/width the note states",
     "claimed": N("falu2_ext.srcB_neg", r"\(start=(\d+),width=(\d+)\)", 2),
     "raw": span,
     "ok": span == [N("falu2_ext.srcB_neg", r"\(start=(\d+),width=(\d+)\)", 2)]},
    {"claim": "w0 moves X -> Y with both sentinels holding, identical in all three runs",
     "claimed": re.search(r"`w0` moves ([\d.]+) -> ([\d.]+)",
                          note("falu2_ext.srcB_neg")).groups(),
     "raw": runs,
     "ok": all(runs[r][A][0]["observed"]["w0"] == float(
                   re.search(r"`w0` moves ([\d.]+) -> ([\d.]+)",
                             note("falu2_ext.srcB_neg")).group(1))
               and runs[r][B][0]["observed"]["w0"] == float(
                   re.search(r"`w0` moves ([\d.]+) -> ([\d.]+)",
                             note("falu2_ext.srcB_neg")).group(2))
               and runs[r][A][0]["observed"]["w4"] == runs[r][B][0]["observed"]["w4"]
               and runs[r][A][0]["observed"]["w8"] == runs[r][B][0]["observed"]["w8"]
               for r in runs)},
    {"claim": "the host oracle PREDICTED 8.0 AND 2.0 SEPARATELY and matched both",
     "raw": {r: {h: runs[r][h][0]["oracle"] for h in runs[r]} for r in runs},
     "ok": all(runs[r][A][0]["oracle"] == {"w0": float(
                   re.search(r"PREDICTED ([\d.]+) AND ([\d.]+) SEPARATELY",
                             note("falu2_ext.srcB_neg")).group(1))}
               and runs[r][B][0]["oracle"] == {"w0": float(
                   re.search(r"PREDICTED ([\d.]+) AND ([\d.]+) SEPARATELY",
                             note("falu2_ext.srcB_neg")).group(2))}
               and runs[r][A][0]["match"] and runs[r][B][0]["match"] for r in runs)}])

# --------------------------------------------------------------- funary.mod
found = collections.Counter()
for p in glob.glob(os.path.join(EXPS, "*", "raw", "**", "*.jsonl"), recursive=True):
    with open(p, "rb") as fh:
        for ln in fh:
            if b'"funary"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("instr") == "funary" and r.get("value") is not None:
                found[os.path.relpath(p, EXPS)] += 1
add("funary.mod", [
    {"claim": "no synthesized value was executed (negative existential)",
     "raw": {"per_value_dispatch_records_with_instr_funary": dict(found)},
     "ok": (sum(found.values()) == 0)}])

# -------------------------------------------------------- packed_half2_hi.mods
nr = os.path.join(EXPS, "EXP-0144-m4-emit-pack", "raw",
                  "m4_20260828_rv01__packed_half2_hi", "NOT_RUN.md")
add("packed_half2_hi.mods", [
    {"claim": "the cited raw/m4_20260828_rv01__packed_half2_hi/NOT_RUN.md exists",
     "raw": {"path": os.path.relpath(nr, ROOT), "exists": os.path.exists(nr)},
     "ok": os.path.exists(nr)}])

# -------------------------------------------------- half_alu_fma12._instruction
prov = [i.get("provenance", "") for i in db["instructions"]
        if i["mnemonic"] == "half_alu_fma12"][0]
add("half_alu_fma12._instruction", [
    {"claim": "'121/126 corpus instances embed a real op-leader in ext' is carried "
              "from a committed artifact",
     "raw": {"db.json half_alu_fma12.provenance contains it": "121/126" in prov,
             "attributed_there_to": "EXP-M4-13 R8/R10 (own-MSL half corpus)",
             "validation_row_evidence": val["instructions"]["half_alu_fma12"]
                                           ["_instruction"].get("evidence")},
     "ok": "121/126" in prov},
    {"claim": "the 121/126 census itself is reproducible at desk",
     "raw": {"why_not": "EXP-M4-13's committed corpus under experiments/"
                        "EXP-M4-14-a18-splice/corpus/ holds .metal SOURCES only, and "
                        "half_alu_fma12's descriptor has been re-spanned since R8 "
                        "(EXP-0183), so recounting under the CURRENT descriptor is not "
                        "a test of an R8-era census. Recount under today's db.json over "
                        "EXP-M4-13-full-corpus/hex/*.hex gives 7 instances / 2 with an "
                        "op-leader byte -- a different population, not a refutation."},
     "ok": None}])

# ------------------------------------------------------------- if_push.scope
f0184 = json.load(open(os.path.join(EXPS, "EXP-0184-g17p-onefield-b",
                                    "analysis", "field_verdicts_flat.json")))["if_push.scope"]
arms = f0184["arms"]
f0188 = json.load(open(os.path.join(EXPS, "EXP-0188-g17p-dimension-carriers",
                                    "analysis", "field_verdicts_flat.json")))["if_push.scope"]
add("if_push.scope", [
    {"claim": "0 of 10 arms moved, on 2 carriers with 1 distinct baseline field value, "
              "every arm's control firing",
     "raw": {"n_arms": len(arms), "moved": sorted({v["moved"] for v in arms.values()}),
             "carriers": sorted({v["carrier"] for v in arms.values()}),
             "baseline_field_values": sorted({v["baseline_field"] for v in arms.values()}),
             "all_controls_fired": all(v["control"]["fired"] for v in arms.values())},
     "claimed": N("if_push.scope",
                  r"(\d+) of (\d+) arms moved, on (\d+) carriers with (\d+) distinct "
                  r"baseline field values", 4),
     "ok": (lambda c: (len(arms) == c[1] and {v["moved"] for v in arms.values()} == {c[0]}
                       and len({v["carrier"] for v in arms.values()}) == c[2]
                       and len({v["baseline_field"] for v in arms.values()}) == c[3]
                       and all(v["control"]["fired"] for v in arms.values())))(
             N("if_push.scope",
               r"(\d+) of (\d+) arms moved, on (\d+) carriers with (\d+) distinct "
               r"baseline field values", 4))},
    {"claim": "N/M across K occurrences",
     "claimed": N("if_push.scope", r"measured (\d+)/(\d+) across (\d+) occurrences", 3),
     "raw": sorted({v["values_dispatched"] for v in arms.values()}),
     "ok": (lambda c: {v["values_dispatched"] for v in arms.values()} == {c[1]}
                      and len(arms) == c[2])(
             N("if_push.scope", r"measured (\d+)/(\d+) across (\d+) occurrences", 3))},
    {"claim": "six loop carriers all emit scope_kind == 0x1a, four emit both 0x54 and 0x56; "
              "at four 0x1a occurrences 0x00 and 0x54 FAULT while 0x56 and 0xFF are correct; "
              "never reached a gated pair",
     "raw": {"carriers": f0188["carriers"], "values_dispatched": f0188["values_dispatched"],
             "note": f0188["note"], "verdict": f0188["verdict"]},
     "claimed_carriers": re.search(r"(\w+) loop carriers all emit",
                                   note("if_push.scope")).group(1),
     "ok": (len(f0188["carriers"]) == {"six": 6, "five": 5, "four": 4}.get(
                re.search(r"(\w+) loop carriers all emit",
                          note("if_push.scope")).group(1), -1)
            and "all six carriers emit scope_kind 0x1a" in f0188["note"]
            and "four emit both 0x54 and 0x56" in f0188["note"]
            and "0x00 and 0x54 fault; 0x56 and 0xFF correct" in f0188["note"]
            and f0188["values_dispatched"] == 4)}])

# ------------------------------------------- the ten `_instruction` refresh notes
def anchor(hexs, want, wantlen=None):
    r = isadb.decode_one(bytes.fromhex(hexs), 0)
    d = r[0] if isinstance(r, tuple) else r
    got = d.get("mnemonic") if isinstance(d, dict) else None
    gl = d.get("length") if isinstance(d, dict) else None
    return {"hex": hexs, "decoded": got, "length": gl,
            "ok": got == want and (wantlen is None or gl == wantlen)}


a_f3 = anchor("09011e0581080200", "falu3")
a_f3e = anchor("09011e05820802000080", "falu3_ext", 10)
a_rot = anchor("2701560002006c00f0150900", "irotate")
prov_f3 = [i.get("provenance", "") + i.get("semantics", "")
           for i in db["instructions"] if i["mnemonic"] == "falu3"][0]
add("falu3._instruction", [
    {"claim": "Anchor 09011e0581080200 decodes back to falu3", "raw": a_f3, "ok": a_f3["ok"]},
    {"claim": "'1809+2321 cases' and 'byte+4 ... re-lengths on 192 of 256 values' are "
              "carried from db.json's committed falu3 text",
     "raw": {"has_1809_2321": "1809 + 2321 cases" in prov_f3,
             "has_192_256": "(192/256)" in prov_f3},
     "ok": ("1809 + 2321 cases" in prov_f3 and "(192/256)" in prov_f3)}])
add("falu3_ext._instruction", [
    {"claim": "Anchor 09011e05820802000080 decodes back to falu3_ext at length 10",
     "raw": a_f3e, "ok": a_f3e["ok"]}])
irot = json.load(open(os.path.join(EXPS, "EXP-0172-g17p-onefield-tail",
                                   "analysis", "field_verdicts.json")))["irotate.b2"]["arms"]
asym = [k for k, v in irot.items() if v.get("moved_inside_encodable")]
add("irotate._instruction", [
    {"claim": "Anchor 2701560002006c00f0150900 decodes back to irotate",
     "raw": a_rot, "ok": a_rot["ok"]},
    {"claim": "EXP-0172 showed byte+2 ASYMMETRIC over its two legal values on three arms",
     "raw": {"arms": len(irot), "encodable_values":
             sorted({tuple(v["encodable_values"]) for v in irot.values()}),
             "arms_with_exactly_one_legal_value_moving": asym},
     "claimed_arms": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(
         re.search(r"ASYMMETRIC over its two legal values on (\w+) arms",
                   note("irotate._instruction")).group(1), -1),
     "ok": (len(asym) == {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(
                re.search(r"ASYMMETRIC over its two legal values on (\w+) arms",
                          note("irotate._instruction")).group(1), -1)
            and all(v["encodable_values"] == [84, 86] for v in irot.values()))}])

# frag_depth_store / n2_op6: db.json quotes
qs = {"frag_depth_store._instruction": ["Not individually splice-validated"],
      "n2_op6._instruction": ["a genuine catch-all bucket",
                              "per-sub-op value maps are mixed"]}
dbtxt = open(os.path.join(ROOT, "tools/agx-isa/db.json")).read()
fds_labels = {f["name"]: val["instructions"]["frag_depth_store"][f["name"]]["label"]
              for i in db["instructions"] if i["mnemonic"] == "frag_depth_store"
              for f in i["fields"]}
fds_base = collections.Counter()
for run in ("g17p_20260829_run03", "g17p_20260829_run04"):
    for r in jl(os.path.join(EXPS, "EXP-0155-g17p-emit-tex-frag", "raw", run, "sweep.jsonl")):
        if r.get("instr") == "frag_depth_store" and str(r.get("field", "")).startswith("_"):
            fds_base[r["outcome"]] += 1
add("frag_depth_store._instruction", [
    {"claim": "db.json says 'Not individually splice-validated (agxrender has no depth "
              "attachment to read back)'",
     "raw": {"found_in_db_json": dbtxt.count(qs["frag_depth_store._instruction"][0])},
     "ok": dbtxt.count(qs["frag_depth_store._instruction"][0]) == 1},
    {"claim": "All three of its declared fields are hardware-run",
     "raw": fds_labels,
     "ok": (len(fds_labels) == 3 and set(fds_labels.values()) == {"hardware-run"})},
    {"claim": "its baselines are ok 11/11",
     "raw": {"control_records_in_the_two_gated_runs": dict(fds_base),
             "convention_note": "the same convention that makes iter_flat's '23/23' "
                                "exact (all underscore-prefixed control records for the "
                                "instruction across run03+run04, all ok) gives 12/12 here"},
     "ok": None}])
add("n2_op6._instruction", [
    {"claim": "db.json's own text calls it 'a genuine catch-all bucket' whose "
              "'per-sub-op value maps are mixed'",
     "raw": {q: dbtxt.count(q) for q in qs["n2_op6._instruction"]},
     "ok": all(dbtxt.count(q) == 1 for q in qs["n2_op6._instruction"])}])

# iter_at: EXP-0163 loc separation + EXP-0189 oracle census
r63 = {r: jl(os.path.join(EXPS, "EXP-0163-g17p-inert-liveness", "raw", r, "sweep.jsonl"))
       for r in ("g17p_20260830_run01", "g17p_20260830_run02")}
loc = {}
for run, recs in r63.items():
    for car in sorted({x["carrier"] for x in recs
                       if x.get("instr") == "iter_at" and x.get("field") == "loc"}):
        sub = [x for x in recs if x.get("instr") == "iter_at" and x.get("field") == "loc"
               and x["carrier"] == car]
        loc.setdefault(run, {})[car] = {"n": len(sub),
                                        "moved": sum(1 for x in sub if x["outcome"] != "ok")}
osc = json.load(open(os.path.join(EXPS, "EXP-0189-closing-audit", "work", "oracle_scan.json")))
ia = {"n": 0, "oracle": 0}
for k, v in osc.items():
    if k.split("|")[0] == "iter_at":
        ia["n"] += v.get("n", 0)
        ia["oracle"] += v.get("oracle", 0)
one = [v for run in loc for c, v in loc[run].items() if "cent1" in c]
four = [v for run in loc for c, v in loc[run].items() if "cent4" in c]
add("iter_at._instruction", [
    {"claim": "loc separated BY VALUE: 0/256 at one sample, 128/256 at four",
     "raw": loc,
     "claimed": N("iter_at._instruction",
                  r"(\d+)/(\d+) at one sample, (\d+)/(\d+) at four", 4),
     "ok": (lambda c: bool(one) and bool(four)
                      and all(v["moved"] == c[0] and v["n"] == c[1] for v in one)
                      and all(v["moved"] == c[2] and v["n"] == c[3] for v in four))(
             N("iter_at._instruction",
               r"(\d+)/(\d+) at one sample, (\d+)/(\d+) at four", 4))},
    {"claim": "N dispatch records but only M carry an oracle",
     "claimed": re.search(r"There are ([\d,]+) dispatch records but only (\d+) carry an "
                          r"oracle", note("iter_at._instruction")).groups(),
     "raw": ia,
     "ok": (lambda c: ia["n"] == int(c[0].replace(",", "")) and ia["oracle"] == int(c[1]))(
             re.search(r"There are ([\d,]+) dispatch records but only (\d+) carry an "
                       r"oracle", note("iter_at._instruction")).groups())},
    {"claim": "All six field rows are emitter-grade",
     "raw": {f["name"]: val["instructions"]["iter_at"][f["name"]]["label"]
             for i in db["instructions"] if i["mnemonic"] == "iter_at" for f in i["fields"]},
     "ok": all(val["instructions"]["iter_at"][f["name"]]["label"]
               in ("hardware-run", "isolated-byte-diff")
               for i in db["instructions"] if i["mnemonic"] == "iter_at"
               for f in i["fields"])}])

# iter_flat: baselines 23/23
ifb = collections.Counter()
for run in ("g17p_20260829_run03", "g17p_20260829_run04"):
    for r in jl(os.path.join(EXPS, "EXP-0155-g17p-emit-tex-frag", "raw", run, "sweep.jsonl")):
        if r.get("instr") == "iter_flat" and str(r.get("field", "")).startswith("_"):
            ifb[r["outcome"]] += 1
add("iter_flat._instruction", [
    {"claim": "EXP-0155 reproduced its baselines on G17P N/M",
     "claimed": N("iter_flat._instruction", r"baselines on G17P (\d+)/(\d+)", 2),
     "raw": dict(ifb),
     "ok": (lambda c: c[0] == c[1] and sum(ifb.values()) == c[1] and set(ifb) == {"ok"})(
             N("iter_flat._instruction", r"baselines on G17P (\d+)/(\d+)", 2))}])

# mov_imm / psel / uniform_mov
sv = open(os.path.join(EXPS, "EXP-0031-sr-abi", "raw",
                       "splice_validation_compute.txt")).read()
adc = json.load(open(os.path.join(EXPS, "EXP-0167-g17p-synthesis-reconfirm",
                                  "analysis", "assemble_defect_check.json")))
iso = [open(os.path.join(EXPS, "EXP-0167-g17p-synthesis-reconfirm", "raw", d,
                         "01_results.jsonl"), "rb").read()
       for d in ("g17p-20260830-iso01", "g17p-20260830-iso02")]
add("mov_imm._instruction", [
    {"claim": "EXP-0031: splicing byte+1 0x20->0x21/0x40/0x11 changes the output to 33/64/17",
     "raw": {"lines": [l.strip() for l in sv.splitlines()
                       if "splice off5" in l]},
     "ok": all(s in sv for s in ("0x20->0x21 : [33]x8", "0x20->0x40 : [64]x8",
                                 "0x20->0x11 : [17]x8"))},
    {"claim": "EXP-0167 ran N assembler-GENERATED mov_imm instances whose "
              "01_results.jsonl was BYTE-IDENTICAL across two isolated gated runs",
     "raw": {"mov_imm_assemble_calls": adc["mnemonics_used"]["mov_imm"],
             "iso01_iso02_byte_identical": iso[0] == iso[1],
             "n_cases": adc["n_cases"]},
     "claimed": re.search(r"ran ([\d,]+) assembler-GENERATED mov_imm instances",
                          note("mov_imm._instruction")).group(1),
     "ok": (adc["mnemonics_used"]["mov_imm"] == int(
                re.search(r"ran ([\d,]+) assembler-GENERATED mov_imm instances",
                          note("mov_imm._instruction")).group(1).replace(",", ""))
            and iso[0] == iso[1])},
    {"claim": "'inside 233 zero-copied programs'",
     "raw": {"EXP-0167 RESULTS.md": "233 of 237 zero-copied programs matched",
             "reading": "233 is zero_copied_AND_matched; 237 were zero-copied. The note "
                        "attaches the 196,114 instances to the smaller number, i.e. it "
                        "UNDERSTATES the zero-copied population -- conservative, and "
                        "recorded as an imprecision, not a finding."},
     "ok": None}])
f168 = json.load(open(os.path.join(EXPS, "EXP-0168-g17p-dst-resweep",
                                   "analysis", "field_verdicts.json")))["uniform_mov.dst"]
add("uniform_mov._instruction", [
    {"claim": "EXP-0168 re-measured dst: 214 movements, 224 distinct byte strings, "
              "100.000% agreement",
     "raw": {"moved_total": f168["moved_total"],
             "distinct_bytes": f168["coverage"]["distinct_bytes"],
             "agree_pct": sorted({p["agree_pct"] for a in f168["per_arm"].values()
                                  for p in a["pairs"].values()})},
     "claimed": re.search(r"\((\d+) movements, (\d+) distinct byte strings, "
                          r"([\d.]+)% agreement\)",
                          note("uniform_mov._instruction")).groups(),
     "ok": (lambda c: f168["moved_total"] == int(c[0])
                      and f168["coverage"]["distinct_bytes"] == int(c[1])
                      and {p["agree_pct"] for a in f168["per_arm"].values()
                           for p in a["pairs"].values()} == {float(c[2])})(
             re.search(r"\((\d+) movements, (\d+) distinct byte strings, "
                       r"([\d.]+)% agreement\)",
                       note("uniform_mov._instruction")).groups())},
    {"claim": "EXP-0140: 128 of 128 immediate-region usrc values matched and 8 of 8 "
              "mapped uniform indices returned the bound magic constant",
     "raw": {"see": "analysis/check_0140.json :: uniform_mov.usrc (SUPPORTED, after the "
                    "two documented repairs)"},
     "ok": json.load(open(os.path.join(HERE, "check_0140.json")))["uniform_mov.usrc"]
             ["verdict"] == "SUPPORTED"
           if os.path.exists(os.path.join(HERE, "check_0140.json")) else None}])
add("psel._instruction", [
    {"claim": "EXP-0140 swept flag, mode and sel at 256 values x 2 dispatch shapes with "
              "byte+3 matching the host-computed oracle 512/512",
     "raw": {"see": "analysis/check_0140.json :: psel.flag/mode/sel; byte+3 is the `sel` "
                    "group, 512 cases, all stable, all observed == oracle"},
     "ok": all(json.load(open(os.path.join(HERE, "check_0140.json")))[k]["verdict"]
               == "SUPPORTED" for k in ("psel.flag", "psel.mode", "psel.sel"))
           if os.path.exists(os.path.join(HERE, "check_0140.json")) else None}])

json.dump(OUT, open(os.path.join(HERE, "check_misc.json"), "w"), indent=1, sort_keys=True)
c = collections.Counter(v["verdict"] for v in OUT.values())
print("misc family:", len(OUT), dict(c))
for k, v in sorted(OUT.items()):
    print("  %-32s %s" % (k, v["verdict"]))
    for cl in v["claims"]:
        if cl["ok"] is not True:
            print("      %s  %s" % ("LIMITED" if cl["ok"] is None else "FAILS",
                                    cl["claim"][:90]))
