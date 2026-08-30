#!/usr/bin/env python3
"""EXP-0158 DIAGNOSTIC (not gated evidence): which off-natural choice does a
MAIN_DAG failure depend on?

run01 returned 23/100 MAIN_DAG correct where EXP-0112 (M4, all-natural fields)
returned 100/100.  Something this generator does differently is load-bearing.
Rather than guess, this script rebuilds a fixed set of FAILING programs with
exactly one off-natural knob disabled at a time and runs each on G17P.

Knobs (synth.DISABLE_OFFNAT):
  dl      device_load's documented don't-care fields go back to their natural values
  ds      device_store's likewise
  modhi   falu2.mod_hi forced to 0xC (EXP-0112's copied value) everywhere
  stop    stop.reserved forced to 0
  extlsb  device_load extmode bit 0 forced to 0 (the documented don't-care)

Output: one JSON row per (case, knob-set), appended and flushed.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
import synth as S        # noqa: E402
import generator as G    # noqa: E402

OUT_WORDS = 260
KNOBS = [(), ("dl",),
         ("dl:space",), ("dl:addr_mode",), ("dl:access_desc",), ("dl:reserved7",),
         ("dl:ld_format",), ("dl:dst_ext9",), ("dl:ldform_hi11",), ("dl:reserved13",)]

SIZE_CYCLE = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26,
              28, 30, 32, 35]


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
            so = r.stdout
        except subprocess.TimeoutExpired:
            return "HANG", [], ""
        status, out_hex, fault = "NO_STATUS", None, ""
        for line in so.splitlines():
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
    ap.add_argument("--seeds", default="1,2,7,9,10,13,15,20,25,30")
    a = ap.parse_args()
    bin_dir = Path(a.bin_dir)
    work = HERE / "run"
    work.mkdir(parents=True, exist_ok=True)
    write_inputs(work)
    f = open(a.out, "a")
    for seed in [int(x) for x in a.seeds.split(",")]:
        n_nodes = SIZE_CYCLE[seed % len(SIZE_CYCLE)]
        for knobs in KNOBS:
            S.DISABLE_OFFNAT = set(knobs)
            hexstr, oracle, meta = G.build_dag_program(
                seed, n_nodes, G.DAG_CARRIER_LEN, base_slot_out=G.SLOT_OUT,
                base_slot_in=G.SLOT_MEM)
            tag = "s%d_%s" % (seed, "+".join(knobs) or "none")
            status, words, fault = run(work, tag, hexstr, bin_dir)
            sent_i = S.sentinel_word_index()
            sent_ok = len(words) > sent_i and words[sent_i] == S.sentinel_expected_f32()
            bad = []
            for k, v in oracle.items():
                got = words[k] if k < len(words) else None
                if got != v:
                    bad.append({"word": k, "got": got, "want": v})
            row = {"seed": seed, "n_nodes": n_nodes, "knobs": list(knobs),
                   "status": status, "sentinel_ok": sent_ok, "n_words": len(oracle),
                   "n_bad": len(bad), "bad": bad[:4], "fault_class": fault}
            f.write(json.dumps(row, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            print(json.dumps(row, sort_keys=True), flush=True)
    S.DISABLE_OFFNAT = set()
    f.close()


if __name__ == "__main__":
    main()
