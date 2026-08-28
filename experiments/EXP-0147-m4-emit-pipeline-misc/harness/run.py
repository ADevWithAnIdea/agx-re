#!/usr/bin/env python3
"""EXP-0147 capture driver -- field sweeps over the pipeline-plumbing ops.

Per FIELD-SWEEP-PROTOCOL: one JSON object per case appended to
raw/<run_id>/sweep.jsonl with an immediate flush+fsync, so a kill or a GPU
wedge costs at most one case. Refuses to reuse an existing run id.

  python3 harness/run.py --run-id m4_YYYYMMDD_runNN --out-root raw
  python3 harness/run.py --run-id smoke --out-root work/smoke --arms matrix_mac
"""
import argparse, json, os, shutil, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools", "agxtest"))
import sweepplan as SP                                   # noqa: E402
from rsdrv import RenderRunner                           # noqa: E402
from persistrun import PersistRunner                     # noqa: E402

BIN = os.path.join(EXP, "work", "bin")                   # built executables
SHDUMP  = os.path.join(BIN, "shdump")                    # tools/shdump (unmodified)
SHDUMP2 = os.path.join(BIN, "shdump2")                   # harness/shdump2.m (MRT/MSAA)
RENDERSWEEP = os.path.join(BIN, "rendersweep")           # harness/rendersweep.m
AGXPERSIST  = os.path.join(BIN, "agxrun_persist")        # tools/agxtest (unmodified)
AGXPARSE = os.path.join(REPO, "tools", "shdump", "agxparse.py")

REQ_TIMEOUT = 10.0
BUILD_TIMEOUT = 60


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def f32v(v):
    return [f32(x) for x in v]


def sh(args, timeout=BUILD_TIMEOUT):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def locate(archive, stage):
    a = [sys.executable, AGXPARSE, archive, "--locate", "_agc.main"]
    if stage: a[3:3] = ["--stage", stage]
    return int(sh(a).stdout.split()[0])


def extract_hex(archive, stage):
    a = [sys.executable, AGXPARSE, archive, "--extract-hex"]
    if stage: a[3:3] = ["--stage", stage]
    return sh(a).stdout.strip()


def build_archive(arm, workdir):
    out = os.path.join(workdir, arm["arm"] + ".bin")
    if arm["stage"] == "compute":
        r = sh([SHDUMP, "-o", out, "-f", arm["func"], "--no-fast-math",
                os.path.join(EXP, arm["kernel"])])
    else:
        r = sh([SHDUMP2, "-o", out, "--render", "--vertex", arm["vs"],
                "--fragment", arm["fs"], "--color-format", "125",
                "--nrt", str(arm["nrt"]), "--samples", str(arm["samples"]),
                "--no-fast-math", os.path.join(EXP, arm["kernel"])])
    if r.returncode != 0:
        raise RuntimeError(f"build failed for {arm['arm']}: {r.stderr[-500:]}")
    return out


# ------------------------------------------------------------- oracles ------

# Oracles built from an EXACT float32 formula (tile/mrt/rog) are compared
# bit-exactly; oracles that go through hardware barycentric interpolation
# (vary_*/samp) are compared with a small relative tolerance because the host
# cannot reproduce the interpolator's rounding bit-for-bit.
EXACT_ORACLES = {"tile", "mrt", "rog"}
TOL = 1e-5


def oracle_for(arm, **kw):
    o = arm["oracle"]
    W, H = arm.get("W", 1), arm.get("H", 1)
    d0 = kw.get("dst0", SP.DST0)
    if o == "tile":      return {"pixels": [f32v(p) for p in SP.o_tile(d0, kw.get("src", SP.SRC), W, H)]}
    if o == "mrt":       return {"pixels": [f32v(p) for p in SP.o_mrt(d0, SP.DST1, kw.get("src", SP.SRC), W, H)]}
    if o == "vary_tern": return {"pixels": [f32v(p) for p in SP.o_vary_tern(W=W, H=H)]}
    if o == "vary_arr":  return {"pixels": [f32v(p) for p in SP.o_vary_arr(vp=kw.get("vp", SP.VP), W=W, H=H)]}
    if o == "samp":      return {"pixels": [f32v(p) for p in SP.o_samp(kw.get("src", SP.SRC), W, H)]}
    if o == "rog":
        d = SP.o_rog(d0, kw.get("src", SP.SRC), W, H, arm["instances"])
        return {"pixels": [f32v(p) for p in d["pixels"]], "tex": f32v(d["tex"])}
    return None


