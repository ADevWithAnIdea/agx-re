#!/usr/bin/env python3
"""EXP-0168 offline correctness check: does our bit surgery agree with the DB's
own encoder?

`harness/casematrix.set_field` mutates a field by writing its bits directly.
`isadb.assemble` builds the same instruction from a field dict. If the two
disagree on bit order or placement, EVERY case in the experiment is mislabelled
and no amount of hardware time can fix it. So this is checked exhaustively,
offline, before any dispatch: for every instruction/field this experiment
touches, over every value in the field's range, `set_field(anchor, v)` must equal
`assemble(fields with that field = v)`.

Fields whose descriptor has a `match` constraint over the same bits (the
declares-a-field-over-pinned-bits defect EXP-0162 fixed in `pixel_order` and
which `iter_at.grp` still has) will DISAGREE by construction, because assemble
re-imposes the match. Those are reported separately as `db_defect_suspect`
rather than as failures -- they are a finding, not a bug in this harness.

CLEAN-ROOM: pure analysis over our own tools. No device, no Apple binary.
"""
from __future__ import print_function
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H
import casematrix as CM
isadb = H.isadb

TARGETS = {
    "uniform_mov": ["dst", "usrc"],
    "reg_move_c0": ["dst", "src_reg", "src_flag", "src_class", "op_desc"],
    "reg_move_c1": ["dst", "src_reg", "src_flag", "src_class", "op_desc"],
    "reg_move_c2var": ["dst", "src_reg", "src_flag", "subform", "op_desc"],
    "reg_move_c9": ["dst", "src_reg", "src_flag", "src_class", "op_desc"],
    "reg_move_cb": ["dst", "src", "form", "b3"],
    "falu2": ["dst", "srcA_reg", "opsel"],
    "falu2i": ["dst", "srcA_reg"],
    "falu_acc": ["dst", "cache", "srcA", "srcB", "op"],
    "get_sr": ["dst", "dst_hi", "form", "sr_sel"],
    "mov_imm": ["dst", "imm7", "imm_top"],
    "stop": ["reserved"],
    "shift_amt_move": ["dst", "src_reg", "src_flag", "kind", "op_desc"],
    "copysign": ["operands"],
    "cvt_f2h": ["op", "src", "b1"],
    "cvt_f2i": ["dst", "b9", "src", "mode"],
    "pack_convert": ["b7", "dst", "src_lane0"],
    "unpack_convert": ["dst", "src", "cache"],
    "if_push": ["scope", "scope_kind"],
    "atomic_mem": ["addr_desc_hi", "oper_reg_hi", "oper_reg_lo", "op"],
    "iter_at": ["grp", "loc", "dst"],
    "pixel_order": ["kind", "scope", "flags"],
    "vtx_out_pos": ["dst", "slot"],
    "frag_color_pack": ["dst", "val", "src_present_mask"],
    "matrix_mac": ["dst", "dtype", "mode"],
}


def anchor_fields(mn):
    """A field dict that satisfies the descriptor's own match constraints."""
    d = CM.INS[mn]
    f = {}
    for fl in d["fields"]:
        f[fl["name"]] = 0
    return f


def main():
    ok = fail = defect = skipped = 0
    problems = []
    defects = []
    for mn, fields in sorted(TARGETS.items()):
        if mn not in CM.INS:
            print("%-16s NOT IN THE PINNED db.json SNAPSHOT" % mn)
            skipped += 1
            continue
        d = CM.INS[mn]
        base_fields = anchor_fields(mn)
        try:
            anchor = isadb.assemble(mn, base_fields)
        except Exception as e:
            print("%-16s assemble(anchor) failed: %s" % (mn, str(e)[:90]))
            skipped += 1
            continue
        # bits the descriptor's own match pins
        pinned = set()
        for (st, w, _v) in d.get("match", []):
            pinned.update(range(st, st + w))
        for fname in fields:
            try:
                st, w = CM.field_geom(mn, fname)
            except KeyError:
                continue
            overlap = sorted(set(range(st, st + w)) & pinned)
            vals = CM.coverage(w)
            bad = 0
            for v in vals:
                mine = CM.set_field(anchor, 0, st, w, v)
                ff = dict(base_fields)
                ff[fname] = v
                try:
                    theirs = isadb.assemble(mn, ff)
                except Exception:
                    bad += 1
                    continue
                if mine != theirs:
                    bad += 1
            if overlap:
                defect += 1
                defects.append((mn, fname, st, w, overlap, bad, len(vals)))
                print("%-16s %-18s DB-DEFECT SUSPECT: declared bits %d..%d but "
                      "match pins %s (%d/%d values differ from assemble)"
                      % (mn, fname, st, st + w - 1,
                         "%d..%d" % (overlap[0], overlap[-1]), bad, len(vals)))
            elif bad:
                fail += 1
                problems.append((mn, fname, st, w, bad, len(vals)))
                print("%-16s %-18s MISMATCH on %d/%d values  <-- HARNESS BUG"
                      % (mn, fname, bad, len(vals)))
            else:
                ok += 1
    print("\n%d field(s) agree exactly, %d db-defect suspects, %d MISMATCH, "
          "%d skipped" % (ok, defect, fail, skipped))
    out = {"agree": ok, "db_defect_suspects": [
        {"instr": m, "field": f, "start": s, "width": w,
         "match_pins_bits": [o[0], o[-1]], "values_differing": b, "of": n}
        for (m, f, s, w, o, b, n) in defects],
        "mismatches": [{"instr": m, "field": f, "start": s, "width": w,
                        "bad": b, "of": n} for (m, f, s, w, b, n) in problems]}
    (HERE / "bitcheck.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", HERE / "bitcheck.json")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
