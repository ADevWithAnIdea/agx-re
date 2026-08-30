#!/usr/bin/env python3
"""EXP-0203 sweep driver (G17P) -- the run loop that carries a HOST ORACLE.

Instruments, and what each one kills:

  ORACLE     every case carries a host-computed predicted 16-word post-dump, derived from
             THAT case's own observed pre-dump.  EXP-0180's records had no `oracle` key at
             all, so nothing in them could discriminate one field value from another.
  PRE-DUMP   the seeds are proved to have landed PER CASE.  There is NO refreshed baseline
             anywhere; a case whose pre-dump differs from the frozen seed vector is
             `invalid_run` and can never be counted as movement.
  POISON     the read-back is 0xDEADBEEF, so "wrote 0" and "never ran" are distinguishable.
             `carrier_dead` is its own outcome and is never scored as an observation.
  SENTINELS  PRE in memory before the block; POST written after the block AND after the
             dump, from a register re-materialized at that moment.
  MARKERS    four 2-byte mov_imm markers follow the instruction under test; the number that
             survives measures the HARDWARE's consumed length, so an identity-changing value
             can never be scored as movement.
  SAFERUNNER one reader thread per child (DEF-0178-1); a malformed response is a MEASUREMENT
             FAILURE, never a hang, never an observation.

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
import oracle as O               # noqa: E402
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
import saferunner                # noqa: E402

SHDUMP = TOOLS / "shdump" / "shdump"
AGXRUN = TOOLS / "agxtest" / "agxrun_persist"

KERNEL = {"A": "carrier_a.metal", "B": "carrier_b.metal"}

VICTIM_MARKERS = ("InnocentVictim", "innocent victim", "Ignored (for causing prior",
                  "IOAF code 4", "IOAF code 2", "Discarded")


def is_victim(err):
    return bool(err) and any(m.lower() in err.lower() for m in VICTIM_MARKERS)


class Carrier:
    """One live device per MSL kernel for the process lifetime."""

    def __init__(self, cid, workdir, timeout=8.0):
        self.cid = cid
        self.source = EXP / "kernels" / KERNEL[cid]
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        base = self.workdir / ("base_%s.bin" % cid)
        r = subprocess.run([str(SHDUMP), "-o", str(base), "-f", "k",
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
            source=str(self.source), function="k", fast_math=False,
            agxrun_persist=str(AGXRUN))
        self.device = self.runner.device
        self.spliced = self.workdir / ("spliced_%s_%d.bin" % (cid, os.getpid()))
        self.poison = self.workdir / ("poison_%d.bin" % os.getpid())
        self.poison.write_bytes(struct.pack("<%dI" % H.OUT_WORDS, *([H.POISON] * H.OUT_WORDS)))
        self.hangs = 0

    def dispatch(self, plan, block, grid=1, tg=1):
        prog = H.synth_program(plan, block, self.region_len)
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


# --------------------------------------------------------------------------
def observe(words):
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
    return (O.digest(o["post"]) + "|%08x%08x" % (o["pre_sent"], o["post_sent"])
            + "|" + ",".join("%d:%08x" % (i, v) for i, v in o["stray"]))


def seed_ok(o, expected):
    return o is not None and all(o["pre"][i] == expected.get(i, 0) for i in range(H.N_REGS))


def markers_seen(o, lay):
    if o is None:
        return None
    return sum(1 for r, v in lay.markers if o["post"][r] == v)


def classify(resp, o, anchor, expected):
    """Frozen outcome domain.  Order matters: a failure to MEASURE is never an observation."""
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


def predict(case, o, lay, hp_model):
    """The host oracle for one case, computed from the case's OWN observed pre-dump."""
    if o is None:
        return None, None
    pre = o["pre"]
    kind = case.get("oracle_kind", "model")
    blk = bytes.fromhex(case["bytes"] if kind == "model" else case["anchor"])
    if case.get("oracle_dst_override") is not None:
        blk = bytes([(case["oracle_dst_override"] << 4) | (blk[0] & 0xF)]) + blk[1:]
    if case["instr"] == "half_alu_fma12":
        orc = O.fma12_predict(pre, blk, lay)
    else:
        orc = O.halfpack_predict(pre, blk, lay, hp_model)
    nul = O.null_predict(pre, lay)
    return orc, nul


def alt2r_match(o, orc, case):
    """Would the TWO-ROUNDING (unfused) prediction have matched?  Recorded per case so a
    fused/unfused disagreement is MEASURED rather than assumed (PRE_REGISTRATION 4.3)."""
    if o is None or orc is None or case["instr"] != "half_alu_fma12":
        return None
    d = orc.get("dst")
    if d is None or orc.get("alt2r") is None:
        return None
    return o["post"][d] == ((o["pre"][d] & 0xFFFF0000) | orc["alt2r"])


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


