#!/usr/bin/env python3
"""EXP-0178 capture driver -- `get_sr` (sysvals) and `tile_read`/`tile_read_mrt`
(tilebuffer) field sweeps on the A18 Pro / G17P.

One JSON object per case is appended to raw/<run_id>/sweep.jsonl and flushed +
fsync'd immediately, so a kill or a GPU wedge costs at most ONE case. Refuses to
reuse an existing run id (SUBAGENT_BRIEF: never reuse or overwrite a run id).

  python3 harness/run.py --run-id g17p_YYYYMMDD_runNN --out-root raw
  python3 harness/run.py --run-id pilot01 --out-root work --arms sr_compute
"""
import argparse
import json
import os
import struct
import subprocess
import traceback
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pinned_isa                                              # noqa: E402
import sweepplan as SP                                         # noqa: E402

# The pinned toolchain gate runs BEFORE anything else can silently resolve a
# stale shared copy.
PINNED = pinned_isa.verify()
ISA = pinned_isa.load_isadb()
AGXPARSE = pinned_isa.agxparse_path()

BIN = os.path.join(EXP, "work", "bin")
SHDUMP2 = os.path.join(BIN, "shdump2")
RENDERSWEEP = os.path.join(BIN, "rendersweep")
AGXPERSIST = os.path.join(BIN, "agxrun_persist")

sys.path.insert(0, BIN)                 # persistrun.py is copied next to the bins
from saferunner import SafePersistRunner, SafeRenderRunner     # noqa: E402

REQ_TIMEOUT = 10.0
BUILD_TIMEOUT = 120
COLOR_FORMAT = 125                       # MTLPixelFormatRGBA32Float


# ------------------------------------------------------------------ utils ----

def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32v(v):
    return [f32(x) for x in v]


def sh(args, timeout=BUILD_TIMEOUT):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def locate(archive, stage):
    a = [sys.executable, AGXPARSE, archive, "--locate", "_agc.main"]
    if stage:
        a[3:3] = ["--stage", stage]
    r = sh(a)
    return int(r.stdout.split()[0])


def extract_hex(archive, stage):
    a = [sys.executable, AGXPARSE, archive, "--extract-hex"]
    if stage:
        a[3:3] = ["--stage", stage]
    return sh(a).stdout.strip()


def get_bits(block, start, width):
    v = int.from_bytes(block, "little")
    return (v >> start) & ((1 << width) - 1)


def set_bits(block, start, width, value):
    v = int.from_bytes(block, "little")
    m = ((1 << width) - 1) << start
    v = (v & ~m) | ((value & ((1 << width) - 1)) << start)
    return v.to_bytes(len(block), "little")


def safe_request(runner, call):
    """A child that dies MID-WRITE leaves a truncated response line, and the
    shared tools/agxtest/persistrun.py parser raises on it (`OUT 0 ` splits into
    two tokens, not three). A crash there would cost the whole run, so the
    exception is converted into the outcome it actually is -- a wedge -- and the
    child is respawned. The shared tool is NOT modified: other experiments are
    running against it."""
    try:
        return call()
    except Exception as e:                                     # noqa: BLE001
        tb = traceback.format_exc().strip().replace("\n", " | ")[-400:]
        try:
            runner._kill()
            runner._start()
        except Exception:                                      # noqa: BLE001
            pass
        return {"status": "RUNNER_EXCEPTION", "outs": {}, "gputime_ns": None,
                "error": "runner raised: %s :: %s" % (str(e)[:120], tb),
                "restarted": True}


def splice(src, dst, off, block):
    with open(src, "rb") as f:
        b = bytearray(f.read())
    b[off:off + len(block)] = block
    with open(dst, "wb") as f:
        f.write(bytes(b))


# ----------------------------------------------------------------- build ----

def build_archive(arm, workdir):
    out = os.path.join(workdir, arm["arm"] + ".bin")
    if arm["stage"] == "compute":
        r = sh([SHDUMP2, "-o", out, "-f", arm["func"], "--no-fast-math",
                os.path.join(EXP, arm["kernel"])])
    else:
        r = sh([SHDUMP2, "-o", out, "--render", "--vertex", arm["vs"],
                "--fragment", arm["fs"], "--color-format", str(COLOR_FORMAT),
                "--nrt", str(arm["nrt"]), "--samples", str(arm["samples"]),
                "--no-fast-math", os.path.join(EXP, arm["kernel"])])
    if r.returncode != 0:
        raise RuntimeError("build failed for %s: %s" % (arm["arm"], r.stderr[-800:]))
    return out, r.stderr


