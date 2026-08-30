#!/usr/bin/env python3
"""EXP-0168 OFFLINE dry run -- no device, no MSL compile.

Exercises the whole non-device path so a bug costs zero device time:
  * every arm's program is BUILT for a sample of its cases,
  * the program length matches the carrier region exactly,
  * the seeds / sentinels / dump / probe all fit,
  * the oracle is computable,
  * every record key required by CAPTURE_CONTRACT's raw schema is present.

Run against the FAKE anchor fixture on the repo host (work/mkfake_anchors.py) or
against the real anchor report on the target. It never dispatches anything.
"""
from __future__ import print_function
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H
import casematrix as CM

REGION = 2400          # a plausible carrier_dag region length; the real one
                       # comes from the device and only has to be >= the body

def build_program(case, carrier_len, blk):
    import importlib.util
    spec = importlib.util.spec_from_file_location("runmod", str(HERE / "run.py"))
    m = importlib.util.module_from_spec(spec)
    sys.argv = ["run.py", "--run", "dry"]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m.build_program(case, carrier_len, blk)

def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = CM.build_cases(rep)
    print("cases:", len(cases), "matrix", CM.matrix_sha256(cases))
    per_arm = {}
    for c in cases:
        per_arm.setdefault(c["arm"], []).append(c)

    required = {"idx", "arm", "role", "instr", "field", "value", "bytes",
                "byte_index", "fstart", "fwidth", "style", "dim", "note"}
    bad = 0
    for c in cases:
        missing = required - set(c)
        if missing:
            print("  RECORD MISSING KEYS", c["arm"], c["role"], sorted(missing))
            bad += 1
            if bad > 5:
                break

    import run as R  # noqa
    nbuilt = 0
    for arm, cs in sorted(per_arm.items()):
        sample = [c for c in cs if c["role"] != "arm_not_run"]
        if not sample:
            print("  %-24s ARM NOT RUN: %s" % (arm, cs[0]["note"][:90]))
            continue
        take = sample[:1] + sample[len(sample)//2:len(sample)//2+1] + sample[-1:]
        lens = set()
        for c in take:
            blk = bytes.fromhex(c["bytes"])
            if c["style"] == "P":
                # STYLE-P dispatches the patched main verbatim
                lens.add(len(blk))
                nbuilt += 1
                continue
            prog = R.build_program(c, REGION, blk)
            assert len(prog) == REGION, (arm, len(prog))
            lens.add(len(prog))
            nbuilt += 1
        # how much of the region the body actually uses
        c = take[0]
        if c["style"] == "S":
            body = R.build_program(c, REGION, bytes.fromhex(c["bytes"]))
            pad = 0
            while body[REGION - 2 - pad*2: REGION - pad*2] == H.mov_imm(14, 0):
                pad += 1
            print("  %-24s style=%s built ok, body=%d B of %d (pad %d x 2B)"
                  % (arm, c["style"], REGION - pad*2, REGION, pad))
        else:
            print("  %-24s style=P patched-main len=%s" % (arm, sorted(lens)))
    print("\nbuilt %d programs, %d bad records" % (nbuilt, bad))

    print("\nORACLE CHECK (dst arms): seeds are host-known a priori")
    seeds = H.seed_regs("int")
    fake_base = list(seeds); fake_base[5] = 0xABCD1234
    exp, wr = R.dst_oracle(9, fake_base, seeds)
    assert exp[9] == 0xABCD1234 and exp[5] == seeds[5], exp
    print("  dst_oracle(9): slot 9 -> 0x%08x, slot 5 restored to seed %d  OK"
          % (exp[9], exp[5]))
    exp2, _ = R.dst_oracle(3, list(seeds), seeds)   # anchor wrote nothing
    print("  anchor writing NO slot -> oracle None (scored structurally):",
          exp2 is None)

    print("\nCOVERAGE CHECK")
    cov = Counter()
    for c in cases:
        if c["role"] == "sweep":
            cov[(c["instr"], c["field"])] += 1
    for k, v in sorted(cov.items()):
        print("  %-28s %d dispatched values" % ("%s.%s" % k, v))

if __name__ == "__main__":
    main()
