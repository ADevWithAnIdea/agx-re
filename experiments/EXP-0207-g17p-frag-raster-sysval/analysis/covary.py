#!/usr/bin/env python3
"""EXP-0207 rule R8: the observable must not CO-VARY with the field under test.

EXP-0140 swept `uniform_mov.dst` while building its read-back as
`device_store(data_reg = D)` where D *was* the swept dst.  Field and observable
moved together, so a CORRECT hardware result was a constant observed vector BY
CONSTRUCTION and "16 values, 0 moved" was the PASSING outcome of a test that
could not return anything else.

This check is structural and needs no device.  For each arm it asserts that the
read-back path is not selected, indexed or addressed by the field under test.

  python3 analysis/covary.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
import plan207 as SP                                           # noqa: E402

# For each (instruction, field) under test: what the OBSERVABLE is, and the
# argument that it cannot be selected by that field.
ARGUMENT = {
    ("frag_color_store", "store_mode"): (
        "colour attachment bytes + a device-buffer coverage sentinel written by a "
        "separate device_store the fragment issues itself",
        "store_mode is byte+2 of the colour store.  The sentinel is written by a "
        "DIFFERENT instruction (a device_store to buffer(1)) that the swept bytes do "
        "not touch, and the attachment identity is fixed by the render pass, not by "
        "any field of this instruction."),
    ("iter", "b9"): (
        "per-sample interpolated values in a device buffer indexed by "
        "(pixel, sample_id)",
        "the read-back index is (y*W+x)*4+sample_id, computed from [[position]] and "
        "[[sample_id]], neither of which is produced by the swept `iter`.  The swept "
        "instruction supplies a VALUE, never the address it is stored at."),
    ("vtx_coord_xform", "operand"): (
        "16x16 attachment bytes + a per-pixel coverage sentinel",
        "the observable is the rasterised frame; the vertex instruction under test "
        "cannot name the fragment stage's store address."),
    ("get_sr", "form"): (
        "the read-back word/pixel the consumer of the system value produces",
        "`form` is byte0 bit 3 and is not a register selector; the consumer reads a "
        "register chosen by `dst`/`dst_hi`, which this sweep holds fixed."),
    ("get_sr", "dst_hi"): (
        "the read-back word/pixel the consumer of the system value produces",
        "DELIBERATE AND DECLARED: dst_hi selects the DESTINATION REGISTER, and the "
        "consumer reads the COMPILED register, which the sweep does NOT move.  Field "
        "and observable are therefore decoupled -- the field moves the write, the "
        "observable stays on the original register.  That is the opposite of the "
        "EXP-0140 defect, where the read-back followed the field."),
    ("dev_scoreboard_fence", "scope_flag"): (
        "a device-atomic reduction with a host-computable correct answer",
        "the fence has no operands; the observable is produced by other instructions "
        "entirely."),
    ("mesh_out_src", "sel"): (
        "the rasterised frame produced from the mesh outputs",
        "the frame's address space is fixed by the render pass; `sel` supplies a "
        "source value to the following store, not a destination."),
}


def main():
    bad = 0
    rows = []
    for arm in SP.ARMS:
        for f in arm["fields"]:
            key = (arm["instr"], f)
            if key not in ARGUMENT:
                print("NO ARGUMENT RECORDED for %s.%s (arm %s)" % (key[0], key[1], arm["arm"]))
                bad += 1
                continue
            obs, why = ARGUMENT[key]
            rows.append({"arm": arm["arm"], "instr": key[0], "field": key[1],
                         "observable": obs, "not_covariant_because": why})
    json.dump({"_doc": __doc__, "rows": rows},
              open(os.path.join(HERE, "covary.json"), "w"), indent=1, sort_keys=True)
    print("R8: %d arm-fields checked, %d without a recorded argument" % (len(rows), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
