#!/usr/bin/env python3
"""EXP-0180 sweep driver (G17P).

Runs the frozen case matrix through `harness/saferunner.py::SafePersistRunner` -- one live
device per carrier for the process lifetime, faults logged and continued past, and NO abort
path: every value dispatches regardless of outcome (FIELD-SWEEP-PROTOCOL 3(c)).

THE FOUR INSTRUMENTS, and what each one kills:

  PRE-DUMP  every case dumps all 16 GPRs BEFORE the block as well as after. "The seeds
            landed" is proved PER CASE. A case whose pre-dump does not match the frozen
            seed vector is `invalid_run` and can never be counted as movement. There is NO
            periodically refreshed baseline anywhere in this experiment -- which is what
            made DEF-0169-1 able to FABRICATE movement.
  POISON    the read-back is 0xDEADBEEF, so "wrote 0" and "never ran" are distinguishable.
            `carrier_dead` (PRE sentinel landed, everything after it still poison, status
            OK) is its own outcome and is never scored as an observation (EXP-0179 lost
            1,395 cases to exactly this, invisible against a zero-initialised buffer).
  SENTINELS PRE in memory before the block; POST written AFTER the block and after the
            dump, so the instruction under test cannot retroactively clobber it.
  SAFERUNNER one reader thread per child. Without it the FIRST hang silently manufactures
            every hang after it (DEF-0178-1), and a false hang is indistinguishable from a
            real inertness in a summary -- the exact failure this experiment must not make.

CLEAN-ROOM: process/file plumbing over our own tools; the only machine code spliced is the
compiled form of our own MSL.
"""
from __future__ import print_function

import argparse
import importlib.util
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H          # noqa: E402
import casematrix as M           # noqa: E402


def _tools():
    for cand in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (cand / "shdump" / "agxparse.py").exists():
            return cand
    raise RuntimeError("cannot locate tools/")


