#!/usr/bin/env python3
"""EXP-0157 arms L and M — the hardware LENGTH probe.

Arm L answers `op04_len8`; arm M answers `mesh_out_src`. Both are the same
question in the end, because the two descriptors COLLIDE: `mesh_out_src` claims
`04 XX` is TWO bytes, `op04_len8` claims a `byte0` low-nibble-4 residue is
EIGHT. EXP-0148 could not settle `op04_len8` because it scored six candidate
length rules on corpus tokenization, and round-trip is blind to
over-consumption by construction. This arm asks the hardware instead.

METHOD (PRE_REGISTRATION section 5.5). A program is synthesised whose
registers WITNESS where instruction decoding resumed:

    mov_imm(r15, 0)                        index register
    mov_imm(r12, 91) ; store out[20]       integrity sentinel, BEFORE the probe
    mov_imm(r1..r5, 0)                     witnesses start at 0
    <PROBE BLOB>                           the bytes under test
    mov_imm(r1,1) mov_imm(r2,2) mov_imm(r3,3) mov_imm(r4,4)
    store out[0]=r1 out[4]=r2 out[8]=r3 out[12]=r4 out[16]=r5
    stop

The read-back witness pattern measures the CONSUMED LENGTH directly:

  * probe = <6 candidate bytes> + mov_imm(r5,5)   (8 bytes total)
      r5 == 5  ->  decoding resumed at +6  ->  true length 6
      r5 == 0  ->  the trailing mov_imm was swallowed -> length >= 8
  * probe = <8 candidate bytes>
      r1..r4 == 1..4  ->  resumed at or before +8
      r1 == 0         ->  resumed at +10 (the first witness was swallowed)
      r1 == r2 == 0   ->  resumed at +12

Two positive controls make the witness mechanism falsifiable:
  * CTRL-INERT: probe = four `mov_imm(r13,0)` (8 bytes of known 2-byte ops).
    Every witness must be set and r5 must be 0.
  * CTRL-LEN6: probe = a known SIX-byte instruction + mov_imm(r5,5).
    r5 MUST read 5. If it does not, the probe cannot see a 6-byte length and
    nothing in this arm may be concluded.

CLEAN-ROOM: every byte is emitted by `isadb.assemble` from our own field
values, except the candidate patterns, which are `op04_len8` instances taken
from OUR OWN G17P compiles.
"""
import argparse
import json
import os
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "analysis"))
import isa_helpers as H       # noqa: E402
import carriers as C          # noqa: E402
import run as R               # noqa: E402  (fault adjudication, session, emit)
import isadb                  # noqa: E402

OUT_WORDS = 12
# `store_word` addresses out[] in 4-word steps (idx_off's unit is 16 bytes),
# which would need 24 words for six values. Instead each store sets the INDEX
# REGISTER to the word index and uses idx_off = 0, so consecutive words are
# addressable: byte address = content(index_reg) * 4.
SENT_SLOT, SENT_REG, SENT_VAL = 0, 12, 91
WIT = [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4), (5, 5, 5)]
# LENMAP witnesses: EIGHT 2-byte markers after the probe, so a consumption of
# up to probe_len + 16 is resolvable. (Added after the first arm-L capture
# showed the six real op04 patterns consuming probe_len + 4, i.e. TWELVE bytes,
# which the five-witness form could only bound. Recorded as a deviation.)
WIT8 = [(i, i, i) for i in range(1, 9)]


def store_at(word, data_reg):
    """out[word] = r[data_reg], via the index register."""
    return H.mov_imm(H.R_IDX, word) + H.device_store(H.R_IDX, 0, data_reg=data_reg,
                                                     idx_off=0)


def base_prologue():
    """Everything before the probe: index register, integrity sentinel through
    a path that does not depend on the probe, and the witnesses zeroed."""
    ins = [H.mov_imm(SENT_REG, SENT_VAL), store_at(SENT_SLOT, SENT_REG)]
    for _, reg, _ in WIT:
        ins.append(H.mov_imm(reg, 0))
    return ins


def epilogue8():
    """Eight distinct 2-byte markers, then one store per marker. The number of
    LEADING markers that did NOT run is exactly half the number of bytes the
    probe consumed beyond its own length."""
    ins = [H.mov_imm(i, i) for i in range(1, 9)]
    for slot, reg, _ in WIT8:
        ins.append(store_at(slot, reg))
    return ins


def program8(probe_bytes, carrier_len):
    ins = [H.mov_imm(SENT_REG, SENT_VAL), store_at(SENT_SLOT, SENT_REG)]
    ins += [H.mov_imm(i, 0) for i in range(1, 9)]
    return H.build_program(ins + [probe_bytes] + epilogue8(), carrier_len)


