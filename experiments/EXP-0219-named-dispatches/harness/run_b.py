#!/usr/bin/env python3
"""EXP-0219 part-B driver: what does `tex_sample.mode` BIT 6 do?  G17P.

  python3 harness/run_b.py --run <id> --phase ruler|repeat|sweep
                           [--order forward|reverse] [--interleave]

Three phases, each pre-registered:

 PHASE `ruler`  -- FIELD-SWEEP-PROTOCOL section 3z, run BEFORE any sweep at a site
   this experiment did not construct.  Two of the four arms under test are
   `located_via: scan` (signature-derived).  A 4-byte `stop` is spliced at the
   arm's own offset and at +-2, +-4, and at the fragment stage's offset 0 (the
   canonical halt, which CALIBRATES what a halt looks like on this carrier).
   THE CLAIM IS ONE-SIDED: a halt proves a boundary; a no-halt is INCONCLUSIVE.

 PHASE `repeat` -- the measurement EXP-0213 could not make.  Every earlier capture
   dispatched each (arm, value) ONCE per process, so "unstable" could mean a race
   OR per-process state.  Here each (arm, value) is dispatched N times INSIDE ONE
   PROCESS, each dispatch recorded separately.  M-B1 (race) predicts within-process
   disagreement; M-B2 (per-process state) predicts 100 % within-process agreement;
   M-B3 (harness artefact) predicts the bit6-CLEAR control set disagrees at a
   comparable rate.

 PHASE `sweep`  -- the structural probe: the full 256-value `mode` sweep on the
   never-armed LAST texture instruction of each carrier and on the new one-read
   carrier `k_msread1`, i.e. the same field in carriers that differ in the number
   of ADJACENT texture instructions.

Everything is spliced into the compiled form of OUR OWN MSL.  gfrun4.m,
runner4.py, carriers.py, oracle.py, arms.py and pinned_b/{isadb,agxparse,db.json}
are BYTE-IDENTICAL COPIES of EXP-0204's (hashes in work/exp0204_copies.sha256);
EXP-0204's own tree is never executed or written to.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  No Apple binary is disassembled.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(EXP, "pinned_b"))
import isadb                                     # noqa: E402  (PINNED copy)
import carriers as CA                            # noqa: E402
import arms as ARMSPEC                           # noqa: E402
import oracle as OR                              # noqa: E402
from runner4 import RenderRunner, render_cmd     # noqa: E402

WORK = os.path.join(EXP, "work")
AGXPARSE = os.path.join(EXP, "pinned_b", "agxparse.py")
GFRUN = os.path.join(WORK, "gfrun4")
DB_SHA = hashlib.sha256(open(os.path.join(EXP, "pinned_b", "db.json"), "rb").read()).hexdigest()
HARNESS_SHA = hashlib.sha256(open(os.path.join(HERE, "gfrun4.m"), "rb").read()).hexdigest()
REQ_TIMEOUT = 15.0
POISON4 = b"\xef\xbe\xad\xde"
STOP4 = bytes.fromhex("0e000000")

_MIP = (16, 16, 3)
EXTRA_CARRIERS = {
    "msread1": dict(kind="render", src="kernels/k_msread1.metal", color_format=125,
                    samples=1, width=16, height=16, tex_mip=_MIP,
                    why="EXP-0219: exactly ONE texture instruction, the extreme of "
                        "the dimension (number of adjacent texture ops) that "
                        "separates the arms where mode bit 6 is live from the "
                        "arms where it is inert."),
}

# The declared value sets (PRE_REGISTRATION section 3, model M-B1/2/3).
BIT6_SET = [v for v in range(256) if (v & 0x40) and not (v & 0x08) and not (v & 0x04)]
BIT6_CLR = [v ^ 0x40 for v in BIT6_SET]          # the same low bits, bit 6 clear
GATE_B_CONTROL = 8


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def sh(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("%s failed: %s %s" % (" ".join(cmd), r.stdout, r.stderr))
    return r.stdout


def f32(vals):
    return [struct.unpack("<I", struct.pack("<f", v))[0] for v in vals]


def bufs_for(name):
    return {i: f32(v) for i, v in (CA.BUFS.get(name) or {}).items()}


def all_carriers():
    d = dict(CA.CARRIERS)
    d.update(EXTRA_CARRIERS)
    return d


def build_carrier(name, cfg):
    arch = os.path.join(WORK, "e0219_%s.bin" % name)
    sh(render_cmd(GFRUN, os.path.join(EXP, cfg["src"]), cfg, build=arch,
                  bufs=bufs_for(name)))
    return arch


def stage_bytes(arch, stage):
    args = [sys.executable, AGXPARSE, arch, "--stage", stage]
    loc = sh(args + ["--locate", "_agc.main"]).split()
    off, ln = int(loc[0]), int(loc[1])
    b = bytes.fromhex(sh(args + ["--extract-hex"]).strip())
    assert len(b) == ln, (len(b), ln)
    return off, b


def tokenize(buf):
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
    """IDENTICAL rule to EXP-0204 run.py::locate (copied, not imported)."""
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


def _os_class(err):
    for tag in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
                "ErrorOutOfMemory", "ErrorInvalidResource", "ErrorMakeCurrent",
                "ErrorRestart", "ErrorRecovery"):
        if tag in err:
            return tag
    return "unclassified" if err else ""


def observe(resp, cfg):
    """Copied from EXP-0204 run.py::observe so observations are comparable."""
    if resp["status"] != "OK":
        return {"status": resp["status"], "error": resp.get("error", "")[:220],
                "os_class": _os_class(resp.get("error", "")),
                "errdom": resp.get("errdom", ""),
                "raw_lines": resp.get("raw_lines", [])[:6],
                "foreign_retries": resp.get("foreign_retries", 0)}
    surf = resp.get("surf", {})
    o = {"status": "OK",
         "hh": {k: hashlib.sha256(v).hexdigest()[:24] for k, v in sorted(surf.items())},
         "missing": sorted(resp.get("missing", []))}
    poisoned = [k for k, v in surf.items()
                if len(v) >= 4 and v == POISON4 * (len(v) // 4)]
    if poisoned:
        o["poison"] = poisoned
    if not surf:
        o["status"] = "NO_SURFACE"
        return o
    if len(poisoned) == len(surf):
        o["status"] = "POISON"
        return o
    Wd = cfg.get("width", 16)
    fmt = cfg.get("color_format", 125)
    bpp = 16 if fmt == 125 else (8 if fmt == 115 else 4)
    pr = {}
    for tag, buf in sorted(surf.items()):
        if tag.startswith("PIX"):
            v = []
            for (x, y) in CA.PROBE_PIXELS:
                base = (y * Wd + x) * bpp
                if base + bpp > len(buf):
                    continue
                if fmt == 125:
                    v.append([round(f, 5) for f in struct.unpack_from("<4f", buf, base)])
                else:
                    v.append(list(buf[base:base + 4]))
            pr[tag] = v
    o["probe"] = pr
    return o


def isadb_set(mnemonic, raw, field, value):
    desc = isadb._BY_MNEM[mnemonic]
    v = int.from_bytes(raw, "little")
    for f in desc["fields"]:
        if f["name"] == field:
            mask = ((1 << f["width"]) - 1) << f["start"]
            v = (v & ~mask) | ((value << f["start"]) & mask)
            return v.to_bytes(desc["length"], "little")
    raise KeyError("%s.%s" % (mnemonic, field))


# ---------------------------------------------------------------- arm spec ---
FROZEN_ARMS = ["tex_sample@msread/0", "tex_sample@msread/1",
               "tex_sample@mslodq/0", "tex_sample@mslodq/1",
               "tex_sample@msfilt/0", "tex_sample@mscmp/0"]
NEW_ARMS = [("msread", 2), ("mslodq", 2), ("mslodq", 3), ("msread1", 0)]


def build_arms(want_phase):
    """Frozen EXP-0204 arms (byte-exact check) plus this experiment's new ones."""
    cars = all_carriers()
    need = set()
    for aid in FROZEN_ARMS:
        need.add(next(a for a in ARMSPEC.ARMS if a["id"] == aid)["carrier"])
    for c, _ in NEW_ARMS:
        need.add(c)
    built, arms, inputs = {}, [], {"carriers": {}, "arms": {}}
    for name in sorted(need):
        cfg = cars[name]
        arch = build_carrier(name, cfg)
        off, buf = stage_bytes(arch, "fragment")
        built[name] = dict(cfg=cfg, arch=arch, abs_off=off, hex=buf.hex())
        inputs["carriers"][name] = {
            "archive_sha256": sha256_file(arch),
            "src_sha256": sha256_file(os.path.join(EXP, cfg["src"])),
            "stage_abs_off": off, "stage_len": len(buf), "stage_hex": buf.hex(),
            "why": cfg["why"]}

    for aid in FROZEN_ARMS:
        a = next(x for x in ARMSPEC.ARMS if x["id"] == aid)
        c = built[a["carrier"]]
        buf = bytes.fromhex(c["hex"])
        hits, how = locate(buf, a["mnemonic"])
        ioff = hits[a["occ"]]["off"]
        d, L = isadb.decode_one(buf, ioff)
        ok = (d["hex"] == a["expect_hex"] and ioff == a["expect_off"])
        rec = dict(id=aid, carrier=a["carrier"], mnemonic=a["mnemonic"],
                   occ=a["occ"], located_via=how, instr_off=ioff, length=L,
                   abs_off=c["abs_off"] + ioff, orig=d["hex"],
                   frozen_match=ok, expect_hex=a["expect_hex"],
                   expect_off=a["expect_off"], source="EXP-0204 frozen arm",
                   stage_hex=c["hex"], n_hits=len(hits))
        inputs["arms"][aid] = {k: v for k, v in rec.items() if k != "stage_hex"}
        if ok:
            arms.append(rec)
    for carrier, occ in NEW_ARMS:
        c = built[carrier]
        buf = bytes.fromhex(c["hex"])
        hits, how = locate(buf, "tex_sample")
        aid = "tex_sample@%s/%d" % (carrier, occ)
        if occ >= len(hits):
            inputs["arms"][aid] = {"error": "occurrence %d of %d not found"
                                            % (occ, len(hits)), "located_via": how}
            continue
        ioff = hits[occ]["off"]
        d, L = isadb.decode_one(buf, ioff)
        rec = dict(id=aid, carrier=carrier, mnemonic="tex_sample", occ=occ,
                   located_via=how, instr_off=ioff, length=L,
                   abs_off=c["abs_off"] + ioff, orig=d["hex"],
                   frozen_match=None, source="EXP-0219 new arm",
                   stage_hex=c["hex"], n_hits=len(hits))
        inputs["arms"][aid] = {k: v for k, v in rec.items() if k != "stage_hex"}
        arms.append(rec)
    return built, arms, inputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--phase", required=True, choices=("ruler", "repeat", "sweep"))
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--interleave", action="store_true",
                    help="repeat phase: round-robin the repeats instead of "
                         "dispatching a value's N repeats adjacently")
    ap.add_argument("--repeats", type=int, default=16)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()

    outdir = os.path.join(EXP, "raw", a.run)
    if os.path.exists(outdir):
        sys.exit("run dir already exists, refusing to reuse: %s" % outdir)
    os.makedirs(outdir)
    built, arms, inputs = build_arms(a.phase)
    if a.arms:
        want = set(a.arms.split(","))
        arms = [x for x in arms if x["id"] in want]
    inputs.update(run_id=a.run, phase=a.phase, order=a.order,
                  interleave=bool(a.interleave), repeats=a.repeats,
                  db_sha256=DB_SHA, gfrun4_sha256=HARNESS_SHA,
                  bit6_set=BIT6_SET, bit6_clear=BIT6_CLR,
                  started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(os.path.join(outdir, "00_inputs.json"), "w") as f:
        json.dump(inputs, f, indent=1, sort_keys=True)

    runners = {}
    for name in sorted({x["carrier"] for x in arms}):
        c = built[name]
        runners[name] = RenderRunner(
            GFRUN, os.path.join(EXP, c["cfg"]["src"]), c["arch"],
            os.path.join(WORK, "scratch_%s_%s.bin" % (a.run, name)),
            c["cfg"], bufs_for(name))

    jl = open(os.path.join(outdir, "sweep.jsonl"), "a")
    seq = [0]

    def emit(rec):
        seq[0] += 1
        rec["seq"] = seq[0]
        rec["t"] = round(time.time(), 3)
        jl.write(json.dumps(rec, sort_keys=True) + "\n")
        jl.flush()
        os.fsync(jl.fileno())

    def dispatch(arm, patched, field=None, value=None, rep=0, note=""):
        resp = runners[arm["carrier"]].render(
            [(arm["abs_off"], patched.hex())], timeout=REQ_TIMEOUT)
        o = observe(resp, built[arm["carrier"]]["cfg"])
        o["sentinel"] = resp.get("sentinel", "")
        # GATE A -- actual bytes as reported by the harness, decoded in context
        L = {"requested_bytes": patched.hex(), "abs_off": arm["abs_off"],
             "instr_off": arm["instr_off"], "prog_hash_fnv1a64": resp.get("proghash"),
             "db_sha256_12": DB_SHA[:12], "harness_sha256_12": HARNESS_SHA[:12]}
        act = resp.get("actual") or ""
        got = None
        for part in act.split(","):
            if "=" in part:
                oo, _, hh = part.partition("=")
                try:
                    if int(oo) == arm["abs_off"]:
                        got = hh
                except ValueError:
                    pass
        L["actual_bytes"] = got
        L["bytes_match"] = (got == patched.hex()) if got else None
        if got and field:
            try:
                buf = bytearray(bytes.fromhex(arm["stage_hex"]))
                buf[arm["instr_off"]:arm["instr_off"] + len(patched)] = bytes.fromhex(got)
                d, _ = isadb.decode_one(bytes(buf), arm["instr_off"])
                L["decoded_mnemonic"] = d["mnemonic"]
                L["decoded_value"] = d["fields"].get(field)
                L["requested_value"] = value
                L["gate_a_ok"] = (d["mnemonic"] == arm["mnemonic"]
                                  and d["fields"].get(field) == value)
            except (ValueError, IndexError, KeyError) as e:
                L.update(decoded_mnemonic=None, decoded_value=None,
                         requested_value=value, gate_a_ok=False,
                         decode_error=str(e)[:100])
        o["_ledger"] = L
        emit({"instr": arm["mnemonic"], "carrier": arm["id"], "field": field or "_",
              "value": -1 if value is None else value, "repeat": rep,
              "bytes": patched.hex(), "observed": o,
              "outcome": ("ok" if o.get("status") == "OK" else
                          ("hang" if o.get("status") == "HANG" else
                           ("measurement_failure" if o.get("status") == "MALFORMED"
                            else "fault"))),
              "note": note})
        return o

    t0 = time.time()
    counts = {"hang": 0, "fault": 0, "measurement_failure": 0, "ok": 0}

    for arm in arms:
        orig = bytes.fromhex(arm["orig"])
        base = dispatch(arm, orig, note="baseline (unmutated)")
        counts[("ok" if base.get("status") == "OK" else "fault")] += 1
        print("[%s] %s baseline %s" % (time.strftime("%H:%M:%S"), arm["id"],
                                       base.get("status")), flush=True)

        if a.phase == "ruler":
            stage = bytearray(bytes.fromhex(arm["stage_hex"]))
            # canonical halt: `stop` at the fragment stage's offset 0
            calib = bytearray(stage)
            calib[0:4] = STOP4
            resp = runners[arm["carrier"]].render(
                [(built[arm["carrier"]]["abs_off"], STOP4.hex())], timeout=REQ_TIMEOUT)
            o = observe(resp, built[arm["carrier"]]["cfg"])
            emit({"instr": "stop", "carrier": arm["id"], "field": "_ruler_calib",
                  "value": 0, "repeat": 0, "bytes": STOP4.hex(),
                  "observed": o, "outcome": "ok" if o.get("status") == "OK" else "fault",
                  "note": "stop at fragment-stage offset 0 -- the canonical HALT "
                          "payload for this carrier; calibrates what a halt looks like"})
            for delta in (-6, -4, -2, 0, 2, 4, 6, 14):
                off = arm["instr_off"] + delta
                if off < 0 or off + 4 > len(stage):
                    continue
                resp = runners[arm["carrier"]].render(
                    [(built[arm["carrier"]]["abs_off"] + off, STOP4.hex())],
                    timeout=REQ_TIMEOUT)
                o = observe(resp, built[arm["carrier"]]["cfg"])
                emit({"instr": "stop", "carrier": arm["id"], "field": "_ruler",
                      "value": delta, "repeat": 0, "bytes": STOP4.hex(),
                      "observed": o,
                      "outcome": "ok" if o.get("status") == "OK" else "fault",
                      "note": "stop spliced at instr_off%+d (abs %d)"
                              % (delta, built[arm["carrier"]]["abs_off"] + off)})
            continue

        # Gate B positive control, every arm, before any repeat block
        pc = isadb_set(arm["mnemonic"], orig, "mode", GATE_B_CONTROL)
        c1 = dispatch(arm, pc, "mode", GATE_B_CONTROL, note="GATE B positive control")
        moved = (c1.get("hh") != base.get("hh"))
        emit({"instr": arm["mnemonic"], "carrier": arm["id"],
              "field": "_detect_summary", "value": GATE_B_CONTROL, "repeat": 0,
              "bytes": pc.hex(), "observed": {"moved": moved},
              "outcome": "moved" if moved else "inert",
              "note": "arm is carrier-undecidable for this experiment if not moved"})

        if a.phase == "sweep":
            vals = list(range(256))
            if a.order == "reverse":
                vals = list(reversed(vals))
            for v in vals:
                p = isadb_set(arm["mnemonic"], orig, "mode", v)
                o = dispatch(arm, p, "mode", v)
                counts[("ok" if o.get("status") == "OK" else "fault")] += 1
            continue

        # phase == repeat
        vals = BIT6_SET + BIT6_CLR + [GATE_B_CONTROL]
        if a.order == "reverse":
            vals = list(reversed(vals))
        pats = {v: isadb_set(arm["mnemonic"], orig, "mode", v) for v in vals}
        if a.interleave:
            for rep in range(a.repeats):
                for v in vals:
                    o = dispatch(arm, pats[v], "mode", v, rep=rep)
                    counts[("ok" if o.get("status") == "OK" else "fault")] += 1
        else:
            for v in vals:
                for rep in range(a.repeats):
                    o = dispatch(arm, pats[v], "mode", v, rep=rep)
                    counts[("ok" if o.get("status") == "OK" else "fault")] += 1
        b2 = dispatch(arm, orig, note="baseline re-check (arm end)")
        emit({"instr": arm["mnemonic"], "carrier": arm["id"],
              "field": "_baseline_final", "value": -1, "repeat": 0,
              "bytes": orig.hex(),
              "observed": {"same_as_first": b2.get("hh") == base.get("hh")},
              "outcome": "ok" if b2.get("hh") == base.get("hh") else "wrong_value",
              "note": "the arm's own carrier still reproduces its baseline"})

    with open(os.path.join(outdir, "02_summary.json"), "w") as f:
        json.dump({"records": seq[0], "counts": counts,
                   "elapsed_s": round(time.time() - t0, 1),
                   "arms": [x["id"] for x in arms]}, f, indent=1, sort_keys=True)
    jl.close()
    print("DONE", seq[0], json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