def same(arm, obs, orc):
    if obs is None or orc is None: return False
    if set(obs.keys()) != set(orc.keys()): return False
    exact = arm["oracle"] in EXACT_ORACLES
    for k in orc:
        a, b = obs[k], orc[k]
        if isinstance(b[0], list):
            if len(a) != len(b): return False
            pairs = [(x, y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)]
        else:
            pairs = list(zip(a, b))
        for x, y in pairs:
            if exact:
                if f32(x) != f32(y): return False
            elif abs(x - y) > TOL * max(1.0, abs(y)):
                return False
    return True


def zero_oracle_for(arm, **kw):
    """What the read-back looks like if the target instruction contributes 0."""
    W, H = arm.get("W", 1), arm.get("H", 1)
    o = arm["oracle"]
    if o == "tile": return {"pixels": [f32v(p) for p in SP.o_tile_zero(kw.get("dst0", SP.DST0), kw.get("src", SP.SRC), W, H)]}
    if o == "mrt":  return {"pixels": [f32v(p) for p in SP.o_mrt_rt1zero(kw.get("dst0", SP.DST0), SP.DST1, kw.get("src", SP.SRC), W, H)]}
    return None


COMPUTE_IN = {}


def compute_inputs(workdir):
    if COMPUTE_IN: return COMPUTE_IN
    A = [(i * 8 + j + 1) * 0.5 for i in range(8) for j in range(8)]
    B = [((i * 8 + j) % 7 - 3) * 1.25 for i in range(8) for j in range(8)]
    C = [(i * 8 + j) * 0.25 - 8.0 for i in range(8) for j in range(8)]
    lin32 = [float(i % 13) - 4.0 for i in range(64)]
    lin256 = [float(i) * 1.5 - 7.0 for i in range(256)]
    for name, vals in (("mm_a", A), ("mm_b", B), ("mm_c", C),
                       ("lin32", lin32), ("lin256", lin256)):
        p = os.path.join(workdir, name + ".bin")
        with open(p, "wb") as f: f.write(struct.pack("<%df" % len(vals), *vals))
        COMPUTE_IN[name] = p
    p = os.path.join(workdir, "ctr.bin")
    with open(p, "wb") as f: f.write(struct.pack("<I", 0))
    COMPUTE_IN["ctr"] = p
    # Poison-prefilled OUTPUT buffers. agxrun_persist reuses a buffer supplied
    # as an input when the same index is also requested as an output, so
    # handing index 0 a poison file gives us a pre-filled output for free.
    for name, n in (("poison64", 64), ("poison32", 32), ("poison256", 256)):
        q = os.path.join(workdir, name + ".bin")
        with open(q, "wb") as f: f.write(struct.pack("<%df" % n, *([SP.POISON_F32] * n)))
        COMPUTE_IN[name] = q
    for name, n in (("sent64", 64), ("sent32", 32), ("sent256", 256)):
        q = os.path.join(workdir, name + ".bin")
        with open(q, "wb") as f: f.write(struct.pack("<%dI" % n, *([0xDEADBEEF] * n)))
        COMPUTE_IN[name] = q
    COMPUTE_IN["A"], COMPUTE_IN["B"], COMPUTE_IN["C"] = A, B, C
    COMPUTE_IN["lin32v"], COMPUTE_IN["lin256v"] = lin32, lin256
    return COMPUTE_IN


def compute_oracle(arm, ci):
    if arm["oracle"] == "mad":
        A, B, C = ci["A"], ci["B"], ci["C"]
        R = []
        for i in range(8):
            for j in range(8):
                s = 0.0
                for k in range(8): s = f32(s + f32(A[i * 8 + k] * B[k * 8 + j]))
                R.append(f32(s + C[i * 8 + j]))
        return {"out0": R}
    if arm["oracle"] == "tgrw":
        # must track kernels/pipe_compute.metal: scratch[(lid + 137) % tgsz]
        a = ci["lin256v"]
        return {"out0": [f32(a[(i + 137) % 256] + a[i]) for i in range(256)]}
    if arm["oracle"] == "atomic":
        # order-independent: the multiset of (out[tid] - 2*a[tid]) is {0..7} x4
        return {"ticket_multiset": sorted([i % 8 for i in range(32)])}
    return None