def run_case(car, plan, c, anchor, expected, log, hp_model, attempts_max=3, grid=1, tg=1):
    """Dispatch one case.  Retries only the classes that are NOT observations."""
    lay = plan["lay"]
    blk = bytes.fromhex(c["bytes"]) + H.marker_chain(lay)
    attempts, out, o, resp = [], None, None, None
    for _ in range(attempts_max):
        resp, words = car.dispatch(plan, blk, grid=grid, tg=tg)
        o = observe(words)
        out = classify(resp, o, anchor, expected)
        attempts.append({"outcome": out, "status": resp["status"],
                         "error": resp.get("error"), "victim": is_victim(resp.get("error")),
                         "raw": resp.get("raw", [])[:6]})
        if out not in ("measurement_failed", "invalid_run", "hang") and \
                not is_victim(resp.get("error")):
            break
    orc, nul = predict(c, o, lay, hp_model)
    tok_mn, tok_len = H.tokenize_first(bytes.fromhex(c["bytes"]))
    mk = markers_seen(o, lay)
    anchor_mk = markers_seen(anchor, lay) if anchor else None
    anchor_tok = H.tokenize_first(bytes.fromhex(c["anchor"]))[0]
    rec = dict(c)
    rec.update(observed=o, outcome=out, status=resp["status"],
               fault_class=resp.get("error"), victim=is_victim(resp.get("error")),
               attempts=attempts, seed_ok=seed_ok(o, expected),
               sentinel_bad=(o is not None and o["pre_sent"] != H.SENT_PRE),
               tok_instr=tok_mn, tok_len=tok_len,
               rt_ok=H.round_trips(bytes.fromhex(c["bytes"])),
               hw_markers=mk,
               identity_changed=((mk != anchor_mk) or (tok_mn != anchor_tok))
                                if (o is not None and anchor is not None) else None,
               oracle=orc,
               oracle_match=(orc is not None and o is not None and o["post"] == orc["post"]),
               oracle_match_alt2r=alt2r_match(o, orc, c),
               null_match=(nul is not None and o is not None and o["post"] == nul["post"]),
               hp_model_fits=(O.hp_model_fits(o["pre"], o["post"], bytes.fromhex(c["bytes"]), lay)
                              if (o is not None and c["instr"] == "half_pack") else None),
               geometry={"grid": grid, "tg": tg},
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
    ap.add_argument("--hp-model", default=O.HP_PRIMARY)
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    if rundir.exists() and a.mode == "gated":
        raise SystemExit("run id %s already exists -- run ids are NEVER reused or topped up "
                         "(SUBAGENT_BRIEF.md). Burn it and take a new id." % a.run)
    rundir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("run_%s" % a.run)

    cases = M.build_cases()
    msha = M.matrix_sha256(cases)
    env = {"experiment": "EXP-0203-g17p-half-oracle", "run": a.run, "order": a.order,
           "mode": a.mode, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "matrix_cases": len(cases), "matrix_sha256": msha,
           "pins": H.assert_pins(), "python": sys.version.split()[0],
           "target": "G17P", "timeout_s": a.timeout,
           "hp_model": a.hp_model, "fma12_model": O.FMA12_PRIMARY,
           "layouts": {k: v.as_json() for k, v in H.LAYOUTS.items()},
           "seed_words": {"%s/%s" % (s, l): {str(k): v for k, v in
                                             H.seed_plan(s, l)["words"].items()}
                          for s in ("A", "B") for l in ("HI", "LO")}}
    (rundir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))

    if a.mode == "pilot":
        keep = set()
        cases = [c for c in cases
                 if c["field"].startswith("__")
                 or (c["field"] == "dst")
                 or (c["field"] == "ext" and c["byte_index"] == 4)
                 or (c["instr"] == "half_pack" and c["value"] % 16 == 13)]
    order = cases if a.order == "forward" else list(reversed(cases))

    log = Log(rundir / "sweep.jsonl")
    alog = Log(rundir / "anchor.jsonl")
    carriers, plans, anchors, counters = {}, {}, {}, {}
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
            pkey = (c["seeds"], c["layout"])
            if pkey not in plans:
                plans[pkey] = H.seed_plan(*pkey)
            plan = plans[pkey]
            expected = plan["words"]
            key = c["arm"]
            if key not in anchors:
                # ONE anchor observation per arm per run.  NEVER refreshed.
                resp, words = car.dispatch(
                    plan, bytes.fromhex(c["anchor"]) + H.marker_chain(plan["lay"]))
                o = observe(words)
                anchors[key] = o
                adq = H.adequacy({i: (o["pre"][i] if o else 0) for i in range(H.N_REGS)},
                                 plan["lay"]) if o else (False, {"why": "no observation"})
                orc, _ = predict({"instr": c["instr"], "bytes": c["anchor"],
                                  "anchor": c["anchor"], "oracle_kind": "model"},
                                 o, plan["lay"], a.hp_model)
                alog.write({"arm": key, "carrier": cid, "layout": c["layout"],
                            "seeds": c["seeds"], "anchor": c["anchor"],
                            "observed": o, "status": resp["status"],
                            "error": resp.get("error"), "seed_ok": seed_ok(o, expected),
                            "seed_adequacy_observed": {"ok": adq[0], "report": adq[1]},
                            "oracle": orc,
                            "oracle_match": (orc is not None and o is not None
                                             and o["post"] == orc["post"]),
                            "tok_instr": H.tokenize_first(bytes.fromhex(c["anchor"]))[0],
                            "hw_markers": markers_seen(o, plan["lay"]),
                            "note": "captured ONCE per arm per run; never refreshed. "
                                    "seed_adequacy_observed is the FROZEN predicate "
                                    "evaluated on the ON-HARDWARE pre-dump."})
            rec = run_case(car, plan, c, anchors[key], expected, log, a.hp_model)
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
