#!/usr/bin/env python3
"""Re-derivation of the decisive pilot-probe findings that shaped this
experiment's design (see PRE_REGISTRATION.md). Each function is one
independently-constructed, single-purpose probe run against real M4
hardware via tools/agxtest/agxtest.py, printing its own PASS/FAIL verdict.
Run: python3 -B diagnostics/redecisive.py 2>&1 | tee diagnostics/redecisive_output.txt
"""
import struct, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb            # noqa: E402
import isa_helpers as H  # noqa: E402

BIN = EXP / "work_diag" / "bin"
WORK = EXP / "work_diag"


def build_tools():
    WORK.mkdir(exist_ok=True)
    r = subprocess.run([str(EXP / "harness" / "build.sh"), str(BIN)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    print("tools built:", r.stdout.strip())


def run_prog(tag, prog_bytes, out_words=2, buf1=None, buf2=None):
    wd = WORK / tag
    wd.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / "carrier_p1.metal"), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(BIN / "shdump"), "--agxrun", str(BIN / "agxrun"),
            "--agxparse", str(REPO / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(wd), "--run-timeout", "30"]
    f1 = wd / "b1.bin"; f1.write_bytes(buf1 or b"\x00" * 16)
    f2 = wd / "b2.bin"; f2.write_bytes(buf2 or b"\x00" * 16)
    argv += ["--buf", "1=@%s" % f1, "--buf", "2=@%s" % f2, "--out", "0=%d" % out_words]
    argv += ["--splice", "_agc.main@0=%s" % prog_bytes.hex()]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
    status, out_hex = "NO_STATUS", None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("OUT 0 "):
            out_hex = line[len("OUT 0 "):].strip()
    print("[%s] argv=%s" % (tag, " ".join(argv)))
    print("[%s] STATUS=%s OUT=%s" % (tag, status, out_hex))
    return status, out_hex


def words(out_hex):
    raw = bytes.fromhex(out_hex) if out_hex else b""
    return [struct.unpack("<f", raw[i:i+4])[0] for i in range(0, len(raw)-3, 4)]


def finding_1_falu2_srcB_needs_opflags3():
    print("\n=== FINDING: falu2 register-form srcB requires opflags=3 (not 1) ===")
    prog = H.build_program([
        H.falu2i(0, "fadd", srcA_reg=50, k=8.0, last_use_srcA=True),
        H.falu2i(2, "fadd", srcA_reg=50, k=5.0, last_use_srcA=True),
        H.falu2(3, "fadd", srcA_reg=0, srcB_reg=2, last_use_srcA=False, opflags_extra=1),  # opflags=1<<1=2 (bit0=0)
        H.device_store(index_reg=0, idx_off=0, base_slot=0, data_reg=3, addr_mode=0x54),
        H.stop(),
    ], 520)
    s, o = run_prog("f1_opflags1", prog)
    print("  opflags~1 (bit1 set, bit0 CLEAR): expect WRONG (not 13.0) -> got", words(o))
    prog2 = H.build_program([
        H.falu2i(0, "fadd", srcA_reg=50, k=8.0, last_use_srcA=True),
        H.falu2i(2, "fadd", srcA_reg=50, k=5.0, last_use_srcA=True),
        H.falu2(3, "fadd", srcA_reg=0, srcB_reg=2, last_use_srcA=True, both_real=True),  # opflags=3
        H.device_store(index_reg=0, idx_off=0, base_slot=0, data_reg=3, addr_mode=0x54),
        H.stop(),
    ], 520)
    s2, o2 = run_prog("f1_opflags3", prog2)
    print("  opflags=3 (bit0 AND bit1 set): expect CORRECT 13.0 -> got", words(o2))
    ok = (words(o2) and abs(words(o2)[0] - 13.0) < 1e-4) and not (words(o) and abs(words(o)[0] - 13.0) < 1e-4)
    print("  VERDICT:", "CONFIRMED" if ok else "NOT REPRODUCED")


def finding_2_device_load_to_falu2i_fails():
    print("\n=== FINDING: device_load's result is NOT reliably readable by falu2i ===")
    instrs = [
        H.mov_imm(15, 0),
        isadb.assemble("device_load", {"space": 0x10, "addr_mode": 0x44, "extmode": 0, "base_slot": 1,
                                         "index_reg": 15, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
                                         "dst_lo": 1, "dst_ext9": 1, "idx_off": 0, "ldform_hi11": 0x10,
                                         "elem_size": 0x46, "reserved13": 0}),
        H.falu2i(9, "fadd", srcA_reg=5, k=0.0, last_use_srcA=True),
        H.device_store(index_reg=15, idx_off=0, base_slot=0, data_reg=9, addr_mode=0x54),
        H.stop(),
    ]
    prog = H.build_program(instrs, 520)
    fin = b"".join(struct.pack("<f", v) for v in [3.0, 4.0, 5.0, 6.0])
    s, o = run_prog("f2_load_to_falu2i", prog, buf1=fin)
    print("  expect fin[0]=3.0 delivered through the load then read via falu2i srcA=5")
    print("  got:", words(o), "-- FALSIFIED (reads 0, not 3.0)" if (words(o) and words(o)[0] == 0.0) else "unexpected")


def finding_3_device_load_to_store_direct_forward_works():
    print("\n=== CONTROL: device_load -> device_store DIRECT FORWARD (addr_mode=0x56) DOES work ===")
    instrs = [
        H.mov_imm(15, 0),
        isadb.assemble("device_load", {"space": 0x10, "addr_mode": 0x44, "extmode": 0, "base_slot": 1,
                                         "index_reg": 15, "access_desc": 0x20, "reserved7": 0, "ld_format": 0x11,
                                         "dst_lo": 1, "dst_ext9": 1, "idx_off": 0, "ldform_hi11": 0x10,
                                         "elem_size": 0x46, "reserved13": 0}),
        isadb.assemble("device_store", {"space": 0, "addr_mode": 0x56, "extmode": 0, "base_slot": 0,
                                          "index_reg": 15, "access_desc": 0x21, "reserved7": 0, "st_format": 0x11,
                                          "st_format_ext": 0, "idx_off": 0, "st_desc_hi": 0x24, "elem_size": 0x11,
                                          "reserved13": 0}),
        H.stop(),
    ]
    prog = H.build_program(instrs, 520)
    fin = b"".join(struct.pack("<f", v) for v in [3.0, 4.0, 5.0, 6.0])
    s, o = run_prog("f3_load_to_store", prog, buf1=fin)
    print("  expect fin[0]=3.0 forwarded directly -> got", words(o),
          "-- CONFIRMED" if (words(o) and abs(words(o)[0] - 3.0) < 1e-4) else "NOT REPRODUCED")


def finding_4_reg_move_cannot_read_alu_written_gpr():
    print("\n=== FINDING: reg_move (EXP-0087 proven encoding) cannot reliably read a falu2-written GPR ===")
    instrs = [
        H.falu2i(0, "fadd", srcA_reg=50, k=8.0, last_use_srcA=True),
        H.falu2(2, "fadd", srcA_reg=0, srcB_reg=51, last_use_srcA=True),  # r2 = 8.0 (proven path)
        H.reg_move(3, 2),
        H.device_store(index_reg=0, idx_off=0, base_slot=0, data_reg=3, addr_mode=0x54),
        H.stop(),
    ]
    prog = H.build_program(instrs, 520)
    s, o = run_prog("f4_regmove", prog)
    print("  r2=8.0 (independently proven correct); reg_move(3,2) then store r3: expect 8.0")
    print("  got:", words(o), "-- FALSIFIED" if not (words(o) and abs(words(o)[0]-8.0) < 1e-4) else "unexpected-pass")


def finding_5_extmode_is_2x_data_reg():
    print("\n=== FINDING: device_store extmode = 2*data_reg (addr_mode=0x54) ===")
    instrs = [
        H.falu2i(0, "fadd", srcA_reg=50, k=3.0, last_use_srcA=True),
        H.falu2i(1, "fadd", srcA_reg=0, k=4.0, last_use_srcA=True),
        H.device_store(index_reg=0, idx_off=0, base_slot=0, data_reg=1, addr_mode=0x54),  # extmode auto = 2*1 = 2
        H.stop(),
    ]
    prog = H.build_program(instrs, 520)
    s, o = run_prog("f5_extmode", prog)
    print("  r1=7.0 (3.0+4.0), stored via data_reg=1 -> extmode auto-computed as 2*1=2")
    print("  got:", words(o), "-- CONFIRMED" if (words(o) and abs(words(o)[0]-7.0) < 1e-4) else "NOT REPRODUCED")


def main():
    build_tools()
    finding_1_falu2_srcB_needs_opflags3()
    finding_2_device_load_to_falu2i_fails()
    finding_3_device_load_to_store_direct_forward_works()
    finding_4_reg_move_cannot_read_alu_written_gpr()
    finding_5_extmode_is_2x_data_reg()
    print("\nAll re-derivations complete.")


if __name__ == "__main__":
    main()
