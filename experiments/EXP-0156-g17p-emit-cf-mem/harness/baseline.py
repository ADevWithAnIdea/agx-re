#!/usr/bin/env python3
"""EXP-0156 baseline (target: **A18 Pro / G17P**): re-derive every carrier fact fresh (compile + static
disassemble only -- no GPU dispatch) instead of trusting a constant.  run.py
calls this before every capture and hard-fails on any drift.

Two traps this defends against:
  * EXP-0112's documented one -- `base_slot` assignment is decided by the
    compiler from the WHOLE kernel body, so the CF skeleton's slots must be read
    off the actual carrier's own compile, never a stand-in probe; and
  * splicing into the wrong instruction -- every atomic site's mnemonic, offset
    and length is re-derived and asserted, so a compiler change is a loud stop.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb      # noqa: E402
import agxparse   # noqa: E402
sys.path.insert(0, str(HERE))
import carriers as C     # noqa: E402
import isa_helpers as H  # noqa: E402


def compile_carrier(bin_dir, kernel_path, out_path):
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(out_path),
                    "--no-fast-math", str(kernel_path), "-f", "k"],
                   check=True, capture_output=True, timeout=180)
    buf = Path(out_path).read_bytes()
    roff, _ = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    return buf, roff, pieces["_agc.main"]


def tokenize(main):
    out, off = [], 0
    while off < len(main):
        try:
            rec, L = isadb.decode_one(main, off)
        except ValueError as e:
            out.append({"off": off, "mnemonic": "<undecodable>", "error": str(e)})
            break
        out.append({"off": off, "mnemonic": rec["mnemonic"], "hex": rec["hex"],
                    "len": L, "base_slot": rec["fields"].get("base_slot")})
        off += L
    return out


def derive(bin_dir, work_dir):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    facts = {"carriers": {}, "sites": {}}
    compiled = {}
    for name, spec in C.CARRIERS.items():
        src = spec["metal"]
        if src not in compiled:
            kp = EXP / "kernels" / src
            buf, roff, main = compile_carrier(bin_dir, kp,
                                              work_dir / (src + ".bin"))
            compiled[src] = (kp, buf, roff, main, tokenize(main))
        kp, buf, roff, main, toks = compiled[src]
        assert len(main) == spec["main_len"], (
            "carrier %s (%s) _agc.main length drifted: %d != %d"
            % (name, src, len(main), spec["main_len"]))
        facts["carriers"][name] = {
            "kernel": src,
            "kernel_sha256": hashlib.sha256(kp.read_bytes()).hexdigest(),
            "main_len": len(main),
            "main_sha256": hashlib.sha256(main).hexdigest(),
            "region_off": roff,
            "archive": str(work_dir / (src + ".bin")),
            "load_slots": [t.get("base_slot") for t in toks
                           if t["mnemonic"] == "device_load"],
            "store_slots": [t.get("base_slot") for t in toks
                            if t["mnemonic"] == "device_store"],
            "tokens": toks,
        }
    # --- CF skeleton: base_slots read off THIS carrier's own compile ---------
    cf = facts["carriers"]["cfN"]
    assert cf["load_slots"] == [H.CF_SLOT_A, H.CF_SLOT_N], cf["load_slots"]
    assert cf["store_slots"] == [H.CF_SLOT_OUT], cf["store_slots"]
    starts = H.cf_starts(cf["main_len"])
    assert starts == H.CF_STARTS_EXPECT, (
        "the frozen CF skeleton's instruction layout drifted:\n%r" % (starts,))
    facts["cf_starts"] = starts
    # --- atomic splice sites: mnemonic + offset + length all asserted --------
    for key, (mnem, want_off, want_len) in C.SITES.items():
        toks = facts["carriers"][key]["tokens"]
        _, _, _, main, _ = compiled[C.CARRIERS[key]["metal"]]
        hits = [t for t in toks if t["mnemonic"] == mnem]
        if len(hits) != 1:
            raise SystemExit("locate: %s appears %d times in carrier %s"
                             % (mnem, len(hits), key))
        t = hits[0]
        if t["off"] != want_off or t["len"] != want_len:
            raise SystemExit("locate: %s in %s at +%d len %d, expected +%d len %d"
                             % (mnem, key, t["off"], t["len"], want_off, want_len))
        facts["sites"][key] = (mnem, t["off"], t["len"],
                               bytes.fromhex(t["hex"]))
    # --- RAW sites: pinned by EXACT BYTES at an EXACT offset ------------------
    # Our own decoder mis-tokenizes the 0x11 native-bfloat group and the 0x?8
    # high-half group (a db defect this experiment reports), so these sites
    # cannot be located by mnemonic.  Asserting the literal bytes is STRICTER
    # than a mnemonic match, and a compiler change is still a loud stop.
    facts["raw_sites"] = {}
    for key, entries in getattr(C, "RAW_SITES", {}).items():
        _, _, _, main, _ = compiled[C.CARRIERS[key]["metal"]]
        got = []
        for (label, off, want) in entries:
            have = bytes(main[off:off + len(want)])
            if have != want:
                raise SystemExit(
                    "raw site %s/%s at +%d: %s != expected %s"
                    % (key, label, off, have.hex(), want.hex()))
            if main.count(want) != 1:
                raise SystemExit(
                    "raw site %s/%s pattern %s is not unique in _agc.main (%d)"
                    % (key, label, want.hex(), main.count(want)))
            got.append((label, off, want))
        facts["raw_sites"][key] = got
    return facts


if __name__ == "__main__":
    f = derive(sys.argv[1] if len(sys.argv) > 1 else str(EXP / "work" / "bin"),
               sys.argv[2] if len(sys.argv) > 2 else str(EXP / "work" / "baseline_bin"))
    out = {"carriers": {k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                        for k, v in f["carriers"].items()},
           "sites": {k: [v[0], v[1], v[2], v[3].hex()] for k, v in f["sites"].items()},
           "cf_starts": f["cf_starts"],
           "raw_sites": {k: [[a, b, c.hex()] for (a, b, c) in v]
                         for k, v in f["raw_sites"].items()}}
    print(json.dumps(out, indent=1))
