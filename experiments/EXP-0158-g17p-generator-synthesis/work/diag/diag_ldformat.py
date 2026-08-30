#!/usr/bin/env python3
"""EXP-0158 DIAGNOSTIC: why does `device_load.ld_format` != 17 corrupt a DAG?

`work/diag/diag01/02.jsonl` isolated it: with `ld_format` forced to its natural
0x11 every generated DAG is bit-exact, and with the generator's off-natural
choice from EXP-0141's "delivers the 32-bit scalar" set {17,19,21,23,25,27} the
DAGs break -- while the pilot's SINGLE-load arm (P7) found all six `ok`.

The obvious explanation is that the other codes describe a WIDER load that
writes additional consecutive registers, which is invisible when nothing else
is live and fatal in a register-allocated program.  This probe tests exactly
that: pre-load r7..r12 with six distinct, exactly-representable constants, do
ONE device_load into r7 under ld_format F, then store all six registers.  A
register other than r7 that changes is a destination the code wrote.

Sweeps F over the whole 0..63 field so the answer covers every code, not just
the six.
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
SLOT_OUT, SLOT_MEM = 0, 1
CARRIER_LEN = 1536
BASE_R = 7
WITNESS = [7, 8, 9, 10, 11, 12]
SEED_K = {7: 2.0, 8: 4.0, 9: 6.0, 10: 8.0, 11: 12.0, 12: 16.0}   # exact minifloats
IDX_OFF = 100


def program(ld_format):
    led = S.Ledger()
    ins = [S.mov_imm(led, S.R_IDX, 0, salt="lf")]
    ins += S.sentinel_instrs(led, SLOT_OUT, "lf")
    for r in WITNESS:
        ins.append(S.falu2i(led, r, "fadd", S.R_UNWRITTEN, SEED_K[r], True, False,
                            salt="lfs%d" % r))
    ins.append(S.device_load(led, S.R_IDX, IDX_OFF, 3, SLOT_MEM, R=BASE_R, salt="lf",
                             offnatural=False, ld_format_override=ld_format))
    for n, r in enumerate(WITNESS):
        ins.append(S.falu2i(led, 0, "fadd", r, 0.0, True, True, salt="lfc%d" % r))
        ins.append(S.device_store(led, S.R_IDX, n, SLOT_OUT, data_reg=0, salt="lf%d" % n,
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
    words = []
    if out_hex:
        raw = bytes.fromhex(out_hex)
        words = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    return status, words, fault


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--codes", default="all")
    a = ap.parse_args()
    bin_dir = Path(a.bin_dir)
    work = HERE / "run_lf"
    work.mkdir(parents=True, exist_ok=True)
    write_inputs(work)
    codes = range(64) if a.codes == "all" else [int(x) for x in a.codes.split(",")]
    loaded = G.MEM_WORDS[S.load_byte_offset(0, IDX_OFF, 3) // 4]
    f = open(a.out, "a")
    for F in codes:
        status, words, fault = run(work, "lf%02d" % F, program(F), bin_dir)
        si = S.sentinel_word_index()
        sent_ok = len(words) > si and words[si] == S.sentinel_expected_f32()
        obs = dict((r, (words[n * 4] if n * 4 < len(words) else None))
                   for n, r in enumerate(WITNESS))
        changed = [r for n, r in enumerate(WITNESS)
                   if r != BASE_R and obs[r] != S.f32(SEED_K[r])]
        f.write(json.dumps({"ld_format": F, "status": status, "sentinel_ok": sent_ok,
                            "fault_class": fault, "loaded_word": loaded,
                            "r7_got_load": obs[BASE_R] == loaded,
                            "observed": dict((str(k), v) for k, v in obs.items()),
                            "seed": dict((str(k), S.f32(v)) for k, v in SEED_K.items()),
                            "clobbered_registers": changed}, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        print("F=%2d status=%-12s r7_loaded=%-5s clobbered=%s obs=%s"
              % (F, status, obs[BASE_R] == loaded, changed,
                 [obs[r] for r in WITNESS]), flush=True)
    f.close()


if __name__ == "__main__":
    main()
