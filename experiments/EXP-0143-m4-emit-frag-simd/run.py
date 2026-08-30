#!/usr/bin/env python3
"""run.py -- EXP-0143 capture driver (field sweep: FRAG + SIMD emission).

    python3 run.py --run-id m4-YYYYMMDD-runNN [--smoke-only]

Builds every carrier archive from OUR OWN MSL, locates each target instruction
occurrence with tools/agx-isa (never by hand-counted byte offsets), then for
every (arm, field, value) splices the value in, runs it on the real M4 GPU, and
appends one JSON record per case to raw/<run_id>/sweep.jsonl, flushed+fsynced
as it completes.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Every byte spliced or inspected is the
compiled form of MSL in kernels/.  No Apple binary is disassembled.
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
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                      # noqa: E402
import casematrix as CM           # noqa: E402
from runner import RenderRunner, ComputeRunner   # noqa: E402

WORK = os.path.join(HERE, "work")
AGXPARSE = os.path.join(REPO, "tools", "shdump", "agxparse.py")
FRUN = os.path.join(WORK, "frun")
AGXPERSIST = os.path.join(WORK, "agxrun_persist")

REQ_TIMEOUT = 15.0          # per-case watchdog, seconds
MAX_HANGS_PER_FIELD = 2     # FIELD-SWEEP-PROTOCOL sec.8: stop an AREA after two
MAX_HANGS_PER_ARM = 6       # ... and the whole arm after six
CONFIRM_N = 3               # sec.7.1: majority-of-3 before ANY `fault` verdict
BASELINE_EVERY = 250        # sec.7.3: re-validate the unmutated carrier
BASELINE_RETRIES = 4        # a baseline failure is only a cascade if ALL fail
POISON = 0xDEADBEEF


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stdout} {r.stderr}")
    return r.stdout


# ---------------------------------------------------------------- carriers
def build_carrier(name, cfg):
    """Build the binary archive for one carrier with the EXACT pipeline
    descriptor the sweep will run, and return its path."""
    arch = os.path.join(WORK, f"{name}.bin")
    src = os.path.join(HERE, cfg["src"])
    if cfg["kind"] == "compute":
        sh([os.path.join(WORK, "shdump"), "-o", arch, "-f", cfg["function"], src])
    else:
        cmd = [FRUN, "--source", src, "--vertex", CM.RENDER_VERTEX,
               "--fragment", CM.RENDER_FRAGMENT,
               "--color-format", str(cfg["color_format"]),
               "--samples", str(cfg.get("samples", 1)),
               "--width", str(cfg["width"]), "--height", str(cfg["height"]),
               "--build-archive", arch]
        if cfg.get("depth"):
            cmd.append("--depth")
        if cfg.get("resolve"):
            cmd.append("--resolve")
        sh(cmd)
    return arch


def stage_bytes(arch, stage):
    """Return (absolute file offset of _agc.main, its bytes)."""
    args = [sys.executable, AGXPARSE, arch]
    if stage != "compute":
        args += ["--stage", stage]
    loc = sh(args + ["--locate", "_agc.main"]).split()
    off, ln = int(loc[0]), int(loc[1])
    hexs = sh(args + ["--extract-hex"]).strip()
    b = bytes.fromhex(hexs)
    assert len(b) == ln, (len(b), ln)
    return off, b


def locate(buf, mnemonic):
    """All offsets in `buf` where isadb decodes `mnemonic`.

    Preferred path: a clean forward tokenization (authoritative).  Where the
    program contains ops the DB cannot yet length-resolve, fall back to an
    anchored decode scan and keep only offsets that also decode cleanly for the
    two following instructions -- recorded in 00_inputs.json so a reviewer can
    check every located offset.
    """
    recs, left = [], None
    off = 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError:
            left = off
            break
        rec["off"] = off
        recs.append(rec)
        off += L
    if left is None:
        return [r["off"] for r in recs if r["mnemonic"] == mnemonic], "tokenize"
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
            hits.append(o)
    return hits, "scan"


# ---------------------------------------------------------------- observation
def obs_render(resp, cfg):
    """Reduce a render response to a compact, fully deterministic observation."""
    if resp["status"] != "OK":
        return {"status": resp["status"], "error": resp.get("error", "")[:220],
                "os_class": _os_class(resp.get("error", "")),
                "foreign_retries": resp.get("foreign_retries", 0)}
    W, H = cfg["width"], cfg["height"]
    fmt = cfg["color_format"]
    pix = resp["pix"]["PIX0"]
    bpp = 16 if fmt == 125 else (8 if fmt == 115 else 4)
    probes = []
    for (x, y) in CM.PROBE_PIXELS:
        base = (y * W + x) * bpp
        if fmt == 125:
            probes.append([round(v, 6) for v in struct.unpack_from("<4f", pix, base)])
        else:
            probes.append(list(pix[base:base + 4]))
    o = {"status": "OK", "probe": probes,
         "h": hashlib.sha256(pix).hexdigest()[:32]}
    # sec.7 guard: the read-back buffer was pre-filled with 0xDEADBEEF by frun,
    # so an unwritten getBytes reports POISON rather than masquerading as zeros.
    if pix[:4] == b"\xef\xbe\xad\xde" and pix == (b"\xef\xbe\xad\xde" * (len(pix) // 4)):
        o["poison"] = True
        o["status"] = "POISON"
    if "depth" in resp:
        d = resp["depth"]
        o["dprobe"] = [round(struct.unpack_from("<f", d, (y * W + x) * 4)[0], 6)
                       for (x, y) in CM.PROBE_PIXELS]
        o["dh"] = hashlib.sha256(d).hexdigest()[:32]
    return o


def _os_class(err):
    """The OS command-buffer fault CLASSIFICATION string (sec.7.2), e.g.
    kIOGPUCommandBufferCallbackErrorInnocentVictim vs ...ErrorHang.  An
    InnocentVictim is evidence about the MACHINE (a sibling experiment's fault
    took our command buffer down as collateral), never about our encoding."""
    for tag in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
                "ErrorOutOfMemory", "ErrorInvalidResource", "ErrorMakeCurrent",
                "ErrorRestart", "ErrorRecovery"):
        if tag in err:
            return tag
    return "unclassified" if err else ""


def obs_compute(resp):
    if resp["status"] != "OK":
        return {"status": resp["status"], "error": resp.get("error", "")[:220],
                "os_class": _os_class(resp.get("error", "")),
                "foreign_retries": resp.get("foreign_retries", 0)}
    b = resp["out"]
    lanes = {}
    for ln in CM.PROBE_LANES:
        lanes[str(ln)] = list(struct.unpack_from("<16I", b, ln * 64))
    o = {"status": "OK", "lanes": lanes,
         "h": hashlib.sha256(b).hexdigest()[:32]}
    if b == (b"\xef\xbe\xad\xde" * (len(b) // 4)):
        o["poison"] = True
        o["status"] = "POISON"
    return o


def classify(obs, base, oracle):
    """outcome per FIELD-SWEEP-PROTOCOL sec.4."""
    if obs.get("status") == "HANG":
        return "hang"
    if obs.get("status") not in ("OK",):
        return "fault"
    if oracle is not None:
        return "ok" if obs.get("probe", obs.get("lanes")) == oracle else "wrong_value"
    same = (obs.get("probe") == base.get("probe")
            and obs.get("lanes") == base.get("lanes")
            and obs.get("dprobe") == base.get("dprobe")
            and obs.get("h") == base.get("h")
            and obs.get("dh") == base.get("dh"))
    if same:
        return "ok"
    vals = obs.get("probe") or list(obs.get("lanes", {}).values())
    flat = [v for row in vals for v in row]
    if flat and all(v == 0 for v in flat):
        return "silent_zero"
    return "wrong_value"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default="", help="comma-separated arm ids (default: all)")
    ap.add_argument("--smoke-only", action="store_true",
                    help="baselines + liveness controls only; writes to work/, not raw/")
    args = ap.parse_args()

    outdir = (os.path.join(WORK, "smoke_" + args.run_id) if args.smoke_only
              else os.path.join(HERE, "raw", args.run_id))
    if os.path.exists(outdir) and not args.smoke_only:
        sys.exit(f"run dir already exists, refusing to reuse: {outdir}")
    os.makedirs(outdir, exist_ok=True)

    t_start = time.time()
    inputs = {"run_id": args.run_id, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                 time.gmtime()),
              "carriers": {}, "arms": {}}

    # ---- build every carrier and locate every target occurrence -----------
    carriers = {}
    for name, cfg in CM.CARRIERS.items():
        arch = build_carrier(name, cfg)
        stage_list = ["compute"] if cfg["kind"] == "compute" else ["vertex", "fragment"]
        entry = {"archive_sha256": sha256_file(arch), "path": arch,
                 "src_sha256": sha256_file(os.path.join(HERE, cfg["src"])), "stages": {}}
        for st in stage_list:
            off, buf = stage_bytes(arch, st)
            entry["stages"][st] = {"abs_off": off, "len": len(buf), "hex": buf.hex()}
        carriers[name] = dict(cfg=cfg, arch=arch, entry=entry)
        inputs["carriers"][name] = entry

    # ---- resolve arm targets ---------------------------------------------
    want = set(x for x in args.arms.split(",") if x)
    arms = []
    for a in CM.ARMS:
        if want and a["id"] not in want:
            continue
        c = carriers[a["carrier"]]
        st = a["stage"]
        sinfo = c["entry"]["stages"][st]
        buf = bytes.fromhex(sinfo["hex"])
        hits, how = locate(buf, a["mnemonic"])
        if a["occ"] >= len(hits):
            inputs["arms"][a["id"]] = {"error": f"occurrence {a['occ']} not found "
                                                f"({len(hits)} hits, via {how})"}
            continue
        ioff = hits[a["occ"]]
        rec, L = isadb.decode_one(buf, ioff)
        arm = dict(a)
        arm.update(instr_off=ioff, abs_off=sinfo["abs_off"] + ioff, length=L,
                   orig=rec["hex"], located_via=how, all_hits=hits,
                   decoded=rec["fields"])
        arms.append(arm)
        inputs["arms"][a["id"]] = {k: arm[k] for k in
                                   ("carrier", "stage", "mnemonic", "occ", "instr_off",
                                    "abs_off", "length", "orig", "located_via",
                                    "all_hits", "decoded", "note")}

    with open(os.path.join(outdir, "00_inputs.json"), "w") as f:
        json.dump(inputs, f, indent=1, sort_keys=True)

    # ---- start runners ----------------------------------------------------
    runners = {}
    for name, c in carriers.items():
        cfg = c["cfg"]
        if cfg["kind"] == "render":
            runners[name] = RenderRunner(
                FRUN, os.path.join(HERE, cfg["src"]), c["arch"],
                os.path.join(WORK, f"scratch_{args.run_id}_{name}.bin"), cfg)
        else:
            infile = os.path.join(WORK, "simd_in.bin")
            if not os.path.exists(infile):
                u = [(i * i * 7 + 3) & 0xFFFFFFFF for i in range(32)]
                fl = [1.0 + 0.25 * i for i in range(32)]
                with open(infile, "wb") as f:
                    f.write(b"".join(struct.pack("<I", x) for x in u))
                    f.write(b"".join(struct.pack("<f", x) for x in fl))
            runners[name] = ComputeRunner(AGXPERSIST, os.path.join(HERE, cfg["src"]),
                                          cfg["function"], infile, cfg["out_bytes"],
                                          cfg["grid"], cfg["tg"])

    jl = open(os.path.join(outdir, "sweep.jsonl"), "a")

    def emit(rec):
        jl.write(json.dumps(rec, sort_keys=True) + "\n")
        jl.flush()
        os.fsync(jl.fileno())

    seq = [0]

    def run_case(arm, patched_instr):
        c = carriers[arm["carrier"]]
        if arm["stage"] == "compute":
            # sec.7: UNIQUE splice-archive path per request, so Metal can never
            # serve a library/pipeline memoized on a reused file URL.  The
            # render side does the same inside frun.m (gReqSeq).
            seq[0] += 1
            spliced = os.path.join(WORK, f"spl_{args.run_id}_{arm['carrier']}.{seq[0]}.bin")
            data = bytearray(open(c["arch"], "rb").read())
            data[arm["abs_off"]:arm["abs_off"] + arm["length"]] = patched_instr
            with open(spliced, "wb") as f:
                f.write(bytes(data))
            # integrity sentinel, independent path: read the file back off disk
            # and verify the spliced window is what we asked for.
            rb = open(spliced, "rb").read()
            ok = rb[arm["abs_off"]:arm["abs_off"] + arm["length"]] == patched_instr
            resp = runners[arm["carrier"]].run(spliced, timeout=REQ_TIMEOUT)
            try:
                os.unlink(spliced)
            except OSError:
                pass
            o = obs_compute(resp)
            o["sentinel"] = "OK 1" if ok else "MISMATCH"
            if not ok:
                o["status"] = "SENTINEL_FAIL"
            return o
        resp = runners[arm["carrier"]].render(
            [(arm["abs_off"], patched_instr.hex())], timeout=REQ_TIMEOUT)
        o = obs_render(resp, c["cfg"])
        o["sentinel"] = resp.get("sentinel", "")
        return o

    def run_confirmed(arm, patched_instr):
        """sec.7.1: NEVER treat a single fault/hang as a property of the field.
        Re-run any non-OK case up to CONFIRM_N times; the verdict is the
        MAJORITY.  Returns (observation, confirm_record)."""
        obs = run_case(arm, patched_instr)
        if obs.get("status") == "OK":
            return obs, None
        trials = [obs]
        for _ in range(CONFIRM_N - 1):
            trials.append(run_case(arm, patched_instr))
        nbad = sum(1 for t in trials if t.get("status") != "OK")
        rec = {"n": len(trials),
               "status": [t.get("status") for t in trials],
               "os_class": [t.get("os_class", "") for t in trials],
               "bad": nbad, "reproduced": nbad * 2 > len(trials)}
        if not rec["reproduced"]:
            for t in trials:
                if t.get("status") == "OK":
                    return t, rec
        return trials[0], rec

    ncases = 0
    hangs_total = 0
    summary = {}
    detection = {}
    cascade = []

    for arm in arms:
        orig = bytes.fromhex(arm["orig"])
        cfg = carriers[arm["carrier"]]["cfg"]

        base = run_case(arm, orig)
        emit({"instr": arm["mnemonic"], "field": "_baseline", "value": -1,
              "bytes": orig.hex(), "observed": base, "oracle": None, "match": True,
              "outcome": "ok" if base.get("status") == "OK" else "fault",
              "carrier": arm["id"], "note": arm["note"]})
        ncases += 1
        if base.get("status") != "OK":
            summary[arm["id"]] = {"live": False, "reason": "baseline failed"}
            continue

        # liveness control: this MUST change the observation, or the arm's
        # instruction is not proven to be on the observed output path.
        live_ok, live_desc = False, None
        if arm["id"] in CM.LIVE_CONTROLS_RAW:
            bpos, bval = CM.LIVE_CONTROLS_RAW[arm["id"]]
            ctl = bytearray(orig)
            ctl[bpos] = bval
            ctl = bytes(ctl)
            live_desc = f"raw byte+{bpos}={bval:#04x}"
        else:
            f, v = arm["live"]
            ctl = isadb_set(arm["mnemonic"], orig, f, v)
            live_desc = f"{f}={v:#04x}"
        cobs = run_case(arm, ctl)
        live_ok = (cobs.get("status") != "OK"
                   or cobs.get("probe") != base.get("probe")
                   or cobs.get("lanes") != base.get("lanes")
                   or cobs.get("dprobe") != base.get("dprobe")
                   or cobs.get("h") != base.get("h")
                   or cobs.get("dh") != base.get("dh"))
        emit({"instr": arm["mnemonic"], "field": "_live_control", "value": -1,
              "bytes": ctl.hex(), "observed": cobs, "oracle": None,
              "match": bool(live_ok), "outcome": "ok" if live_ok else "wrong_value",
              "carrier": arm["id"], "note": f"liveness control {live_desc}; "
                                            f"changed={live_ok}"})
        ncases += 1
        summary[arm["id"]] = {"live": bool(live_ok), "control": live_desc}

        if args.smoke_only:
            continue

        def baseline_holds():
            """sec.7.3.  A single failure inside a sibling's error-recovery
            window is NOT a cascade; only an all-attempts failure is."""
            for k in range(BASELINE_RETRIES):
                b = run_case(arm, orig)
                if (b.get("status") == "OK"
                        and b.get("probe") == base.get("probe")
                        and b.get("lanes") == base.get("lanes")
                        and b.get("dprobe") == base.get("dprobe")):
                    return True, b, k
                time.sleep(0.5 * (k + 1))
            return False, b, BASELINE_RETRIES

        desc = isadb._BY_MNEM[arm["mnemonic"]]
        arm_hangs = 0
        since_baseline = 0
        for fname in arm["fields"]:
            vals = CM.field_values(desc["fields"], fname)
            detect = 0            # how many values of THIS field moved the output
            nfault = nzero = nok = 0
            field_hangs = 0
            swept = 0
            for v in vals:
                if since_baseline >= BASELINE_EVERY:
                    ok, b, tries = baseline_holds()
                    emit({"instr": arm["mnemonic"], "field": "_baseline_recheck",
                          "value": ncases, "bytes": orig.hex(), "observed": b,
                          "oracle": None, "match": bool(ok),
                          "outcome": "ok" if ok else "fault", "carrier": arm["id"],
                          "note": f"periodic re-validation, retries={tries}"})
                    ncases += 1
                    since_baseline = 0
                    if not ok:
                        cascade.append((arm["id"], fname, ncases))
                        emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                              "bytes": "", "observed": {"status": "ARM_STOPPED"},
                              "oracle": None, "match": False, "outcome": "fault",
                              "carrier": arm["id"],
                              "note": "ARM STOPPED: unmutated carrier stopped "
                                      "reproducing its own baseline on all "
                                      f"{BASELINE_RETRIES} attempts (sec.7.3)"})
                        break
                patched = isadb_set(arm["mnemonic"], orig, fname, v)
                oracle = predictive_oracle(arm, fname, v, cfg, base)
                obs, confirm = run_confirmed(arm, patched)
                since_baseline += 1
                swept += 1
                # sec.8: a GENUINE hang is a watchdog timeout OR a command
                # buffer the OS classified as ErrorHang -- run01 counted only
                # the former and kept driving a reproducible hang.
                genuine_hang = (confirm is not None and confirm["reproduced"]
                                and (obs.get("status") == "HANG"
                                     or obs.get("os_class") == "ErrorHang"))
                if genuine_hang:
                    field_hangs += 1
                    arm_hangs += 1
                    hangs_total += 1
                    time.sleep(2.0)   # let the GPU (and our siblings) recover
                outcome = classify(obs, base, oracle)
                # sec.7.2: a fault we could not reproduce, or one the OS blames
                # on another client, is NOT a property of this field value.
                if confirm and not confirm["reproduced"]:
                    outcome = "ok" if obs.get("status") == "OK" else "unreproduced"
                if obs.get("os_class") == "InnocentVictim":
                    outcome = "foreign"
                try:
                    d, _ = isadb.decode_one(patched, 0)
                    dm = d["mnemonic"]
                except ValueError:
                    dm = None
                if dm != arm["mnemonic"]:
                    outcome = "undecodable" if outcome == "ok" else outcome
                if outcome in ("wrong_value", "silent_zero"):
                    detect += 1
                if outcome == "silent_zero":
                    nzero += 1
                if outcome in ("fault", "hang"):
                    nfault += 1
                if outcome == "ok":
                    nok += 1
                emit({"instr": arm["mnemonic"], "field": fname, "value": v,
                      "bytes": patched.hex(), "observed": obs, "oracle": oracle,
                      "match": (outcome == "ok"), "outcome": outcome,
                      "carrier": arm["id"], "confirm": confirm,
                      "note": "" if dm == arm["mnemonic"] else f"re-decodes as {dm}"})
                ncases += 1
                if field_hangs >= MAX_HANGS_PER_FIELD:
                    emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                          "bytes": "", "observed": {"status": "FIELD_STOPPED"},
                          "oracle": None, "match": False, "outcome": "hang",
                          "carrier": arm["id"],
                          "note": f"FIELD STOPPED after {field_hangs} genuine "
                                  f"hangs at {swept}/{len(vals)} values "
                                  f"(FIELD-SWEEP-PROTOCOL sec.8); remaining "
                                  f"values NOT swept"})
                    ncases += 1
                    break
                if arm_hangs >= MAX_HANGS_PER_ARM:
                    emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                          "bytes": "", "observed": {"status": "ARM_STOPPED"},
                          "oracle": None, "match": False, "outcome": "hang",
                          "carrier": arm["id"],
                          "note": f"ARM STOPPED after {arm_hangs} hangs "
                                  f"(FIELD-SWEEP-PROTOCOL sec.8)"})
                    ncases += 1
                    break
            detection[f"{arm['id']}/{fname}"] = {
                "n": len(vals), "swept": swept, "moved_output": detect,
                "faults": nfault, "silent_zero": nzero, "unchanged": nok,
                "hangs": field_hangs,
                "complete": swept == len(vals) and field_hangs < MAX_HANGS_PER_FIELD}
            if arm_hangs >= MAX_HANGS_PER_ARM or cascade:
                break
        # end-of-arm baseline confirmation
        okb, b, tries = baseline_holds()
        emit({"instr": arm["mnemonic"], "field": "_baseline_final", "value": -1,
              "bytes": orig.hex(), "observed": b, "oracle": None, "match": bool(okb),
              "outcome": "ok" if okb else "fault", "carrier": arm["id"],
              "note": f"end-of-arm re-validation, retries={tries}"})
        ncases += 1
        summary[arm["id"]]["baseline_final_ok"] = bool(okb)
        if cascade:
            break

    # ---- the 0x57 opcode-collision hardware probe -------------------------
    if not args.smoke_only:
        collision_probe(carriers, runners, emit, args)

    jl.close()
    for r in runners.values():
        r.close()

    man = {"run_id": args.run_id, "cases": ncases, "hangs": hangs_total,
           "arms": summary, "detection": detection, "cascade": cascade,
           "elapsed_s": round(time.time() - t_start, 1),
           "restarts": {k: r.restarts for k, r in runners.items()}}
    with open(os.path.join(outdir, "05_run_manifest.json"), "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps(man, indent=1, sort_keys=True))


def isadb_set(mnemonic, raw, field, value):
    desc = isadb._BY_MNEM[mnemonic]
    v = int.from_bytes(raw, "little")
    for f in desc["fields"]:
        if f["name"] == field:
            mask = ((1 << f["width"]) - 1) << f["start"]
            v = (v & ~mask) | ((value << f["start"]) & mask)
            return v.to_bytes(desc["length"], "little")
    raise KeyError(f"{mnemonic}.{field}")


def predictive_oracle(arm, fname, v, cfg, base):
    """Host-computed expected observation, or None (=> null/inert oracle)."""
    key = (arm["id"], fname)
    if key not in CM.PREDICTIVE:
        return None
    W, H = cfg.get("width", 16), cfg.get("height", 16)
    if key == ("iter@frag1", "src_slot"):
        slot = v >> 1
        val = CM.interp(slot, 0, 0, W, H)
        if val is None:
            return None
        out = []
        for i, (x, y) in enumerate(CM.PROBE_PIXELS):
            row = list(base["probe"][i])
            row[0] = round(CM.interp(slot, x, y, W, H), 6)
            out.append(row)
        return out
    if key == ("fcs@iter0", "rt_index"):
        if v == 0:
            return base["probe"]
        return [[0.0, 0.0, 0.0, 0.0] for _ in CM.PROBE_PIXELS]
    if key == ("sshuffle@simd1", "lane"):
        src_lane = v >> 1
        if src_lane > 31:
            return None
        u = [(i * i * 7 + 3) & 0xFFFFFFFF for i in range(32)]
        lanes = {}
        for ln in CM.PROBE_LANES:
            row = list(base["lanes"][str(ln)])
            row[10] = u[src_lane]
            lanes[str(ln)] = row
        return lanes
    return None


def collision_probe(carriers, runners, emit, args):
    """Hardware test of the 0x57 vertex-store / fragment-kill discriminator."""
    P = CM.COLLISION_PROBE
    # FRAGMENT side: c_kill's 6-byte `57 14 54 00 00 01`
    for cname in ("c_kill", "c_mask"):
        c = carriers[cname]
        buf = bytes.fromhex(c["entry"]["stages"]["fragment"]["hex"])
        idx = buf.find(bytes([0x57]))
        while idx >= 0 and idx + 6 <= len(buf) and buf[idx + 2] != 0x54:
            idx = buf.find(bytes([0x57]), idx + 1)
        if idx < 0:
            continue
        abs_off = c["entry"]["stages"]["fragment"]["abs_off"] + idx
        orig6 = buf[idx:idx + 6]
        base = obs_render(runners[cname].render([], timeout=REQ_TIMEOUT), c["cfg"])
        emit({"instr": "op57_fragment", "field": "_baseline", "value": -1,
              "bytes": orig6.hex(), "observed": base, "oracle": None, "match": True,
              "outcome": "ok", "carrier": f"{cname}/frag@{idx}",
              "note": P["hypothesis"]})
        for v in P["fs_byte1_values"]:
            b = bytearray(orig6)
            b[1] = v
            obs = obs_render(runners[cname].render([(abs_off, bytes(b).hex())],
                                                   timeout=REQ_TIMEOUT), c["cfg"])
            emit({"instr": "op57_fragment", "field": "byte1", "value": v,
                  "bytes": bytes(b).hex(), "observed": obs, "oracle": None,
                  "match": (obs.get("probe") == base.get("probe")
                            and obs.get("h") == base.get("h")),
                  "outcome": classify(obs, base, None),
                  "carrier": f"{cname}/frag@{idx}", "note": ""})
    # VERTEX side: c_iter's first 8-byte varying store
    for cname in ("c_iter", "c_vary16"):
        c = carriers[cname]
        buf = bytes.fromhex(c["entry"]["stages"]["vertex"]["hex"])
        hits, how = locate(buf, "vary_store")
        if not hits:
            continue
        idx = hits[0]
        abs_off = c["entry"]["stages"]["vertex"]["abs_off"] + idx
        orig8 = buf[idx:idx + 8]
        base = obs_render(runners[cname].render([], timeout=REQ_TIMEOUT), c["cfg"])
        emit({"instr": "op57_vertex", "field": "_baseline", "value": -1,
              "bytes": orig8.hex(), "observed": base, "oracle": None, "match": True,
              "outcome": "ok", "carrier": f"{cname}/vert@{idx}",
              "note": P["hypothesis"]})
        for v in P["vs_byte1_values"]:
            b = bytearray(orig8)
            b[1] = v
            obs = obs_render(runners[cname].render([(abs_off, bytes(b).hex())],
                                                   timeout=REQ_TIMEOUT), c["cfg"])
            emit({"instr": "op57_vertex", "field": "byte1", "value": v,
                  "bytes": bytes(b).hex(), "observed": obs, "oracle": None,
                  "match": (obs.get("probe") == base.get("probe")
                            and obs.get("h") == base.get("h")),
                  "outcome": classify(obs, base, None),
                  "carrier": f"{cname}/vert@{idx}", "note": ""})


if __name__ == "__main__":
    main()
