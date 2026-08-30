#!/usr/bin/env python3
"""EXP-0168 gated-run driver (A18 Pro / G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--arms A,B] [--limit N]
                         [--order forward|reverse] [--style S|P|both]

Per case: build the program, dispatch it once, and append one
FIELD-SWEEP-PROTOCOL section-4 record IMMEDIATELY (flush + fsync).

THE ORACLE CONVENTION, STATED ONCE BECAUSE IT INVERTS BETWEEN ARMS
-----------------------------------------------------------------
`outcome == "ok"` always means "matched the HOST PREDICTION". What the
prediction IS depends on what the field is:

  * a DESTINATION-REGISTER field predicts MOVEMENT: for `dst = v` the prediction
    is "register v holds the written value, every other register still holds its
    host-known seed". `predicts` = `moves_to_slot_v`.
  * every other field predicts NO CHANGE (the null hypothesis is inertness), so
    movement shows up as `wrong_value` / `silent_zero`. `predicts` = `no_change`.

Every record therefore ALSO carries `moved` (did the observation differ from the
unmutated baseline?) and `moved_slots`, so the audit's own "moved_total" metric
is recomputable from this raw without knowing the convention.

Safety / anti-contamination (FIELD-SWEEP-PROTOCOL section 7, binding):
  * majority-of-3 before any `fault`/`hang` is recorded;
  * the OS fault-classification string on EVERY non-ok case;
  * `...ErrorInnocentVictim`-class failures flagged and re-run, never scored;
  * `validity` separate from `outcome`: an all-poison read-back, a failed
    sentinel or a clobbered tail region is `invalid_*` and is RE-RUN, never
    recorded as a silent zero;
  * the unmutated baseline re-validated every BASELINE_EVERY cases;
  * a per-field and per-arm HANG BUDGET: after 2 genuine hangs in a field the
    field STOPS and is reported PARTIAL (FIELD-SWEEP-PROTOCOL section 8);
  * a unique splice-archive path per process;
  * the read-back buffer poisoned with 0xDEADBEEF before every dispatch.
"""
from __future__ import print_function

import argparse
import hashlib
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

BASELINE_EVERY = 300
RETRIES = 3                  # majority-of-3
REQ_TIMEOUT = 8.0
MAX_HANGS_PER_FIELD = 2      # FIELD-SWEEP-PROTOCOL section 8
MAX_HANGS_PER_ARM = 6
HANG_COOLDOWN_S = 2.0


# ---------------------------------------------------------------------------
# STYLE-P input decks (authored here, written to work/ as plain binary)
# ---------------------------------------------------------------------------
def _u32(vals):
    return struct.pack("<%dI" % len(vals), *vals)


# 32 lanes split across the 50 / 100 / 200 thresholds so that the four nesting
# levels of k_if_nest3 each contain a DIFFERENT, non-empty subset of the SIMD.
IF_LANES = [0, 10, 20, 30, 40, 45, 49, 51, 60, 70, 80, 90, 99, 101, 120, 140,
            160, 180, 199, 201, 210, 220, 230, 240, 250, 255, 300, 400, 500,
            600, 700, 800]
ATOMIC_GRID = 8


def write_inputs(work):
    work.mkdir(parents=True, exist_ok=True)
    paths = {}
    p = work / "if_a.bin"
    p.write_bytes(_u32(IF_LANES))
    paths["if_a"] = str(p)
    # 32 lanes x 8 slots, poisoned so an unwritten slot is visibly unwritten
    p = work / "if_out_poison.bin"
    p.write_bytes(_u32([H.POISON] * (32 * 8)))
    paths["if_out"] = str(p)

    p = work / "at_zero.bin"
    p.write_bytes(_u32([0] * ATOMIC_GRID))
    paths["at_zero"] = str(p)
    p = work / "at_b.bin"
    p.write_bytes(_u32([(i * 7 + 3) & 0xFFFF for i in range(ATOMIC_GRID * 24)]))
    paths["at_b"] = str(p)
    p = work / "at_out_poison.bin"
    p.write_bytes(_u32([H.POISON] * (ATOMIC_GRID * 2)))
    paths["at_out"] = str(p)
    return paths


