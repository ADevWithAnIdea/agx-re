#!/usr/bin/env python3
"""cube_probe.py -- EXP-0204 tier-3 SYNTHESIS probe for `cubearray_coord_const`.

NOT A FIELD SWEEP, and no promotion is possible from it (PRE_REGISTRATION sec.3
H5 says so in advance).  Two prior experiments already established that the
descriptor cannot be provoked from MSL at all:

  EXP-0148 -- 0 firings in 1080 corpus files under both the strict and the
              resync walk.  In k_tex_array_cube, the kernel it is NAMED after,
              its `f0 c0 04` signature sits at offset 48, INTERIOR to the 12-byte
              tex_addr_setup token spanning 40..52, so it can never be reached.
  EXP-0187 -- 31 cube / cube-array constructs authored and compiled across 12
              shapes, 0 signature hits and 0 walk hits.

Re-running either would learn nothing.  The one question neither answered is the
ORCHESTRATOR'S question -- is the descriptor real, or should it be deleted or
re-anchored?  That is answerable by SYNTHESIS rather than provocation: place the
four bytes BY HAND at a proven instruction boundary and see whether the hardware
and the framing accept them.

Method
  1. take a carrier whose fragment stage tokenizes COMPLETELY (no undecodable
     tail), so every instruction boundary is proven rather than scanned;
  2. enumerate its 4-byte instructions -- those are the only places a 4-byte
     descriptor can be substituted without changing the length of the stream;
  3. establish DETECTION POWER at each site by overwriting it with a control
     pattern and confirming the observation moves (i.e. the splice reaches the
     GPU at all);
  4. splice `f0 c0 04 <b3>` for every b3 in 0..255, and record BOTH
       (a) whether the patched stream still tokenizes to the end -- an ISA-level
           fact about the modelled 4-byte length, independent of the hardware;
       (b) the hardware outcome.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Our own compiled MSL, our own bytes.
"""
import json, os, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import isadb                                   # noqa: E402
import carriers as CA                          # noqa: E402
from runner4 import RenderRunner, render_cmd   # noqa: E402

WORK = os.path.join(HERE, "work")
GFRUN = os.path.join(WORK, "gfrun4")
AGXPARSE = os.path.join(HERE, "pinned", "agxparse.py")
CARRIER = "deriv"          # fragment stage tokenizes completely (census run2)
SIG = bytes.fromhex("f0c004")


def sh(cmd, timeout=240):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stdout} {r.stderr}")
    return r.stdout


def stage_bytes(arch, stage):
    args = [sys.executable, AGXPARSE, arch, "--stage", stage]
    loc = sh(args + ["--locate", "_agc.main"]).split()
    off, ln = int(loc[0]), int(loc[1])
    b = bytes.fromhex(sh(args + ["--extract-hex"]).strip())
    assert len(b) == ln
    return off, b


def tokenize(buf):
    recs, off = [], 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError:
            return recs, off
        rec["off"] = off
        rec["len"] = L
        recs.append(rec)
        off += L
    return recs, None


def main():
    outdir = os.path.join(HERE, "raw", "cube_probe")
    os.makedirs(outdir, exist_ok=True)
    jl = open(os.path.join(outdir, "sweep.jsonl"), "a")

    def emit(r):
        jl.write(json.dumps(r, sort_keys=True) + "\n")
        jl.flush()
        os.fsync(jl.fileno())

    cfg = CA.CARRIERS[CARRIER]
    arch = os.path.join(WORK, f"{CARRIER}.bin")
    sh(render_cmd(GFRUN, os.path.join(HERE, cfg["src"]), cfg, build=arch))
    abs_off, buf = stage_bytes(arch, "fragment")
    recs, undec = tokenize(buf)
    assert undec is None, f"carrier does not tokenize completely (stops at {undec})"
    sites = [r for r in recs if r["len"] == 4]
    emit({"instr": "cubearray_coord_const", "field": "_sites", "value": -1,
          "bytes": "", "observed": {"status": "OK"},
          "oracle": {"predict": "enumerate_4byte_instruction_boundaries"},
          "match": True, "outcome": "ok", "carrier": CARRIER,
          "note": json.dumps([{"off": r["off"], "mnem": r["mnemonic"],
                               "hex": r["hex"]} for r in sites])})
    if not sites:
        print("no 4-byte instruction in the carrier; probe cannot be built")
        return

    runner = RenderRunner(GFRUN, os.path.join(HERE, cfg["src"]), arch,
                          os.path.join(WORK, "scratch_cube.bin"), cfg)

    def obs(splice):
        resp = runner.render([splice], timeout=15.0)
        if resp["status"] != "OK":
            return {"status": resp["status"], "error": resp.get("error", "")[:180]}
        import hashlib
        return {"status": "OK",
                "hh": {k: hashlib.sha256(v).hexdigest()[:24]
                       for k, v in sorted(resp["surf"].items())}}

    base = obs((abs_off, recs[0]["hex"]))          # unspliced-equivalent request
    base = obs((abs_off + sites[0]["off"], sites[0]["hex"]))
    emit({"instr": "cubearray_coord_const", "field": "_baseline", "value": -1,
          "bytes": sites[0]["hex"], "observed": base,
          "oracle": {"predict": "unmutated_baseline"}, "match": True,
          "outcome": "ok" if base["status"] == "OK" else "fault",
          "carrier": CARRIER, "note": f"site @{sites[0]['off']} "
                                      f"({sites[0]['mnemonic']})"})

    for site in sites:
        o = site["off"]
        # (3) detection power: does a splice at this site reach the GPU at all?
        ctl = bytes.fromhex(site["hex"])
        ctl = bytes([ctl[0], ctl[1] ^ 0xFF, ctl[2], ctl[3]])
        cobs = obs((abs_off + o, ctl.hex()))
        power = cobs.get("hh") != base.get("hh") or cobs["status"] != "OK"
        emit({"instr": "cubearray_coord_const", "field": "_detect", "value": -1,
              "bytes": ctl.hex(), "observed": cobs,
              "oracle": {"predict": "control_splice_should_move_observation"},
              "match": not power, "outcome": "moved" if power else "inert",
              "carrier": f"{CARRIER}@{o}",
              "note": f"site @{o} was {site['mnemonic']} {site['hex']}"})
        for b3 in range(256):
            patched = SIG + bytes([b3])
            tb = bytearray(buf)
            tb[o:o + 4] = patched
            trecs, tundec = tokenize(bytes(tb))
            dec = None
            try:
                dec = isadb.decode_one(bytes(tb), o)[0]["mnemonic"]
            except ValueError:
                dec = None
            r = obs((abs_off + o, patched.hex()))
            same = r.get("hh") == base.get("hh")
            emit({"instr": "cubearray_coord_const", "field": "b3", "value": b3,
                  "bytes": patched.hex(), "observed": r,
                  "oracle": {"predict": "synthesised_4byte_descriptor",
                             "decodes_as": dec,
                             "framing_preserved": tundec is None},
                  "match": bool(same),
                  "outcome": ("ok" if same else "wrong_value")
                             if r["status"] == "OK" else "fault",
                  "carrier": f"{CARRIER}@{o}",
                  "note": f"tokenizes_to_end={tundec is None}; "
                          f"decodes_as={dec}; site_was={site['mnemonic']}"})
    runner.close()
    jl.close()
    print("cube probe done ->", outdir)


if __name__ == "__main__":
    main()
