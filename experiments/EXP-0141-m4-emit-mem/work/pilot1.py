#!/usr/bin/env python3
"""EXP-0141 PILOT (work/, NOT raw/): validate the synthesis carrier + the
device_load->consumer construction, and measure persistent-runner throughput.
Pilot output is scratch; nothing here is evidence."""
import json, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # work/
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(REPO / "tools" / "agxtest"))
import isa_helpers as H
from persistrun import PersistRunner

BIN = HERE / "pilot_bin"
ARCH = BIN / "carrier.bin"
CARRIER_LEN = 170
SLOT_OUT, SLOT_MEM = 0, 1
MEM = [133.75, -8.5, 7.25, -3.125, 0.5, -64.0, 1024.0, 0.03125,
       2.0, -1.0, 16.0, -256.0, 0.25, 3.5, -0.5, 8.0]
OUT_WORDS = 8

MAIN_OFF = int(subprocess.check_output(
    [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
     str(ARCH), "--locate", "_agc.main"], text=True).split()[0])
BASE = ARCH.read_bytes()
memf = HERE / "mem.bin"
memf.write_bytes(b"".join(struct.pack("<f", v) for v in MEM))
spf = HERE / "sp.bin"


def run(r, prog=None, timeout=10):
    if prog is None:
        spf.write_bytes(BASE)
    else:
        assert len(prog) == CARRIER_LEN
        b = bytearray(BASE)
        b[MAIN_OFF:MAIN_OFF + CARRIER_LEN] = prog
        spf.write_bytes(bytes(b))
    resp = r.request(archive=str(spf), grid=1, tg=1, ins={1: str(memf)},
                     outs={0: OUT_WORDS * 4}, timeout=timeout)
    ws = None
    if 0 in resp["outs"]:
        raw = resp["outs"][0]
        ws = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw), 4)]
    return resp["status"], ws


def prog_alu(R, dst_lo=1, dst_ext9=1, extmode=None, D=8, idx=None, **ldkw):
    if extmode is None:
        extmode = 2 * R
    if idx is None:
        idx = H.pick_idx_reg(R)
    return H.build_program([
        H.mov_imm(idx, 0),
        H.device_load(idx, SLOT_MEM, extmode, dst_lo=dst_lo, dst_ext9=dst_ext9,
                      idx_off=1, **ldkw),
        H.falu2i_raw(D, R, 1.5),
        H.device_store(idx, SLOT_OUT, data_reg=D),
    ], CARRIER_LEN)


def prog_fwd(R, addr_mode=0x54, dst_lo=1, dst_ext9=1, idx=None, **ldkw):
    if idx is None:
        idx = H.pick_idx_reg(R)
    return H.build_program([
        H.mov_imm(idx, 0),
        H.device_load(idx, SLOT_MEM, 2 * R, dst_lo=dst_lo, dst_ext9=dst_ext9,
                      idx_off=1, **ldkw),
        H.device_store(idx, SLOT_OUT, data_reg=R, addr_mode=addr_mode),
    ], CARRIER_LEN)


def main():
    r = PersistRunner(source=str(EXP / "kernels" / "carrier.metal"), function="k",
                      fast_math=False, agxrun_persist=str(BIN / "agxrun_persist"))
    try:
        print("device:", r.device)
        print("P0 unspliced          :", run(r))
        print("P1 alu R=7 tok(1,1)   :", run(r, prog_alu(7)), " expect out0=-7.0")
        print("P2 alu R=7 tok(0,0)   :", run(r, prog_alu(7, dst_lo=0, dst_ext9=0)), " expect silent 1.5")
        print("P3 fwd R=7 am=0x54    :", run(r, prog_fwd(7, 0x54)), " expect -8.5?")
        print("P4 fwd R=7 am=0x56    :", run(r, prog_fwd(7, 0x56)), " expect -8.5?")
        print("P5 alu R=3            :", run(r, prog_alu(3)))
        print("P6 alu R=20           :", run(r, prog_alu(20)))
        print("P7 alu extmode odd 15 :", run(r, prog_alu(7, extmode=15)))
        t0 = time.time()
        N = 60
        for i in range(N):
            run(r, prog_alu(7 if i % 2 == 0 else 3))
        dt = time.time() - t0
        print("throughput: %d req in %.2fs = %.1f ms/req" % (N, dt, dt / N * 1000))
    finally:
        r.close()


main()
