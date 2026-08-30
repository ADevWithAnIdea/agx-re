#!/usr/bin/env python3
"""census.py -- EXP-0204 PRE-FREEZE calibration.  NO VERDICT MAY CITE THIS.

Builds every carrier with the EXACT pipeline descriptor the sweep will use,
tokenizes the compiled bytes with the PINNED isa DB, and reports every
occurrence of every target mnemonic with its decoded field values.

Its whole job is to answer, BEFORE any gated run:
  * does each carrier actually emit the instruction under test?
  * what value does the COMPILER ITSELF choose for the field?  For a
    carrier-dimension experiment that is the primary calibration number: if all
    six tex_sample carriers compile to the same `mode`, they do not span the
    dimension and the arm list must say so rather than sweeping six copies of
    one carrier.

Output: raw/prefreeze/census_<tag>.json (calibration only).
"""
import hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import isadb                                  # noqa: E402  (PINNED copy)
import carriers as CA                         # noqa: E402
from runner4 import render_cmd                # noqa: E402

WORK = os.path.join(HERE, "work")
GFRUN = os.path.join(WORK, "gfrun4")
AGXPARSE = os.path.join(HERE, "pinned", "agxparse.py")


def sh(cmd, timeout=240):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def f32(vals):
    import struct
    return [struct.unpack("<I", struct.pack("<f", v))[0] for v in vals]


def bufs_for(name):
    return {i: f32(v) for i, v in (CA.BUFS.get(name) or {}).items()}


def stage_bytes(arch, stage):
    args = [sys.executable, AGXPARSE, arch]
    if stage != "compute":
        args += ["--stage", stage]
    loc = sh(args + ["--locate", "_agc.main"]).split()
    off, ln = int(loc[0]), int(loc[1])
    b = bytes.fromhex(sh(args + ["--extract-hex"]).strip())
    assert len(b) == ln, (len(b), ln)
    return off, b


def tokenize(buf):
    """Forward tokenization from 0; returns (records, first_undecodable_off)."""
    recs, off = [], 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError:
            return recs, off
        rec["off"] = off
        recs.append(rec)
        off += L
    return recs, None


def locate(buf, mnemonic):
    """Every offset where the PINNED isadb decodes `mnemonic`.

    IDENTICAL rule to run.py::locate, so the census and the gated run can never
    disagree about occurrence indices (EXP-0172 caught them disagreeing on three
    arms and refused the arms rather than sweeping the wrong bytes):

      1. forward-tokenize from 0 and take hits found in the tokenized PREFIX --
         those are on the real instruction grid;
      2. only if the prefix yields NO hit, fall back to an anchored decode scan
         over the whole buffer, keeping offsets whose two FOLLOWING instructions
         also decode.  A scan hit is not on a proven instruction boundary, so an
         arm resolved that way is usable only if its detection profile passes.
    """
    recs, undec = tokenize(buf)
    pre = [r for r in recs if r["mnemonic"] == mnemonic]
    if undec is None:
        return pre, "tokenize"
    if pre:
        return pre, "tokenize-prefix"
    hits = []
    for o in range(len(buf) - 1):
        try:
            rec, L = isadb.decode_one(buf, o)
        except ValueError:
            continue
        if rec["mnemonic"] != mnemonic:
            continue
        ok, p = True, o + L
        for _ in range(2):
            if p >= len(buf):
                break
            try:
                _r, _l = isadb.decode_one(buf, p)
            except ValueError:
                ok = False
                break
            p += _l
        if ok:
            rec["off"] = o
            hits.append(rec)
    return hits, "scan"


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "run1"
    outdir = os.path.join(HERE, "raw", "prefreeze")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    rep = {"tag": tag, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "isadb": hashlib.sha256(open(os.path.join(HERE, "pinned", "db.json"), "rb")
                                   .read()).hexdigest(),
           "carriers": {}}
    for name in sorted(CA.CARRIERS):
        cfg = CA.CARRIERS[name]
        ent = {"why": cfg["why"], "src": cfg["src"]}
        arch = os.path.join(WORK, f"{name}.bin")
        try:
            sh(render_cmd(GFRUN, os.path.join(HERE, cfg["src"]), cfg, build=arch,
                          bufs=bufs_for(name)))
        except Exception as e:
            ent["build_error"] = str(e)[:1500]
            rep["carriers"][name] = ent
            print(f"{name}: BUILD FAILED")
            continue
        ent["archive_sha256"] = hashlib.sha256(open(arch, "rb").read()).hexdigest()
        ent["stages"] = {}
        for st in ("vertex", "fragment"):
            try:
                off, buf = stage_bytes(arch, st)
            except Exception as e:
                ent["stages"][st] = {"error": str(e)[:400]}
                continue
            recs, undec = tokenize(buf)
            occ, how = {}, {}
            for m in CA.TARGETS:
                hits, hw = locate(buf, m)
                how[m] = hw
                if hits:
                    occ[m] = [{"off": r["off"], "hex": r["hex"],
                               "fields": {k: v for k, v in r["fields"].items()}}
                              for r in hits]
            ent["stages"][st] = {"abs_off": off, "len": len(buf),
                                 "n_tokens": len(recs), "undecodable_at": undec,
                                 "mnemonics": sorted({r["mnemonic"] for r in recs}),
                                 "located_via": how,
                                 "occurrences": occ,
                                 "hex": buf.hex()}
        rep["carriers"][name] = ent
        # human summary line
        for st in ("fragment", "vertex"):
            s = ent["stages"].get(st, {})
            for m, lst in (s.get("occurrences") or {}).items():
                for k, o in enumerate(lst):
                    tf = {f: o["fields"].get(f) for f in CA.TARGETS[m]}
                    print(f"{name}/{st} {m}#{k} @{o['off']} {tf}")
    p = os.path.join(outdir, f"census_{tag}.json")
    with open(p, "w") as f:
        json.dump(rep, f, indent=1, sort_keys=True)
    print("wrote", p)


if __name__ == "__main__":
    main()
