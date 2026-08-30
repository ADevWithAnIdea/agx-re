#!/usr/bin/env python3
"""EXP-0156 pilot: compile each NEW carrier on the G17P and tokenize its
`_agc.main` with our own tools/agx-isa decoder, so the frozen contract can pin
each splice site (mnemonic, offset, length, original bytes) instead of guessing.
No GPU dispatch -- compile + static disassemble only."""
import hashlib, json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb, agxparse  # noqa: E402

def compile_one(bin_dir, kp, out):
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(out),
                    "--no-fast-math", str(kp), "-f", "k"],
                   check=True, capture_output=True, timeout=180)
    buf = Path(out).read_bytes()
    roff, _ = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    return roff, pieces["_agc.main"]

def toks(main):
    out, off = [], 0
    while off < len(main):
        try:
            rec, L = isadb.decode_one(main, off)
        except ValueError as e:
            out.append({"off": off, "mnemonic": "<undecodable>", "err": str(e),
                        "hex": main[off:off+8].hex()})
            break
        out.append({"off": off, "mnemonic": rec["mnemonic"], "len": L,
                    "hex": rec["hex"]})
        off += L
    return out

if __name__ == "__main__":
    bin_dir = sys.argv[1]
    work = Path(sys.argv[2]); work.mkdir(parents=True, exist_ok=True)
    res = {}
    for kp in sorted((EXP / "kernels").glob("*.metal")):
        if kp.name in sys.argv[3:] or not sys.argv[3:]:
            try:
                roff, main = compile_one(bin_dir, kp, work / (kp.name + ".bin"))
                res[kp.name] = {"region_off": roff, "main_len": len(main),
                                "main_sha256": hashlib.sha256(main).hexdigest(),
                                "kernel_sha256": hashlib.sha256(kp.read_bytes()).hexdigest(),
                                "tokens": toks(main)}
            except subprocess.CalledProcessError as e:
                res[kp.name] = {"error": "compile failed",
                                "stderr": e.stderr.decode()[-800:]}
    print(json.dumps(res, indent=1))