def sentinel_ok(sent_bytes, n):
    """The kernel writes SENTINEL_BASE+tid through a path independent of the
    instruction under test. If the buffer still holds the host poison, the
    dispatch did not execute and the measurement is invalid (EXP-0141)."""
    if sent_bytes is None or len(sent_bytes) < 4 * n: return False
    got = struct.unpack("<%dI" % n, sent_bytes[:4 * n])
    return all(g == (SP.SENTINEL_BASE + i) & 0xFFFFFFFF for i, g in enumerate(got))


def classify_compute(arm, ci, out_bytes):
    """Return (observed, match, outcome)."""
    if arm["oracle"] == "mad":
        got = list(struct.unpack("<64f", out_bytes))
        exp = compute_oracle(arm, ci)["out0"]
        if got == exp: return {"out0": got}, True, "ok"
        if all(g == 0.0 for g in got): return {"out0": got}, False, "silent_zero"
        return {"out0": got}, False, "wrong_value"
    if arm["oracle"] == "tgrw":
        got = list(struct.unpack("<256f", out_bytes))
        exp = compute_oracle(arm, ci)["out0"]
        if got == exp: return {"out0_head": got[:8], "out0_sha": sum(got)}, True, "ok"
        if all(g == 0.0 for g in got): return {"out0_head": got[:8]}, False, "silent_zero"
        return {"out0_head": got[:8], "n_wrong": sum(1 for g, e in zip(got, exp) if g != e)}, False, "wrong_value"
    if arm["oracle"] == "atomic":
        got = list(struct.unpack("<32f", out_bytes[:128]))
        a = ci["lin32v"]
        tickets = sorted(int(round(g - f32(a[i] * 2.0))) for i, g in enumerate(got))
        exp = compute_oracle(arm, ci)["ticket_multiset"]
        if tickets == exp: return {"tickets": tickets, "out0_head": got[:6]}, True, "ok"
        if all(g == 0.0 for g in got): return {"out0_head": got[:6]}, False, "silent_zero"
        return {"tickets": tickets, "out0_head": got[:6]}, False, "wrong_value"
    raise AssertionError(arm["oracle"])


# ----------------------------------------------------------- case emitters --

def field_cases(f):
    """(value, [(byte_index, new_byte_value_fn), ...]) -- description of the
    mutation for each swept value of field f. Byte fns take the original byte."""
    nb = f.get("nbytes")
    if nb:
        for bi in range(nb):
            for v in range(256):
                yield (f"byte{bi}=0x{v:02x}", [(f["byte"] + bi, (lambda v: (lambda o: v))(v))])
        for v in SP.wide_values(f["width"]):
            muts = [(f["byte"] + k, (lambda vv: (lambda o: vv))((v >> (8 * k)) & 0xFF))
                    for k in range(nb)]
            yield (f"whole=0x{v:0{nb*2}x}", muts)
        return
    w, sh_ = f["width"], f.get("shift", 0)
    mask = ((1 << w) - 1) << sh_
    for v in range(1 << w):
        yield (v, [(f["byte"], (lambda vv: (lambda o: (o & ~mask & 0xFF) | ((vv << sh_) & mask)))(v))])


def splice(src_archive, dst_archive, abs_off, muts):
    shutil.copyfile(src_archive, dst_archive)
    with open(dst_archive, "r+b") as fp:
        for bi, fn in muts:
            fp.seek(abs_off + bi); orig = fp.read(1)[0]
            fp.seek(abs_off + bi); fp.write(bytes([fn(orig) & 0xFF]))