def measured_length(words, probe_len):
    """words = out[0..8]; returns the consumed length in bytes, or None."""
    if len(words) < 9:
        return None
    w = words[1:9]
    k = 0
    while k < 8 and w[k] == 0:
        k += 1
    if any(w[j] != j + 1 for j in range(k, 8)):
        return None                     # not a clean prefix-swallow pattern
    return probe_len + 2 * k


def epilogue():
    ins = [H.mov_imm(1, 1), H.mov_imm(2, 2), H.mov_imm(3, 3), H.mov_imm(4, 4)]
    for slot, reg, _ in WIT:
        ins.append(store_at(slot, reg))
    return ins


def program(probe_bytes, carrier_len):
    return H.build_program(base_prologue() + [probe_bytes] + epilogue(), carrier_len)


def witness_oracle(resumed_at, probe_len):
    """Host-computed expected witness words for a decode that resumes
    `resumed_at` bytes into an 8-byte probe blob whose tail is mov_imm(r5,5)."""
    raise NotImplementedError


def cases_L(candidates, carrier_len):
    out = []
    # --- controls -----------------------------------------------------------
    inert = H.mov_imm(13, 0) * 4
    out.append({"case": "CTRL_INERT", "probe": inert.hex(),
                "oracle": {0: [SENT_VAL, 1, 2, 3, 4, 0]},
                "expect_match": True,
                "note": "positive control: 8 bytes of known 2-byte mov_imm; "
                        "every witness must be set and r5 must stay 0"})
    six = H.falu2_raw(6, 0, 1)          # a known SIX-byte instruction
    assert len(six) == 6, len(six)
    out.append({"case": "CTRL_LEN6", "probe": (six + H.mov_imm(5, 5)).hex(),
                "oracle": {0: [SENT_VAL, 1, 2, 3, 4, 5]},
                "expect_match": True,
                "note": "positive control: a KNOWN 6-byte instruction followed by "
                        "mov_imm(r5,5). r5 MUST read 5, otherwise this probe "
                        "cannot detect a 6-byte length and arm L proves nothing"})
    # --- candidates ---------------------------------------------------------
    for name, hx in candidates:
        b = bytes.fromhex(hx)
        out.append({"case": "%s_V8" % name, "probe": b.hex(),
                    "oracle": None, "expect_match": None,
                    "note": "candidate's own 8 bytes; witness pattern measures "
                            "whether decoding resumed at +8, +10 or +12"})
        out.append({"case": "%s_V6" % name, "probe": (b[:6] + H.mov_imm(5, 5)).hex(),
                    "oracle": None, "expect_match": None,
                    "note": "candidate truncated to 6 bytes + mov_imm(r5,5): "
                            "r5 == 5 proves a 6-byte consumption"})
        out.append({"case": "%s_V4" % name,
                    "probe": (b[:4] + H.mov_imm(5, 5) + H.mov_imm(6, 6)).hex(),
                    "oracle": None, "expect_match": None,
                    "note": "candidate truncated to 4 bytes + two markers"})
    return out


def cases_lenmap(candidates, sweep_bytes, carrier_len):
    """For each candidate pattern, sweep the named byte positions over all 256
    values and MEASURE the consumed length for each. This is what turns the
    single V8 observation into a length RULE."""
    out = []
    inert = H.mov_imm(13, 0) * 4
    out.append({"case": "LENMAP_CTRL_INERT8", "probe": inert.hex(), "prog8": True,
                "oracle": {0: [SENT_VAL, 1, 2, 3, 4, 5, 6, 7, 8]},
                "expect_match": True,
                "note": "positive control for the 8-witness form: 8 bytes of "
                        "known 2-byte mov_imm must leave every marker set"})
    for name, hx in candidates:
        b = bytes.fromhex(hx)
        for bi in sweep_bytes:
            for v in range(256):
                nb = bytearray(b)
                nb[bi] = v
                out.append({"case": "LENMAP_%s_b%d_%02x" % (name, bi, v),
                            "probe": bytes(nb).hex(), "prog8": True,
                            "oracle": None, "expect_match": None,
                            "instr": "op04_len8", "field": "lenmap.byte+%d" % bi,
                            "value": v,
                            "note": "measure the CONSUMED LENGTH of %s with "
                                    "byte+%d = 0x%02x" % (name, bi, v)})
    return out


