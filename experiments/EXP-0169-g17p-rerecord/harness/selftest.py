#!/usr/bin/env python3
"""EXP-0169 offline CODE test -- no GPU, no device, NOT evidence.

Runs on the repo host (where GPU work is retired) to prove the matrix builder,
the bit surgery, the crossings and the semantic oracle are correct BEFORE any
device time is spent. It builds a stand-in anchor report from instructions
ASSEMBLED by tools/agx-isa (not from any compiled shader), so nothing it
produces is a hardware observation and nothing it writes goes under raw/.

  python3 harness/selftest.py
"""
from __future__ import print_function

import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import casematrix as CM      # noqa: E402
import run as R              # noqa: E402

FAIL = []


def check(name, cond, detail=""):
    print("%-46s %s %s" % (name, "ok" if cond else "FAIL", detail))
    if not cond:
        FAIL.append(name)


def fake_report():
    """A stand-in anchor report: each 'kernel' is a short ASSEMBLED program
    containing one instruction of the family an arm wants. This exercises the
    resolver and the bit surgery; it is NOT a compiled shader and NOT evidence."""
    def prog(instr_bytes):
        body = instr_bytes + H.mov_imm(1, 5) + H.stop()
        return body
    mk = {}
    falu2 = H.isadb.assemble("falu2", {
        "dst": 1, "srcA_size": 1, "srcA_reg": 2, "opsel": 4, "opflags": 0,
        "srcB_size": 1, "srcB_reg": 3, "ctrl": 0, "srcB_imm": 0,
        "srcA_class": 0, "srcB_class": 0, "srcB_neg": 0, "mod_hi": 0,
        "srcA_reg_top": 0, "srcB_reg_top": 0})
    falu2i = H.falu2i_raw(1, 2, 3.0, mods=0)
    mk["k_fadd"] = prog(falu2)
    mk["k_faddi"] = prog(falu2i)
    out = {}
    for fn, body in mk.items():
        recs, leftover = H.isadb.disassemble(body)
        off, toks = 0, []
        for r in recs:
            toks.append({"off": off, "len": r["length"], "mn": r["mnemonic"],
                         "bytes": body[off:off + (r["length"] or 0)].hex()})
            if r["length"] is None:
                break
            off += r["length"]
        out[fn] = {"main_len": len(body), "main_hex": body.hex(),
                   "leftover": leftover.hex(), "tokens": toks}
    return out


