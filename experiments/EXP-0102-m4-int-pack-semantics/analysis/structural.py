#!/usr/bin/env python3
"""EXP-0102 structural analysis: post-processes the ALREADY-CAPTURED
_agc.main bytes (main_len/main_hex, read from the promoted run's
01_results.jsonl + raw/<run>/full/*.main.hex sidecars) to answer the
structural sub-claims (INT-06, INT-09/10, INT-12, INT-13, PACK-01/02/03/04/
07/08/11 family-membership). NO new hardware contact -- this is pure
post-processing of data already gated and cross-run-compared by
verify.py --captured --compare.

Uses tools/agx-isa (READ-ONLY, not modified) to tokenize bytes where it can;
falls back to raw byte-length/byte-diff comparison where a family is not
(yet) in db.json, which is itself a fact worth recording.

Usage: python3 -B analysis/structural.py --run raw/<run-id> [--repo ../..]
Prints a JSON report and also writes analysis/structural_report.json.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def load_run(run_dir):
    run_dir = Path(run_dir)
    recs = {}
    for line in open(run_dir / "01_results.jsonl"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        recs[r["id"]] = r
    return recs, run_dir


def main_bytes_for(rec, run_dir):
    """Return the full _agc.main hex for a case, whether it was inlined in
    the gated record (<=64B) or written to a full_dir sidecar (>64B)."""
    if rec.get("main_hex") and not str(rec["main_hex"]).startswith("see "):
        return rec["main_hex"]
    p = run_dir / "full" / f"{rec['id']}.main.hex"
    if p.exists():
        return p.read_text().strip()
    return None


def try_disasm(isadb, hexstr):
    if not hexstr:
        return None
    try:
        buf = bytes.fromhex(hexstr)
        toks, rest = isadb.disassemble(buf)
        return {"mnemonics": [t.get("mnemonic", "?") for t in toks],
                "lengths": [t.get("length") for t in toks],
                "n_instructions": len(toks),
                "undecoded_tail_len": len(rest) if rest else 0}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--repo", default=str(EXP.parent.parent))
    a = ap.parse_args()
    recs, run_dir = load_run(a.run)

    sys.path.insert(0, str(Path(a.repo) / "tools" / "agx-isa"))
    import isadb  # noqa: E402

    report = {}

    # --- INT-04/06: rotate immediate family fold + var vs imm length ---
    rot_ids = [f"int04_rotate_imm{k}" for k in (0, 1, 31, 32, 33, 63, 64)]
    rot = {rid: (recs[rid]["main_len"], main_bytes_for(recs[rid], run_dir)) for rid in rot_ids}
    var_len, var_hex = recs["int0506_rotate_var"]["main_len"], main_bytes_for(recs["int0506_rotate_var"], run_dir)
    report["INT04_INT06_rotate"] = {
        "imm_lengths": {k: v[0] for k, v in rot.items()},
        "imm0_eq_imm32_eq_imm64_bytes": rot["int04_rotate_imm0"][1] == rot["int04_rotate_imm32"][1] == rot["int04_rotate_imm64"][1],
        "imm31_eq_imm63_bytes": rot["int04_rotate_imm31"][1] == rot["int04_rotate_imm63"][1],
        "imm33_eq_imm1_bytes": rot["int04_rotate_imm33"][1] == rot["int04_rotate_imm1"][1],
        "var_len": var_len,
        "var_longer_than_every_nontrivial_imm": all(
            var_len > rot[k][0] for k in ("int04_rotate_imm1", "int04_rotate_imm31", "int04_rotate_imm33", "int04_rotate_imm63")),
        "imm31_disasm": try_disasm(isadb, rot["int04_rotate_imm31"][1]),
        "var_disasm": try_disasm(isadb, var_hex),
    }

    # --- INT-09/10: clz vs popcount ---
    clz = recs["int0910_clz"]
    popc = recs["int0910_popcount_baseline"]
    clz_hex = main_bytes_for(clz, run_dir)
    popc_hex = main_bytes_for(popc, run_dir)
    report["INT09_INT10_clz_vs_popcount"] = {
        "clz_len": clz["main_len"], "popcount_len": popc["main_len"],
        "clz_longer": clz["main_len"] > popc["main_len"],
        "clz_disasm": try_disasm(isadb, clz_hex),
        "popcount_disasm": try_disasm(isadb, popc_hex),
    }

    # --- INT-11 structural (already functionally closed; add length note) ---
    ins = recs["int11_insert_bits"]
    report["INT11_insert_bits"] = {
        "len": ins["main_len"],
        "disasm": try_disasm(isadb, main_bytes_for(ins, run_dir)),
    }

    # --- INT-12: 16 logic functions, compare op families ---
    logic = {}
    for i in range(16):
        rid = f"int12_logic{i:02d}"
        r = recs[rid]
        h = main_bytes_for(r, run_dir)
        logic[i] = {"len": r["main_len"], "hash": r["main_hash_sha256"], "disasm": try_disasm(isadb, h)}
    report["INT12_logic16"] = logic

    # --- INT-13: u64 carry-generate adjacency in two different shapes ---
    u64a = recs["int1314_u64add"]
    u64b = recs["int13_u64add_expr"]
    report["INT13_carry_adjacency"] = {
        "u64add_len": u64a["main_len"], "u64add_expr_len": u64b["main_len"],
        "u64add_disasm": try_disasm(isadb, main_bytes_for(u64a, run_dir)),
        "u64add_expr_disasm": try_disasm(isadb, main_bytes_for(u64b, run_dir)),
    }

    # --- PACK-01/02: half2x16 vs insert_bits/half-pack signature ---
    ph = recs["pack0102_pack_half2x16"]
    uh = recs["pack0102_unpack_half2x16"]
    report["PACK0102_half2x16"] = {
        "pack_len": ph["main_len"], "unpack_len": uh["main_len"],
        "pack_disasm": try_disasm(isadb, main_bytes_for(ph, run_dir)),
        "unpack_disasm": try_disasm(isadb, main_bytes_for(uh, run_dir)),
        "insert_bits_reference_len": ins["main_len"],
        "insert_bits_reference_disasm": report["INT11_insert_bits"]["disasm"],
    }

    # --- PACK-03/04: snorm2x16 vs unorm2x16 family membership ---
    psn = recs["pack0304_pack_snorm2x16"]
    pun = recs["pack0506_pack_unorm2x16_edge"]
    usn_exh = recs["pack0304_unpack_snorm2x16_exhaustive"]
    uun_exh = recs["pack0506_unpack_unorm2x16_exhaustive"]
    report["PACK0304_0506_snorm_unorm_family"] = {
        "pack_snorm_len": psn["main_len"], "pack_unorm_edge_len": pun["main_len"],
        "pack_snorm_len_eq_unorm_len": psn["main_len"] == pun["main_len"],
        "unpack_snorm_exh_len": usn_exh["main_len"], "unpack_unorm_exh_len": uun_exh["main_len"],
        "unpack_lens_eq": usn_exh["main_len"] == uun_exh["main_len"],
        "pack_snorm_disasm": try_disasm(isadb, main_bytes_for(psn, run_dir)),
        "pack_unorm_disasm": try_disasm(isadb, main_bytes_for(pun, run_dir)),
        "unpack_snorm_disasm": try_disasm(isadb, main_bytes_for(usn_exh, run_dir)),
        "unpack_unorm_disasm": try_disasm(isadb, main_bytes_for(uun_exh, run_dir)),
    }

    # --- PACK-07/08: 4x8 builtin vs manual-generic vs unpack family ---
    pu4 = recs["pack0708_pack_unorm4x8"]
    ps4 = recs["pack0708_pack_snorm4x8"]
    pman = recs["pack07_pack4x8_manual_generic"]
    uu4 = recs["pack0708_unpack_unorm4x8"]
    us4 = recs["pack0708_unpack_snorm4x8"]
    report["PACK0708_4x8"] = {
        "pack_unorm4x8_len": pu4["main_len"], "pack_snorm4x8_len": ps4["main_len"],
        "pack_manual_generic_len": pman["main_len"],
        "unpack_unorm4x8_len": uu4["main_len"], "unpack_snorm4x8_len": us4["main_len"],
        "pack_unorm4x8_disasm": try_disasm(isadb, main_bytes_for(pu4, run_dir)),
        "pack_snorm4x8_disasm": try_disasm(isadb, main_bytes_for(ps4, run_dir)),
        "pack_manual_generic_disasm": try_disasm(isadb, main_bytes_for(pman, run_dir)),
        "unpack_unorm4x8_disasm": try_disasm(isadb, main_bytes_for(uu4, run_dir)),
        "unpack_snorm4x8_disasm": try_disasm(isadb, main_bytes_for(us4, run_dir)),
    }

    # --- PACK-11: short2 decomposition into two 32-bit ops ---
    s2 = {}
    for op in ("add", "mul", "and"):
        rid = f"pack11_short2_{op}"
        r = recs[rid]
        s2[op] = {"len": r["main_len"], "disasm": try_disasm(isadb, main_bytes_for(r, run_dir))}
    report["PACK11_short2"] = s2

    out_path = HERE / "structural_report.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str))
    print(f"wrote {out_path}")
    print(json.dumps({k: "..." for k in report}, indent=2))


if __name__ == "__main__":
    main()