INPLACE_BIND = {
    # kernel -> (ins {idx: key}, outs {idx: nbytes}, grid, tg, out_idx)
    "k_if_flat":   ({0: "if_a", 1: "if_out"}, {1: 32 * 8 * 4}, 32, 32, 1),
    "k_if_nest2":  ({0: "if_a", 1: "if_out"}, {1: 32 * 8 * 4}, 32, 32, 1),
    "k_if_nest3":  ({0: "if_a", 1: "if_out"}, {1: 32 * 8 * 4}, 32, 32, 1),
    "k_if_loop":   ({0: "if_a", 1: "if_out"}, {1: 32 * 8 * 4}, 32, 32, 1),
    "k_atomic_lo": ({0: "at_zero", 1: "at_b", 2: "at_out"},
                    {2: ATOMIC_GRID * 2 * 4}, ATOMIC_GRID, ATOMIC_GRID, 2),
    "k_atomic_min": ({0: "at_zero", 1: "at_b", 2: "at_out"},
                     {2: ATOMIC_GRID * 2 * 4}, ATOMIC_GRID, ATOMIC_GRID, 2),
    "k_atomic_hi": ({0: "at_zero", 1: "at_b", 2: "at_out"},
                    {2: ATOMIC_GRID * 2 * 4}, ATOMIC_GRID, ATOMIC_GRID, 2),
}


# ---------------------------------------------------------------------------
# STYLE-S program construction per arm
# ---------------------------------------------------------------------------
def reread_tail(kind):
    """FALU_ACC/reread: an AUTHORED second consumer of the accumulate's srcB,
    placed after the block, whose result lands in a dumped register. If
    `cache` is a last-use/release hint, this second read is exactly what it
    would affect."""
    return H.falu2i_raw(H.R_PROBE, 8, 0.0)


def build_program(case, carrier_len, blk):
    kind = case.get("kind") or "int"
    arm = case["arm"]
    high = None
    pr = case.get("probe_reg")
    if pr and case["field"] in ("dst_hi",):
        high = 40                       # a register outside the dump window

    if arm == "STOP/midprogram":
        return H.synth_program_midstop(kind, blk, carrier_len)
    if arm == "STOP/terminal":
        # MUST NOT fall through to synth_program(): that would place the stop
        # under test in the BODY, making this arm byte-identical in shape to
        # STOP/midprogram. Measured as identical on hardware in the prefreeze
        # smoke (both: whole dump poison, POST poison) before it was fixed.
        return H.synth_program_terminalstop(kind, blk, carrier_len)

    if arm == "MOVIMM/padded":
        # mov_imm under test -> INERT padding -> dump. r7 is the destination
        # under test; r5 is the witness that must be untouched.
        pre = b""
        tail = b""
        body = blk + H.mov_imm(14, 0) * 2
        return H.synth_program(kind, body, carrier_len, high_probe=high)
    if arm == "MOVIMM/unpadded":
        # mov_imm under test IMMEDIATELY followed by a LOAD-BEARING witness
        # write. If the first instruction consumes the second, r5 keeps its
        # seed (127-ish) instead of taking the witness value 99.
        body = blk + H.mov_imm(5, 99)
        return H.synth_program(kind, body, carrier_len, high_probe=high)

    after = case.get("after")
    tail = b""
    if after == "reread_srcB":
        # placed BEFORE the dump so its result is visible in r11
        return H.synth_program(kind, blk + reread_tail(kind), carrier_len,
                               high_probe=high)

    if arm in ("REGMOVE/consumer", "REGMOVE/consumer9"):
        # a FIXED consumer reads rC and writes R_PROBE; only the coincidence
        # dst == rC changes it. Two sub-arms use two rC values (3 and 9), so the
        # coincidence INDEX itself has to move with the consumer -- which a
        # single consumer index could never show.
        rc = 9 if arm.endswith("9") else 3
        return H.synth_program(kind, blk + H.falu2i_raw(H.R_PROBE, rc, 0.0),
                               carrier_len, high_probe=high)

    return H.synth_program(kind, blk, carrier_len, high_probe=high)


