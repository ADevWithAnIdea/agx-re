#!/usr/bin/env python3
"""EXP-0187 TARGET-2 OPCODE CENSUS: can any MSL we author make the compiler emit
`cubearray_coord_const`, `mesh_out_src`, or `n4_cf_word`?

Runs ON THE NEO. NO DEVICE SWEEP -- this is compile + disassemble only, with our
own tools, and it is deliberately the whole of target 2 unless it finds a
carrier. All three fields have been DECLINED on a MEASURED basis before:

  cubearray_coord_const.b3  0 occurrences across 24 carriers (EXP-0184);
                            0 firings in 1080 corpus files (EXP-0148)
  mesh_out_src.sel          0 occurrences across 24 carriers (EXP-0184) --
                            but all 24 were COMPUTE kernels and this op is
                            mesh-stage-only, so the census was blind by
                            construction. This is the first mesh-pipeline attempt.
  n4_cf_word.b3             EXP-0172 dispatched all 256 values: the WHOLE 4-byte
                            word had no detection power ("no observable effect at
                            all, not merely b3" -- its DEF-0172-4)

So the question answered here is the prior one -- *does a carrier exist* -- and a
bounded negative ("N constructs tried, none emitted it") is a first-class result.
Device time is not spent on a carrier that could not be built.

TWO NUMBERS PER CONSTRUCT, because they answer different questions:
  signature hits : the raw `match`-satisfying byte pattern anywhere in our own
                   compiled code. An UPPER BOUND -- a hit may be another op's
                   operand tail, which is exactly what EXP-0148 found for
                   `cubearray_coord_const` (its `f0 c0 04` sits INTERIOR to a
                   12-byte `tex_addr_setup` token and cannot fire).
  walk hits      : the mnemonic actually produced by a resync tokenizer walk from
                   offset 0. This is the number that decides "the compiler emits
                   it". A walk that stops early can only UNDERCOUNT, so the
                   leftover is recorded too.

Output: `analysis/census.json` (pulled back into the repo) + stdout summary.
CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled and scanned.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import locate187 as L        # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work" / "census2"

# (construct id, metal file, shdump args, target mnemonic(s))
COMPUTE = [
    ("k_cube187.metal", ["k_cu_sample", "k_cu_arr", "k_cu_arr_n", "k_cu_arr_lod",
                         "k_cu_arr_grad", "k_cu_arr_bias", "k_cu_arr_gather",
                         "k_cu_gather", "k_cu_depth", "k_cu_half", "k_cu_read",
                         "k_cu_dyn"]),
    ("k_cf187.metal", ["k_cf_if", "k_cf_if3", "k_cf_loop", "k_cf_barrier",
                       "k_cf_divbar", "k_cf_rq", "k_cf_ret", "k_cf_simd"]),
]
# (construct id, object fn or None, mesh fn, fragment fn, stages to scan)
MESH = [
    ("mesh_tri",    "obj_main", "mesh_tri",    "frag_main"),
    ("mesh_vonly",  "obj_main", "mesh_vonly",  "frag_vonly"),
    ("mesh_wide",   "obj_main", "mesh_wide",   "frag_wide"),
    ("mesh_line",   "obj_main", "mesh_line",   "frag_main"),
    ("mesh_dyn",    "obj_main", "mesh_dyn",    "frag_main"),
    ("mesh_noobj",  None,       "mesh_noobj",  "frag_main"),
]
TARGETS = ["cubearray_coord_const", "mesh_out_src", "n4_cf_word", "n4_rt_word"]
FIELD = {"cubearray_coord_const": "b3", "mesh_out_src": "sel",
         "n4_cf_word": "b3", "n4_rt_word": "dst"}


def scan(main):
    rec = {}
    by, ntok, leftover = L.walk(main)
    rec["walk_tokens"] = ntok
    rec["walk_leftover_hex"] = leftover
    for mn in TARGETS:
        s, w = L.field_span(mn, FIELD[mn])
        hits = L.find_occurrences(main, mn, step=1)
        for h in hits:
            raw = bytes.fromhex(h["bytes"])
            h["baseline_field"] = (int.from_bytes(raw, "little") >> s) & ((1 << w) - 1)
        walk_offs = by.get(mn, [])
        rec[mn] = {
            "signature_hits": len(hits),
            "signature_hits_aligned": sum(1 for h in hits if h["parcel_aligned"]),
            "walk_hits": len(walk_offs),
            "walk_offsets": walk_offs[:64],
            "distinct_baseline_field": sorted({h["baseline_field"] for h in hits}),
            "occurrences": hits[:64],
        }
    return rec


def main():
    out = {"_doc": __doc__.strip().splitlines()[0], "constructs": {}}
    for metal, funcs in COMPUTE:
        for fn in funcs:
            key = "%s:%s" % (metal, fn)
            rec = {"metal": metal, "func": fn, "stage": "compute"}
            try:
                arch, off, mainb = L.compile_carrier(
                    BIN, EXP / "kernels" / metal, fn, WORK)
            except Exception as e:                              # noqa: BLE001
                rec["error"] = str(e)[:600]
                out["constructs"][key] = rec
                print("%-34s COMPILE FAIL %s" % (fn, str(e)[:90]))
                continue
            rec.update(main_off=off, main_len=len(mainb),
                       main_sha256=hashlib.sha256(mainb).hexdigest())
            rec.update(scan(mainb))
            out["constructs"][key] = rec
            print("%-34s len=%-6d %s" % (fn, len(mainb),
                  " ".join("%s sig=%d walk=%d" % (m[:14], rec[m]["signature_hits"],
                                                  rec[m]["walk_hits"])
                           for m in TARGETS)))
    for cid, obj, mesh, frag in MESH:
        extra = ["--mesh", mesh, "--fragment", frag]
        if obj:
            extra += ["--object", obj]
        else:
            extra += ["--no-object"]
        for stage in ("mesh", "object"):
            if stage == "object" and not obj:
                continue
            key = "k_mesh187.metal:%s/%s" % (cid, stage)
            rec = {"metal": "k_mesh187.metal", "func": mesh, "stage": stage,
                   "construct": cid}
            try:
                arch, off, mainb = L.compile_carrier(
                    BIN, EXP / "kernels" / "k_mesh187.metal", cid, WORK,
                    tool="shdump_mesh", extra=extra, stage=stage)
            except Exception as e:                              # noqa: BLE001
                rec["error"] = str(e)[:600]
                out["constructs"][key] = rec
                print("%-34s COMPILE/EXTRACT FAIL %s" % (key, str(e)[:80]))
                continue
            rec.update(main_off=off, main_len=len(mainb),
                       main_sha256=hashlib.sha256(mainb).hexdigest())
            rec.update(scan(mainb))
            out["constructs"][key] = rec
            print("%-34s len=%-6d %s" % (key, len(mainb),
                  " ".join("%s sig=%d walk=%d" % (m[:14], rec[m]["signature_hits"],
                                                  rec[m]["walk_hits"])
                           for m in TARGETS)))

    summary = {}
    for mn in TARGETS:
        tried = [k for k, r in out["constructs"].items() if mn in r]
        failed = [k for k, r in out["constructs"].items() if "error" in r]
        sig = {k: r[mn]["signature_hits"] for k, r in out["constructs"].items()
               if mn in r and r[mn]["signature_hits"]}
        walk = {k: r[mn]["walk_hits"] for k, r in out["constructs"].items()
                if mn in r and r[mn]["walk_hits"]}
        summary[mn] = {"constructs_compiled": len(tried),
                       "constructs_failed_to_compile": len(failed),
                       "constructs_with_signature_hits": sig,
                       "constructs_with_walk_hits": walk,
                       "emitted": bool(walk)}
    out["summary"] = summary
    p = EXP / "analysis" / "census.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\n" + json.dumps(summary, indent=1))
    print("wrote", p)


if __name__ == "__main__":
    main()
