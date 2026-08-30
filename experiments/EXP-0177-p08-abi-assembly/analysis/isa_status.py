#!/usr/bin/env python3
"""EXP-0177 analysis: extract the emit status of every instruction a VS/FS/CS stage
ABI (P0.8 / DRV-ABI-01) has to emit, straight out of tools/agx-isa/validation.json.

Read-only. Writes analysis/isa_status.json next to this script.

Emitter-grade labels are the two `validate_labels.py` counts as emitter-grade
(`docs/evidence-classification.md`): hardware-run and isolated-byte-diff.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VALIDATION = os.path.join(REPO, "tools", "agx-isa", "validation.json")

EMITTER_GRADE = {"hardware-run", "isolated-byte-diff"}

# The instructions a VS/FS/CS stage ABI + prolog/epilog linkage must emit,
# grouped by the P0.8 sub-area each one serves.
SUBAREA_INSTRUCTIONS = {
    "interpolation": ["iter", "iter_at", "iter_flat"],
    "outputs_fs": [
        "frag_color_store",
        "frag_color_pack",
        "frag_tile_setup",
        "frag_depth_store",
        "imageblock_store",
    ],
    "outputs_vs": ["vary_store", "vary_slot", "vtx_out_pos", "vtx_coord_xform", "mesh_out_src"],
    "tilebuffer": ["tile_read", "tile_read_mrt", "imageblock_load", "n3_sample_read", "pixel_order"],
    "sysvals": ["get_sr", "sr_read_wide"],
    "calls_linking": [
        "call",
        "ret",
        "ret_luse",
        "link_save_restore",
        "frame_prologue",
        "frame_marker_compact",
        "spill_frame_marker",
        "pop_reconverge",
    ],
}


def main():
    v = json.load(open(VALIDATION))
    ins = v["instructions"]
    emittable = set(v["coverage"]["emittable_mnemonics"])

    out = {
        "_source": "tools/agx-isa/validation.json",
        "_validation_generated": v.get("generated"),
        "_db_sha256": v.get("db_sha256"),
        "_warning": (
            "validation.json and db.json are owned by another live experiment "
            "(EXP-0175). These numbers are a snapshot, not a stable figure."
        ),
        "_emitter_grade_labels": sorted(EMITTER_GRADE),
        "coverage_headline": {
            k: v["coverage"][k]
            for k in (
                "total_instructions",
                "total_fields",
                "emittable_instructions",
                "emitter_relevant_instructions",
                "emittable_of_emitter_relevant",
            )
        },
        "subareas": {},
    }

    for sub, mnemonics in SUBAREA_INSTRUCTIONS.items():
        rows = []
        for m in mnemonics:
            d = ins.get(m)
            if d is None:
                rows.append({"mnemonic": m, "present_in_db": False})
                continue
            inst = d.get("_instruction", {})
            fields = {k: x for k, x in d.items() if k != "_instruction"}
            blockers = [
                {
                    "field": k,
                    "label": x.get("label"),
                    "target": x.get("target"),
                    "evidence": x.get("evidence"),
                    "range": x.get("range"),
                }
                for k, x in fields.items()
                if x.get("label") not in EMITTER_GRADE
            ]
            rows.append(
                {
                    "mnemonic": m,
                    "present_in_db": True,
                    "emittable": m in emittable,
                    "instruction_label": inst.get("label"),
                    "instruction_label_is_emitter_grade": inst.get("label") in EMITTER_GRADE,
                    "instruction_target": inst.get("target"),
                    "instruction_evidence": inst.get("evidence"),
                    "n_fields": len(fields),
                    "field_targets": sorted({x.get("target", "?") for x in fields.values()}),
                    "n_blocking_fields": len(blockers),
                    "blocking_fields": blockers,
                }
            )
        out["subareas"][sub] = rows

    dst = os.path.join(HERE, "isa_status.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=False)
        fh.write("\n")

    # human summary to stdout
    for sub, rows in out["subareas"].items():
        print(f"== {sub}")
        for r in rows:
            if not r["present_in_db"]:
                print(f"   {r['mnemonic']:22s} ABSENT from validation.json")
                continue
            print(
                f"   {r['mnemonic']:22s} emittable={str(r['emittable']):5s} "
                f"_instr={r['instruction_label']:26s} "
                f"blocking={r['n_blocking_fields']:2d} "
                f"targets={','.join(r['field_targets'])}"
            )
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