def main():
    rep = fake_report()
    cases, resolved, misses = CM.build_cases(rep)
    check("build_cases produced cases", len(cases) > 0, "%d cases" % len(cases))
    check("matrix sha is deterministic",
          CM.matrix_sha256(cases) == CM.matrix_sha256(CM.build_cases(rep)[0]))

    # --- bit surgery round trip ------------------------------------------
    spec = CM.INS["falu2"]
    F = {f["name"]: f for f in spec["fields"]}
    blk = bytes.fromhex(rep["k_fadd"]["tokens"][0]["bytes"])
    good = True
    for f in spec["fields"]:
        for v in (0, 1, (1 << f["width"]) - 1):
            nb = CM.set_field(blk, 0, f["start"], f["width"], v)
            if CM.get_field(nb, 0, f["start"], f["width"]) != v:
                good = False
            for g in spec["fields"]:
                if g["name"] == f["name"]:
                    continue
                if (g["start"] + g["width"] <= f["start"]
                        or f["start"] + f["width"] <= g["start"]):
                    if CM.get_field(nb, 0, g["start"], g["width"]) != \
                            CM.get_field(blk, 0, g["start"], g["width"]):
                        good = False
    check("set_field/get_field are exact and non-overlapping", good)

    # --- coverage: every falu2/falu2i field swept over its whole range ----
    for mn in ("falu2", "falu2i"):
        for f in CM.INS[mn]["fields"]:
            vals = {c["value"] for c in cases
                    if c["instr"] == mn and c["field"] == f["name"]
                    and c.get("cross") is None}
            want = (1 << f["width"]) if f["width"] <= 8 else 256
            check("%s.%s dense coverage" % (mn, f["name"]),
                  len(vals) >= want, "%d/%d" % (len(vals), want))

    # --- the crossings ----------------------------------------------------
    cx = [c for c in cases if c["instr"] == "falu2" and c.get("cross")]
    kinds = sorted({c["cross"].split(",")[0].split("=")[0] for c in cx})
    check("falu2 crossings present", len(cx) > 0,
          "%d cases, dims %s" % (len(cx), kinds))
    imm = collections.Counter((c["arm"], c["carrier"]) for c in cases
                              if c["instr"] == "falu2i" and c.get("cross"))
    check("falu2i full immediate space per arm",
          bool(imm) and all(v == 2 * 16 * 8 * 2 for v in imm.values()),
          json.dumps({"%s@%s" % k: v for k, v in imm.items()}))

    # --- the semantic oracle ---------------------------------------------
    seeds = H.seed_values("float", 1)
    checked = 0
    agree = True
    for c in cx:
        if c["field"] != "srcB_reg" or "srcB_class=1" not in (c["cross"] or ""):
            continue
        o = R.sem_oracle(c, seeds)
        if o is None:
            continue
        checked += 1
        v = c["value"]
        k = H.inline_minifloat(v)
        if k is None:
            continue
        exp = -k if "srcB_neg=0" in c["cross"] else k
        if abs(o["srcB"] - exp) > 0:
            agree = False
    check("sem_oracle reproduces the inline-minifloat claim", agree and checked,
          "%d values" % checked)

    # a spot value from EXP-0138's HW-confirmed list
    known = {64: 0.0, 66: 0.0625, 95: 1.875, 96: 2.0, 112: 8.0, 120: 16.0,
             127: 30.0}
    check("inline_minifloat matches EXP-0138's confirmed points",
          all(H.inline_minifloat(k) == v for k, v in known.items()))

    # --- programs build at a plausible carrier length ---------------------
    for kind in ("int", "float", "load"):
        p = H.synth_program(kind, blk, 2412)
        check("synth_program(%s) builds" % kind, len(p) == 2412)
    st = H.device_store(**CM.DSTORE_BASE)
    check("store_probe_program builds",
          len(H.store_probe_program("int", st, 2412)) == 2412)

    # --- reg_move synth bases tokenize as their target descriptor ---------
    for mn, p in CM.SYNTH_BASE.items():
        b = H.regmove(p["dst"], p["src"], p["form"], p["opdesc"])
        check("SYNTH_BASE[%s] tokenizes as %s" % (mn, mn),
              H.tokenize_first(b) == mn, H.tokenize_first(b) or "?")

    # --- ladder steps exist for every arm ---------------------------------
    lad = {}
    for c in cases:
        if c["field"].startswith("__ladder"):
            lad.setdefault((c["arm"], c["carrier"]), []).append(c["field"])
    for c in cases:
        if c["field"] == "__falsifier_byte0":
            k = (c["arm"], c["carrier"])
            check("ladder present for %s@%s" % k, len(lad.get(k, [])) >= 2,
                  ",".join(sorted(set(lad.get(k, [])))))

    # --- end-to-end: matrix -> fake raw -> verdicts.py -------------------
    # A synthetic two-run pair under work/ (NEVER under raw/), so the whole
    # analysis path -- coverage counting, the gate, the reproduction verdict --
    # is proven before any device time is spent. The observations are
    # fabricated by a deterministic rule, so nothing here is evidence and
    # nothing here can be mistaken for it.
    import subprocess
    vt = EXP / "work" / "vtest"
    if vt.exists():
        import shutil
        shutil.rmtree(str(vt))
    seedmap = H.seed_values("float", 1)
    for runid in ("vrun01", "vrun02"):
        d = vt / runid
        d.mkdir(parents=True)
        with open(str(d / "sweep.jsonl"), "w") as fh:
            for i, c in enumerate(cases):
                blk = bytes.fromhex(c["bytes"])
                tgt = c.get("tgt") or 0
                # deterministic pseudo-observation: a live field moves the dump,
                # an "inert" one (chosen by name) never does.
                inert = c["field"] in ("srcA_reg_top", "srcB_reg_top")
                h = 0 if inert else (int(c["bytes"], 16) % 7919)
                regs = [(h + j) & 0xFFFFFFFF for j in range(16)]
                oc = "ok" if h == 0 else "wrong_value"
                pred = c.get("predict", "")
                if c["field"].startswith("__"):
                    oc = "wrong_value" if pred in ("not_ok", "move") else "ok"
                rec = {"idx": c["idx"], "seq": i + 1, "t": 0.0,
                       "arm": c["arm"], "carrier": c["carrier"],
                       "instr": c["instr"], "field": c["field"],
                       "value": c["value"], "bytes": c["bytes"],
                       "mode": c["mode"], "kind": c["kind"],
                       "cross": c.get("cross"), "tgt": tgt,
                       "observed": {"regs": regs, "pre": 90, "post": 111,
                                    "stray": [], "n_stray": 0},
                       "oracle": {"digest": "x", "sem": None},
                       "match": oc == "ok", "sem_match": None,
                       "outcome": oc, "rt_ok": True, "tok_instr": c["instr"],
                       "victim": False, "sentinel_bad": False,
                       "attempts": [], "predict": pred,
                       "byte_index": c.get("byte_index"),
                       "fstart": c.get("fstart"), "fwidth": c.get("fwidth"),
                       "foreign": c.get("foreign", False), "note": ""}
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
    r = subprocess.run([sys.executable, str(EXP / "analysis" / "verdicts.py"),
                        "--out-dir", str(vt),
                        str(vt / "vrun01"), str(vt / "vrun02")],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode()
    check("verdicts.py runs end to end", r.returncode == 0, out.strip()[-160:])
    fvp = vt / "field_verdicts.json"
    check("field_verdicts.json written", fvp.exists())
    if fvp.exists():
        fv = json.loads(fvp.read_text())
        rows = {k: v for k, v in fv.items() if k != "_meta"}
        need = ("values_dispatched", "distinct_bytes", "encodable_range",
                "start", "width", "coverage_pct", "thin", "under_covered")
        missing = [k for k, v in rows.items() if any(n not in v for n in need)]
        check("every row carries the coverage keys", not missing,
              "%d rows, %d missing" % (len(rows), len(missing)))
        f2 = rows.get("falu2.mod_hi", {})
        check("falu2.mod_hi coverage is exact",
              f2.get("values_dispatched") == 16 and f2.get("encodable_range") == 16
              and f2.get("thin") is False,
              json.dumps({k: f2.get(k) for k in need}))
        ctrl = rows.get("falu2.ctrl", {})
        check("falu2.ctrl (7 bits) coverage is exact",
              ctrl.get("values_dispatched") == 128
              and ctrl.get("encodable_range") == 128,
              json.dumps({k: ctrl.get(k) for k in need}))
        wide = rows.get("device_store.idx_off", {})
        check("device_store.idx_off byte sweep counted in FIELD units",
              wide.get("width") == 11 and wide.get("encodable_range") == 2048
              and (wide.get("values_dispatched") or 0) > 256,
              json.dumps({k: wide.get(k) for k in need}))
        check("no row is UNDER-COVERED (bit surgery never sticks bits)",
              not [k for k, v in rows.items() if v.get("under_covered")],
              str([k for k, v in rows.items() if v.get("under_covered")])[:120])
        check("foreign fields get no verdict",
              all(rows[k]["label"] == "untested"
                  for k in rows if k.endswith(".dst") or k == "get_sr.form"),
              "%d foreign rows" % len([k for k in rows if k.endswith(".dst")]))
        check("internal _fvals stripped from output",
              not any("_fvals" in x for v in rows.values()
                      for x in (v.get("arms") or [])))

    (EXP / "work").mkdir(exist_ok=True)
    (EXP / "work" / "selftest.json").write_text(json.dumps(
        {"cases": len(cases), "failures": FAIL,
         "resolved": {"%s/%s/%s" % k: v for k, v in resolved.items()},
         "misses": misses,
         "note": "OFFLINE CODE TEST on a stand-in assembled anchor report. "
                 "NOT a hardware observation and NOT evidence."},
        indent=1, sort_keys=True))
    print("\n%d checks failed" % len(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