def cases_Q(carrier_len):
    """Arm Q (post-freeze): the `byte0 == 0x04` group's LENGTH as a function of
    byte+1 and byte+2, measured on hardware.

    Arms L/M/N together showed the length is NOT a function of byte+1 alone:
      * a 2-byte `04 XX` probe consumes 2 when bit7 of XX is clear and 4 when
        it is set (arm M, 128/128 split, both clean);
      * an 8-byte candidate consumes 8 when bit7 is SET and 12 when clear
        (arm N, 128/128 split on three independent candidates);
      * two candidates truncated to 6 bytes consume 6, three consume 10.
    All four statements are consistent only if bytes beyond +1 also feed the
    length. This arm sweeps byte+1 densely against seven byte+2 values and
    measures the consumed length for each of the 1792 combinations.

    The probe is FOUR bytes so the eight witnesses resolve any length in
    4..20."""
    out = []
    inert = H.mov_imm(13, 0) * 2
    out.append({"case": "Q_CTRL_INERT", "probe": inert.hex(), "prog8": True,
                "oracle": {0: [SENT_VAL, 1, 2, 3, 4, 5, 6, 7, 8]},
                "expect_match": True,
                "note": "positive control: 4 bytes of known 2-byte mov_imm"})
    for b2 in (0x00, 0x02, 0x06, 0x40, 0x80, 0xC0, 0xFF):
        for b1 in range(256):
            pb = bytes([0x04, b1, b2, 0x00])
            out.append({"case": "Q_b2%02x_b1%02x" % (b2, b1), "probe": pb.hex(),
                        "prog8": True, "oracle": None, "expect_match": None,
                        "instr": "op04_len8", "field": "qlen.byte+2=%02x" % b2,
                        "value": b1,
                        "note": "measure the consumed length of 04 %02x %02x 00"
                                % (b1, b2)})
    return out


def cases_Q2(carrier_len):
    """Arm Q2: the transpose of arm Q -- byte+2 swept densely against the two
    halves of byte+1, plus two byte+3 values, so the `04` group's length is
    characterised in byte+2 as well."""
    out = []
    for b3 in (0x00, 0x80):
        for b1 in (0x00, 0x02, 0x80, 0x82):
            for b2 in range(256):
                pb = bytes([0x04, b1, b2, b3])
                out.append({"case": "Q2_b1%02x_b3%02x_b2%02x" % (b1, b3, b2),
                            "probe": pb.hex(), "prog8": True, "oracle": None,
                            "expect_match": None, "instr": "op04_len8",
                            "field": "q2len.b1=%02x,b3=%02x" % (b1, b3),
                            "value": b2,
                            "note": "measure the consumed length of 04 %02x %02x %02x"
                                    % (b1, b2, b3)})
    return out


def cases_M(carrier_len):
    """Arm M: sweep `mesh_out_src`'s only field (`sel` = byte+1) as a 2-byte
    `04 XX` in a compute program, with the SAME witness epilogue. This
    simultaneously answers (a) is `sel` live in compute, and (b) does the
    hardware consume TWO bytes (mesh_out_src) or EIGHT (op04_len8) for a
    `byte0 == 0x04` leader?"""
    out = []
    for v in range(256):
        out.append({"case": "mesh_sel_%02x" % v,
                    "probe": bytes([0x04, v]).hex(),
                    "oracle": None, "expect_match": None,
                    "instr": "mesh_out_src", "field": "sel", "value": v,
                    "note": "2-byte `04 XX` spliced into a compute program; the "
                            "witness pattern measures the consumed length"})
    return out


def decode_witnesses(observed):
    """The witness pattern, read straight out of the record `summarize` already
    produced (words 0..5 are inside its 12-word window)."""
    w = observed.get("out0")
    if not w or len(w) < 6:
        return None
    got = {"sent": w[SENT_SLOT]}
    for slot, reg, _ in WIT:
        got["r%d" % reg] = w[slot]
    got["resumed"] = _resumed(got)
    return got


