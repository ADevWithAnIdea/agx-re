#!/usr/bin/env python3
"""DRY-RUN ONLY. Fabricates an anchor_report.json shaped like the real one, so
the case-matrix generator and the program builder can be exercised on the repo
host WITHOUT compiling any MSL (GPU work is retired on this machine).

This is a TEST FIXTURE, never evidence: it is written under work/, is not in
raw/, and the real anchor report is produced on the target by harness/anchors.py.
"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import isa_helpers as H
isadb = H.isadb

def mk(instrs):
    main = b"".join(instrs)
    recs, left = isadb.disassemble(main)
    toks, off, occ = [], 0, {}
    for r in recs:
        ln = r.get("length")
        n = occ.get(r["mnemonic"], 0); occ[r["mnemonic"]] = n + 1
        toks.append({"i": len(toks), "off": off, "len": ln, "mn": r["mnemonic"],
                     "occ": n, "fields": r.get("fields"),
                     "bytes": main[off:off+ln].hex() if ln else None,
                     "liftable": True})
        if ln is None: break
        off += ln
    return {"main_len": len(main), "main_hex": main.hex(), "leftover": left.hex(),
            "region_off": 0, "region_len": len(main), "archive": "FAKE",
            "counts": occ, "tokens": toks}

A = lambda mn, f: isadb.assemble(mn, f)
rep = {}
rep["k_uni_each"] = mk([A("uniform_mov", {"dst": 5, "usrc": 0x1c})])
rep["k_fadd"] = mk([A("falu2", {"dst": 2, "srcA_size":1, "srcA_reg":3, "opsel":0,
    "opflags":0, "srcB_size":1, "srcB_reg":4, "ctrl":0, "srcB_imm":0,
    "srcA_class":0, "srcB_class":0, "srcB_neg":0, "mod_hi":0xC,
    "srcA_reg_top":0, "srcB_reg_top":0})])
rep["k_faddi"] = mk([H.falu2i_raw(2, 3, 3.0)])
rep["k_getsr"] = mk([A("get_sr", {"form":0, "dst":4, "sr_sel":0x98,
                                  "dp_width":0x11, "dp_marker":6, "dst_hi":0})])
rep["k_f2i"] = mk([A("cvt_f2i", {"mode":0x56, "dst":0x18, "src_class":0x02,
    "src":0x00, "cvtop":0x96, "signflag":0x48, "dst_class":0x03, "b9":0})])
rep["k_f2i_consumed"] = mk([A("cvt_f2i", {"mode":0x54, "dst":0x18,
    "src_class":0x02, "src":0x00, "cvtop":0x96, "signflag":0x48,
    "dst_class":0x03, "b9":0})])
for k in ("k_unpack_unorm2", "k_unpack_snorm2", "k_unpack_consumed"):
    rep[k] = mk([A("unpack_convert", {"src_class":0x04, "cache":0x56, "dst":0,
        "inert4":0, "src":0x08, "opdesc":0x0e, "size":0xa, "fmt_sel":0xc})])
rep["k_sum"] = mk([A("falu_acc", {"dst":2, "srcA":8, "op":0, "cache":0, "srcB":10})])
rep["k_sum_reuse"] = rep["k_sum"]
rep["k_rot_var"] = mk([A("shift_amt_move", {"dst":3, "src_reg":5, "src_flag":0,
                                            "kind":0x1c, "op_desc":0x08})])
rep["k_rot_uni"] = rep["k_rot_var"]
rep["k_copysign"] = mk([A("copysign", {"operands": 0})])
rep["k_copysign_rp"] = rep["k_copysign"]
rep["k_f2h_standalone"] = mk([A("cvt_f2h", {"b1":0x03, "op":0x14, "src":0x81,
                                            "b4":0x04, "tail":0x02})])
rep["k_f2h_consumed"] = rep["k_f2h_standalone"]
for k in ("k_pack_unorm2", "k_pack_snorm2", "k_pack_unorm4"):
    rep[k] = mk([A("pack_convert", {"src_desc":0x04, "fmt_class":0x56, "dst":0x18,
        "mode":0x02, "src_lane0":0x08, "src_lane1":0x02, "b7":0x50,
        "cvt_enable":0x44, "fmt_sel":0x82})])
# STYLE-P fakes: a whole "main" with the target inside
rep["k_if_flat"] = mk([A("if_push", {"scope":0x54, "scope_kind":0x01}),
                       A("stop", {"reserved":0})])
rep["k_if_nest3"] = mk([A("if_push", {"scope":0x54, "scope_kind":0x01}),
                        A("if_push", {"scope":0x56, "scope_kind":0x01}),
                        A("if_push", {"scope":0x54, "scope_kind":0x01}),
                        A("stop", {"reserved":0})])
rep["k_if_nest2"] = rep["k_if_nest3"]
rep["k_if_loop"] = mk([A("if_push", {"scope":0x54, "scope_kind":0x01}),
                       A("if_push", {"scope":0x56, "scope_kind":0x1a}),
                       A("stop", {"reserved":0})])
at = A("atomic_mem", {"amode":0x54, "rsv3":0, "base_slot":0, "index_reg":0,
    "oper_reg_lo":1, "oper_reg_hi":1, "addr_desc_hi":0, "ret_flag":0x21,
    "ret_desc":0x11, "idx_off":0, "rsv10":0, "rsv11":0, "op_lsb":0, "op":16,
    "per_lane":0, "op_msb":0, "amode_hi":0})
for k in ("k_atomic_lo", "k_atomic_hi", "k_atomic_min"):
    rep[k] = mk([at, A("stop", {"reserved":0})])
out = HERE / "anchors" / "anchor_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(rep, indent=1, sort_keys=True))
print("wrote FAKE", out)
