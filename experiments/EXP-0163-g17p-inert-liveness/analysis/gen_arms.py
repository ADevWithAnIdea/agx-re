#!/usr/bin/env python3
"""gen_arms.py -- EXP-0163: turn the PRE-FREEZE census into the frozen arm list.

Reads raw/prefreeze/census_run3.json (calibration, not evidence) and writes
harness/arms.py.  Each arm records the carrier, stage, mnemonic, occurrence
index, the target fields swept on it, and the EXACT instruction bytes the census
saw there -- run.py asserts the located bytes still match, so a shifted
occurrence index is a recorded error rather than a silently wrong arm.

Selection rule (frozen): for each target field, take carriers that differ
STRUCTURALLY, and inside a carrier prefer occurrences whose OTHER field values
differ from each other, so an inert verdict is not an artefact of one context.
The `cent1` arms are deliberately kept as the CONTROL that reproduces EXP-0155's
null on the identical program at one sample.
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
CEN = json.load(open(os.path.join(EXP, "raw", "prefreeze", "census_run3.json")))

# (mnemonic, [ (carrier, stage, occ), ... ], fields, why)
SPEC = [
 ("iter_at", ["cent1/fragment/0", "cent1/fragment/1",
              "cent4/fragment/0", "cent4/fragment/1", "cent4/fragment/2",
              "atoff1/fragment/0", "atoff4/fragment/0", "atoff4/fragment/1",
              "ms4cent/fragment/0", "ms4out/fragment/0"],
  ["loc"],
  "cent1 is EXP-0155's exact configuration (1 sample) and is the control; "
  "cent4 is the SAME MSL at 4 samples; atoff* reach the same op through the "
  "interpolant<> pull model instead of a qualifier"),

 ("iter", ["vmany/fragment/0", "vmany/fragment/5", "vhalf/fragment/3",
           "vflat/fragment/1", "cent4/fragment/0", "atoff1/fragment/0",
           "mrt3/fragment/2"],
  ["b9"],
  "wide/half/flat/multisample/pull-model/MRT interpolation contexts, versus "
  "EXP-0155's three plain 32-bit-scalar arms"),

 ("vary_store", ["vmany/vertex/0", "vmany/vertex/9", "vmany/vertex/16",
                 "vhalf/vertex/0", "vhalf/vertex/6", "vflat/vertex/4",
                 "vsrc/vertex/5", "vsrc/vertex/6", "vclip/vertex/0"],
  ["hint2", "hint6", "b7"],
  "slots past 7, half/vector components, flat integers, memory-sourced "
  "varyings and a clip distance -- the census shows hint2 takes 0x54/0x55/0x56 "
  "and hint6 takes 0x48..0x4d across these, versus one value in EXP-0155"),

 ("tex_coord_setup", ["bits/fragment/0", "bits/fragment/1",
                      "fclass/fragment/0", "fclass/fragment/1",
                      "vsrc/vertex/0", "vsrc/vertex/1",
                      "vhalf/vertex/0", "ms4out/fragment/0",
                      "sball/compute/0"],
  ["b5", "b6", "b8", "b9", "idx"],
  "the census finds THREE distinct `form` values: 0x00 (float-classify / "
  "bitfield ALU, b5=0x02) and 0x42 (attribute / varying destination address, "
  "idx = 0x04..0x94, b5 up to 0x20, b8 up to 0x10).  EXP-0155 had one arm, on "
  "one form, with idx=0 and b5/b6/b8/b9 all zero"),

 ("frag_color_store", ["mrt3/fragment/0", "mrt3/fragment/2",
                       "tileread/fragment/0", "tilerw2/fragment/0",
                       "layer/fragment/0", "cent4/fragment/0",
                       "ibhalf/fragment/0", "vflat/fragment/0"],
  ["store_mode"],
  "MRT, tile-read, layered and 4x-multisample stores plus a 16-bit "
  "attachment; the multisample arms are the only ones in the whole repository "
  "whose slice_addr is non-zero (0x08000008)"),

 ("frag_tile_setup", ["mrt3/fragment/0", "mrt3/fragment/1", "mrt3/fragment/3",
                      "tileread/fragment/1", "tilerw2/fragment/2",
                      "tilerw2/fragment/3", "ibmrt/fragment/1",
                      "layer/fragment/0"],
  ["access", "sel", "b5"],
  "the census shows sel taking 0x00/0x04/0x08/0x0c/0x10/0x20/0x30/0xc0 across "
  "these carriers, versus 0x00 and 0x0c on EXP-0155's two arms, and both "
  "access modes now bracket real tile reads"),

 ("imageblock_store", ["ibsamp/fragment/0", "atoff4/fragment/0",
                      "ibms4/fragment/0"],
  ["b4"],
  "the single-sample store EXP-0155 saw, plus the 4x-multisample store whose "
  "tail is 0x08000008 rather than 0"),

 ("tex_write", ["twdim/fragment/0", "twdim/fragment/1", "twdim/fragment/2",
                "twdim/fragment/3", "twtype/fragment/2", "twtype/fragment/3"],
  ["amode", "rsv11"],
  "2D, 2D-array (non-zero slice), 3D and half/uint destinations; the census "
  "shows amode taking 0x55 on the last write of each program, not only 0x54, "
  "and data_desc taking 0x3a/0x2a/0x1a"),

 ("simd_ballot", ["scache/compute/0", "sdiv/compute/0",
                  "sball/compute/0", "sball/compute/1"],
  ["cache"],
  "a ballot whose mask has many consumers; a ballot under a divergent branch "
  "so the active mask is a proper subset of the group; and BOTH db.json ballot "
  "forms -- the active-mask form (psrctype 0x02, form_sig 0x180208) and the "
  "predicate form (psrctype 0x04, form_sig 0x122258)"),

 ("simd_shuffle", ["scache/compute/0", "scache/compute/2",
                   "stype/compute/13", "stype/compute/15",
                   "stype/compute/8", "stype/compute/10",
                   "sdiv/compute/0", "sball/compute/0"],
  ["cache", "rsv9"],
  "the census finds rsv9 NON-ZERO (0xa1 / 0x91) in the mode-0x06 rotate/fill "
  "form, which neither EXP-0155 arm emitted; stype/8 and stype/10 add the "
  "srctype 0x14 and 0x00 operand widths"),
]


def main():
    arms, missing = [], []
    for mnem, keys, fields, why in SPEC:
        for k in keys:
            carrier, stage, occ = k.split("/")
            occ = int(occ)
            e = CEN.get(carrier, {})
            st = e.get("stages", {}).get(stage, {})
            lst = st.get("targets", {}).get(mnem, [])
            if occ >= len(lst):
                missing.append((mnem, k, len(lst)))
                continue
            r = lst[occ]
            arms.append(dict(
                id=f"{mnem}@{carrier}/{stage}#{occ}",
                carrier=carrier, stage=stage, mnemonic=mnem, occ=occ,
                fields=fields, expect_hex=r["hex"], expect_off=r["off"],
                census_fields=r["fields"], tokenized=st["tokenized"], why=why))
    src = ['#!/usr/bin/env python3',
           '"""arms.py -- EXP-0163 FROZEN arm list.',
           '',
           'GENERATED by analysis/gen_arms.py from the pre-freeze census',
           '(raw/prefreeze/census_run2.json) and then FROZEN: run.py asserts that the',
           'instruction it locates still has `expect_hex`, so a shifted occurrence index',
           'is a recorded error, never a silently different arm.',
           '',
           '`tokenized` records whether the carrier stage tokenized cleanly; where it is',
           'False the occurrence was located by anchored decode scan and the arm is only',
           'usable if its liveness ladder passes (a spurious scan hit cannot move the',
           'observation).',
           '',
           'CLEAN-ROOM: OWN-SHADER.  Every byte named here is compiled from kernels/*.metal.',
           '"""',
           'ARMS = [']
    for a in arms:
        src.append("    " + repr(a) + ",")
    src.append("]")
    src.append("")
    src.append("MISSING = %r  # (mnemonic, key, n_occurrences_found)" % (missing,))
    open(os.path.join(EXP, "harness", "arms.py"), "w").write("\n".join(src) + "\n")
    print("arms:", len(arms), " missing:", missing)
    c = collections.Counter(a["mnemonic"] for a in arms)
    for m, n in sorted(c.items()):
        print(f"  {m:20s} {n} arms")
    ncases = sum(len(a["fields"]) * 256 for a in arms)
    print("dense sweep cases per run (excl. ladders/baselines): ~", ncases)


if __name__ == "__main__":
    main()
