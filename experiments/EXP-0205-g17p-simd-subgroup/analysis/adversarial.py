#!/usr/bin/env python3
"""EXP-0205 ADVERSARIAL PROBE (runs ON THE NEO). NOT a gated run.

    python3 analysis/adversarial.py adversarial01

The gated runs found `simd_ballot.pred` INERT across its whole 16-value range on
four carriers whose generic control fired. Protocol section 9 says an inertness
reading is only worth anything if the carrier is proven live IN THE DIMENSION the
field would control -- here, WHICH BALLOT FORM the instruction computes. Two of
our carriers demonstrably compute different forms (`sb_ballot` returns the
predicate mask 0x6C8AF35D, `sb_active` returns 0xFFFFFFFF) from the SAME
descriptor with the SAME `pred` value, so the dimension IS expressible; what the
gated runs cannot say is WHICH bytes carry it.

This probe answers that directly, by converting one compiled form into the other
one byte group at a time:

  A   byte+5 (`psrctype`)  0x00 <-> 0x02
  B   byte+7..9 (`form_sig`)  58 22 12 <-> 08 02 18
  C   both together
and then, for the converted program C, re-sweeps `pred` over all 16 values --
because a field that is inert in one form may be live in the other, and a sweep
that never leaves its own form could not tell.

Every case carries the same poison, sentinel and majority-of-3 machinery as the
gated runs. It is reported as an ADVERSARIAL OBSERVATION and is not eligible to
promote any label: no second gated run, and the arms are not in the frozen
`arms205.json`.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
import json
import os
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP / "harness"))

import carriers205 as C          # noqa: E402
import locate205 as L            # noqa: E402
import run as R                  # noqa: E402

# (name, [(byte_index_within_instruction, new_value), ...])
BALLOT_OFF = None       # filled per carrier from the signature scan

MUTATIONS = {
    "sb_ballot": [
        ("baseline", []),
        ("A_psrctype_to_02", [(5, 0x02)]),
        ("B_tail_to_080218", [(7, 0x08), (8, 0x02), (9, 0x18)]),
        ("C_both", [(5, 0x02), (7, 0x08), (8, 0x02), (9, 0x18)]),
        ("D_form_to_14", [(6, 0x14)]),
    ],
    "sb_active": [
        ("baseline", []),
        ("A_psrctype_to_00", [(5, 0x00)]),
        ("B_tail_to_582212", [(7, 0x58), (8, 0x22), (9, 0x12)]),
        ("C_both", [(5, 0x00), (7, 0x58), (8, 0x22), (9, 0x12)]),
        ("D_form_to_14", [(6, 0x14)]),
    ],
}


def apply_bytes(main, off, ilen, muts):
    m = bytearray(main)
    for (bi, val) in muts:
        m[off + bi] = val
    return bytes(m)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "adversarial01"
    out_dir = EXP / "raw" / tag
    if out_dir.exists():
        sys.stderr.write("REFUSING: %s exists; raw/ is append-only.\n" % out_dir)
        return 2
    out_dir.mkdir(parents=True)
    f = open(out_dir / "probe.jsonl", "a")

    for carrier, muts in MUTATIONS.items():
        cr = R.CarrierRunner(carrier)
        occ = L.find_occurrences(cr.main, "simd_ballot")[0]
        off, ilen = occ["off"], occ["len"]
        base_expect = C.baseline_oracle(carrier)

        def emit(name, main_bytes, pred_value=None):
            blob = bytearray(cr.base)
            blob[cr.main_off:cr.main_off + len(main_bytes)] = main_bytes
            p = cr.spdir / ("adv_%s.bin" % carrier)
            p.write_bytes(bytes(blob))
            try:
                resp = cr.runner.request(
                    archive=str(p), grid=cr.spec["grid"], tg=cr.spec["tg"],
                    ins=cr.ins, outs={0: 4 * cr.spec["nwords"]}, timeout=8.0)
            finally:
                try:
                    os.unlink(str(p))
                except OSError:
                    pass
            blob_out = resp["outs"].get(0, b"")
            obs, words = ({}, [])
            if blob_out:
                obs, words = C.summarize(carrier, blob_out)
            rec = {"carrier": carrier, "mutation": name,
                   "pred_value": pred_value,
                   "bytes": main_bytes[off:off + ilen].hex(),
                   "token": L.token_at(main_bytes, off),
                   "status": resp["status"], "error": resp.get("error"),
                   "gputime_ns": resp.get("gputime_ns"),
                   "sentinel_ok": C.sentinel_ok(carrier, words) if words else None,
                   "vals_u32": obs.get("vals_u32"),
                   "head": ("0x%08x" % obs["vals_u32"][0]) if obs.get("vals_u32") else None,
                   "all_lanes_equal": (len(set(obs["vals_u32"])) == 1)
                                      if obs.get("vals_u32") else None,
                   "matches_baseline_oracle":
                       C.match_oracle(carrier, words, base_expect) if words else None,
                   "ts": time.time()}
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
            print("%-11s %-20s pred=%-4s status=%-6s head=%s equal=%s"
                  % (carrier, name, pred_value, resp["status"], rec["head"],
                     rec["all_lanes_equal"]))
            return rec

        for name, mut in muts:
            mb = apply_bytes(cr.main, off, ilen, mut)
            emit(name, mb)
            if name == "C_both":
                # Re-sweep `pred` INSIDE the converted form: a field inert in one
                # form may be live in the other, and a sweep that never leaves
                # its own form could not tell.
                start, width = L.field_span("simd_ballot", "pred")
                for v in range(1 << width):
                    m2 = bytearray(mb)
                    m2[off:off + ilen] = L.patch_instr(
                        bytes(mb[off:off + ilen]), start, width, v)
                    emit("C_both+pred", bytes(m2), pred_value=v)
        cr.close()
    f.close()
    print("wrote", out_dir / "probe.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
