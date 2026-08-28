#!/usr/bin/env python3
"""EXP-0141: compile kernels/rayquery_probe.metal and report every `mem_fence8`
instance the compiler emits. COMPILE-ONLY -- no dispatch, so this is
corpus-correlation evidence about the byte+3 `mask` value and nothing more.
"""
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


def main():
    bindir = EXP / "work" / "mf8"
    bindir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(EXP / "harness" / "build.sh"), str(bindir)], check=True,
                   capture_output=True, timeout=300)
    out = bindir / "rq.bin"
    subprocess.run([str(bindir / "shdump"), "-o", str(out), "--no-fast-math",
                    str(EXP / "kernels" / "rayquery_probe.metal"), "-f", "k"],
                   check=True, capture_output=True, timeout=180)
    hx = subprocess.check_output(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(out), "--extract-hex"], text=True, timeout=120).strip()
    b = bytes.fromhex(hx)
    recs, _ = isadb.disassemble(b)
    off, found = 0, []
    for r in recs:
        L = r.get("length")
        if not L:
            break
        if r["mnemonic"] == "mem_fence8":
            found.append({"offset": off, "bytes": b[off:off + L].hex(),
                          "fields": r["fields"]})
        off += L
    rep = {"kernel": "kernels/rayquery_probe.metal", "method": "compile-only",
           "main_len": len(b), "decoded_to": off, "mem_fence8_instances": found,
           "note": "mask (byte+3) values observed here; db.json records 0x14 / "
                   "0x0c. NOT dispatched: agxrun_persist cannot bind an "
                   "acceleration structure, so mem_fence8.mask and .tail remain "
                   "`untested` in analysis/field_verdicts.json."}
    (EXP / "analysis" / "memfence8_locate.json").write_text(
        json.dumps(rep, indent=1, sort_keys=True) + "\n")
    print(json.dumps(rep, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
