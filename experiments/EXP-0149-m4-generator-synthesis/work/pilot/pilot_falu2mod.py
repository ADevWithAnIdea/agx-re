#!/usr/bin/env python3
"""EXP-0149 DISCLOSED PRE-FREEZE PILOT (PRE_REGISTRATION.md SS6).

EXP-0112 copied falu2's `mod_hi = 0xC` verbatim ("the natural value observed
in every own-compiled falu2 reg-reg instance") and left `mod_lo = 0`, which
`validation.json` still labels `untested`.  Those are two of the copied
tokens this experiment must eliminate, and no prior sweep covers them.

This pilot sweeps both on OUR carrier, on a fully synthesised program, so the
frozen generator can pick a value from a MEASURED accepted set instead of
copying one.  Its result is recorded in PRE_REGISTRATION.md before freeze and
re-executed inside the gated runs.
"""
import json, struct, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
import synth as S
import generator as G
import isadb

BIN = EXP / "work" / "baseline_bin"
WORK = HERE / "run"
WORK.mkdir(parents=True, exist_ok=True)
POISON = 0xDEADBEEF


def falu2_raw(led, dst, opsel, srcA, srcB, last, mod_hi, mod_lo):
    return S.emit(led, "falu2", {
        "dst": S.FV(dst, S.RULE, "p"), "srcA_size": S.FV(1, S.RULE, "p"),
        "srcA_reg": S.FV(srcA & 0x3F, S.RULE, "p"), "opsel": S.FV(opsel, S.RULE, "p"),
        "opflags": S.FV(((1 if last else 0) | 2), S.RULE, "p"),
        "srcB_size": S.FV(1, S.RULE, "p"), "srcB_reg": S.FV(srcB & 0x3F, S.RULE, "p"),
        "ctrl": S.FV(0, S.RULE, "p"), "srcB_imm": S.FV(0, S.RULE, "p"),
        "mod_lo": S.FV(mod_lo & 0x7, S.RULE, "p"), "srcB_neg": S.FV(0, S.RULE, "p"),
        "mod_hi": S.FV(mod_hi & 0xF, S.RULE, "p"),
        "srcA_reg_top": S.FV(0, S.RULE, "p"), "srcB_reg_top": S.FV(0, S.RULE, "p"),
    })


def program(mod_hi, mod_lo):
    led = S.Ledger()
    ins = [S.mov_imm(led, S.R_IDX, 0, salt="p"),
           S.falu2i(led, 0, "fadd", S.R_UNWRITTEN, 3.0, True, False, salt="p0"),
           S.falu2i(led, 1, "fadd", S.R_UNWRITTEN, 5.0, True, False, salt="p1"),
           falu2_raw(led, 2, 4, 0, 1, True, mod_hi, mod_lo),
           S.device_store(led, S.R_IDX, 0, G.SLOT_OUT, data_reg=2, salt="p",
                          offnatural=False),
           S.stop(led, offnatural=False)]
    prog = S.build_program(led, ins, G.DAG_CARRIER_LEN)
    S.assert_round_trip(prog)
    return prog.hex()


def run(hexstr, tag):
    w = WORK / tag
    w.mkdir(parents=True, exist_ok=True)
    mem = w / "mem.bin"
    mem.write_bytes(b"".join(struct.pack("<f", v) for v in G.MEM_WORDS))
    imem = w / "imem.bin"
    imem.write_bytes(b"".join(struct.pack("<i", v) for v in G.IMEM_WORDS))
    poison = w / "poison.bin"
    poison.write_bytes(struct.pack("<I", POISON))
    argv = [sys.executable, "-B", str(REPO / "tools" / "agxtest" / "agxtest.py"),
            "--source", str(EXP / "kernels" / "carrier_dag.metal"), "--function", "k",
            "--grid", "1", "--tg", "1", "--no-fast-math",
            "--shdump", str(BIN / "shdump"), "--agxrun", str(BIN / "agxrun"),
            "--agxparse", str(REPO / "tools" / "shdump" / "agxparse.py"),
            "--workdir", str(w), "--archive", str(w / ("arch_%s.bin" % tag)),
            "--run-timeout", "30",
            "--buf", "0=@%s" % poison, "--buf", "1=@%s" % mem, "--buf", "2=@%s" % imem,
            "--out", "0=1", "--splice", "_agc.main@0=%s" % hexstr]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    status, out_hex, err = "NO_STATUS", None, None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("OUT 0 "):
            out_hex = line[len("OUT 0 "):].strip()
        elif line.startswith("ERROR "):
            err = line[6:].strip()
    val = None
    if out_hex:
        val = struct.unpack("<f", bytes.fromhex(out_hex))[0]
    return status, val, err


def main():
    S.freeze_pilot([0xC], [0])
    out = []
    print("== mod_hi sweep (mod_lo=0), expect 8.0 ==")
    for mh in range(16):
        st, v, e = run(program(mh, 0), "mh%02d" % mh)
        rec = {"field": "mod_hi", "value": mh, "status": st, "out": v, "err": e,
               "ok": (st == "OK" and v == 8.0)}
        out.append(rec)
        print("  mod_hi=%2d %-14s out=%r %s" % (mh, st, v, "OK" if rec["ok"] else ""))
    print("== mod_lo sweep (mod_hi=0xC), expect 8.0 ==")
    for ml in range(8):
        st, v, e = run(program(0xC, ml), "ml%02d" % ml)
        rec = {"field": "mod_lo", "value": ml, "status": st, "out": v, "err": e,
               "ok": (st == "OK" and v == 8.0)}
        out.append(rec)
        print("  mod_lo=%2d %-14s out=%r %s" % (ml, st, v, "OK" if rec["ok"] else ""))
    (HERE / "pilot_falu2mod.json").write_text(json.dumps(out, indent=1) + "\n")
    print("mod_hi accepted:", [r["value"] for r in out if r["field"] == "mod_hi" and r["ok"]])
    print("mod_lo accepted:", [r["value"] for r in out if r["field"] == "mod_lo" and r["ok"]])


if __name__ == "__main__":
    main()