# ---------------------------------------------------------------------------
# oracles
# ---------------------------------------------------------------------------
DST_FIELDS = {"dst", "dst_hi"}


def predicts(case):
    return "moves_to_slot_v" if (case["role"] == "sweep"
                                 and case["field"] in DST_FIELDS
                                 and (case.get("fwidth") or 0) <= 4) \
        else "no_change"


def dst_oracle(value, base_regs, seed_regs):
    """Host prediction for `dst = value`.

    The GPU-independent half is the seed table: fifteen of the sixteen slots
    must still hold the value THIS PROGRAM WROTE INTO THEM, which the host
    knows a priori. The written value itself is taken from the unmutated
    anchor -- ONE GPU measurement, reused for every value of the field -- so the
    oracle is labelled `slot_pattern`, not `value_exact`.

    Returns (expect_regs, written_value) or (None, None) when the anchor did not
    write exactly one slot, in which case the arm has no dst prediction and its
    cases are scored structurally.
    """
    changed = [i for i in range(H.N_REGS) if base_regs[i] != seed_regs[i]]
    if len(changed) != 1:
        return None, None
    written = base_regs[changed[0]]
    exp = list(seed_regs)
    if 0 <= value < H.N_REGS:
        exp[value] = written
    return exp, written


# ---------------------------------------------------------------------------
def env_block(dev, region_len):
    def sh(cmd):
        try:
            return subprocess.check_output(cmd, shell=True,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "?"
    return {
        # recorded from the LIVE device, never from a literal: EXP-0138's
        # run.py hardcoded "Apple M4 (G16G) local" into its evidence file.
        "target_reported_by_device": dev,
        "host": platform.node(),
        "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
        "machine": sh("sysctl -n hw.model"),
        "gpu_cores": sh("system_profiler SPDisplaysDataType 2>/dev/null | "
                        "awk -F': ' '/Total Number of Cores/{print $2; exit}'"),
        "python": sys.version.split()[0],
        "region_len": region_len,
        "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "db.json")),
        "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "isadb.py")),
        "isa_dir": str(H.ISA_DIR),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def words_digest(words):
    h = hashlib.sha256(_u32(words)).hexdigest()[:24] if words else None
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--style", default="both", choices=("S", "P", "both"))
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--deadline-s", type=float, default=0.0)
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    if (rundir / "02_summary.json").exists():
        raise SystemExit("run id %s already completed -- never reuse a run id "
                         "(SUBAGENT_BRIEF)" % a.run)
    rundir.mkdir(parents=True, exist_ok=True)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = CM.build_cases(rep)
    mhash = CM.matrix_sha256(cases)
    if a.arms:
        want = set(a.arms.split(","))
        cases = [c for c in cases if c["arm"] in want]
    if a.style != "both":
        cases = [c for c in cases if c.get("style") == a.style]
    if a.limit:
        cases = cases[:a.limit]
    if a.order == "reverse":
        # The gated runs execute the SAME frozen matrix in opposite arm order,
        # so that if they ever run concurrently they are not hitting the same
        # illegal encodings at the same moment. A contamination mitigation, not
        # a change of matrix.
        arms = []
        for c in cases:
            if not arms or arms[-1] != c["arm"]:
                arms.append(c["arm"])
        rank = dict((n, -i) for i, n in enumerate(arms))
        cases = sorted(cases, key=lambda c: (rank[c["arm"]], c["idx"]))

    # resume: never re-run or overwrite a case already recorded in this run
    done = set()
    jl = rundir / "sweep.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done.add(json.loads(ln)["idx"])
            except Exception:
                pass
        print("resume: %d cases already recorded" % len(done))

    work = EXP / "work" / ("run_%s" % a.run)
    inputs = write_inputs(work)
    log = S.Log(jl)
    blog = S.Log(rundir / "baseline.jsonl")

    carriers = {}
    seed_cache = {}
    baselines = {}
    hangs_field = {}
    hangs_arm = {}
    stopped = set()
    counters = dict(ok=0, silent_zero=0, wrong_value=0, fault=0, hang=0,
                    undecodable=0, victim=0, invalid=0, baseline_fail=0,
                    stopped_fields=0)
    env_written = False
    t0 = time.time()
    n = 0

    def get_carrier(case):
        style = case["style"]
        if style == "S":
            key = "S"
            if key not in carriers:
                carriers[key] = S.SynthCarrier(
                    EXP / "kernels" / "carrier_dag.metal", "k",
                    work, timeout=REQ_TIMEOUT)
            return carriers[key]
        key = "P:" + case["probe"]
        if key not in carriers:
            ins, outs, grid, tg, oidx = INPLACE_BIND[case["probe"]]
            carriers[key] = S.InPlaceCarrier(
                EXP / "kernels" / "probes.metal", case["probe"], work,
                dict((k, inputs[v]) for k, v in ins.items()), outs,
                grid, tg, timeout=REQ_TIMEOUT)
            carriers[key].out_index = oidx
        return carriers[key]

    def dispatch(case, car):
        """One dispatch. Returns (status, err, observed-dict-or-None)."""
        blk = bytes.fromhex(case["bytes"])
        if case["style"] == "S":
            prog = build_program(case, car.region_len, blk)
            resp, words = car.run_program(prog, grid=(8 if case["arm"]
                                                      == "GETSR/dump" else 1),
                                          tg=(8 if case["arm"] == "GETSR/dump"
                                              else 1))
            d = S.digest(words)
            return resp["status"], resp["error"], d, words
        # STYLE-P: `bytes` is the whole patched _agc.main
        resp, outs = car.run_patched(blk)
        words = outs.get(car.out_index, [])
        d = None
        if words:
            d = {"words": words,
                 "all_poison": all(w == H.POISON for w in words),
                 "poison_slots": [i for i, w in enumerate(words)
                                  if w == H.POISON]}
        return resp["status"], resp["error"], d, words

    def validity_for(case, status, err, d):
        if S.is_victim(err):
            return "invalid_victim"
        if status != "OK":
            return "valid"
        if d is None:
            return "invalid_nodata"
        if case["style"] == "S":
            return S.validity_of(status, err, d,
                                 terminating=(case["arm"] == "STOP/midprogram"))
        return "invalid_poison" if d["all_poison"] else "valid"

    def observe(case, car, want_valid=True):
        """Dispatch with victim/invalid retries. Returns a dict of the run."""
        attempts = []
        for k in range(RETRIES + 2):
            status, err, d, words = dispatch(case, car)
            val = validity_for(case, status, err, d)
            attempts.append({"status": status, "error": (err or "")[:200],
                             "os_class": S.os_class(err), "validity": val})
            if val == "valid":
                return {"status": status, "error": err, "d": d,
                        "words": words, "validity": val, "attempts": attempts}
            if val in ("invalid_victim", "invalid_poison", "invalid_nodata"):
                time.sleep(1.0 + 1.5 * k)
                if k == 2:
                    car.restart()
                continue
            return {"status": status, "error": err, "d": d, "words": words,
                    "validity": val, "attempts": attempts}
        return {"status": status, "error": err, "d": d, "words": words,
                "validity": val, "attempts": attempts}

    def baseline_for(case, car, force=False):
        key = case["arm"]
        if key in baselines and not force:
            return baselines[key]
        bc = dict(case)
        bc["bytes"] = case["anchor"]
        bc["role"] = "baseline"
        bc["field"] = "-"
        r = observe(bc, car)
        d = r["d"]
        blog.write({"arm": key, "status": r["status"],
                    "error": (r["error"] or "")[:200],
                    "validity": r["validity"],
                    "regs": (d["regs"] if (d and "regs" in d) else None),
                    "hash": (S.digest_hex(d) if (d and "regs" in d)
                             else words_digest(r["words"])),
                    "kind": "refresh" if force else "initial"})
        if r["validity"] != "valid" or d is None:
            counters["baseline_fail"] += 1
            return None
        baselines[key] = d
        return d

    cur_arm = None
    car = None
    for c in cases:
        if c["idx"] in done:
            continue
        if a.deadline_s and (time.time() - t0) > a.deadline_s:
            print("deadline reached; stopping cleanly at %d cases" % n)
            break
        if c["role"] == "arm_not_run":
            log.write(dict(c, outcome="undecodable", validity="valid",
                           observed=None, oracle=None, match=False,
                           moved=None, moved_slots=None, predicts="n/a",
                           rt_ok=None, victim=False, os_class=None,
                           attempts=[]))
            n += 1
            continue
        fkey = (c["arm"], c["field"])
        if fkey in stopped or c["arm"] in stopped:
            log.write(dict(c, outcome="undecodable", validity="valid",
                           observed=None, oracle=None, match=False,
                           moved=None, moved_slots=None, predicts="n/a",
                           rt_ok=None, victim=False, os_class=None,
                           attempts=[],
                           note="NOT DISPATCHED: hang budget exhausted for this "
                                "field/arm (FIELD-SWEEP-PROTOCOL section 8). "
                                "This is a SKIP PLACEHOLDER, not an "
                                "observation -- see analysis/rescore_0144.py "
                                "for what happens when those are conflated."))
            n += 1
            continue

        try:
            car = get_carrier(c)
        except Exception as e:
            log.write(dict(c, outcome="undecodable", validity="invalid_nodata",
                           observed=None, oracle=None, match=False, moved=None,
                           moved_slots=None, predicts="n/a", rt_ok=None,
                           victim=False, os_class=None, attempts=[],
                           note="carrier build failed: %s" % str(e)[:200]))
            n += 1
            continue

        if not env_written:
            (rundir / "00_env.json").write_text(json.dumps(
                dict(env_block(car.device, getattr(car, "region_len", 0)),
                     matrix_sha256=mhash, n_cases=len(cases),
                     run=a.run, order=a.order, style=a.style),
                indent=1, sort_keys=True))
            env_written = True

        if c["arm"] != cur_arm:
            cur_arm = c["arm"]
            b = baseline_for(c, car)
            print("[%s] arm %-24s baseline %s"
                  % (time.strftime("%H:%M:%S"), cur_arm, "OK" if b else "FAILED"))
        base = baselines.get(c["arm"])

        blk = bytes.fromhex(c["bytes"])
        rt_ok = H.round_trips(blk) if c["style"] == "S" else None

        r = observe(c, car)
        d = r["d"]
        status = r["status"]

        # ---- oracle ---------------------------------------------------
        expect = None
        oracle_kind = "baseline_null"
        pred = predicts(c)
        if c["style"] == "S" and base is not None and "regs" in base:
            seeds = seed_cache.setdefault(c.get("kind") or "int",
                                          H.seed_regs(c.get("kind") or "int"))
            if pred == "moves_to_slot_v":
                exp, _w = dst_oracle(c["value"], base["regs"], seeds)
                if exp is not None:
                    expect = {"regs": exp}
                    oracle_kind = "slot_pattern"
                else:
                    oracle_kind = "structural_anchor_not_single_slot"
            else:
                expect = {"regs": base["regs"]}
                oracle_kind = "baseline_null"

        # ---- outcome --------------------------------------------------
        if c["style"] == "S":
            outcome = S.classify_slots(status, d, base, expect)
            mv = S.moved_slots(d, base) if (d and base) else None
            moved = bool(mv) if mv is not None else None
            obs_rec = ({"digest": S.digest_hex(d), "regs": d["regs"],
                        "pre": d["pre"], "post": d["post"],
                        "probe": d["probe"], "tail_ok": d["tail_ok"]}
                       if d else None)
            orc_rec = {"kind": oracle_kind,
                       "regs": (expect["regs"] if expect else None),
                       "derived_from":
                           "the host-known seed table for the 15 unchanged "
                           "slots, plus the anchor's written value (one GPU "
                           "measurement reused across the whole sweep)"
                           if oracle_kind == "slot_pattern" else
                           "the unmutated anchor's register state"}
        else:
            if status == "HANG":
                outcome = "hang"
            elif status != "OK":
                outcome = "fault"
            elif d is None or base is None:
                outcome = "undecodable"
            elif d["words"] == base["words"]:
                outcome = "ok"
            else:
                bad = [i for i in range(min(len(d["words"]), len(base["words"])))
                       if d["words"][i] != base["words"][i]]
                outcome = "silent_zero" if all(d["words"][i] == 0 for i in bad) \
                    else "wrong_value"
            mv = None
            if d and base:
                mv = [i for i in range(min(len(d["words"]), len(base["words"])))
                      if d["words"][i] != base["words"][i]]
            moved = bool(mv) if mv is not None else None
            obs_rec = ({"hash": words_digest(d["words"]),
                        "words": d["words"][:64],
                        "n_poison_slots": len(d["poison_slots"]),
                        "poison_slots": d["poison_slots"][:64]}
                       if d else None)
            orc_rec = {"kind": "baseline_null",
                       "hash": words_digest(base["words"]) if base else None,
                       "derived_from": "the unmutated anchor's output buffer"}

        victim = any(x["validity"] == "invalid_victim" for x in r["attempts"])
        if r["validity"] != "valid":
            counters["invalid"] += 1
        if victim:
            counters["victim"] += 1
        counters[outcome] = counters.get(outcome, 0) + 1

        if outcome == "hang":
            hangs_field[fkey] = hangs_field.get(fkey, 0) + 1
            hangs_arm[c["arm"]] = hangs_arm.get(c["arm"], 0) + 1
            time.sleep(HANG_COOLDOWN_S)
            if hangs_field[fkey] >= MAX_HANGS_PER_FIELD:
                stopped.add(fkey)
                counters["stopped_fields"] += 1
                print("  !! FIELD STOPPED after %d hangs: %s.%s"
                      % (hangs_field[fkey], c["arm"], c["field"]))
            if hangs_arm[c["arm"]] >= MAX_HANGS_PER_ARM:
                stopped.add(c["arm"])
                print("  !! ARM STOPPED after %d hangs: %s"
                      % (hangs_arm[c["arm"]], c["arm"]))

        log.write(dict(c,
                       outcome=outcome, validity=r["validity"],
                       observed=obs_rec, oracle=orc_rec,
                       match=(outcome == "ok"),
                       moved=moved, moved_slots=mv, predicts=pred,
                       rt_ok=rt_ok, victim=victim,
                       os_class=S.os_class(r["error"]),
                       error=((r["error"] or "")[:200] or None),
                       attempts=r["attempts"]))
        n += 1

        if n % BASELINE_EVERY == 0:
            d2 = baseline_for(c, car, force=True)
            ok = (d2 is not None and base is not None and
                  ((d2.get("regs") == base.get("regs")) if "regs" in (base or {})
                   else (d2.get("words") == base.get("words"))))
            if not ok:
                print("  !! baseline drift at n=%d arm=%s -> restarting child"
                      % (n, c["arm"]))
                counters["baseline_fail"] += 1
                car.restart()
                baselines.pop(c["arm"], None)
                baseline_for(c, car)
        if n % 2000 == 0:
            el = time.time() - t0
            print("  %6d/%d  %.1f case/s  %s"
                  % (n, len(cases) - len(done), n / max(el, 1e-9),
                     json.dumps(counters, sort_keys=True)))
            (rundir / "01_progress.json").write_text(json.dumps(
                {"done": n, "counters": counters, "elapsed_s": round(el, 1),
                 "stopped": sorted(str(x) for x in stopped)},
                indent=1, sort_keys=True))

    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "counters": counters,
         "hangs": sum(getattr(c, "hangs", 0) for c in carriers.values()),
         "stopped": sorted(str(x) for x in stopped),
         "matrix_sha256": mhash,
         "elapsed_s": round(time.time() - t0, 1),
         "matrix_len": len(cases)}, indent=1, sort_keys=True))
    log.close()
    blog.close()
    for c in carriers.values():
        c.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
