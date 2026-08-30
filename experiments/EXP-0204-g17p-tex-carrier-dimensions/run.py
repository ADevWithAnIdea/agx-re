#!/usr/bin/env python3
"""run.py -- EXP-0204 capture driver.

    python3 run.py --run-id g17p_YYYYMMDD_runNN [--smoke-only] [--deadline-s N]

FORKED FROM OUR OWN experiments/EXP-0172-g17p-onefield-tail/run.py.  What is new
here, and why:

  * ORACLE ON EVERY CASE.  harness/oracle.py computes, on the host, the exact
    float4 each carrier's BASELINE must produce -- from the triangle our own
    vertex shaders draw (all three vertices have w == 1, so every varying is
    affine in screen space) and from the texture content gfrun4.m itself writes.
    `tools/agx-isa/wave_audit.py` counts distinct oracle payloads because a
    CONSTANT oracle predicts the instruction, not the field.
  * DIMENSION CONTROL.  Beyond the generic detection profile, each arm records
    whether a control IN THE FIELD'S OWN DIMENSION moved
    (FIELD-SWEEP-PROTOCOL sec.9 rule 1).  An inert verdict without one is not
    reported as inert.
  * MACHINE-QUIET MEASUREMENT.  The device process table is sampled every 20 s
    into raw/<run_id>/procs.jsonl, so "the machine was quiet" is a MEASUREMENT
    (sec.7's own requirement) rather than a claim.  tex_deriv.dstsrc -- whose
    whole open question is cross-run stability -- is only promoted from a pair of
    runs both measured QUIET.
  * NAMED MAPPING PASS for tex_deriv.dstsrc: a hang budget of 2 is what stopped
    EXP-0172 at 39 of 65 values, and sec.3(c) says a per-field budget "guarantees
    the region is never mapped".  Budget 8, declared in advance.
  * runner4.py's per-child reader thread (sec.3(d)) and MALFORMED handling.

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
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import isadb                                     # noqa: E402  (PINNED copy)
import carriers as CA                            # noqa: E402
import arms as ARMSPEC                           # noqa: E402
import oracle as OR                              # noqa: E402
from runner4 import RenderRunner, render_cmd     # noqa: E402

WORK = os.path.join(HERE, "work")
AGXPARSE = os.path.join(HERE, "pinned", "agxparse.py")
GFRUN = os.path.join(WORK, "gfrun4")

REQ_TIMEOUT = 15.0
MAX_HANGS_PER_FIELD = 2
MAPPING_PASS = {("tex_deriv", "dstsrc"): 8}      # pre-registered, named
MAX_HANGS_PER_ARM = 10
CONFIRM_N = 3
FOREIGN_CASCADE_N = 8
BASELINE_EVERY = 250
BASELINE_RETRIES = 4
DEADLINE = None
POISON4 = b"\xef\xbe\xad\xde"

# Controls that count as being IN the field's own dimension (authored; mirrors
# carriers.py::DIMENSION and PRE_REGISTRATION sec.6.2).
DIM_CONTROLS = {
    "tex_sample.mode":   ["variant", "result_desc", "lod_present"],
    "tex_deriv.dstsrc":  ["src_comp", "b1"],
    "tex_write.amode":   ["coord_pack", "coord_regs", "coord_dim", "layer_reg"],
    "tex_write.rsv11":   ["data_desc", "data_desc_hi", "rsv8"],
}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(cmd, timeout=240):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {r.stdout} {r.stderr}")
    return r.stdout


def f32(vals):
    return [struct.unpack("<I", struct.pack("<f", v))[0] for v in vals]


def bufs_for(name):
    return {i: f32(v) for i, v in (CA.BUFS.get(name) or {}).items()}


def build_carrier(name, cfg):
    arch = os.path.join(WORK, f"{name}.bin")
    sh(render_cmd(GFRUN, os.path.join(HERE, cfg["src"]), cfg, build=arch,
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
    """IDENTICAL rule to analysis/census.py::locate."""
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


def redecode(arm, patched):
    """The mnemonic a patched instruction decodes as, IN CONTEXT (several length
    rules look ahead past the instruction's own bytes, so decoding the patched
    bytes alone is wrong and can also raise)."""
    try:
        buf = bytearray(bytes.fromhex(arm["stage_hex"]))
        o = arm["instr_off"]
        buf[o:o + len(patched)] = patched
        d, _ = isadb.decode_one(bytes(buf), o)
        return d["mnemonic"]
    except (ValueError, IndexError, KeyError):
        return None


def _os_class(err):
    for tag in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
                "ErrorOutOfMemory", "ErrorInvalidResource", "ErrorMakeCurrent",
                "ErrorRestart", "ErrorRecovery"):
        if tag in err:
            return tag
    return "unclassified" if err else ""


def observe(resp, cfg):
    """Reduce a runner response to a compact, deterministic observation.

    EVERY surface the harness reported is hashed, so a change anywhere in any
    attachment, writable texture, depth buffer or output buffer is DETECTED --
    not only at the probe points.  The probes are kept because they make a
    difference READABLE; the hashes are what make it DETECTABLE."""
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
    Wd, Hd = cfg.get("width", 16), cfg.get("height", 16)
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
        elif tag == "TEXW" or tag.startswith("TEXWA") or tag.startswith("TEXWM") \
                or tag.startswith("TEXWC"):
            tw = 8
            v = []
            for (x, y) in CA.PROBE_TEXELS:
                base = (y * tw + x) * 16
                if base + 16 <= len(buf):
                    v.append([round(f, 5) for f in struct.unpack_from("<4f", buf, base)])
            pr[tag] = v
        elif tag == "TEXWB":
            v = []
            for k in (0, 3, 17, 31):
                if (k + 1) * 16 <= len(buf):
                    v.append([round(f, 5) for f in struct.unpack_from("<4f", buf, k * 16)])
            pr[tag] = v
        elif tag == "TEXWR":
            pr[tag] = [round(struct.unpack_from("<f", buf, (y * 8 + x) * 4)[0], 5)
                       for (x, y) in CA.PROBE_TEXELS if (y * 8 + x) * 4 + 4 <= len(buf)]
        elif tag == "TEXWG":
            pr[tag] = [[round(f, 5) for f in struct.unpack_from("<2f", buf, (y * 8 + x) * 8)]
                       for (x, y) in CA.PROBE_TEXELS if (y * 8 + x) * 8 + 8 <= len(buf)]
    o["probe"] = pr
    return o


def same_obs(a, b):
    return (a.get("status") == "OK" and b.get("status") == "OK"
            and a.get("hh") == b.get("hh"))


def classify(obs, base):
    if obs.get("status") == "HANG":
        return "hang"
    if obs.get("status") == "MALFORMED":
        return "malformed"
    if obs.get("status") != "OK":
        return "fault"
    if same_obs(obs, base):
        return "ok"
    return "wrong_value"


def isadb_set(mnemonic, raw, field, value):
    desc = isadb._BY_MNEM[mnemonic]
    v = int.from_bytes(raw, "little")
    for f in desc["fields"]:
        if f["name"] == field:
            mask = ((1 << f["width"]) - 1) << f["start"]
            v = (v & ~mask) | ((value << f["start"]) & mask)
            return v.to_bytes(desc["length"], "little")
    raise KeyError(f"{mnemonic}.{field}")


# --------------------------------------------------------------------------
# Machine-quiet measurement (PRE_REGISTRATION sec.9)
# --------------------------------------------------------------------------
QUIET_MATCH = ("gfrun", "frun", "agxrun", "rendersweep", "shdump",
               "persistrun", "rsdrv", "run.py")


def quiet_sampler(path, stop_evt, my_pid, period=20.0):
    f = open(path, "a")
    while not stop_evt.is_set():
        try:
            out = subprocess.run(["ps", "-eo", "pid,ppid,etime,command"],
                                 capture_output=True, text=True, timeout=10).stdout
        except Exception as e:
            out = f"PS_FAILED {e}"
        mine, foreign = [], []
        for ln in out.splitlines()[1:]:
            if not any(m in ln for m in QUIET_MATCH):
                continue
            parts = ln.split(None, 3)
            if len(parts) < 4:
                continue
            pid = parts[0]
            cmd = parts[3][:150]
            (mine if "EXP-0204" in cmd or pid == str(my_pid) else foreign).append(
                {"pid": pid, "cmd": cmd})
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "n_foreign": len(foreign), "foreign": foreign[:12],
                            "n_mine": len(mine)}, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        stop_evt.wait(period)
    f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--mnem", default="")
    ap.add_argument("--smoke-only", action="store_true")
    ap.add_argument("--deadline-s", type=float, default=0.0)
    args = ap.parse_args()
    global DEADLINE
    DEADLINE = (time.time() + args.deadline_s) if args.deadline_s > 0 else None

    outdir = (os.path.join(WORK, "smoke_" + args.run_id) if args.smoke_only
              else os.path.join(HERE, "raw", args.run_id))
    if os.path.exists(outdir) and not args.smoke_only:
        sys.exit(f"run dir already exists, refusing to reuse: {outdir}")
    os.makedirs(outdir, exist_ok=True)
    t_start = time.time()

    stop_evt = threading.Event()
    qt = threading.Thread(target=quiet_sampler,
                          args=(os.path.join(outdir, "procs.jsonl"), stop_evt,
                                os.getpid()), daemon=True)
    qt.start()

    want_arm = set(x for x in args.arms.split(",") if x)
    want_mn = set(x for x in args.mnem.split(",") if x)
    spec = [a for a in ARMSPEC.ARMS
            if (not want_arm or a["id"] in want_arm)
            and (not want_mn or a["mnemonic"] in want_mn)]
    need = sorted({a["carrier"] for a in spec})

    inputs = {"run_id": args.run_id,
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "carriers": {}, "arms": {}}
    carriers = {}
    for name in need:
        cfg = CA.CARRIERS[name]
        arch = build_carrier(name, cfg)
        entry = {"archive_sha256": sha256_file(arch), "path": arch,
                 "src_sha256": sha256_file(os.path.join(HERE, cfg["src"])),
                 "why": cfg["why"], "stages": {}}
        for st in ("vertex", "fragment"):
            off, buf = stage_bytes(arch, st)
            entry["stages"][st] = {"abs_off": off, "len": len(buf), "hex": buf.hex()}
        carriers[name] = dict(cfg=cfg, arch=arch, entry=entry)
        inputs["carriers"][name] = entry

    arms = []
    for a in spec:
        c = carriers[a["carrier"]]
        sinfo = c["entry"]["stages"][a["stage"]]
        buf = bytes.fromhex(sinfo["hex"])
        hits, how = locate(buf, a["mnemonic"])
        rec = {"located_via": how, "n_hits": len(hits)}
        if a["occ"] >= len(hits):
            rec["error"] = f"occurrence {a['occ']} not found ({len(hits)} hits)"
            inputs["arms"][a["id"]] = rec
            continue
        ioff = hits[a["occ"]]["off"]
        d, L = isadb.decode_one(buf, ioff)
        rec.update(instr_off=ioff, abs_off=sinfo["abs_off"] + ioff, length=L,
                   orig=d["hex"], decoded=d["fields"],
                   expect_hex=a["expect_hex"], expect_off=a["expect_off"])
        # FROZEN INTEGRITY CHECK: the census's bytes must still be there.
        if d["hex"] != a["expect_hex"] or ioff != a["expect_off"]:
            rec["error"] = ("frozen occurrence moved: census had "
                            f"{a['expect_hex']}@{a['expect_off']}, found "
                            f"{d['hex']}@{ioff}")
            inputs["arms"][a["id"]] = rec
            continue
        arm = dict(a)
        arm.update(rec)
        arm["stage_hex"] = sinfo["hex"]
        arms.append(arm)
        inputs["arms"][a["id"]] = rec

    with open(os.path.join(outdir, "00_inputs.json"), "w") as f:
        json.dump(inputs, f, indent=1, sort_keys=True)

    runners = {}
    for name in need:
        c = carriers[name]
        runners[name] = RenderRunner(
            GFRUN, os.path.join(HERE, c["cfg"]["src"]), c["arch"],
            os.path.join(WORK, f"scratch_{args.run_id}_{name}.bin"),
            c["cfg"], bufs_for(name))

    jl = open(os.path.join(outdir, "sweep.jsonl"), "a")

    def emit(rec):
        jl.write(json.dumps(rec, sort_keys=True) + "\n")
        jl.flush()
        os.fsync(jl.fileno())

    def run_case(arm, patched):
        resp = runners[arm["carrier"]].render(
            [(arm["abs_off"], patched.hex())], timeout=REQ_TIMEOUT)
        o = observe(resp, carriers[arm["carrier"]]["cfg"])
        o["sentinel"] = resp.get("sentinel", "")
        return o

    def run_confirmed(arm, patched):
        obs = run_case(arm, patched)
        if obs.get("status") == "OK":
            return obs, None
        if obs.get("status") == "FOREIGN_FAULT" or obs.get("os_class") == "InnocentVictim":
            return obs, {"n": 1, "status": [obs.get("status")],
                         "os_class": [obs.get("os_class", "")], "bad": 1,
                         "reproduced": False, "foreign_shortcut": True}
        trials = [obs] + [run_case(arm, patched) for _ in range(CONFIRM_N - 1)]
        nbad = sum(1 for t in trials if t.get("status") != "OK")
        rec = {"n": len(trials), "status": [t.get("status") for t in trials],
               "os_class": [t.get("os_class", "") for t in trials],
               "bad": nbad, "reproduced": nbad * 2 > len(trials)}
        if not rec["reproduced"]:
            for t in trials:
                if t.get("status") == "OK":
                    return t, rec
        return trials[0], rec

    ncases, hangs_total = 0, 0
    summary, detection, cascade = {}, {}, []

    for arm in arms:
        if DEADLINE and time.time() > DEADLINE:
            emit({"instr": arm["mnemonic"], "field": "_arm_not_run", "value": -1,
                  "bytes": "", "observed": {"status": "DEADLINE"},
                  "oracle": {"predict": "n/a"}, "match": False,
                  "outcome": "not_run", "carrier": arm["id"],
                  "note": "wall-clock budget exhausted before this arm started"})
            ncases += 1
            summary[arm["id"]] = {"detect_ok": None, "reason": "deadline, not run"}
            continue
        orig = bytes.fromhex(arm["orig"])
        base = run_case(arm, orig)
        # Host-computed baseline check -- the oracle that can actually fail.
        nchk, nagree, bad = OR.baseline_agrees(arm["carrier"], CA.PROBE_PIXELS,
                                               base.get("probe"),
                                               texels=CA.PROBE_TEXELS)
        emit({"instr": arm["mnemonic"], "field": "_baseline", "value": -1,
              "bytes": orig.hex(), "observed": base,
              "oracle": {"predict": "host_computed_baseline",
                         "pixels": OR.predicted_pixels(arm["carrier"], CA.PROBE_PIXELS),
                         "texw": OR.predicted_texw(arm["carrier"], CA.PROBE_TEXELS),
                         "checked": nchk, "agree": nagree},
              "match": bool(nchk and nagree == nchk),
              "outcome": "ok" if base.get("status") == "OK" else "fault",
              "carrier": arm["id"],
              "note": f"host-oracle baseline {nagree}/{nchk} channels agree; "
                      f"mismatches={json.dumps(bad)[:400]}"})
        ncases += 1
        if base.get("status") != "OK":
            summary[arm["id"]] = {"detect_ok": False, "reason": "baseline failed"}
            continue

        # ---- DETECTION PROFILE + DIMENSION CONTROL -----------------------
        desc = isadb._BY_MNEM[arm["mnemonic"]]
        live_same, live_any, dim_live = [], [], {}
        cur = arm["decoded"]
        for f in desc["fields"]:
            fn, w = f["name"], f["width"]
            mask = (1 << w) - 1
            for v in (((~cur.get(fn, 0)) & mask), 0):
                if v == cur.get(fn, 0):
                    continue
                ctl = isadb_set(arm["mnemonic"], orig, fn, v)
                dm = redecode(arm, ctl)
                cobs = run_case(arm, ctl)
                changed = not same_obs(cobs, base)
                if changed:
                    live_any.append(f"{fn}={v:#x}")
                    if dm == arm["mnemonic"]:
                        live_same.append(f"{fn}={v:#x}")
                        for tgt in arm["fields"]:
                            key = f"{arm['mnemonic']}.{tgt}"
                            if fn in DIM_CONTROLS.get(key, ()):
                                dim_live.setdefault(key, []).append(f"{fn}={v:#x}")
                emit({"instr": arm["mnemonic"], "field": "_detect", "value": v,
                      "bytes": ctl.hex(), "observed": cobs,
                      "oracle": {"predict": "control_should_move_if_arm_is_live",
                                 "control_field": fn},
                      "match": not changed,
                      "outcome": "moved" if changed else "inert",
                      "carrier": arm["id"],
                      "note": f"detection profile: {fn}={v:#x}; changed={changed}; "
                              f"redecodes_as={dm}; status={cobs.get('status')}"})
                ncases += 1
        summary[arm["id"]] = {
            "detect_ok": bool(live_same), "detect_any": bool(live_any),
            "live_same_mnemonic": live_same, "live_any": live_any,
            "dimension_controls_moved": dim_live,
            "located_via": arm["located_via"],
            "baseline_host_oracle": {"checked": nchk, "agree": nagree},
        }
        emit({"instr": arm["mnemonic"], "field": "_detect_summary", "value": -1,
              "bytes": "", "observed": {"status": "OK"},
              "oracle": {"predict": "arm_has_detection_power"},
              "match": bool(live_same),
              "outcome": "has_power" if live_same else "no_power",
              "carrier": arm["id"],
              "note": json.dumps(summary[arm["id"]], sort_keys=True)})
        ncases += 1

        if args.smoke_only:
            continue

        def baseline_holds():
            b = base
            for k in range(BASELINE_RETRIES):
                b = run_case(arm, orig)
                if same_obs(b, base):
                    return True, b, k
                time.sleep(0.5 * (k + 1))
            return False, b, BASELINE_RETRIES

        consec_foreign = [0]
        arm_hangs = 0
        since_baseline = 0
        widths = {f["name"]: f["width"] for f in desc["fields"]}
        for fname in arm["fields"]:
            budget = MAPPING_PASS.get((arm["mnemonic"], fname), MAX_HANGS_PER_FIELD)
            if fname not in widths:
                emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                      "bytes": "", "observed": {"status": "NO_SUCH_FIELD"},
                      "oracle": {"predict": "n/a"}, "match": False,
                      "outcome": "not_run", "carrier": arm["id"],
                      "note": "field absent from the pinned db.json"})
                ncases += 1
                continue
            if DEADLINE and time.time() > DEADLINE:
                emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                      "bytes": "", "observed": {"status": "DEADLINE"},
                      "oracle": {"predict": "n/a"}, "match": False,
                      "outcome": "not_run", "carrier": arm["id"],
                      "note": "wall-clock budget exhausted; field UNSWEPT"})
                ncases += 1
                continue
            w = widths[fname]
            vals = list(range(1 << w)) if w <= 8 else sorted(
                {0, 1, 2, (1 << w) - 2, (1 << w) - 1}
                | {1 << i for i in range(w)}
                | {(1 << i) - 1 for i in range(1, w)}
                | {(k * 0x9E3779B1) & ((1 << w) - 1)
                   for k in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59)})
            bval = arm["decoded"].get(fname)
            moved = nfault = nok = 0
            field_hangs = swept = 0
            for v in vals:
                if since_baseline >= BASELINE_EVERY:
                    ok, b, tries = baseline_holds()
                    emit({"instr": arm["mnemonic"], "field": "_baseline_recheck",
                          "value": ncases, "bytes": orig.hex(), "observed": b,
                          "oracle": {"predict": "baseline_reproduces"},
                          "match": bool(ok), "outcome": "ok" if ok else "fault",
                          "carrier": arm["id"],
                          "note": f"periodic re-validation, retries={tries}"})
                    ncases += 1
                    since_baseline = 0
                    if not ok:
                        cascade.append((arm["id"], fname, ncases))
                        emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                              "bytes": "", "observed": {"status": "ARM_STOPPED"},
                              "oracle": {"predict": "n/a"},
                              "match": False, "outcome": "fault",
                              "carrier": arm["id"],
                              "note": "ARM STOPPED: unmutated carrier stopped "
                                      f"reproducing its baseline on all "
                                      f"{BASELINE_RETRIES} attempts"})
                        break
                patched = isadb_set(arm["mnemonic"], orig, fname, v)
                obs, confirm = run_confirmed(arm, patched)
                since_baseline += 1
                swept += 1
                genuine_hang = (confirm is not None and confirm["reproduced"]
                                and (obs.get("status") == "HANG"
                                     or obs.get("os_class") == "ErrorHang"))
                if genuine_hang:
                    field_hangs += 1
                    arm_hangs += 1
                    hangs_total += 1
                    time.sleep(2.0)
                outcome = classify(obs, base)
                if confirm and not confirm["reproduced"]:
                    outcome = "ok" if obs.get("status") == "OK" else "unreproduced"
                if obs.get("os_class") == "InnocentVictim":
                    outcome = "foreign"
                dm = redecode(arm, patched)
                if dm != arm["mnemonic"] and outcome == "ok":
                    outcome = "undecodable"
                if outcome == "wrong_value":
                    moved += 1
                if outcome == "foreign":
                    consec_foreign[0] += 1
                    if consec_foreign[0] >= FOREIGN_CASCADE_N:
                        time.sleep(3.0)
                        okb, bb, tries = baseline_holds()
                        emit({"instr": arm["mnemonic"], "field": "_cascade_check",
                              "value": ncases, "bytes": orig.hex(), "observed": bb,
                              "oracle": {"predict": "baseline_reproduces"},
                              "match": bool(okb), "outcome": "ok" if okb else "fault",
                              "carrier": arm["id"],
                              "note": f"{consec_foreign[0]} consecutive foreign "
                                      f"outcomes; baseline_ok={okb} after {tries}"})
                        ncases += 1
                        consec_foreign[0] = 0
                        if not okb:
                            cascade.append((arm["id"], fname, ncases))
                            break
                else:
                    consec_foreign[0] = 0
                if outcome in ("fault", "hang"):
                    nfault += 1
                if outcome == "ok":
                    nok += 1
                emit({"instr": arm["mnemonic"], "field": fname, "value": v,
                      "bytes": patched.hex(), "observed": obs,
                      "oracle": OR.oracle_for(arm["mnemonic"], fname, v,
                                              arm["carrier"], bval),
                      "match": (outcome == "ok"), "outcome": outcome,
                      "carrier": arm["id"], "confirm": confirm,
                      "note": "" if dm == arm["mnemonic"] else f"re-decodes as {dm}"})
                ncases += 1
                if field_hangs >= budget:
                    emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                          "bytes": "", "observed": {"status": "FIELD_STOPPED"},
                          "oracle": {"predict": "n/a"},
                          "match": False, "outcome": "hang", "carrier": arm["id"],
                          "note": f"FIELD STOPPED after {field_hangs} genuine hangs "
                                  f"at {swept}/{len(vals)} values (budget {budget})"})
                    ncases += 1
                    break
                if arm_hangs >= MAX_HANGS_PER_ARM:
                    emit({"instr": arm["mnemonic"], "field": fname, "value": -1,
                          "bytes": "", "observed": {"status": "ARM_STOPPED"},
                          "oracle": {"predict": "n/a"},
                          "match": False, "outcome": "hang", "carrier": arm["id"],
                          "note": f"ARM STOPPED after {arm_hangs} hangs"})
                    ncases += 1
                    break
            detection[f"{arm['id']}/{fname}"] = {
                "n": len(vals), "swept": swept, "moved_output": moved,
                "faults": nfault, "unchanged": nok, "hangs": field_hangs,
                "hang_budget": budget,
                "complete": swept == len(vals) and field_hangs < budget}
            if arm_hangs >= MAX_HANGS_PER_ARM or cascade:
                break
        okb, b, tries = baseline_holds()
        emit({"instr": arm["mnemonic"], "field": "_baseline_final", "value": -1,
              "bytes": orig.hex(), "observed": b,
              "oracle": {"predict": "baseline_reproduces"},
              "match": bool(okb),
              "outcome": "ok" if okb else "fault", "carrier": arm["id"],
              "note": f"end-of-arm re-validation, retries={tries}"})
        ncases += 1
        summary[arm["id"]]["baseline_final_ok"] = bool(okb)
        if cascade:
            break

    jl.close()
    for r in runners.values():
        r.close()
    stop_evt.set()
    qt.join(timeout=25)
    man = {"run_id": args.run_id, "cases": ncases, "hangs": hangs_total,
           "arms": summary, "detection": detection, "cascade": cascade,
           "elapsed_s": round(time.time() - t_start, 1),
           "restarts": {k: r.restarts for k, r in runners.items()}}
    with open(os.path.join(outdir, "05_run_manifest.json"), "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({k: man[k] for k in ("run_id", "cases", "hangs", "cascade",
                                          "elapsed_s", "restarts")}, indent=1))


if __name__ == "__main__":
    main()