# --------------------------------------------------------- anchor resolve ----

def tokenize(hexstr):
    """(records, leftover) from the PINNED tokenizer, or (None, reason)."""
    try:
        recs, leftover = ISA.disassemble(bytes.fromhex(hexstr))
        return recs, leftover.hex()
    except Exception as e:                                     # noqa: BLE001
        return None, "tokenize_error: %s" % e


def resolve_get_sr(hexstr, anchor_sr):
    """Byte offset (within _agc.main) of the get_sr whose sr_sel == anchor_sr.

    Path A: a clean full tokenization by the pinned tokenizer (authoritative).
    Path B: if tokenization is not clean, an even-offset scan requiring
            (byte0 & 7) == 4, byte1 == anchor_sr AND a successful decode_one to
            mnemonic get_sr, with EXACTLY ONE match. Ambiguity -> no anchor.
    """
    b = bytes.fromhex(hexstr)
    recs, leftover = tokenize(hexstr)
    hits = []
    if recs is not None and leftover == "":
        off = 0
        for r in recs:
            if r["mnemonic"] == "get_sr" and r["fields"].get("sr_sel") == anchor_sr:
                hits.append(off)
            off += r["length"]
        if len(hits) >= 1:
            return hits[0], "tokenized", hits, leftover
    for off in range(0, len(b) - 3, 2):
        if (b[off] & 7) == 4 and b[off + 1] == anchor_sr:
            try:
                rec, ln = ISA.decode_one(b, off)
            except Exception:                                  # noqa: BLE001
                continue
            if rec["mnemonic"] == "get_sr":
                hits.append(off)
    hits = sorted(set(hits))
    if len(hits) == 1:
        return hits[0], "scan", hits, leftover
    return None, ("scan_ambiguous" if hits else "scan_absent"), hits, leftover


def resolve_pattern(hexstr, patterns, expect_mnems):
    """Byte offset of the first anchor whose bytes match one of `patterns` AND
    whose pinned decode gives one of `expect_mnems`. Returns (off, mnemonic)."""
    for pat in patterns:
        i = hexstr.find(pat)
        while i >= 0:
            if i % 2 == 0:
                off = i // 2
                try:
                    rec, _ = ISA.decode_one(bytes.fromhex(hexstr), off)
                except Exception:                              # noqa: BLE001
                    rec = None
                if rec and rec["mnemonic"] in expect_mnems:
                    return off, rec["mnemonic"], pat
            i = hexstr.find(pat, i + 1)
    return None, None, None


# --------------------------------------------------------------- oracles ----

TOL = 1e-5


def same_pixels(a, b, exact=True):
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        for x, y in zip(ra, rb):
            if exact:
                if f32(x) != f32(y):
                    return False
            elif abs(x - y) > TOL * max(1.0, abs(y)):
                return False
    return True


def sr_pixels_from_values(vals, tri, W, H, centre_c):
    """Expected .r channel for a per-corner (len 3) or per-pixel (len W*H) SR."""
    if len(vals) == 3:
        out = []
        for py in range(H):
            for px in range(W):
                l = SP.bary(tri, px, py, W, H)
                out.append(sum(l[i] * float(vals[i]) for i in range(3)))
        return out
    return [float(v) + centre_c for v in vals]


