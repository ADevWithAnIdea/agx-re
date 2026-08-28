#!/usr/bin/env python3
"""EXP-0140 capture driver.

One `agxrun_persist` process per CARRIER (cases are ordered so the carrier
changes at most three times).  Every case appends ONE JSON object to
raw/<run_id>/sweep.jsonl with flush+fsync immediately, so a kill or a wedge
costs at most the case in flight (SUBAGENT_BRIEF.md).

CONTAMINATION DEFENCES (FIELD-SWEEP-PROTOCOL.md SS7 + EXP-0141 + EXP-0143):

  D1  UNIQUE SPLICE-ARCHIVE PATH PER REQUEST.  Reusing one path produces
      phantom `CMDBUF_ERROR`s (EXP-0141, ~8%).  Each request writes a fresh
      numbered file and unlinks it afterwards.

  D2  PRE-POISONED OUTPUT BUFFER + INTEGRITY SENTINEL.  Buffer 0 is bound as
      an INPUT filled with POISON_WORD(i), so an unwritten word is
      recognisable as unwritten rather than reading as a legal zero.  On the
      carriers with room (uni, cf) the generated program additionally stores a
      fixed SENTINEL value through three instructions that run BEFORE, and are
      independent of, the instruction under test.  A measurement whose
      sentinel is missing is `invalid_run` and is repeated.

  D3  NEVER CONCLUDE `fault` FROM ONE OBSERVATION.  Every case is replicated
      (2 trials; 3 whenever the first two disagree or either is not `ok`).  A
      case is only labelled `fault`/`hang` if that reproduces as the majority.
      The OS fault-classification string is recorded verbatim for every
      failing trial; `...ErrorInnocentVictim` failures are segregated as
      environmental (`invalid_run`), never as a property of the encoding.

  D4  PERIODIC BASELINE RE-VALIDATION.  Every `--baseline-every` cases the
      unmutated carrier is re-run and checked.  Two consecutive baseline
      failures mean a GPU error cascade: the runner process is restarted, and
      if the baseline still fails the run stops rather than recording the
      cascade as data.  Every check is written to the log as a
      `baseline_check` record.

SAFETY (FIELD-SWEEP-PROTOCOL.md SS8): two genuine hangs inside one arm abort
the remainder of THAT arm; `--cf-hang-budget` hangs across the control-flow
arms abort every remaining CF arm; `--global-hang-budget` aborts the run.
Aborted cases are recorded as `skipped`, never silently dropped.

Usage: run.py --run RUN_ID [--only PREFIX] [--limit N] [--raw-root DIR]
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
for p in ("tools/agx-isa", "tools/shdump", "tools/agxtest"):
    sys.path.insert(0, str(REPO / p))
sys.path.insert(0, str(HERE))
import isadb        # noqa: E402
import agxparse     # noqa: E402
from persistrun import PersistRunner  # noqa: E402
import cases as C   # noqa: E402
import isa_helpers as H  # noqa: E402
import baseline as B     # noqa: E402

CARRIER_SRC = {"uni": "carrier_uni.metal", "dsel5": "dsel5.metal",
                "gsel4": "gsel4.metal", "cf": "carrier_cf.metal"}
REQ_TIMEOUT = 8.0
ARM_HANG_BUDGET = 2
POISON_BYTES = 256          # words of poison pre-filled into buffer 0


def sha(b):
    return hashlib.sha256(b).hexdigest()


def u32s(raw, n):
    return [struct.unpack_from("<I", raw, 4 * i)[0] if 4 * i + 4 <= len(raw) else None
            for i in range(n)]


def f32bits(v):
    return struct.unpack("<I", struct.pack("<f", float(v)))[0]


def as_mode(u, mode):
    """Reinterpret a raw u32 output word in the case's own mode: int32 for int
    mode, the IEEE-754 bit pattern (kept as an integer, so JSON is exact) for
    float mode."""
    if u is None:
        return None
    return struct.unpack("<i", struct.pack("<I", u))[0] if mode == "int" else u


def oracle_words(case):
    if case["mode"] == "float":
        return {str(k): f32bits(v) for k, v in case["oracle"].items()}
    return {str(k): int(v) for k, v in case["oracle"].items()}


def poison_word(i, mode):
    return as_mode(struct.unpack("<I", struct.pack("<i", C.POISON_WORD(i)))[0], mode)


def classify(case, status, out_raw, err):
    """(observed, match, outcome, valid).

    `valid` is the integrity verdict (D2): the sentinel word must carry the
    sentinel value, or -- on the carriers with no room for one -- at least one
    oracle word must differ from its poison fill."""
    if status == "HANG":
        return {}, None, "hang", True
    if status != "OK":
        victim = "InnocentVictim" in (err or "")
        return {}, None, ("invalid_run" if victim else "fault"), (not victim)
    idxs = sorted(int(k) for k in case["oracle"])
    n = max(idxs + [case["sentinel"][0] if case["sentinel"] else 0]) + 1
    raw = u32s(out_raw, n)
    if any(raw[i] is None for i in idxs):
        return {str(i): None for i in idxs}, False, "invalid_run", False

    if case["sentinel"]:
        sidx, sval = case["sentinel"]
        valid = (raw[sidx] is not None and raw[sidx] == sval)
    else:
        valid = any(raw[i] != struct.unpack("<I", struct.pack("<i", C.POISON_WORD(i)))[0]
                    for i in idxs)

    observed = {str(i): as_mode(raw[i], case["mode"]) for i in idxs}
    orc = oracle_words(case)
    # Compare in the SAME representation the record stores, i.e. signed int32 for
    # int mode.  (Comparing a raw u32 against a signed oracle silently fails for
    # every value with bit 31 set -- a harness bug found after run02/run03 and
    # repaired in analysis for those captures; see analysis/verdicts.py.)
    obs_cmp = {str(i): (observed[str(i)] if case["mode"] == "int" else raw[i])
               for i in idxs}
    match = all(obs_cmp[k] == orc[k] for k in orc)
    if not valid:
        return observed, match, "invalid_run", False
    if match:
        outcome = "ok"
    else:
        prim = obs_cmp[str(idxs[0])]
        outcome = "silent_zero" if prim == 0 else "wrong_value"
    return observed, match, outcome, True


def make_inputs(work):
    work.mkdir(parents=True, exist_ok=True)
    paths = {}
    p = work / "poison_out.bin"
    p.write_bytes(b"".join(struct.pack("<i", C.POISON_WORD(i)) for i in range(POISON_BYTES)))
    paths["poison"] = str(p)
    p = work / "uni_mem.bin"
    p.write_bytes(b"".join(struct.pack("<i", 1000 + i) for i in range(64)))
    paths["uni_mem"] = str(p)
    for i, v in enumerate(C.MAGIC):
        p = work / ("uni_u%d.bin" % i)
        p.write_bytes(struct.pack("<I", v))
        paths["uni_u%d" % i] = str(p)
    for nm, vec in (("A1", C.SEL_A1), ("A2", C.SEL_A2)):
        p = work / ("sel_%s.bin" % nm)
        p.write_bytes(b"".join(struct.pack("<i", v) for v in vec))
        paths["sel_" + nm] = str(p)
    p = work / "cf_a.bin"
    p.write_bytes(b"".join(struct.pack("<f", v) for v in C.CF_A))
    paths["cf_a"] = str(p)
    p = work / "cf_n.bin"
    p.write_bytes(b"".join(struct.pack("<i", v) for v in C.CF_N))
    paths["cf_n"] = str(p)
    return paths


def ins_for(carrier, paths, invec="A1"):
    d = {0: paths["poison"]}          # D2: pre-poisoned output buffer
    if carrier == "uni":
        d.update({1: paths["uni_mem"], 2: paths["uni_u0"], 3: paths["uni_u1"],
                  4: paths["uni_u2"], 5: paths["uni_u3"]})
    elif carrier == "dsel5":
        d[1] = paths["sel_" + invec]
    elif carrier == "gsel4":
        d[1] = paths["sel_A1"]
    elif carrier == "cf":
        d.update({1: paths["cf_a"], 2: paths["cf_n"]})
    else:
        raise ValueError(carrier)
    return d


def splice(case, buf, roff, mainlen):
    b = bytearray(buf)
    if "prog" in case:
        prog = case["prog"]
        assert len(prog) == mainlen, (len(prog), mainlen)
        b[roff:roff + mainlen] = prog
    elif "patch" in case:
        off, val = case["patch"]
        b[roff + off] = val
    elif "patch3" in case:
        off, blob = case["patch3"]
        b[roff + off:roff + off + len(blob)] = blob
    else:
        raise ValueError("case has no splice directive")
    return bytes(b)


def roundtrip_note(spliced, roff, mainlen):
    """Does OUR OWN decoder still tokenize the spliced region cleanly?  Recorded
    as db-defect evidence; never used to skip a case -- the hardware does not
    consult our decoder.  EXP-0148 warns tokenization is NON-LOCAL, so this is
    a property of the whole region, not of the spliced instruction alone."""
    main = bytes(spliced[roff:roff + mainlen])
    try:
        recs, leftover = isadb.disassemble(main)
        if leftover:
            return "leftover:%d" % len(leftover)
        for r in recs:
            if r.get("mnemonic") == "<unknown>":
                return "unknown"
        return "clean"
    except Exception as e:                       # pragma: no cover
        return "error:%s" % type(e).__name__


class Bench:
    """Owns the persistent runner, the unique-archive-path counter (D1) and the
    periodic baseline re-validation (D4)."""

    def __init__(self, bin_dir, spdir, paths, timeout):
        self.bin_dir = Path(bin_dir)
        self.spdir = Path(spdir)
        self.spdir.mkdir(parents=True, exist_ok=True)
        self.paths = paths
        self.timeout = timeout
        self.runner = None
        self.carrier = None
        self.seq = 0

    def use(self, carrier):
        if carrier != self.carrier:
            self.close()
            src = EXP / "kernels" / CARRIER_SRC[carrier]
            # A FOURTH contamination mode, seen killing this experiment's own run03 at
            # case 7365: under many concurrent agents `MTLCompilerService` can become
            # unavailable ("Reentrancy avoided"), so the persistent runner cannot even
            # start.  That is a property of the machine, not of any encoding -- back off
            # and retry rather than losing the capture.
            last = None
            for attempt in range(6):
                try:
                    self.runner = PersistRunner(
                        source=str(src), function="k", fast_math=False,
                        agxrun_persist=str(self.bin_dir / "agxrun_persist"))
                    self.carrier = carrier
                    return
                except Exception as e:                        # noqa: BLE001
                    last = e
                    print("runner start failed (%d/6): %s" % (attempt + 1, e), flush=True)
                    time.sleep(5 * (attempt + 1))
            raise RuntimeError("agxrun_persist would not start after 6 attempts: %s" % last)

    def restart(self):
        c = self.carrier
        self.close()
        self.carrier = None
        self.use(c)

    def close(self):
        if self.runner:
            try:
                self.runner.close()
            except Exception:
                pass
        self.runner = None

    def submit(self, spliced, grid, tg, ins, nwords):
        """One dispatch on a UNIQUE archive path (D1)."""
        self.seq += 1
        pth = self.spdir / ("sp_%08d.bin" % self.seq)
        pth.write_bytes(spliced)
        try:
            rp = self.runner.request(archive=str(pth), grid=grid, tg=tg, ins=ins,
                                      outs={0: max(4 * nwords, 8)}, timeout=self.timeout)
        finally:
            try:
                pth.unlink()
            except OSError:
                pass
        return rp

    def attempt(self, spliced, grid, tg, ins, nwords):
        """One measurement, retrying immediately past `InnocentVictim` (D3)."""
        att, errs = 0, []
        while True:
            att += 1
            rp = self.submit(spliced, grid, tg, ins, nwords)
            errs.append(rp.get("error"))
            if rp["status"] == "OK" or att >= 4:
                return rp, att, errs
            if "InnocentVictim" not in (rp.get("error") or ""):
                return rp, att, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--groups", default=None,
                    help="comma-separated exact group names to capture")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=REQ_TIMEOUT)
    ap.add_argument("--cf-hang-budget", type=int, default=6)
    ap.add_argument("--global-hang-budget", type=int, default=10)
    ap.add_argument("--baseline-every", type=int, default=250)
    ap.add_argument("--raw-root", default=None)
    a = ap.parse_args()

    run_dir = (Path(a.raw_root) / a.run) if a.raw_root else (EXP / "raw" / a.run)
    if run_dir.exists():
        sys.exit("run id %s already exists -- never reuse or overwrite a run id" % a.run)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("run_" + a.run)
    bin_dir = EXP / "work" / "bin"

    facts = B.derive(str(bin_dir), str(work / "baseline_bin"))
    mainlens = {k: v["main_len"] for k, v in facts.items()}
    cs = C.build_cases(mainlens)
    if a.only:
        cs = [c for c in cs if c["group"].startswith(a.only)]
    if a.groups:
        want = set(a.groups.split(","))
        cs = [c for c in cs if c["group"] in want]
    if a.limit:
        cs = cs[:a.limit]

    paths = make_inputs(work)
    arch = {}
    for name, fn in CARRIER_SRC.items():
        buf, roff, main = B.compile_carrier(bin_dir, EXP / "kernels" / fn,
                                             work / (name + "_base.bin"))
        arch[name] = (buf, roff, len(main))

    # the unmutated-carrier reference outputs used by D4
    ref_cases = {}
    for c in cs:
        if c["carrier"] not in ref_cases and c["carrier"] in ("uni", "cf"):
            ref_cases[c["carrier"]] = None
    baseline_ref = {
        "uni": dict(carrier="uni", dispatch=(1, 1), mode="int",
                     prog=H.build_program(
                         list(H.sentinel_prologue(C.UNI_SLOT_OUT, C.UNI_SENT_IDX))
                         + [H.mov_imm(j, C.POISON) for j in range(16)]
                         + [H.mov_imm(15, 0),
                            H.device_store(15, 0, C.UNI_SLOT_OUT, data_reg=3),
                            H.stop()], mainlens["uni"]),
                     oracle={0: C.POISON}, sentinel=[C.UNI_SENT_IDX, C.SENT_VAL],
                     note="baseline", expect_match=True),
        "cf": dict(carrier="cf", dispatch=(8, 8), mode="float",
                    prog=H.cf_program(carrier_len=mainlens["cf"]),
                    oracle=C.cf_baseline_oracle(), sentinel=None,
                    note="baseline", expect_match=True),
        "dsel5": dict(carrier="dsel5", dispatch=(8, 8), mode="int",
                       patch3=(C.SEL_INSTR_OFF + 1, bytes(C.SEL_BASE_BODY)),
                       oracle=C._sel_oracle(C.SEL_A1, C.SEL_TRUE, C.SEL_FALSE),
                       sentinel=None, note="baseline", expect_match=True),
        "gsel4": dict(carrier="gsel4", dispatch=(8, 8), mode="int",
                       patch3=(C.PSEL_INSTR_OFF + 1, bytes(C.PSEL_BASE_BODY)),
                       oracle=C._psel_oracle(C.PSEL_TRUE, C.PSEL_FALSE, 8),
                       sentinel=None, note="baseline", expect_match=True),
    }

    inputs_rec = {
        "run": a.run, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": "local Apple M4 / G16G", "n_cases": len(cs),
        "carriers": {k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                     for k, v in facts.items()},
        "carrier_tokens": {k: v["tokens"] for k, v in facts.items()},
        "inputs": {"uni_magic": ["0x%08x" % m for m in C.MAGIC],
                    "sel_A1": C.SEL_A1, "sel_A2": C.SEL_A2,
                    "cf_a": C.CF_A, "cf_n": C.CF_N, "poison": C.POISON,
                    "poison_word0": C.POISON_WORD(0), "sentinel_value": C.SENT_VAL,
                    "uni_sentinel_idx": C.UNI_SENT_IDX, "cf_sentinel_idx": H.CF_SENT_IDX},
        "timeouts": {"per_request_s": a.timeout},
        "defences": {"unique_archive_path_per_request": True,
                      "poisoned_output_buffer": True,
                      "integrity_sentinel": ["uni", "cf"],
                      "replication_trials_min": 2, "replication_trials_max": 3,
                      "innocent_victim_retries": 4,
                      "baseline_every": a.baseline_every},
        "hang_budgets": {"per_arm": ARM_HANG_BUDGET, "cf_total": a.cf_hang_budget,
                          "global": a.global_hang_budget},
        "tool_sha256": {
            "isadb.py": sha((REPO / "tools/agx-isa/isadb.py").read_bytes()),
            "db.json": sha((REPO / "tools/agx-isa/db.json").read_bytes()),
            "agxrun_persist.m": sha((REPO / "tools/agxtest/agxrun_persist.m").read_bytes()),
            "persistrun.py": sha((REPO / "tools/agxtest/persistrun.py").read_bytes()),
            "shdump.m": sha((REPO / "tools/shdump/shdump.m").read_bytes()),
        },
        "harness_sha256": {p.name: sha(p.read_bytes())
                            for p in sorted((EXP / "harness").glob("*.py"))},
        "kernel_sha256": {p.name: sha(p.read_bytes())
                           for p in sorted((EXP / "kernels").glob("*.metal"))},
        "git_rev": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                                   capture_output=True, text=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                                          capture_output=True, text=True).stdout.strip()),
    }
    (run_dir / "00_inputs.json").write_text(json.dumps(inputs_rec, indent=1, sort_keys=True))

    fh = open(run_dir / "sweep.jsonl", "a")
    bench = Bench(bin_dir, work / "spliced", paths, a.timeout)
    arm_hangs, cf_hangs, total_hangs = {}, 0, 0
    dead_arms, cf_dead = set(), False
    invalid_runs, baseline_fail_streak, aborted = 0, 0, None
    t0 = time.time()

    def emit(rec):
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush(); os.fsync(fh.fileno())

    def measure(case, invec="A1"):
        buf, roff, mainlen = arch[case["carrier"]]
        spliced = splice(case, buf, roff, mainlen)
        rt = roundtrip_note(spliced, roff, mainlen)
        grid, tg = case["dispatch"]
        nwords = max([int(k) for k in case["oracle"]]
                      + ([case["sentinel"][0]] if case["sentinel"] else [0])) + 1
        ins = ins_for(case["carrier"], paths, invec)
        trials = []
        for t in range(3):
            rp, att, errs = bench.attempt(spliced, grid, tg, ins, nwords)
            o, m, oc, ok = classify(case, rp["status"], rp["outs"].get(0, b""),
                                     rp.get("error"))
            trials.append({"resp": rp, "attempts": att, "errors": errs,
                            "observed": o, "match": m, "outcome": oc, "valid": ok})
            if t == 0 and oc == "ok":
                continue
            if t == 1:
                k0 = (trials[0]["outcome"], json.dumps(trials[0]["observed"], sort_keys=True))
                k1 = (trials[1]["outcome"], json.dumps(trials[1]["observed"], sort_keys=True))
                if k0 == k1 and trials[0]["outcome"] == "ok":
                    break
                # D3: any non-`ok` observation gets a third look before it is believed
        keys = [(t["outcome"], json.dumps(t["observed"], sort_keys=True)) for t in trials]
        winner = max(set(keys), key=keys.count)
        pick = trials[keys.index(winner)]
        return trials, pick, len(set(keys)) > 1, rt, spliced, roff, mainlen

    try:
        for n, c in enumerate(cs):
            arm = c["arm"]
            is_cf = (c["carrier"] == "cf")
            skip = None
            if aborted:
                skip = aborted
            elif arm in dead_arms:
                skip = "arm_stopped_after_%d_hangs" % ARM_HANG_BUDGET
            elif is_cf and cf_dead:
                skip = "cf_arm_stopped_after_%d_hangs" % a.cf_hang_budget
            elif total_hangs >= a.global_hang_budget:
                skip = "run_stopped_after_%d_hangs" % a.global_hang_budget
            if skip:
                emit({"kind": "case", "instr": c["instr"], "field": c["field"],
                      "value": c["value"], "bytes": c["bytes"], "observed": {},
                      "oracle": {}, "match": None, "outcome": "skipped",
                      "carrier": c["carrier"], "note": skip, "i": c["i"],
                      "group": c["group"], "arm": arm,
                      "expect_match": c["expect_match"], "status": "SKIPPED"})
                continue

            bench.use(c["carrier"])

            # ---- D4 periodic baseline re-validation ------------------------
            if a.baseline_every and n % a.baseline_every == 0:
                ref = baseline_ref[c["carrier"]]
                bt, bp, bu, _, _, _, _ = measure(ref)
                emit({"kind": "baseline_check", "at_case": n, "carrier": c["carrier"],
                      "outcome": bp["outcome"], "match": bp["match"],
                      "observed": bp["observed"],
                      "oracle": oracle_words(ref), "unstable": bu,
                      "statuses": [t["resp"]["status"] for t in bt],
                      "errors": [t["errors"] for t in bt],
                      "elapsed_s": round(time.time() - t0, 1)})
                if bp["outcome"] != "ok":
                    baseline_fail_streak += 1
                    print("BASELINE FAIL #%d at case %d (%s)"
                          % (baseline_fail_streak, n, bp["outcome"]), flush=True)
                    bench.restart()
                    bt2, bp2, _, _, _, _, _ = measure(ref)
                    emit({"kind": "baseline_check", "at_case": n, "carrier": c["carrier"],
                          "outcome": bp2["outcome"], "match": bp2["match"],
                          "observed": bp2["observed"], "oracle": oracle_words(ref),
                          "note": "after runner restart",
                          "statuses": [t["resp"]["status"] for t in bt2],
                          "errors": [t["errors"] for t in bt2],
                          "elapsed_s": round(time.time() - t0, 1)})
                    if bp2["outcome"] != "ok":
                        aborted = "aborted_baseline_cascade_at_case_%d" % n
                        print("  -> ABORTING: baseline still failing after restart",
                              flush=True)
                        continue
                else:
                    baseline_fail_streak = 0

            trials, pick, unstable, rt, spliced, roff, mainlen = measure(
                c, c.get("inputs", "A1"))
            outcome = pick["outcome"]
            if outcome == "invalid_run":
                invalid_runs += 1

            emit({"kind": "case", "instr": c["instr"], "field": c["field"],
                  "value": c["value"], "bytes": c["bytes"],
                  "observed": pick["observed"], "oracle": oracle_words(c),
                  "match": pick["match"], "outcome": outcome, "carrier": c["carrier"],
                  "note": c["note"], "i": c["i"], "group": c["group"], "arm": arm,
                  "expect_match": c["expect_match"],
                  "status": pick["resp"]["status"], "mode": c["mode"],
                  "dispatch": list(c["dispatch"]), "inputs": c.get("inputs"), "rt": rt,
                  "attempts": pick["attempts"],
                  "fault_class": pick["resp"].get("error"),
                  "trial_statuses": [t["resp"]["status"] for t in trials],
                  "trial_outcomes": [t["outcome"] for t in trials],
                  "trial_errors": [t["errors"] for t in trials],
                  "replicates": len(trials), "unstable": unstable,
                  "sentinel_ok": pick["valid"],
                  "prog_sha256": sha(spliced[roff:roff + mainlen]),
                  "restarted": any(t["resp"].get("restarted") for t in trials)})

            if outcome == "hang":
                total_hangs += 1
                arm_hangs[arm] = arm_hangs.get(arm, 0) + 1
                if is_cf:
                    cf_hangs += 1
                print("HANG #%d arm=%s value=%s" % (total_hangs, arm, c["value"]), flush=True)
                if arm_hangs[arm] >= ARM_HANG_BUDGET:
                    dead_arms.add(arm)
                    print("  -> STOPPING arm %s" % arm, flush=True)
                if is_cf and cf_hangs >= a.cf_hang_budget:
                    cf_dead = True
                    print("  -> STOPPING all CF arms (%d hangs)" % cf_hangs, flush=True)
            if n % 500 == 0:
                print("[%5d/%5d] %-30s %.1fs inv=%d" % (n, len(cs), c["group"],
                                                         time.time() - t0, invalid_runs),
                      flush=True)
    finally:
        bench.close()
        fh.close()
    dur = time.time() - t0
    summary = {"run": a.run, "n_cases": len(cs), "duration_s": round(dur, 1),
               "hangs": total_hangs, "cf_hangs": cf_hangs,
               "invalid_runs": invalid_runs,
               "arms_stopped": sorted(dead_arms), "cf_arm_stopped": cf_dead,
               "aborted": aborted,
               "sweep_sha256": sha((run_dir / "sweep.jsonl").read_bytes())}
    (run_dir / "01_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
