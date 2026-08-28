#!/usr/bin/env python3
"""EXP-0141 splice-site locator: recompile every own-MSL carrier and re-derive
each target instruction's offset inside `_agc.main` by disassembling with
tools/agx-isa. Nothing is hardcoded: the offset in `sweepdefs.SITES` is an
ASSERTION, re-checked before every capture, so a compiler change is a loud stop
rather than a silent splice into the wrong instruction.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
import carriers as C  # noqa: E402
import sweepdefs as SD  # noqa: E402


def compile_carrier(name, bin_dir, out_dir):
    spec = C.CARRIERS[name]
    arch = Path(out_dir) / ("carrier_%s.bin" % name)
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(arch), "--no-fast-math",
                    str(EXP / spec["metal"]), "-f", spec["func"]],
                   check=True, capture_output=True, timeout=120)
    off = int(subprocess.check_output(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(arch), "--locate", "_agc.main"], text=True, timeout=60).split()[0])
    hexstr = subprocess.check_output(
        [sys.executable, "-B", str(REPO / "tools" / "shdump" / "agxparse.py"),
         str(arch), "--extract-hex"], text=True, timeout=60).strip()
    return arch, off, bytes.fromhex(hexstr)


def tokenize(main):
    out, off = [], 0
    recs, _ = isadb.disassemble(main)
    for r in recs:
        L = r.get("length")
        if not L:
            break
        out.append((off, r["mnemonic"], main[off:off + L]))
        off += L
    return out


def locate_all(bin_dir, out_dir):
    """Returns {site_key: (mnemonic, main_offset, length, original_bytes)} plus
    {carrier: (archive_path, main_off, main_len, main_sha)}."""
    sites, mains = {}, {}
    for key, (mnem, want_off, ln) in SD.SITES.items():
        carrier = key.split("_")[0]
        if carrier not in mains:
            arch, moff, main = compile_carrier(carrier, bin_dir, out_dir)
            mains[carrier] = (str(arch), moff, main)
        arch, moff, main = mains[carrier]
        toks = tokenize(main)
        hits = [(o, m, b) for (o, m, b) in toks if m == mnem]
        if not hits:
            raise SystemExit("locate: %s not found in carrier %s" % (mnem, carrier))
        match = [h for h in hits if h[0] == want_off]
        if not match:
            raise SystemExit("locate: %s expected at +0x%x in %s, found at %s"
                             % (mnem, want_off, carrier, [hex(h[0]) for h in hits]))
        o, m, b = match[0]
        if len(b) != ln:
            raise SystemExit("locate: %s length %d != expected %d" % (mnem, len(b), ln))
        sites[key] = (mnem, o, ln, b)
    return sites, mains


if __name__ == "__main__":
    import json
    bin_dir, out_dir = sys.argv[1], sys.argv[2]
    sites, mains = locate_all(bin_dir, out_dir)
    print(json.dumps({k: [v[0], v[1], v[2], v[3].hex()] for k, v in sites.items()},
                     indent=1, sort_keys=True))
    for c, (a, mo, main) in sorted(mains.items()):
        print("carrier %-9s main_off=%d main_len=%d" % (c, mo, len(main)))