# ------------------------------------------------------------------ main ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-root", default="raw")
    ap.add_argument("--arms", default="")
    ap.add_argument("--fields", default="")
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--hang-tolerant", action="store_true",
                    help="rule 3c MAPPING pass only; forbidden in a gated run id")
    args = ap.parse_args()

    if args.hang_tolerant and not args.run_id.startswith("MAPPING_"):
        sys.exit("--hang-tolerant requires a run id starting with MAPPING_ (rule 3c)")

    outdir = os.path.join(EXP, args.out_root, args.run_id)
    if os.path.exists(outdir):
        sys.exit("run id already exists: %s (never reuse a run id)" % outdir)
    os.makedirs(outdir)
    workdir = os.path.join(EXP, "work", "arch_" + args.run_id)
    os.makedirs(workdir, exist_ok=True)

    sweep = open(os.path.join(outdir, "sweep.jsonl"), "w")
    counter = {"n": 0}

    def emit(rec):
        rec.setdefault("t", round(time.time(), 3))
        rec.setdefault("idx", counter["n"])
        counter["n"] += 1
        sweep.write(json.dumps(rec, sort_keys=True) + "\n")
        sweep.flush()
        os.fsync(sweep.fileno())

    # ---------------------------------------------------------- environment --
    env = {
        "run_id": args.run_id,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pinned": {k: v[1] for k, v in PINNED.items()},
        "pinned_db_instructions": len(ISA.DB),
        "host": sh(["hostname"]).stdout.strip(),
        "uname": sh(["uname", "-a"]).stdout.strip(),
        "sw_vers": sh(["sw_vers"]).stdout.strip(),
        "xcrun": sh(["xcrun", "--version"]).stdout.strip(),
        "python": sys.version.split()[0],
        "color_format": COLOR_FORMAT,
        "argv": sys.argv,
    }
    json.dump(env, open(os.path.join(outdir, "00_env.json"), "w"), indent=1, sort_keys=True)

    want = set(a for a in args.arms.split(",") if a)
    wantf = set(f for f in args.fields.split(",") if f)
    resolution = {}
    hangs_total = 0

    for arm in SP.ARMS:
        if want and arm["arm"] not in want:
            continue
        t_arm = time.time()
        try:
            archive, buildlog = build_archive(arm, workdir)
        except Exception as e:                                 # noqa: BLE001
            emit({"kind": "arm_error", "arm": arm["arm"], "error": str(e)[:600],
                  "outcome": "undecodable"})
            resolution[arm["arm"]] = {"status": "BUILD_FAILED", "error": str(e)[:600]}
            continue

        stage = arm["stage"] if arm["stage"] != "compute" else None
        hx = extract_hex(archive, stage)
        base = locate(archive, stage)

        if arm["instr"] == "get_sr" or arm.get("anchor_sr") is not None:
            off, how, hits, leftover = resolve_get_sr(hx, arm["anchor_sr"])
            mnem = "get_sr"
        else:
            off, mnem, pat = resolve_pattern(hx, arm["pattern"],
                                             ("tile_read", "tile_read_mrt"))
            how, hits, leftover = ("pattern:%s" % pat if off is not None else "absent"), \
                                  ([off] if off is not None else []), tokenize(hx)[1]

        if off is None:
            res = {"status": "NOT_ATTEMPTED", "why": how, "hits": hits,
                   "program_len": len(hx) // 2}
            resolution[arm["arm"]] = res
            emit({"kind": "arm_not_attempted", "arm": arm["arm"], **res})
            continue

        desc = next(d for d in ISA.DB if d["mnemonic"] == mnem)
        ilen = desc["length"]
        blk0 = bytes.fromhex(hx)[off:off + ilen]
        abs_off = base + off
        real_fields = {f["name"] for f in desc["fields"]}
        ruled = [f for f in arm["fields"] if f in real_fields]
        dropped = [f for f in arm["fields"] if f not in real_fields]
        foreign = {k: v for k, v in arm.get("foreign", {}).items() if k in real_fields}

        resolution[arm["arm"]] = {
            "status": "RESOLVED", "instr": mnem, "how": how, "hits": hits,
            "main_offset": off, "abs_off": abs_off, "instr_hex": blk0.hex(),
            "instr_len": ilen, "program_len": len(hx) // 2,
            "tokenize_leftover": leftover,
            "fields_ruled": ruled, "fields_dropped_not_in_descriptor": dropped,
            "fields_foreign": foreign,
            "fields_not_swept": arm.get("not_swept", {}),
            "baseline_field_values": {f["name"]: get_bits(blk0, f["start"], f["width"])
                                      for f in desc["fields"]},
        }
        emit({"kind": "arm_meta", "arm": arm["arm"], "instr": mnem, "stage": arm["stage"],
              "carrier": {k: arm.get(k) for k in
                          ("kernel", "func", "vs", "fs", "nrt", "samples", "W", "H",
                           "grid", "tg", "draw", "basevertex", "baseinstance", "instances")},
              "observable": arm["observable"], "never_spliced": arm["never_spliced"],
              **resolution[arm["arm"]], "program_hex": hx})

        spdir = os.path.join(workdir, arm["arm"] + "_sp")
        os.makedirs(spdir, exist_ok=True)
        spseq = [0]

        def next_splice_path():
            spseq[0] += 1
            q = os.path.join(spdir, "sp%06d.bin" % spseq[0])
            old = os.path.join(spdir, "sp%06d.bin" % (spseq[0] - 64))
            if os.path.exists(old):
                try:
                    os.unlink(old)
                except OSError:
                    pass
            return q

        # --------------------------------------------------- runner + case --
        if arm["stage"] == "compute":
            poison = os.path.join(workdir, "poison.bin")
            with open(poison, "wb") as f:
                f.write(struct.pack("<%dI" % SP.CGRID, *([SP.POISON_U32] * SP.CGRID)))
            runner = SafePersistRunner(source=os.path.join(EXP, arm["kernel"]),
                                   function=arm["func"], fast_math=False,
                                   agxrun_persist=AGXPERSIST)
            nb = SP.CGRID * 4

            def raw_case(arcpath):
                r = safe_request(
                    runner, lambda: runner.request(
                        archive=arcpath, grid=arm["grid"], tg=arm["tg"],
                        ins={0: poison, 4: poison}, outs={0: nb, 4: nb},
                        timeout=REQ_TIMEOUT))
                if r["status"] != "OK" or 0 not in r["outs"]:
                    return None, r
                sent = list(struct.unpack("<%dI" % SP.CGRID, r["outs"][4]))
                if any(s != SP.SENTINEL_U32 for s in sent[:arm["grid"]]):
                    r = dict(r)
                    r["status"] = "SENTINEL_MISS"
                    r["error"] = "integrity sentinel not written: dispatch did not execute"
                    return None, r
                vals = list(struct.unpack("<%dI" % SP.CGRID, r["outs"][0]))
                # DEF-0169-2 (the DSTORE finding, 2026-08-30): a device_store
                # through an unbound slot is SILENTLY DROPPED -- no fault, no
                # diagnostic. Absence of a fault therefore proves nothing about
                # whether the store landed. The poison is what proves it: the
                # sentinel says the dispatch RAN, so out[] still holding
                # 0xDEADBEEF means our store did NOT land, which is a different
                # fact from "the store wrote 0".
                if all(v == SP.POISON_U32 for v in vals[:arm["grid"]]):
                    r = dict(r)
                    r["status"] = "OUT_NOT_WRITTEN"
                    r["error"] = ("dispatch ran (sentinel written) but the "
                                  "read-back is still 0xDEADBEEF poison")
                    return None, r
                return {"words": vals}, r

            def restart():
                runner._kill(); runner._start()
        else:
            runner = SafeRenderRunner(os.path.join(EXP, arm["kernel"]), exe=RENDERSWEEP)
            clears = [SP.DST0, SP.DST1, SP.DST2][:arm["nrt"]]

            def raw_case(arcpath, src=None, clear=None):
                req = {"id": "c", "archive": arcpath, "vs": arm["vs"], "fs": arm["fs"],
                       "w": arm["W"], "h": arm["H"], "nrt": arm["nrt"],
                       "samples": arm["samples"], "clear": clear or clears,
                       "fbuf": src or SP.SRC, "vbuf": SP.VP}
                if arm.get("draw"):
                    req["draw"] = arm["draw"]
                    req["basevertex"] = arm["basevertex"]
                    req["baseinstance"] = arm["baseinstance"]
                    req["instances"] = arm["instances"]
                r = safe_request(runner, lambda: runner.request(req, timeout=REQ_TIMEOUT))
                if r.get("status") != "OK":
                    return None, r
                npx = arm["W"] * arm["H"]
                cl = req["clear"]
                untouched = all(f32v(px) == f32v(cl[i // npx])
                                for i, px in enumerate(r["pixels"]))
                if untouched:
                    r = dict(r)
                    r["status"] = "SENTINEL_MISS"
                    r["error"] = "every pixel still holds the clear colour: nothing was drawn"
                    return None, r
                return {"pixels": r["pixels"]}, r

            def restart():
                runner.restart()

        recovery = {"restarts": 0, "retries": 0, "collateral": 0, "unrecovered": 0}
        OWN_FAULT = "Caused GPU Hang Error"
        COLLATERAL = ("Discarded (victim", "Ignored (for causing prior")

        def is_collateral(r):
            e = str(r.get("error", ""))
            return any(c in e for c in COLLATERAL)

        def healthy():
            g, _ = raw_case(archive)
            return g is not None

        def wait_for_health():
            delay, waited, n = 0.2, 0.0, 0
            while waited < 40.0:
                restart(); recovery["restarts"] += 1; n += 1
                time.sleep(delay); waited += delay
                if healthy():
                    return n
                delay = min(delay * 2.0, 5.0)
            return -1

        def run_case(arcpath, **kw):
            """EXP-0147's measured recovery order: retry IN PLACE first (a
            sibling's reset makes the very next submission a victim, and a fresh
            child's first request just becomes the next victim), restart only if
            that fails, and NEVER record collateral as a fault."""
            n = 0
            for attempt in range(5):
                g, r = raw_case(arcpath, **kw)
                if g is not None:
                    return g, r, n, attempt + 1
                recovery["retries"] += 1
                if r.get("status") == "SENTINEL_MISS":
                    g2, r2 = raw_case(arcpath, **kw)
                    if g2 is not None:
                        return g2, r2, n, attempt + 2
                    if healthy():
                        return None, r2, n, attempt + 2
                    r = r2
                if is_collateral(r):
                    recovery["collateral"] += 1
                time.sleep(0.05 + 0.1 * attempt)
            n = wait_for_health()
            if n < 0:
                recovery["unrecovered"] += 1
                return None, r, 99, 6
            g2, r2 = raw_case(arcpath, **kw)
            return g2, r2, n, 7

        # ------------------------------------------------------- baseline ---
        base_obs, base_raw, _, _ = run_case(archive)
        emit({"kind": "baseline", "arm": arm["arm"], "instr": mnem,
              "bytes": blk0.hex(), "observed": base_obs,
              "status": base_raw.get("status"), "outcome":
              "ok" if base_obs is not None else "fault"})
        if base_obs is None:
            emit({"kind": "arm_error", "arm": arm["arm"],
                  "error": "baseline did not run: %s" % base_raw.get("error", "")[:300],
                  "outcome": "fault"})
            continue

        # ------------------------------------------------- calibration ------
        calib = {}
        if arm["oracle"] == "sr_compute":
            # threadExecutionWidth is a DEVICE CONFIGURATION value printed by
            # shdump2 for compute pipelines. It parameterises the oracle; it is
            # not an observation of the field under test.
            w = 32
            for ln in buildlog.splitlines():
                if "threadExecutionWidth" in ln:
                    try:
                        w = int(ln.split("threadExecutionWidth =")[1].split(",")[0])
                    except Exception:                          # noqa: BLE001
                        pass
            calib["exec_width"] = w
            exp = SP.sr_oracle_compute(arm["anchor_sr"], w)
            calib["baseline_matches_documented_sr"] = (
                exp is not None and
                base_obs["words"][:arm["grid"]] ==
                [v + SP.SR_BIAS for v in exp][:arm["grid"]])
        elif arm["oracle"] == "sr_frag":
            # C is CONFIRMED against the baseline, never fitted per case: the
            # baseline selector is the DOCUMENTED pixel-X register, so
            # (.r - px) must be one constant across all W*H pixels.
            r = [p[0] for p in base_obs["pixels"]]
            cs = [f32(r[py * arm["W"] + px] - px)
                  for py in range(arm["H"]) for px in range(arm["W"])]
            calib["centre_offsets"] = cs
            calib["affine_model_holds"] = len(set(cs)) == 1
            calib["centre_c"] = cs[0] if calib["affine_model_holds"] else None
            calib["preregistered_c"] = SP.FRAG_CENTRE_C
            calib["preregistered_c_confirmed"] = (
                calib["affine_model_holds"] and f32(cs[0]) == f32(SP.FRAG_CENTRE_C))
        elif arm["oracle"] == "sr_vertex":
            exp = SP.sr_oracle_vertex(arm["anchor_sr"])
            pred = sr_pixels_from_values(exp, SP.TRI_SR, arm["W"], arm["H"], 0.0)
            got = [p[0] for p in base_obs["pixels"]]
            calib["baseline_matches_documented_sr"] = all(
                abs(a - b) <= TOL * max(1.0, abs(b)) for a, b in zip(got, pred))
            calib["predicted"] = pred
        emit({"kind": "calibration", "arm": arm["arm"], **calib})

        centre_c = calib.get("centre_c", SP.FRAG_CENTRE_C)

        # --------------------------------------------- semantic oracle -------
        def sem_oracle(field, value):
            """Host-computed expected observation, or None where the pinned db
            documents no meaning for this (stage, selector)."""
            if field != "sr_sel":
                return None
            if arm["oracle"] == "sr_compute":
                exp = SP.sr_oracle_compute(value, calib.get("exec_width", 32))
                if exp is None:
                    return None
                return {"words": [v + SP.SR_BIAS for v in exp]}
            if arm["oracle"] == "sr_frag":
                exp = SP.sr_oracle_frag(value, arm["W"], arm["H"])
                if exp is None or not calib.get("affine_model_holds"):
                    return None
                return {"r": [f32(v + centre_c) for v in exp]}
            if arm["oracle"] == "sr_vertex":
                exp = SP.sr_oracle_vertex(value)
                if exp is None:
                    return None
                return {"r": sr_pixels_from_values(exp, SP.TRI_SR, arm["W"], arm["H"], 0.0)}
            return None

        # The GOOD oracle and one ZERO-oracle CANDIDATE PER ATTACHMENT. Which
        # attachment the resolved `tile_read_mrt` anchor feeds is not assumed:
        # every candidate is host-computed up front and the `class` records
        # which one matched, so "attachment j read as zero" is itself evidence
        # about rt_index routing rather than a fitted assumption.
        GOOD, ZEROS = SP.tile_oracles(arm)

        def classify(field, value, obs, raw, attempts):
            """Outcome from the FROZEN 6-value enum, plus an orthogonal `class`
            for cases with no semantic oracle (which is the informative outcome
            for an undocumented selector, not a defect)."""
            if raw.get("status") == "HANG":
                return "hang", None, False, None
            if obs is None:
                st = raw.get("status")
                if st == "SENTINEL_MISS":
                    return ("no_dispatch" if arm["stage"] == "compute" else "no_draw",
                            None, False, None)
                if st == "OUT_NOT_WRITTEN":
                    return "not_written", None, False, "POISON_INTACT"
                if is_collateral(raw):
                    return "invalid_run", None, False, None
                return "fault", None, False, None
            moved = not obs_equal(obs, base_obs)
            sem = sem_oracle(field, value)
            sem_match = None
            if sem is not None:
                sem_match = sem_equal(obs, sem)
            if arm["oracle"] in ("tile", "tile2", "mrt", "mrt3"):
                if same_pixels(obs["pixels"], GOOD):
                    return "ok", GOOD, True, "CORRECT"
                for lbl, z in ZEROS:
                    if same_pixels(obs["pixels"], z):
                        return "silent_zero", z, False, "SILENT_ZERO:" + lbl
                return "wrong_value", GOOD, False, ("WRONG_MOVED" if moved else "WRONG_NOMOVE")
            if sem_match is True:
                return "ok", sem, True, "SEM_MATCH"
            if is_zeroish(obs):
                return "silent_zero", sem, False, "ZERO"
            return "wrong_value", sem, False, ("MOVED" if moved else "NO_MOVE")

        def obs_equal(a, b):
            if a is None or b is None:
                return False
            if "words" in a:
                return a["words"] == b["words"]
            return same_pixels(a["pixels"], b["pixels"])

        def sem_equal(obs, sem):
            if "words" in sem:
                return obs["words"][:arm["grid"]] == sem["words"][:arm["grid"]]
            got = [p[0] for p in obs["pixels"]]
            return all(abs(a - b) <= TOL * max(1.0, abs(b))
                       for a, b in zip(got, sem["r"]))

        def sentinel_channels(obs):
            """Status of the integrity channels the instruction under test
            cannot name. None when the case did not produce an observation."""
            if obs is None:
                return None
            if "words" in obs:
                # the compute sentinel is checked inside raw_case; reaching here
                # means it was written.
                return {"compute_sentinel": True}
            px = obs["pixels"]
            n = arm["W"] * arm["H"]
            out = {}
            if arm["oracle"] == "sr_frag":
                ys = [py for py in range(arm["H"]) for _ in range(arm["W"])]
                out["g_is_pixel_y"] = all(
                    abs(px[i][1] - (ys[i] + centre_c)) <= TOL * max(1.0, ys[i] + 1)
                    for i in range(n))
                out["a_is_uniform"] = all(f32(p[3]) == f32(SP.SRC[1]) for p in px[:n])
            elif arm["oracle"] == "sr_vertex":
                out["a_is_uniform"] = all(f32(p[3]) == f32(SP.SRC[1]) for p in px[:n])
            elif arm["oracle"] in ("tile2", "mrt", "mrt3"):
                # every attachment OTHER than the one that moved must still be
                # byte-exactly correct.
                good = GOOD
                nat = len(good) // n
                out["other_attachments_correct"] = [
                    all(f32(px[j * n + i][k]) == f32(good[j * n + i][k])
                        for i in range(n) for k in range(4))
                    for j in range(nat)]
            return out

        def is_zeroish(obs):
            if "words" in obs:
                return all(w == SP.SR_BIAS for w in obs["words"][:arm["grid"]])
            return all(abs(p[0]) <= 1e-9 for p in obs["pixels"])

        # ------------------------------------------------------- record -----
        arm_hangs = [0]
        hang_values = {}

        def tokenize_anchor(block):
            """EXP-0169 lesson (falu2_uni.uni_mode): a swept byte can change
            WHICH INSTRUCTION the bytes tokenize as, and then the "movement" is
            the sweep encoding something else entirely -- that field was
            withdrawn after being recorded LIVE at full range. So record the
            decoded mnemonic and length of the spliced anchor on EVERY case.
            Padding with the program's real following bytes keeps the length
            rule honest for descriptors whose length depends on later bytes."""
            ctx = bytes.fromhex(hx)
            buf = bytearray(ctx)
            buf[off:off + len(block)] = block
            try:
                rec, ln = ISA.decode_one(bytes(buf), off)
                return rec["mnemonic"], ln
            except Exception as e:                             # noqa: BLE001
                return "UNDECODABLE:%s" % str(e)[:60], None

        def record(kind, field, value, block, note="", foreign_flag=False,
                   start=None, width=None, rng=None, ndisp=None, ndistinct=None):
            nonlocal hangs_total
            tok_instr, tok_len = tokenize_anchor(block)
            sp = next_splice_path()
            splice(archive, sp, abs_off, block)
            obs, raw, nres, attempts = run_case(sp)
            outcome, orc, ok, cls = classify(field, value, obs, raw, attempts)
            rec = {"kind": kind, "arm": arm["arm"], "carrier": arm["arm"],
                   "stage": arm["stage"], "instr": mnem, "field": field,
                   "value": value, "bytes": block.hex(),
                   "observed": obs, "oracle": orc, "match": ok,
                   "outcome": outcome, "class": cls,
                   "tok_instr": tok_instr, "tok_len": tok_len,
                   "tok_same_instr": (tok_instr == mnem and tok_len == ilen),
                   "sent_ok": sentinel_channels(obs),
                   "moved": (None if obs is None else not obs_equal(obs, base_obs)),
                   "victim": (str(raw.get("error", ""))[:200]
                              if outcome not in ("ok", "silent_zero", "wrong_value") else ""),
                   "own_fault": OWN_FAULT in str(raw.get("error", "")),
                   "sentinel_bad": raw.get("status") == "SENTINEL_MISS",
                   "attempts": attempts, "restarts": nres,
                   "foreign": foreign_flag,
                   "start": start, "width": width, "encodable_range": rng,
                   "values_dispatched": ndisp, "distinct_bytes": ndistinct,
                   "note": note}
            emit(rec)
            if outcome == "hang":
                arm_hangs[0] += 1
                hangs_total += 1
                hang_values.setdefault(field, []).append(value)
            return rec

        # -------------------------------------------------- ladder etc. -----
        fieldsdesc = {f["name"]: f for f in desc["fields"]}
        for (nm, fname, alt, why) in arm["ladder"]:
            f = fieldsdesc.get(fname)
            if f is None:
                emit({"kind": "ladder", "arm": arm["arm"], "step": nm,
                      "field": fname, "outcome": "undecodable",
                      "note": "field absent from the resolved descriptor"})
                continue
            cur = get_bits(blk0, f["start"], f["width"])
            v = alt if alt is not None and alt != cur else (cur + 1) % (1 << f["width"])
            record("ladder", "__ladder_" + nm, v,
                   set_bits(blk0, f["start"], f["width"], v),
                   note=why)

        pf, pv, pwhy = arm["power_probe"]
        f = fieldsdesc.get(pf)
        if f is not None:
            record("power_probe", "__power_" + pf, pv,
                   set_bits(blk0, f["start"], f["width"], pv), note=pwhy)

        sf, sv, swhy = arm["sensitivity"]
        if sf == "byte0_bit2":
            nb = bytearray(blk0); nb[0] &= ~0x04
            record("sensitivity", "__sens_byte0_bit2", 0, bytes(nb), note=swhy)
        elif sf == "byte1":
            nb = bytearray(blk0); nb[1] = sv
            record("sensitivity", "__sens_byte1", sv, bytes(nb), note=swhy)

        # ------------------------------------------------------- sweeps -----
        hp = SP.hang_policy()
        allf = [(x, False) for x in ruled] + \
               [(x, True) for x in sorted(foreign.keys())]
        ndone = 0
        for fname, is_foreign in allf:
            if wantf and fname not in wantf:
                continue
            f = fieldsdesc[fname]
            mode, vals, rng, start, width = SP.field_values(mnem, fname)
            if width > 8:
                # per constituent BYTE dense, then the structured whole-field set
                nbytes = (width + 7) // 8
                plan = []
                for k in range(nbytes):
                    for v in range(256):
                        cur = get_bits(blk0, start, width)
                        wv = (cur & ~(0xFF << (8 * k))) | (v << (8 * k))
                        plan.append((wv, "byte%d=%d" % (k, v)))
                plan += [(v, "structured") for v in vals]
            else:
                plan = [(v, mode) for v in vals]
            ndisp = len(plan)
            nbytes_distinct = len({set_bits(blk0, start, width, v).hex()
                                   for (v, _tag) in plan})
            for (v, tag) in plan:
                if args.max_cases and ndone >= args.max_cases:
                    break
                record("case", fname, v, set_bits(blk0, start, width, v),
                       note=tag, foreign_flag=is_foreign,
                       start=start, width=width, rng=rng, ndisp=ndisp,
                       ndistinct=nbytes_distinct)
                ndone += 1
                # RULE 3(c), applied at DESIGN time rather than by a budget.
                # A per-field hang budget cannot characterise a CONTIGUOUS
                # hazard; it guarantees the region is never mapped (a budget of
                # 2 discovers exactly two bad values per run). So there is NO
                # per-field abort here: every planned value of every field is
                # dispatched regardless of outcome, which is how EXP-0169's
                # DSTORE arm mapped `device_store.index_reg` ((v & 0x60) ==
                # 0x60) and `extmode` (v >= 0xFC) exactly, in the gated run,
                # with no mapping pass. The only stop is a GLOBAL circuit
                # breaker against a runaway.
                if hangs_total >= hp["global_circuit_breaker"]:
                    emit({"kind": "run_stopped", "arm": arm["arm"], "field": fname,
                          "reason": "global circuit breaker %d hangs"
                                    % hp["global_circuit_breaker"],
                          "hang_values": hang_values,
                          "contiguous": _contiguous(hang_values)})
                    break
            if hangs_total >= hp["global_circuit_breaker"]:
                break

        emit({"kind": "arm_done", "arm": arm["arm"], "seconds": round(time.time() - t_arm, 1),
              "recovery": recovery, "hangs": arm_hangs[0],
              "hang_values": hang_values, "contiguous": _contiguous(hang_values)})
        with open(os.path.join(EXP, "PROGRESS.md"), "a") as pf2:
            pf2.write("- %s run=%s arm=%s done in %.1fs (hangs=%d)\n" % (
                time.strftime("%Y-%m-%dT%H:%M:%S"), args.run_id, arm["arm"],
                time.time() - t_arm, arm_hangs[0]))
        try:
            runner.close()
        except Exception:                                      # noqa: BLE001
            try:
                runner._kill()
            except Exception:                                  # noqa: BLE001
                pass

    json.dump(resolution, open(os.path.join(outdir, "00_arm_resolution.json"), "w"),
              indent=1, sort_keys=True)
    json.dump({"records": counter["n"], "hangs": hangs_total},
              open(os.path.join(outdir, "02_summary.json"), "w"), indent=1)
    sweep.close()
    print("run %s: %d records, %d hangs" % (args.run_id, counter["n"], hangs_total))


def _contiguous(hang_values):
    """Rule 3c trigger: are >=2 hangs on ADJACENT values of one field?"""
    out = {}
    for k, vs in hang_values.items():
        s = sorted(set(vs))
        out[k] = any(b - a == 1 for a, b in zip(s, s[1:]))
    return out


if __name__ == "__main__":
    main()