def _resumed(g):
    """Translate a witness pattern into the consumed length, per section 5.5."""
    r1, r2, r3, r4, r5 = g["r1"], g["r2"], g["r3"], g["r4"], g["r5"]
    if (r1, r2, r3, r4) == (1, 2, 3, 4):
        return "<=probe_len (r5=%s)" % r5
    if r1 == 0 and (r2, r3, r4) == (2, 3, 4):
        return "probe_len+2"
    if (r1, r2) == (0, 0) and (r3, r4) == (3, 4):
        return "probe_len+4"
    if (r1, r2, r3) == (0, 0, 0) and r4 == 4:
        return "probe_len+6"
    return "unclassified"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--candidates", required=True,
                    help="json file: [[name, hex8], ...] op04_len8 patterns "
                         "observed in OUR OWN G17P compiles")
    ap.add_argument("--arms", default="L,M")
    a = ap.parse_args()

    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw); raw.mkdir(parents=True, exist_ok=True)
    (raw / "00_env.json").write_text(json.dumps(R.env_report(), indent=1, sort_keys=True) + "\n")

    # A LOCAL carrier spec: `synth` with a 32-word output so five witnesses and
    # the sentinel each get their own 4-word-aligned store slot. carriers.py is
    # FROZEN and is not edited.
    # The 8-witness LENMAP program needs ~190 bytes; EXP-0141's `synth` carrier
    # only gives 170. `carrier_dag.metal` (EXP-0139/0140, via EXP-0153) is the
    # long own-MSL carrier this project already uses for whole-program
    # synthesis, so it is reused here verbatim.
    spec = {"metal": "kernels/carrier_dag.metal", "func": "k", "grid": 1, "tg": 1,
            "inputs": {0: ("poison_lm.bin", C.poison_bytes(OUT_WORDS)),
                       1: ("mem_f32.bin", C.pack_f32(C.MEM_F32)),
                       2: ("imem_u32.bin", C.pack_u32([0] * 16))},
            "outs": {0: 4 * OUT_WORDS}, "dtype": {0: C.U32}, "oracle": None,
            "src_exp": "EXP-0139", "doc": "long synthesis carrier for arms L/M/N"}
    C.CARRIERS["synth_lm"] = spec

    mains, build = R.prepare(a.bin_dir, work, ["synth_lm"])
    (raw / "00_build.json").write_text(json.dumps(build, indent=1, sort_keys=True) + "\n")
    carrier_len = len(mains["synth_lm"][2])

    cands = json.load(open(a.candidates))
    allcases = []
    if "L" in a.arms:
        allcases += [dict(c, arm="L") for c in cases_L(cands, carrier_len)]
    if "M" in a.arms:
        allcases += [dict(c, arm="M") for c in cases_M(carrier_len)]
    if "Q2" in a.arms:
        allcases += [dict(c, arm="Q2") for c in cases_Q2(carrier_len)]
    if "Q" in a.arms.replace("Q2", ""):
        allcases += [dict(c, arm="Q") for c in cases_Q(carrier_len)]
    if "N" in a.arms:
        allcases += [dict(c, arm="N") for c in cases_lenmap(
            cands[:int(os.environ.get("LENMAP_CANDS", "2"))],
            [int(x) for x in os.environ.get("LENMAP_BYTES", "1,4,6,7").split(",")],
            carrier_len)]
    for c in allcases:
        pb = bytes.fromhex(c["probe"])
        c["prog"] = (program8(pb, carrier_len) if c.get("prog8")
                     else program(pb, carrier_len)).hex()
        c["probe_len"] = len(pb)
        c["splice"] = []
    (raw / "00_cases.json").write_text(json.dumps(allcases, indent=1) + "\n")
    (raw / "00_manifest.json").write_text(json.dumps(
        {"run_id": a.run_id, "target": "G17P", "arms": a.arms,
         "carrier_len": carrier_len, "n_cases": len(allcases),
         "candidates": cands, "witness_slots": WIT,
         "sentinel": {"slot": SENT_SLOT, "reg": SENT_REG, "value": SENT_VAL}},
        indent=1, sort_keys=True) + "\n")
    print("cases=%d carrier_len=%d" % (len(allcases), carrier_len), flush=True)

    sess = R.CarrierSession("synth_lm", a.bin_dir, work, mains)
    sess.start()
    fres = open(raw / "sweep.jsonl", "a")
    try:
        for i, case in enumerate(allcases):
            blob = sess.blob_of(case)
            oc, obs, m, st, sts, cls, inn = sess.measure(case, blob)
            rec = {"arm": case["arm"], "carrier": "synth_lm",
                   "instr": case.get("instr", "op04_len8"),
                   "anchor_idx": 0, "anchor": 0, "after_gap": False,
                   "field": case.get("field", case["case"]),
                   "value": case.get("value", 0), "bytes": case["probe"],
                   "observed": obs,
                   "witnesses": (None if case.get("prog8")
                                 else decode_witnesses(obs)),
                   "measured_length": (measured_length(obs.get("out0") or [],
                                                       case["probe_len"])
                                       if case.get("prog8") else None),
                   "probe_len": case["probe_len"],
                   "oracle": case.get("oracle"), "match": bool(m), "outcome": oc,
                   "status": st, "statuses": sts if len(sts) > 1 else None,
                   "fault_classes": cls or None, "innocent_retries": inn or None,
                   "expect_match": case["expect_match"], "note": case["note"],
                   "case": case["case"]}
            R.emit(fres, rec)
            if (i + 1) % 64 == 0:
                print("  %d/%d" % (i + 1, len(allcases)), flush=True)
    finally:
        sess.stop()
        fres.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