# ------------------------------------------------------------------ main ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--arms", default="")
    args = ap.parse_args()

    run_dir = os.path.join(EXP, args.out_root, args.run_id) if not os.path.isabs(args.out_root) \
              else os.path.join(args.out_root, args.run_id)
    if os.path.exists(run_dir):
        print(f"REFUSING: run dir exists: {run_dir}", file=sys.stderr); sys.exit(1)
    os.makedirs(run_dir)
    workdir = os.path.join(EXP, "work", "build", args.run_id)
    os.makedirs(workdir, exist_ok=True)

    want = set(a for a in args.arms.split(",") if a)
    arms = [a for a in SP.ARMS if not want or a["arm"] in want]
    ci = compute_inputs(workdir)
    path = os.path.join(run_dir, "sweep.jsonl")
    fp = open(path, "a")
    hangs = 0

    def emit(rec):
        fp.write(json.dumps(rec, sort_keys=True) + "\n"); fp.flush(); os.fsync(fp.fileno())

    emit({"kind": "run_meta", "run_id": args.run_id, "t": time.time(),
          "git_rev": sh(["git", "-C", REPO, "rev-parse", "HEAD"]).stdout.strip(),
          "arms": [a["arm"] for a in arms]})

    for arm in arms:
        t_arm = time.time()
        archive = build_archive(arm, workdir)
        stage = arm["stage"] if arm["stage"] != "compute" else None
        h = extract_hex(archive, stage)
        i = h.find(arm["pattern"])
        if i < 0 or i % 2:
            emit({"kind": "arm_error", "arm": arm["arm"], "error": "pattern not found"}); continue
        abs_off = locate(archive, stage) + i // 2
        instr_hex = h[i:i + 24]
        emit({"kind": "arm_meta", "arm": arm["arm"], "instr": arm["instr"], "stage": arm["stage"],
              "carrier": {k: arm.get(k) for k in ("kernel", "vs", "fs", "func", "nrt", "samples",
                                                  "W", "H", "grid", "tg", "instances")},
              "pattern": arm["pattern"], "main_offset": i // 2, "abs_off": abs_off,
              "instr_hex": instr_hex, "program_hex": h, "program_len": len(h) // 2})

        spdir = os.path.join(workdir, arm["arm"] + "_sp")
        os.makedirs(spdir, exist_ok=True)
        spseq = [0]

        def next_splice_path():
            """A UNIQUE archive path per persistent-runner request. EXP-0141
            measured ~8% phantom CMDBUF_ERROR when every request reuses one
            path. Old files are unlinked lazily to bound disk use."""
            spseq[0] += 1
            q = os.path.join(spdir, "sp%06d.bin" % spseq[0])
            old = os.path.join(spdir, "sp%06d.bin" % (spseq[0] - 64))
            if os.path.exists(old):
                try: os.unlink(old)
                except OSError: pass
            return q

        if arm["stage"] == "compute":
            runner = PersistRunner(source=os.path.join(EXP, arm["kernel"]), function=arm["func"],
                                   fast_math=False, agxrun_persist=AGXPERSIST)
            # Only `grid` threads run, so only the first `grid` sentinel slots
            # are written -- checking more would reject every valid run.
            nsent = arm["grid"]
            if arm["oracle"] == "mad":
                ins = {0: ci["poison64"], 1: ci["mm_a"], 2: ci["mm_b"], 3: ci["mm_c"],
                       4: ci["sent64"]}
                outs = {0: 256, 4: 256}
            elif arm["oracle"] == "atomic":
                ins = {0: ci["poison32"], 1: ci["lin32"], 2: ci["ctr"], 4: ci["sent32"]}
                outs = {0: 128, 4: 128}
            else:
                ins = {0: ci["poison256"], 1: ci["lin256"], 4: ci["sent256"]}
                outs = {0: 1024, 4: 1024}

            def raw_case(arcpath, **_):
                # A fresh zeroed counter per case keeps k_atomic's oracle exact.
                if arm["oracle"] == "atomic":
                    with open(ci["ctr"], "wb") as cf: cf.write(struct.pack("<I", 0))
                r = runner.request(archive=arcpath, grid=arm["grid"], tg=arm["tg"],
                                   ins=ins, outs=outs, timeout=REQ_TIMEOUT)
                if r["status"] != "OK" or 0 not in r["outs"]:
                    return None, r
                if not sentinel_ok(r["outs"].get(4), nsent):
                    r = dict(r); r["status"] = "SENTINEL_MISS"
                    r["error"] = "integrity sentinel not written: dispatch did not execute"
                    return None, r
                return r["outs"][0], r

            def restart():
                runner._kill(); runner._start()
        else:
            runner = RenderRunner(os.path.join(EXP, arm["kernel"]), exe=RENDERSWEEP)

            def raw_case(arcpath, src=None, vp=None, dst0=None):
                req = {"id": "c", "archive": arcpath, "vs": arm["vs"], "fs": arm["fs"],
                       "w": arm["W"], "h": arm["H"], "nrt": arm["nrt"], "samples": arm["samples"],
                       "clear": [dst0 or SP.DST0, SP.DST1][:arm["nrt"]],
                       "fbuf": src or SP.SRC, "vbuf": vp or SP.VP}
                if arm.get("tex") is not None:
                    req["tex"] = arm["tex"]; req["instances"] = arm["instances"]
                r = runner.request(req, timeout=REQ_TIMEOUT)
                if r.get("status") != "OK": return None, r
                obs = {"pixels": r["pixels"]}
                if "tex" in r: obs["tex"] = r["tex"]
                # INTEGRITY SENTINEL for the render arms (EXP-0141 "STATUS OK,
                # nothing executed"). The colour target is cleared by
                # FIXED-FUNCTION hardware on a path that cannot involve the
                # instruction under test, so if EVERY pixel still holds the
                # exact clear colour the fragment program never wrote and the
                # measurement is invalid rather than a "silent zero". The
                # correct and the zeroed answers both differ from the clear
                # colour for every carrier here (checked in the plan).
                clears = req["clear"]
                untouched = all(f32v(px) == f32v(clears[i // (arm["W"] * arm["H"])])
                                for i, px in enumerate(r["pixels"]))
                if untouched and r.get("gputime_ns", 1) is not None:
                    r = dict(r); r["status"] = "SENTINEL_MISS"
                    r["error"] = "every pixel still holds the clear colour: nothing was drawn"
                    return None, r
                return obs, r

            def restart():
                runner.restart()

        recovery = {"restarts": 0, "unrecovered": 0, "retries": 0, "collateral": 0}

        def healthy():
            """Is the device accepting work again? Run the UNSPLICED baseline."""
            g, r = raw_case(archive)
            return g is not None

        # macOS classifies a failed command buffer. Only the first of these is
        # evidence about OUR encoding; the other two are collateral damage from
        # another process's GPU errors -- and EXP-0140 / EXP-0144 are sweeping
        # this same device right now, so collateral is the COMMON case.
        OWN_FAULT = "Caused GPU Hang Error"
        COLLATERAL = ("Discarded (victim", "Ignored (for causing prior")

        def is_collateral(r):
            e = str(r.get("error", ""))
            return any(c in e for c in COLLATERAL)

        def wait_for_health():
            """Restart the child and block until the unspliced carrier runs.
            Only used when in-place retries have already failed."""
            delay, waited, n = 0.2, 0.0, 0
            while waited < 40.0:
                restart(); recovery["restarts"] += 1; n += 1
                time.sleep(delay); waited += delay
                if healthy():
                    return n
                delay = min(delay * 2.0, 5.0)
            return -1

        def run_case(arcpath, **kw):
            """One case, hardened against the shared-GPU failure modes.

            Measured on this host: after ANOTHER process's command buffer
            faults, the next submission here comes back 'Discarded (victim of
            GPU error/recovery)' and then succeeds again WITHOUT any restart.
            Restarting first (as an earlier version did) made the fresh child's
            first request the next victim, so the sweep never recovered. So:
            retry IN PLACE first, restart only if that fails, and never record a
            collateral failure as a fault. Batch 1 measured 44% of gated faults
            failing to reproduce; this is the mechanism behind that number."""
            n = 0
            for attempt in range(5):
                g, r = raw_case(arcpath, **kw)
                if g is not None:
                    return g, r, n
                recovery["retries"] += 1
                if r.get("status") == "SENTINEL_MISS":
                    # NOT a transport failure: the runner returned OK and the
                    # integrity sentinel says the work never executed. Confirm
                    # once in place, then check the device is still healthy. If
                    # it is, this is a REPRODUCIBLE property of the spliced
                    # encoding (a value that suppresses the draw/dispatch), and
                    # it is recorded as its own outcome -- never as `ok` and
                    # never as `silent_zero`, which is the confusion EXP-0141
                    # warns about. Doing this here avoids burning a 40s recovery
                    # cycle on every such case.
                    g2, r2 = raw_case(arcpath, **kw)
                    if g2 is not None:
                        return g2, r2, n
                    if healthy():
                        return None, r2, n
                    r = r2
                if is_collateral(r):
                    recovery["collateral"] += 1
                if os.environ.get("EXP0147_DEBUG"):
                    print("RETRY %d: %s | %s" % (attempt, r.get("status"),
                          str(r.get("error"))[:120]), file=sys.stderr, flush=True)
                time.sleep(0.05 + 0.1 * attempt)
            # In-place retries exhausted: the child or the device really is sick.
            n = wait_for_health()
            if n < 0:
                recovery["unrecovered"] += 1
                return None, r, 99
            g2, r2 = raw_case(arcpath, **kw)
            return g2, r2, n

        def record(field, value, muts, note=""):
            nonlocal hangs
            spliced = next_splice_path()
            splice(archive, spliced, abs_off, muts)
            with open(spliced, "rb") as f2:
                f2.seek(abs_off); shex = f2.read(12).hex()
            got, raw, nres = run_case(spliced)
            if nres: note = (note + f" [recovered after {nres} restart(s)]").strip()
            if raw.get("status") in ("HANG",):
                hangs += 1
                emit({"instr": arm["instr"], "field": field, "value": value, "bytes": shex,
                      "observed": None, "oracle": None, "match": False, "outcome": "hang",
                      "carrier": arm["arm"], "note": note or raw.get("error", "")})
                return
            if got is None:
                st = raw.get("status")
                if st == "SENTINEL_MISS":
                    # confirmed twice with a healthy device in between
                    oc = "no_dispatch" if arm["stage"] == "compute" else "no_draw"
                elif is_collateral(raw):
                    # still collateral after 5 in-place retries + a restart cycle:
                    # this says nothing about the spliced encoding.
                    oc = "invalid_run"
                else:
                    oc = "fault"
                emit({"instr": arm["instr"], "field": field, "value": value, "bytes": shex,
                      "observed": {"status": st}, "oracle": None, "match": False,
                      "outcome": oc, "carrier": arm["arm"],
                      # The OS fault-classification string distinguishes a real
                      # illegal encoding ("Caused GPU Hang Error") from collateral
                      # damage ("Ignored (for causing prior/excessive GPU errors)",
                      # "Discarded (victim of GPU error/recovery)"). Batch 1 showed
                      # 44% of gated faults were collateral, so this string is
                      # evidence, not decoration.
                      "os_error": str(raw.get("error", ""))[:300],
                      "confirmations": nres,
                      "note": (note + " [re-observed after restart+health-check]").strip()[:300]})
                return
            if arm["stage"] == "compute":
                obs, ok, outcome = classify_compute(arm, ci, got)
                orc = None
            else:
                obs = got; orc = oracle_for(arm)
                ok = same(arm, obs, orc)
                outcome = "ok" if ok else "wrong_value"
                if not ok:
                    z = zero_oracle_for(arm)
                    if z is not None and same(arm, obs, z): outcome = "silent_zero"
            reps, stable, obs_list, oc_list = 1, True, [obs], [outcome]
            if outcome != "ok":
                # NEVER conclude a non-ok outcome from ONE observation. Batch 1
                # measured 44% of gated-run faults failing to reproduce and up to
                # 22 wrong per 100 under concurrent GPU load; EXP-0140/EXP-0144
                # are sweeping the same device while this runs. Re-observe on a
                # FRESH unique archive path and keep the result only if it
                # reproduces; otherwise mark it unstable and keep both.
                for _ in range(2):
                    q2 = next_splice_path()
                    splice(archive, q2, abs_off, muts)
                    g2, r2, _n2 = run_case(q2)
                    reps += 1
                    if arm["stage"] == "compute":
                        o2, ok2, oc2 = classify_compute(arm, ci, g2) if g2 is not None \
                                       else ({"status": r2.get("status")}, False,
                                             "no_dispatch" if r2.get("status") == "SENTINEL_MISS"
                                             else ("invalid_run" if is_collateral(r2) else "fault"))
                    else:
                        o2 = g2
                        if g2 is None:
                            ok2 = False
                            oc2 = ("no_draw" if r2.get("status") == "SENTINEL_MISS"
                                   else ("invalid_run" if is_collateral(r2) else "fault"))
                        else:
                            ok2 = same(arm, g2, oracle_for(arm))
                            oc2 = "ok" if ok2 else "wrong_value"
                            if not ok2:
                                z2 = zero_oracle_for(arm)
                                if z2 is not None and same(arm, g2, z2): oc2 = "silent_zero"
                    obs_list.append(o2); oc_list.append(oc2)
                    if oc2 != outcome: stable = False
                if not stable:
                    note = (note + " | replicates disagreed").strip()
                    outcome = "unstable"
            emit({"instr": arm["instr"], "field": field, "value": value, "bytes": shex,
                  "observed": obs, "oracle": orc, "match": ok, "outcome": outcome,
                  "replicates": reps, "stable": stable, "status": raw.get("status"),
                  "restarts": nres, "carrier": arm["arm"], "note": note,
                  **({} if stable else {"replicate_observations": obs_list,
                                        "replicate_outcomes": oc_list})})

        # --- baseline -------------------------------------------------------
        got, raw, nres = run_case(archive)
        if arm["stage"] == "compute":
            obs, ok, outcome = classify_compute(arm, ci, got) if got is not None else (None, False, "fault")
            orc = None
        else:
            obs = got; orc = oracle_for(arm); ok = same(arm, obs, orc)
            outcome = "ok" if ok else ("fault" if obs is None else "wrong_value")
        base_obs = obs
        emit({"instr": arm["instr"], "field": "_baseline", "value": None, "bytes": instr_hex,
              "observed": obs, "oracle": orc, "match": ok, "outcome": outcome,
              "carrier": arm["arm"], "note": "unspliced program vs host-computed oracle"})

        # --- liveness controls: change an INPUT, the observable must follow --
        if arm["stage"] != "compute":
            controls = [("src_alt", {"src": SP.SRC_ALT},
                         "fragment uniform: proves the fragment ALU path is observed")]
            if arm["oracle"] in ("tile", "mrt", "rog"):
                controls.append(("dst_alt", {"dst0": SP.DST0_ALT},
                                 "CLEAR COLOUR: this is the value the tilebuffer read returns, "
                                 "so a following observable change proves the tile read reaches the pixel"))
            if arm["arm"] == "vtx_coord_xform":
                controls.append(("vp_alt", {"vp": SP.SRC_ALT},
                                 "vertex uniform: proves the vertex stage output reaches the pixel"))
            for lbl, kw, why in controls:
                g2, r2, _n = run_case(archive, **kw)
                o2 = oracle_for(arm, **kw)
                m2 = same(arm, g2, o2)
                emit({"instr": arm["instr"], "field": "_liveness_" + lbl, "value": None,
                      "bytes": instr_hex, "observed": g2, "oracle": o2, "match": m2,
                      "outcome": "ok" if m2 else ("fault" if g2 is None else "wrong_value"),
                      "carrier": arm["arm"],
                      "note": why + "; differs from baseline: " + str(g2 != base_obs)})
            if arm["oracle"] in ("vary_tern", "vary_arr", "samp"):
                distinct = len({tuple(p) for p in (base_obs or {}).get("pixels", [])})
                emit({"instr": arm["instr"], "field": "_liveness_spatial", "value": None,
                      "bytes": instr_hex, "observed": {"distinct_pixels": distinct},
                      "oracle": {"distinct_pixels": arm["W"] * arm["H"]},
                      "match": distinct == arm["W"] * arm["H"],
                      "outcome": "ok" if distinct == arm["W"] * arm["H"] else "wrong_value",
                      "carrier": arm["arm"],
                      "note": "the vertex stage drives a spatial gradient: all "
                              f"{arm['W']*arm['H']} pixels must differ, which proves the "
                              "vertex-stage output reaches the observed pixels"})

        # --- litmus-power probe ---------------------------------------------
        # Demanded after EXP-0141 found its first tile litmus could not detect a
        # spliced-out barrier at all -- i.e. it would have "proven" inert
        # something it had no power to observe. Before any field of this
        # instruction may be promoted, the measurement must be shown able to SEE
        # the thing under test disappear.
        pp = arm.get("power_probe")
        if pp:
            ppi = h.find(pp["pattern"])
            if ppi < 0 or ppi % 2:
                emit({"instr": arm["instr"], "field": "_litmus_power", "value": None,
                      "bytes": "", "observed": None, "oracle": None, "match": False,
                      "outcome": "invalid_run", "carrier": arm["arm"],
                      "note": "power-probe pattern not found: " + pp["pattern"]})
            else:
                pp_off = locate(archive, stage) + ppi // 2
                q = next_splice_path()
                splice(archive, q, pp_off, [(pp["byte"], (lambda v: (lambda o: v))(pp["value"]))])
                g3, r3, _n3 = run_case(q)
                if arm["stage"] == "compute":
                    o3, m3, oc3 = classify_compute(arm, ci, g3) if g3 is not None \
                                  else (None, False, "fault")
                else:
                    o3 = g3
                    if g3 is None:
                        m3, oc3 = False, "fault"
                    else:
                        m3 = same(arm, g3, oracle_for(arm))
                        oc3 = "ok" if m3 else "wrong_value"
                # "Moved" must be judged on the OUTCOME CLASS, not on the raw
                # read-back: k_atomic's per-thread tickets are arrival-ordered and
                # therefore differ between two identical runs, which would make a
                # raw comparison declare power that does not exist.
                moved = (oc3 != "ok")
                emit({"instr": arm["instr"], "field": "_litmus_power", "value": pp["value"],
                      "bytes": pp["pattern"], "observed": o3, "oracle": None,
                      "match": moved,
                      "outcome": "ok" if moved else "no_power",
                      "carrier": arm["arm"],
                      "note": pp["why"] + " | observable moved: " + str(moved)})

        # --- identity splice control ----------------------------------------
        record("_identity_splice", None, [(0, lambda o: o)],
               note="rewrite byte0 with its own value: must equal baseline")

        # --- method-sensitivity control -------------------------------------
        s = arm["sensitivity"]
        record("_sensitivity", s["value"], [(s["byte"], (lambda v: (lambda o: v))(s["value"]))],
               note="pre-registered to FAIL: " + s["why"])

        # --- the field sweeps -----------------------------------------------
        ncase = [0]
        for f in arm["fields"]:
            for value, muts in field_cases(f):
                ncase[0] += 1
                if ncase[0] % 128 == 0:
                    # Periodic baseline re-validation: proves the device was
                    # still healthy for the block of cases just recorded, so a
                    # run of "silent_zero" cannot be a quiet cascade.
                    gb, rb, nb_ = run_case(archive)
                    if arm["stage"] == "compute":
                        ob, mb, ocb = classify_compute(arm, ci, gb) if gb is not None else (None, False, "fault")
                    else:
                        ob = gb; mb = same(arm, gb, oracle_for(arm))
                        ocb = "ok" if mb else ("fault" if ob is None else "wrong_value")
                    emit({"instr": arm["instr"], "field": "_baseline_recheck",
                          "value": ncase[0], "bytes": instr_hex, "observed": ob,
                          "oracle": None, "match": mb,
                          "outcome": "ok" if mb else "wrong_value", "carrier": arm["arm"],
                          "note": "device health after %d swept cases" % ncase[0]})
                record(f["name"], value, muts)
                if recovery["unrecovered"] >= 3:
                    emit({"kind": "arm_stopped", "arm": arm["arm"],
                          "reason": "device did not recover after 3 full back-off cycles"})
                    hangs = 99
                if hangs >= 2:
                    emit({"kind": "arm_stopped", "arm": arm["arm"], "reason": "two hangs"})
                    break
            if hangs >= 2: break

        try: runner.close()
        except Exception: pass
        emit({"kind": "arm_done", "arm": arm["arm"], "wall_s": round(time.time() - t_arm, 2),
              **recovery})
        with open(os.path.join(EXP, "PROGRESS.md"), "a") as pg:
            pg.write(f"- {time.strftime('%Y-%m-%dT%H:%M:%S')} run={args.run_id} arm={arm['arm']} "
                     f"done in {round(time.time()-t_arm,1)}s\n")

    fp.close()
    print("wrote", path)


if __name__ == "__main__":
    main()