TOOLS = _tools()
sys.path.insert(0, str(TOOLS / "agxtest"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


agxparse = _load("agxparse", TOOLS / "shdump" / "agxparse.py")
import saferunner                # noqa: E402  (subclasses persistrun; see DEF-0178-1)

SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN = TOOLS / "agxtest" / "agxrun_persist"

VICTIM_MARKERS = ("InnocentVictim", "innocent victim", "Ignored (for causing prior",
                  "IOAF code 4", "IOAF code 2", "Discarded")


def is_victim(err):
    return bool(err) and any(m.lower() in err.lower() for m in VICTIM_MARKERS)


class Carrier:
    def __init__(self, cid, workdir, timeout=8.0):
        cfg = M.CARRIERS[cid]
        self.cid, self.cfg = cid, cfg
        self.seeds = cfg["seeds"]
        self.source = EXP / "kernels" / cfg["source"]
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        base = self.workdir / ("base_%s.bin" % cid)
        r = subprocess.run([str(SHDUMP), "-o", str(base), "-f", cfg["function"],
                            "--no-fast-math", str(self.source)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if r.returncode != 0 or not base.exists():
            raise RuntimeError("shdump failed for %s: %s" % (cid, r.stderr.decode()[-800:]))
        self.basebuf = base.read_bytes()
        loc = agxparse.locate_region(self.basebuf, "_agc.main")
        if loc is None:
            raise RuntimeError("could not locate _agc.main in %s" % cid)
        self.region_off, self.region_len = loc
        self.runner = saferunner.SafePersistRunner(
            source=str(self.source), function=cfg["function"], fast_math=False,
            agxrun_persist=str(AGXRUN))
        self.device = self.runner.device
        self.spliced = self.workdir / ("spliced_%s_%d.bin" % (cid, os.getpid()))
        self.poison = self.workdir / ("poison_%d.bin" % os.getpid())
        self.poison.write_bytes(struct.pack("<%dI" % H.OUT_WORDS, *([H.POISON] * H.OUT_WORDS)))
        self.hangs = 0
        self.variant = H.SEED_STAGE2_VARIANTS[0]

    def program(self, block):
        return H.synth_program(self.seeds, block, self.region_len,
                               slack=self.cfg["slack"],
                               consumer=(H.second_consumer(0x0D, 0x11)
                                         if self.cfg["consumer"] else None),
                               variant=self.variant)

    def dispatch(self, block, grid=1, tg=1):
        prog = self.program(block)
        buf = bytearray(self.basebuf)
        buf[self.region_off:self.region_off + self.region_len] = prog
        self.spliced.write_bytes(bytes(buf))
        resp = self.runner.request(archive=str(self.spliced), grid=grid, tg=tg,
                                   ins={0: str(self.poison)},
                                   outs={0: H.OUT_WORDS * 4}, timeout=self.timeout)
        if resp["status"] == "HANG":
            self.hangs += 1
        raw = resp["outs"].get(0, b"")
        words = [struct.unpack_from("<I", raw, i)[0] for i in range(0, len(raw) - 3, 4)]
        return resp, words

    def close(self):
        try:
            self.runner.close()
        except Exception:                                          # noqa: BLE001
            pass


def observe(words):
    """pre[], post[], both sentinels, and every OTHER word that is no longer poison."""
    if len(words) <= H.W_POST_SENT:
        return None
    pre = [words[H.W_PRE_REGS + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    post = [words[H.W_POST_REGS + i * H.STORE_STRIDE_WORDS] for i in range(H.N_REGS)]
    stray = [[i, words[i]] for i in range(len(words))
             if i not in H.KNOWN_WORDS and words[i] != H.POISON]
    return {"pre": pre, "post": post, "pre_sent": words[H.W_PRE_SENT],
            "post_sent": words[H.W_POST_SENT], "stray": stray[:48], "n_stray": len(stray)}


def digest(o):
    if o is None:
        return None
    return ("".join("%08x" % v for v in o["post"]) + "|%08x%08x" % (o["pre_sent"], o["post_sent"])
            + "|" + ",".join("%d:%08x" % (i, v) for i, v in o["stray"]))


def seed_ok(o, expected):
    if o is None:
        return False
    return all(o["pre"][i] == expected.get(i, 0) for i in range(H.N_REGS))


def classify(resp, o, anchor, expected):
    """Frozen outcome domain. Order matters: a failure to MEASURE is never an observation."""
    st = resp["status"]
    if st == "MALFORMED":
        return "measurement_failed"
    if st == "HANG":
        return "hang"
    if st != "OK":
        return "fault"
    if o is None:
        return "undecodable"
    if (o["pre_sent"] == H.SENT_PRE and o["post_sent"] == H.POISON
            and all(v == H.POISON for v in o["post"])):
        return "carrier_dead"
    if not seed_ok(o, expected):
        return "invalid_run"
    if anchor is None:
        return "ok"
    if o["post"] != anchor["post"]:
        bad = [i for i in range(H.N_REGS) if o["post"][i] != anchor["post"][i]]
        return "silent_zero" if all(o["post"][i] == 0 for i in bad) else "wrong_value"
    if o["stray"] != anchor["stray"] or o["post_sent"] != anchor["post_sent"] \
            or o["pre_sent"] != anchor["pre_sent"]:
        return "wrong_value"
    return "ok"


def markers_seen(o):
    """The LEN arm's read-out: how many of the four 2-byte mov_imm markers executed."""
    if o is None:
        return None
    return sum(1 for r, v in H.LEN_MARKERS if o["post"][r] == v)


class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(str(self.path), "a", buffering=1)
        self.n = 0

    def write(self, rec):
        self.n += 1
        rec = dict(rec)
        rec.setdefault("note", "")
        rec["seq"] = self.n
        rec["t"] = round(time.time(), 3)
        self.f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.f.flush()
        os.fsync(self.f.fileno())


def run_case(car, c, anchor, expected, log, attempts_max=3, grid=1, tg=1):
    """Dispatch one case. Retries only the classes that are NOT observations
    (measurement_failed / invalid_run / hang / victim); never breaks on the first non-fault,
    which is how EXP-0169's majority-of-3 failed to engage."""
    blk = bytes.fromhex(c["bytes"])
    attempts, out, o, resp = [], None, None, None
    for _ in range(attempts_max):
        resp, words = car.dispatch(blk, grid=grid, tg=tg)
        o = observe(words)
        out = classify(resp, o, anchor, expected)
        attempts.append({"outcome": out, "status": resp["status"],
                         "error": resp.get("error"), "victim": is_victim(resp.get("error")),
                         "raw": resp.get("raw", [])[:6]})
        if out not in ("measurement_failed", "invalid_run", "hang") and \
                not is_victim(resp.get("error")):
            break
    tok_mn, tok_len = H.tokenize_first(blk)
    rec = dict(c)
    rec.update(observed=o, outcome=out, status=resp["status"],
               fault_class=resp.get("error"), victim=is_victim(resp.get("error")),
               attempts=attempts, seed_ok=seed_ok(o, expected),
               sentinel_bad=(o is not None and o["pre_sent"] != H.SENT_PRE),
               tok_instr=tok_mn, tok_len=tok_len, rt_ok=H.round_trips(blk),
               hw_markers=markers_seen(o), geometry={"grid": grid, "tg": tg},
               match=(digest(o) == digest(anchor)) if anchor is not None else None,
               resp_raw=resp.get("raw", [])[:6])
    log.write(rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--order", choices=("forward", "reverse"), default="forward")
    ap.add_argument("--mode", choices=("pilot", "gated"), default="gated")
    ap.add_argument("--timeout", type=float, default=8.0)
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    if rundir.exists() and a.mode == "gated":
        raise SystemExit("run id %s already exists -- run ids are NEVER reused or topped up "
                         "(SUBAGENT_BRIEF.md). Burn it and take a new id." % a.run)
    rundir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("run_%s" % a.run)

    rep_path = EXP / "work" / "anchors" / "anchor_report.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    cases, misses = M.build_cases(rep)
    msha = M.matrix_sha256(cases)

    env = {"experiment": "EXP-0180-g17p-halfalu-rerecord", "run": a.run, "order": a.order,
           "mode": a.mode, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "matrix_cases": len(cases), "matrix_sha256": msha,
           "pins": H.assert_pins(), "python": sys.version.split()[0],
           "target": "G17P", "timeout_s": a.timeout,
           "seed_words": {"A": {str(k): v for k, v in H.SEED_A.items()},
                          "B": {str(k): v for k, v in H.SEED_B.items()}},
           "unresolved_arms": misses}
    (rundir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))

    log = Log(rundir / "sweep.jsonl")
    alog = Log(rundir / "anchor.jsonl")
    if a.mode == "pilot":
        # PRE_REGISTRATION.md 12b + amendment 01: the pilot runs the INSTRUMENTS only --
        # anchors, the three falsifiers, the five ladder steps, DSTNIB and the whole LEN
        # map -- at BOTH geometries for the `__` cases. Its job is to decide whether each
        # carrier is admissible at all; it is never evidence for a field verdict.
        cases = [c for c in cases if c["field"].startswith("__") or c["arm"] in ("LEN", "DSTNIB")]
    order = cases if a.order == "forward" else list(reversed(cases))

    carriers, anchors, counters = {}, {}, {}
    try:
        for c in order:
            cid = c["carrier"]
            if cid not in carriers:
                car = Carrier(cid, work / cid, timeout=a.timeout)
                carriers[cid] = car
                env.setdefault("devices", {})[cid] = car.device
                env.setdefault("regions", {})[cid] = car.region_len
                (rundir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))
            car = carriers[cid]
            expected = H.SEEDS[car.seeds][1]
            key = (c["arm"], cid)
            if key not in anchors:
                # ONE anchor observation per (arm, carrier) per run. NEVER refreshed.
                resp, words = car.dispatch(bytes.fromhex(c["anchor"]))
                o = observe(words)
                anchors[key] = o
                adq = H.adequacy({i: (o["pre"][i] if o else 0) for i in range(H.N_REGS)}) \
                    if o else (False, {"why": "no observation"})
                alog.write({"arm": c["arm"], "carrier": cid, "anchor": c["anchor"],
                            "observed": o, "status": resp["status"],
                            "error": resp.get("error"),
                            "seed_ok": seed_ok(o, expected),
                            "seed_adequacy_observed": {"ok": adq[0], "report": adq[1]},
                            "tok_instr": H.tokenize_first(bytes.fromhex(c["anchor"]))[0],
                            "hw_markers": markers_seen(o),
                            "seed_variant": car.variant,
                            "note": "captured ONCE per (arm,carrier) per run; never refreshed. "
                                    "seed_adequacy_observed is the FROZEN predicate evaluated "
                                    "on the ON-HARDWARE pre-dump."})
            geoms = [(1, 1)]
            if a.mode == "pilot" and c["arm"] not in ("LEN",):
                geoms.append((32, 32))          # 12b: geometry is MEASURED, not asserted
            for (g, t) in geoms:
                rec = run_case(car, c, anchors[key], expected, log, grid=g, tg=t)
                counters[rec["outcome"]] = counters.get(rec["outcome"], 0) + 1
            if log.n % 250 == 0:
                (rundir / "01_progress.json").write_text(json.dumps(
                    {"done": log.n, "of": len(cases), "counters": counters,
                     "hangs": {k: v.hangs for k, v in carriers.items()}},
                    indent=1, sort_keys=True))
    finally:
        for car in carriers.values():
            car.close()
        (rundir / "02_summary.json").write_text(json.dumps(
            {"cases": log.n, "of": len(cases), "counters": counters,
             "hangs": {k: v.hangs for k, v in carriers.items()},
             "matrix_sha256": msha}, indent=1, sort_keys=True))
    print(json.dumps({"run": a.run, "cases": log.n, "counters": counters,
                      "matrix_sha256": msha}, sort_keys=True))


if __name__ == "__main__":
    main()
