#!/usr/bin/env python3
"""EXP-0169 gated-run driver (G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--arms A,B] [--limit N]
                         [--order forward|reverse]

Per case: build the program for the case's mode, dispatch it once, and append
one FIELD-SWEEP-PROTOCOL section-4 record IMMEDIATELY (flush + fsync), so a
kill costs at most one case.

Safety / anti-contamination (FIELD-SWEEP-PROTOCOL section 7, binding):
  * the read-back buffer is poisoned with 0xDEADBEEF before EVERY dispatch;
  * two integrity sentinels, neither in a register the instruction under test
    can name while it runs;
  * majority-of-3 before any `fault`/`hang` is recorded;
  * the OS fault-classification string is recorded VERBATIM on every non-OK
    case and `...ErrorInnocentVictim`-class failures are flagged `victim`;
  * the unmutated baseline is re-validated every BASELINE_EVERY cases; a
    baseline failure restarts the child rather than logging a GPU error
    cascade as data;
  * a unique splice-archive path per process.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
from __future__ import print_function

import argparse
import json
import os
import platform
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import casematrix as CM      # noqa: E402

BASELINE_EVERY = 250
RETRIES = 3            # majority-of-3
REQ_TIMEOUT = 8.0
NAT_OUT_SLOT = 2       # k_cmp_chain writes buffer(2)
NAT_OUT_WORDS = 32
NAT_GRID = NAT_TG = 8


# --------------------------------------------------------------------------
# Input buffers.
# --------------------------------------------------------------------------
def prepare_inputs(workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mem = workdir / "mem_ramp.bin"
    mem.write_bytes(H.mem_image())
    imem = workdir / "imem_ramp.bin"
    imem.write_bytes(struct.pack("<%dI" % 1024,
                                 *[(i * 0x01010101) & 0xFFFFFFFF
                                   for i in range(1024)]))
    uni = workdir / "uni.bin"
    uni.write_bytes(struct.pack("<4f", 2.5, 6.25, 12.5, 25.0))
    return {"mem": str(mem), "imem": str(imem), "uni": str(uni)}


def carrier_for(cid, files, workdir, cache):
    if cid in cache:
        return cache[cid]
    if cid == "NAT_kcmp":
        c = S.Carrier(EXP / "kernels" / "probes.metal", "k_cmp_chain",
                      workdir / "car_NAT", timeout=REQ_TIMEOUT,
                      extra_ins={0: files["imem"], 1: files["mem"]})
        cache[cid] = c
        return c
    src, fn, seedkind, outw, _why = CM.CARRIERS[cid]
    extra = {1: files["mem"]}
    extra[2] = files["uni"] if src == "carrier_uni.metal" else files["imem"]
    c = S.Carrier(EXP / "kernels" / src, fn, workdir / ("car_" + cid),
                  timeout=REQ_TIMEOUT, extra_ins=extra)
    cache[cid] = c
    return c



# --------------------------------------------------------------------------
# Program construction / dispatch / observation. Module level so harness/smoke.py
# runs the ladder through EXACTLY the same code path as the gated sweep.
# --------------------------------------------------------------------------
def out_words_for(case):
    if case["mode"] == "nat":
        return NAT_OUT_WORDS
    return CM.CARRIERS[case["carrier"]][3]


def build_prog_static(case, blk, car, rep):
    """Return (program bytes, native_flag) for one case."""
    if case["mode"] in ("lift", "synth"):
        return H.synth_program(case["kind"], blk, car.region_len), None
    if case["mode"] == "store":
        return H.store_probe_program(case["kind"], blk, car.region_len), None
    main = bytes.fromhex(rep[case["probe"]]["main_hex"])
    lo, hi = case["block_lo"], case["block_hi"]
    return main[:lo] + blk + main[hi:], "native"


def dispatch_static(case, prog, native, car):
    if native:
        return car.run_native(prog, NAT_OUT_SLOT, NAT_OUT_WORDS,
                              grid=NAT_GRID, tg=NAT_TG)
    return car.run_program(prog, out_words=out_words_for(case))


def observe_static(case, resp, words):
    if resp["status"] != "OK":
        return None
    if case["mode"] == "nat":
        return S.native_digest(words)
    return S.digest(words)


# --------------------------------------------------------------------------
# The semantic (host-computed) oracle.
# --------------------------------------------------------------------------
def sem_oracle(case, seeds):
    """A HOST-COMPUTED expected destination word, independent of the GPU, for
    the arms where the point of the sweep is a published SEMANTIC claim:

      falu2  srcB_class==1, srcB_reg 64..127 -> the EXP-0138 inline 8-bit
             minifloat immediate, sign per EXP-0158's srcB_neg reading;
      falu2i                                 -> isadb.imm_decode of the packed
             immediate (exp/mant/sign/flag), the EXP-0006 claim.

    Returns None where no independent oracle exists (then the oracle is the
    unmutated anchor's full architectural state, as in EXP-0154).
    """
    ins = case["instr"]
    if ins not in ("falu2", "falu2i"):
        return None
    spec = CM.INS[ins]
    F = {f["name"]: f for f in spec["fields"]}
    blk = bytes.fromhex(case["bytes"])
    tgt = case.get("tgt") or 0
    if tgt + spec["length"] > len(blk):
        return None

    def g(n):
        f = F[n]
        return CM.get_field(blk, tgt, f["start"], f["width"])

    try:
        dst = g("dst")
        opsel = g("opsel")
        if opsel not in (4, 5):
            return None
        if ins == "falu2":
            if g("srcA_size") != 1 or g("srcB_class") != 1:
                return None
            a_reg = g("srcA_reg")
            if a_reg not in seeds:
                return None
            v = g("srcB_reg") | (g("srcB_reg_top") << 6)
            k = H.inline_minifloat(v)
            if k is None:
                return None
            if g("srcB_neg") == 0:
                k = -k          # EXP-0158: the sign is NEGATIVE at srcB_neg==0
            a = H.bits_to_f32(seeds[a_reg])
            claim = "EXP-0138 inline minifloat + EXP-0158 sign-at-neg0"
        else:
            if g("srcA_size") != 1:
                return None
            a_reg = g("srcA_reg") | (g("srcA_reg_top") << 6)
            if a_reg not in seeds:
                return None
            b1 = ((g("imm_exp") & 0xF) << 4) | ((g("imm_mant") & 0x7) << 1) \
                 | (g("imm_flag") & 1)
            k = H.isadb.imm_decode(b1, g("imm_sign"))
            a = H.bits_to_f32(seeds[a_reg])
            claim = "EXP-0006 packed minifloat immediate (isadb.imm_decode)"
        want = H.f32(a + k) if opsel == 4 else H.f32(a * k)
        return {"dst": dst, "srcA_reg": a_reg, "srcA": a, "srcB": k,
                "op": "fadd" if opsel == 4 else "fmul",
                "want_bits": H.f32_to_bits(want), "want": want, "claim": claim}
    except Exception:
        return None


def env_block(devices, files, calib, matrix_sha, ncases):
    def sh(cmd):
        try:
            return subprocess.check_output(cmd, shell=True,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "?"
    return {
        "experiment": "EXP-0169-g17p-rerecord",
        "target": "G17P",
        "devices": devices,
        "host": platform.node(),
        "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
        "machine": sh("sysctl -n hw.model"),
        "python": sys.version.split()[0],
        "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "db.json")),
        "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "isadb.py")),
        "matrix_sha256": matrix_sha,
        "matrix_cases": ncases,
        "load_idx_unit_words": calib.get("idx_unit_words"),
        "calibration": calib,
        "inputs": files,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--carriers", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    workdir = EXP / "work" / ("run_%s" % a.run)
    files = prepare_inputs(workdir)
    calib_path = EXP / "work" / "calib.json"
    calib = json.loads(calib_path.read_text()) if calib_path.exists() else {}
    idx_unit = int(calib.get("idx_unit_words", 1))

    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases, resolved, misses = CM.build_cases(rep)
    matrix_sha = CM.matrix_sha256(cases)
    if a.arms:
        want = set(a.arms.split(","))
        cases = [c for c in cases if c["arm"] in want]
    if a.carriers:
        want = set(a.carriers.split(","))
        cases = [c for c in cases if c["carrier"] in want]
    if a.limit:
        cases = cases[:a.limit]
    if a.order == "reverse":
        groups = []
        for c in cases:
            k = (c["carrier"], c["arm"])
            if not groups or groups[-1] != k:
                groups.append(k)
        rank = dict((k, -i) for i, k in enumerate(groups))
        cases = sorted(cases, key=lambda c: (rank[(c["carrier"], c["arm"])],
                                             c["idx"]))

    done = set()
    jl = rundir / "sweep.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done.add(json.loads(ln)["idx"])
            except Exception:
                pass
        print("resume: %d cases already recorded" % len(done))

    cache = {}
    log = S.Log(jl)
    blog = S.Log(rundir / "baseline.jsonl")
    (rundir / "00_arm_resolution.json").write_text(json.dumps(
        {"resolved": {"%s/%s/%s" % k: v for k, v in resolved.items()},
         "misses": misses}, indent=1, sort_keys=True))

    baselines = {}
    counters = dict(ok=0, silent_zero=0, wrong_value=0, fault=0, hang=0,
                    undecodable=0, victim=0, sentinel_bad=0, baseline_fail=0,
                    sem_checked=0, sem_match=0)

    def build_prog(case, blk, car):
        return build_prog_static(case, blk, car, rep)

    def dispatch(case, prog, native, car):
        return dispatch_static(case, prog, native, car)

    def observe(case, resp, words):
        return observe_static(case, resp, words)

    def baseline_for(case, car, force=False):
        key = (case["carrier"], case["arm"])
        if key in baselines and not force:
            return baselines[key]
        blk0 = bytes.fromhex(case["anchor"]) if case["mode"] != "lift" else None
        if case["mode"] in ("lift", "nat"):
            main = bytes.fromhex(rep[case["probe"]]["main_hex"])
            blk0 = main[case["block_lo"]:case["block_hi"]]
        prog, native = build_prog(case, blk0, car)
        d = None
        for att in range(8):
            resp, words = dispatch(case, prog, native, car)
            if resp["status"] == "OK":
                d = observe(case, resp, words)
                break
            if S.is_victim(resp["error"]):
                # a sibling's device reset -- retry with backoff rather than
                # losing the arm's baseline to someone else's fault
                time.sleep(5.0 * (att + 1))
                if att == 3:
                    car.restart()
            else:
                break
        blog.write({"arm": case["arm"], "carrier": case["carrier"],
                    "status": resp["status"], "error": resp["error"],
                    "observed": d,
                    "digest": (S.digest_hex(d) if (d and "regs" in d) else None),
                    "kind": "refresh" if force else "initial"})
        if d is None:
            counters["baseline_fail"] += 1
        else:
            baselines[key] = d
        return d

    n = 0
    t0 = time.time()
    cur = None
    devices = {}
    for c in cases:
        if c["idx"] in done:
            continue
        car = carrier_for(c["carrier"], files, workdir, cache)
        devices.setdefault(c["carrier"], car.device)
        key = (c["carrier"], c["arm"])
        if key != cur:
            cur = key
            base = baseline_for(c, car)
            print("[%s] %s/%s baseline %s"
                  % (time.strftime("%H:%M:%S"), c["carrier"], c["arm"],
                     "OK" if base else "FAILED"))
        base = baselines.get(key)
        blk = bytes.fromhex(c["bytes"])
        prog, native = build_prog(c, blk, car)
        rt_ok = H.round_trips(blk)
        tok = H.tokenize_first(blk[(c.get("tgt") or 0):])

        attempts, outcome, obs = [], None, None
        for k in range(RETRIES):
            resp, words = dispatch(c, prog, native, car)
            d = observe(c, resp, words)
            oc = S.classify(resp["status"], d, base) if base else "undecodable"
            attempts.append({"status": resp["status"], "outcome": oc,
                             "error": resp["error"],
                             "victim": S.is_victim(resp["error"])})
            if oc in ("ok", "silent_zero", "wrong_value"):
                outcome, obs = oc, d
                break
            if k == RETRIES - 1:
                bad = [x["outcome"] for x in attempts]
                outcome = max(set(bad), key=bad.count)
                obs = d
        victim = any(x["victim"] for x in attempts)
        sent_bad = bool(obs and "pre" in obs
                        and (obs["pre"] != H.expected_pre()
                             or obs["post"] != H.SENT_POST))
        counters[outcome] = counters.get(outcome, 0) + 1
        if victim:
            counters["victim"] += 1
        if sent_bad:
            counters["sentinel_bad"] += 1

        sem = sem_oracle(c, H.seed_values(c["kind"], idx_unit))
        sem_match = None
        if sem is not None and obs and "regs" in obs:
            counters["sem_checked"] += 1
            sem_match = (obs["regs"][sem["dst"]] == sem["want_bits"])
            if sem_match:
                counters["sem_match"] += 1

        rec = {
            "idx": c["idx"], "arm": c["arm"], "carrier": c["carrier"],
            "instr": c["instr"], "field": c["field"], "value": c["value"],
            "bytes": c["bytes"], "mode": c["mode"], "kind": c["kind"],
            "cross": c.get("cross"),
            # `tgt` is the instruction's byte offset inside `bytes`. Logged so
            # analysis can recover the FIELD VALUE exactly -- for a byte-wise
            # sweep of a >8-bit field, `value` is a BYTE value, not the field's
            # value, and counting `value`s would understate coverage. Without
            # this, coverage has to be re-derived by fitting db.json's match
            # constraints, which is what EXP-0164's indexer has to do.
            "tgt": c.get("tgt") or 0,
            "observed": obs,
            "oracle": {"digest": S.digest_hex(base) if (base and "regs" in base)
                       else (base if base else None),
                       "sem": sem},
            "match": bool(obs and base and obs == base),
            "sem_match": sem_match,
            "outcome": outcome,
            "rt_ok": rt_ok, "tok_instr": tok,
            "victim": victim, "sentinel_bad": sent_bad,
            "attempts": attempts, "predict": c.get("predict", ""),
            "byte_index": c.get("byte_index"), "fstart": c.get("fstart"),
            "fwidth": c.get("fwidth"), "foreign": c.get("foreign", False),
            "note": c.get("note", "") or "",
        }
        log.write(rec)
        n += 1

        if n % BASELINE_EVERY == 0:
            d = baseline_for(c, car, force=True)
            if d is None or base is None or d != base:
                print("  !! baseline drift/failure at n=%d %s/%s -> restart"
                      % (n, c["carrier"], c["arm"]))
                counters["baseline_fail"] += 1
                car.restart()
                baselines.pop(key, None)
                baseline_for(c, car)
        if n % 2000 == 0:
            el = time.time() - t0
            print("  %6d  %.1f case/s  %s"
                  % (n, n / max(el, 1e-9), json.dumps(counters, sort_keys=True)))
            (rundir / "01_progress.json").write_text(json.dumps(
                {"done": n, "counters": counters, "elapsed_s": round(el, 1)},
                indent=1, sort_keys=True))
            (rundir / "00_env.json").write_text(json.dumps(
                env_block(devices, files, calib, matrix_sha, len(cases)),
                indent=1, sort_keys=True))

    (rundir / "00_env.json").write_text(json.dumps(
        env_block(devices, files, calib, matrix_sha, len(cases)),
        indent=1, sort_keys=True))
    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "counters": counters,
         "hangs_seen": {k: v.hangs for k, v in cache.items()},
         "elapsed_s": round(time.time() - t0, 1),
         "matrix_len": len(cases), "matrix_sha256": matrix_sha},
        indent=1, sort_keys=True))
    log.close()
    blog.close()
    for v in cache.values():
        v.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
