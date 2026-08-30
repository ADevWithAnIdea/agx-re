#!/usr/bin/env python3
"""EXP-0158 PILOT ARM P11 (disclosed, pre-freeze): iadd2 register mode's
supposedly-INERT fields, swept on G17P in OUR carrier.

WHY.  `g17p-20260830-run01` returned six `IADD_SYNTH` cases with the result
equal to the SECOND operand alone instead of the sum -- while the pilot's P9
arm, which used the same operands but NATURAL values for every non-operand
field, returned the correct sum 7/8 times.  The only difference is that the
gated corpus set the fields EXP-0139 recorded as INERT
(`srcA`, `opc_tail`, `opc_tail2`, `opmode`, `b2_fmt`, `store_en`, `b2_bit0`,
`srcB_reg_hi`, `srcB_ext`) to deliberately off-natural values.

EXP-0139's masks were established on the M4.  This arm measures them on G17P,
one field at a time, so the frozen generator picks from a set MEASURED on the
target instead of inheriting an M4 inertness claim.  A disagreement is a
first-class G16G-vs-G17P finding, not a nuisance.

Shape: r0 = A (mov_imm), r_N = B (mov_imm), iadd2 register mode into r_dst,
device_store r_dst.  Oracle = A + B as a raw 32-bit word.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
import synth as S      # noqa: E402
import generator as G  # noqa: E402

OUT_WORDS = 260
SLOT_OUT = 0
CARRIER_LEN = 1536
A, B, N, DST = 10, 7, 1, 2

NATURAL = {"lenbit": 1, "srcB_reg_hi": 0, "b2_bit0": 0, "store_en": 1, "b2_fmt": 0x15,
           "opmode": 2, "srcB_imm_hi": 0, "srcB_ext": 0, "srcA": 0xA8,
           "opc_tail": 0x17, "opc_tail2": 0x05}

SWEEPS = {
    "srcA": [v for v in range(0, 256, 4)],                    # EXP-0139: bits 0,1 must be 0
    "opc_tail": [v for v in range(256) if v & 0x11 == 0x11],  # bits 0,4 set
    "opc_tail2": [v for v in range(256) if v & 0x05 == 0x05],  # bits 0,2 set
    "opmode": [v for v in range(256) if v & 0x02][::8],
    "b2_fmt": list(range(64)),
    "srcB_ext": [0, 1, 2, 3],
    "store_en": [0, 1],
    "b2_bit0": [0, 1],
    "srcB_reg_hi": list(range(0, 128, 8)),
    "lenbit": [0, 1],
    "srcB_imm_hi": [0, 1],
}


def program(field, value):
    f = dict(NATURAL)
    f[field] = value
    led = S.Ledger()
    ins = [S.mov_imm(led, S.R_IDX, 0, salt="ia")]
    ins += S.sentinel_instrs(led, SLOT_OUT, "ia")
    ins.append(S.mov_imm(led, 0, A, salt="iaa"))
    ins.append(S.mov_imm(led, N, B, salt="iab"))
    ins.append(S.emit(led, "iadd2", {
        "addsub": S.FV(1, S.RULE, "EXP-0128 SS1.4"),
        "lenbit": S.FV(f["lenbit"], S.PILOT, "P11"),
        "srcB_reg_hi": S.FV(f["srcB_reg_hi"], S.PILOT, "P11"),
        "b2_bit0": S.FV(f["b2_bit0"], S.PILOT, "P11"),
        "store_en": S.FV(f["store_en"], S.PILOT, "P11"),
        "b2_fmt": S.FV(f["b2_fmt"], S.PILOT, "P11"),
        "dst": S.FV(((DST << 1) | 1) & 0xFF, S.RULE, "EXP-0139 dst=(reg<<1)|size"),
        "opmode": S.FV(f["opmode"], S.PILOT, "P11"),
        "srcB_imm": S.FV((4 * N) & 0xFF, S.RULE, "EXP-0128 srcB_imm=4*N"),
        "srcB_imm_hi": S.FV(f["srcB_imm_hi"], S.PILOT, "P11"),
        "srcB_ext": S.FV(f["srcB_ext"], S.PILOT, "P11"),
        "srcA": S.FV(f["srcA"], S.PILOT, "P11"),
        "opc_tail": S.FV(f["opc_tail"], S.PILOT, "P11"),
        "opc_tail2": S.FV(f["opc_tail2"], S.PILOT, "P11")}))
    ins.append(S.device_store(led, S.R_IDX, 0, SLOT_OUT, data_reg=DST, salt="ia",
                              offnatural=False))
    ins.append(S.stop(led, offnatural=False))
    prog = S.build_program(led, ins, CARRIER_LEN)
    S.assert_round_trip(prog)
    return prog.hex()


def write_inputs(work):
    (work / "mem.bin").write_bytes(b"".join(struct.pack("<f", v) for v in G.MEM_WORDS))
    (work / "imem.bin").write_bytes(b"".join(struct.pack("<i", v) for v in G.IMEM_WORDS))
    (work / "poison.bin").write_bytes(struct.pack("<I", S.POISON_U32) * OUT_WORDS)


def run(work, tag, hexstr, bin_dir):
    d = work / tag
    d.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / "carrier_dag.metal"), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(bin_dir / "shdump"), "--agxrun", str(bin_dir / "agxrun"),
            "--agxparse", str(REPO / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(d), "--run-timeout", "20",
            "--buf", "0=@%s" % (work / "poison.bin"),
            "--buf", "1=@%s" % (work / "mem.bin"),
            "--buf", "2=@%s" % (work / "imem.bin"),
            "--out", "0=%d" % OUT_WORDS,
            "--splice", "_agc.main@0=%s" % hexstr]
    for _ in range(6):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired:
            return "HANG", [], ""
        status, out_hex, fault = "NO_STATUS", None, ""
        for line in r.stdout.splitlines():
            if line.startswith("STATUS "):
                status = line.split(None, 1)[1].strip()
            elif line.startswith("OUT 0 "):
                out_hex = line[len("OUT 0 "):].strip()
            elif line.startswith("ERROR "):
                fault = line[len("ERROR "):].strip()
        if "InnocentVictim" not in fault:
            break
    u, fw = [], []
    if out_hex:
        raw = bytes.fromhex(out_hex)
        u = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
        fw = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    return status, u, fw, fault


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fields", default="all")
    a = ap.parse_args()
    bin_dir = Path(a.bin_dir)
    work = HERE / "run_iadd"
    work.mkdir(parents=True, exist_ok=True)
    write_inputs(work)
    want = SWEEPS.keys() if a.fields == "all" else a.fields.split(",")
    expect = (A + B) & 0xFFFFFFFF
    f = open(a.out, "a")
    for field in want:
        for v in SWEEPS[field]:
            status, u, fw, fault = run(work, "%s_%d" % (field, v), program(field, v), bin_dir)
            si = S.sentinel_word_index()
            sent_ok = len(fw) > si and fw[si] == S.sentinel_expected_f32()
            got = u[0] if u else None
            if status != "OK":
                outcome = "victim" if "InnocentVictim" in fault else "fault"
            elif not sent_ok:
                outcome = "invalid_run"
            elif got == S.POISON_U32:
                outcome = "no_write"
            elif got == expect:
                outcome = "ok"
            elif got == 0:
                outcome = "silent_zero"
            else:
                outcome = "wrong_value"
            f.write(json.dumps({"arm": "P11", "field": field, "value": v,
                                "outcome": outcome, "observed": got, "expect": expect,
                                "status": status, "fault_class": fault,
                                "sentinel_ok": sent_ok}, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        print("%-14s done" % field, flush=True)
    f.close()


if __name__ == "__main__":
    main()
