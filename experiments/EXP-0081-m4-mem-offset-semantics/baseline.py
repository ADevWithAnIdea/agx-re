#!/usr/bin/env python3
"""EXP-0077 baseline derivation (single source of truth for the probe anchors).

Deterministically re-derives, from the frozen kernel sources and the read-only
tools, the compiled `_agc.main` bytes of both probe kernels and the location and
decoded fields of the probe instructions:

  * kernels/ld_bank.metal -> the unique device_load with base_slot == 2
    (the `a[j]` load whose address fields the matrix splices);
  * kernels/st_bank.metal -> the unique device_store with base_slot == 1
    (the `tgt[j] = const` store whose address fields the matrix splices).

Everything is done with OUR OWN tools on OUR OWN compiled MSL: `shdump`
(public-API runtime compile + archive serialization), `agxparse` (our container
parser) and `tools/agx-isa` (our instruction DB codec). No Apple binary is
inspected; the only machine code touched is the compiled form of our own MSL.

CLI (used by run.py as a receipt-producing subprocess):
  python3 baseline.py --bin-dir DIR --out FILE.json
    compiles both kernels with DIR/shdump into DIR, derives the anchors,
    checks them against the frozen expectations below, writes JSON.
  python3 baseline.py --check-existing DIR
    same derivation, result on stdout only (no file), for verify gates.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHDUMP_TOOLS = REPO / "tools" / "shdump"
ISA_TOOLS = REPO / "tools" / "agx-isa"
sys.path.insert(0, str(SHDUMP_TOOLS))
sys.path.insert(0, str(ISA_TOOLS))
import agxparse          # noqa: E402  (our own parser)
import isadb             # noqa: E402  (our own instruction DB)

KERNELS = {"ld": "kernels/ld_bank.metal", "st": "kernels/st_bank.metal"}

# Frozen anchors (authored-stage derivation on this M4, macOS 26.6.2 / 25G82,
# clang 21, `--no-fast-math`). run.py re-derives at capture time and STOPs if
# any anchor differs: the frozen perturbation matrix is expressed over THESE
# bytes, so a different compiler output must not be silently swept.
FROZEN = {
    "ld": {
        "main_len": 114,
        "main_sha256": None,          # filled by freeze below (kept for readability)
        "probe_main_offset": 0x26,
        "probe_hex": "6700440202002000510100404600",
        "probe_fields": {"space": 0, "addr_mode": 68, "extmode": 2, "base_slot": 2,
                         "index_reg": 0, "access_desc": 32, "reserved7": 0,
                         "ld_format": 17, "dst_lo": 1, "dst_ext9": 1, "idx_off": 0,
                         "ldform_hi11": 16, "elem_size": 70, "reserved13": 0},
    },
    "st": {
        "main_len": 108,
        "main_sha256": None,
        "probe_main_offset": 0x4C,
        "probe_hex": "e700540401012100110000901100",
        "probe_fields": {"space": 0, "addr_mode": 84, "extmode": 4, "base_slot": 1,
                         "index_reg": 1, "access_desc": 33, "reserved7": 0,
                         "st_format": 17, "st_format_ext": 0, "idx_off": 0,
                         "st_desc_hi": 36, "elem_size": 17, "reserved13": 0},
    },
}
# The load's elem_size field is the full byte 0x46 (code 3 in bits[1:4]);
# the store's baseline byte+12 is 0x11 (bits[1:4] code 8, bit0 set) -- the
# store-side size descriptor encoding is NOT pre-assumed (the matrix probes it).


def compile_kernel(bin_dir, kernel_key, out_path):
    """Compile OUR MSL with OUR shdump. Returns (argv, exit, stderr)."""
    argv = [str(Path(bin_dir) / "shdump"), "-o", str(out_path), "-f", "k",
            "--no-fast-math", str(HERE / KERNELS[kernel_key])]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    return argv, p.returncode, p.stderr


def derive(bin_dir):
    """Derive anchors from a fresh compile. Returns the derivation dict."""
    out = {"schema": 1, "kernels": {}}
    for key in ("ld", "st"):
        arch = Path(bin_dir) / ("%s_bank.bin" % key)
        argv, rc, err = compile_kernel(bin_dir, key, arch)
        if rc != 0 or not arch.exists():
            raise SystemExit("baseline: shdump failed for %s (exit %d): %s" % (key, rc, err))
        buf = arch.read_bytes()
        pieces_ok, pieces = agxparse.extract_agx(buf)
        main = pieces.get("_agc.main") if pieces_ok else None
        if main is None:
            raise SystemExit("baseline: no _agc.main for %s" % key)
        recs, leftover = isadb.disassemble(main)
        if leftover:
            raise SystemExit("baseline: %s main does not tokenize cleanly "
                             "(leftover %s)" % (key, leftover.hex()))
        # every instruction must survive an assemble(decode()) round trip
        off = 0
        probe_hits = []
        for r in recs:
            if isadb.assemble(r["mnemonic"], r["fields"]) != bytes.fromhex(r["hex"]):
                raise SystemExit("baseline: %s round-trip failure at +0x%x" % (key, off))
            want = "device_load" if key == "ld" else "device_store"
            slot = 2 if key == "ld" else 1
            if r["mnemonic"] == want and r["fields"]["base_slot"] == slot:
                probe_hits.append((off, r))
            off += r["length"]
        if len(probe_hits) != 1:
            raise SystemExit("baseline: %s probe rule matched %d instructions (want 1)"
                             % (key, len(probe_hits)))
        poff, prec = probe_hits[0]
        out["kernels"][key] = {
            "source": KERNELS[key],
            "source_sha256": hashlib.sha256((HERE / KERNELS[key]).read_bytes()).hexdigest(),
            "archive_sha256": hashlib.sha256(buf).hexdigest(),
            "main_len": len(main),
            "main_hex": main.hex(),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "probe_main_offset": poff,
            "probe_hex": prec["hex"],
            "probe_fields": prec["fields"],
        }
    return out


def check_frozen(d):
    """Compare a derivation against the frozen anchors. Returns list of diffs."""
    diffs = []
    for key in ("ld", "st"):
        got, want = d["kernels"][key], FROZEN[key]
        for f in ("main_len", "probe_main_offset", "probe_hex", "probe_fields"):
            if got[f] != want[f]:
                diffs.append("%s.%s: got %r want %r" % (key, f, got[f], want[f]))
    return diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    d = derive(a.bin_dir)
    d["frozen_anchor_diffs"] = check_frozen(d)
    txt = json.dumps(d, indent=2, sort_keys=True) + "\n"
    if a.out:
        Path(a.out).write_text(txt)
    sys.stdout.write(txt)
    return 1 if d["frozen_anchor_diffs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
