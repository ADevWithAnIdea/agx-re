#!/usr/bin/env python3
"""EXP-0158 per-case executor (G17P).

Builds the case's input buffers, invokes tools/agxtest/agxtest.py as a fresh
subprocess (splice-and-run on the real A18 Pro), parses the OUT hex, and
classifies the result.  One case per process invocation; run.py launches one
subprocess per case and never re-runs a case in place.

FIELD-SWEEP-PROTOCOL.md section 7 compliance, all of it visible here:

  * POISONED READ-BACK.  Buffer 0 is pre-filled with 0xDEADBEEF words before
    the dispatch, so a word that was never written is distinguishable from a
    word that was written with 0.0.  `no_write` and `silent_zero` are
    different observations and are recorded as different outcomes.
  * INTEGRITY SENTINEL.  Every `dag`-carrier program writes a fixed constant
    to out word 252 through a mov_imm -> device_store path that contains no
    falu2/falu2i/device_load.  A wrong or still-poisoned sentinel means the
    program did not run or was not spliced, and the case is `invalid_run` --
    NOT evidence about the field under test.
  * FAULT CLASS.  The OS's own classification string (e.g.
    `kIOGPUCommandBufferCallbackErrorInnocentVictim` vs `...ErrorHang`) is
    captured verbatim on every non-OK case, so a sibling agent's cascade is
    identifiable rather than silently recorded as a property of our encoding.
  * UNIQUE SPLICE-ARCHIVE PATH.  Every invocation gets its own workdir, so the
    compiled archive and the spliced archive are per-request files that no
    concurrent process can share.

Usage: case_exec.py --case-index N --run-dir DIR --bin-dir DIR --repo DIR
Prints one JSON object to stdout (the complete case record).
"""
import argparse
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402
import generator as G    # noqa: E402
import synth as S        # noqa: E402

CARRIER_DAG = "carrier_dag.metal"
CARRIER_CF = "carrier_cf.metal"
OUT_WORDS = CM.OUT_WORDS
POISON_F = S.bits_f32(S.POISON_U32)


def build_dag_buffers(work):
    (work / "mem.bin").write_bytes(b"".join(struct.pack("<f", v) for v in G.MEM_WORDS))
    (work / "imem.bin").write_bytes(b"".join(struct.pack("<i", v) for v in G.IMEM_WORDS))
    (work / "poison.bin").write_bytes(struct.pack("<I", S.POISON_U32) * OUT_WORDS)
    return work / "mem.bin", work / "imem.bin", work / "poison.bin"


def classify_word(got, expected):
    if got is None:
        return "missing"
    if got == POISON_F:
        return "no_write"
    if got == expected:
        return "ok"
    if got == 0.0:
        return "silent_zero"
    return "wrong_value"


def classify_bits(got, expected):
    if got is None:
        return "missing"
    if got == S.POISON_U32:
        return "no_write"
    if got == expected:
        return "ok"
    if got == 0:
        return "silent_zero"
    return "wrong_value"


def decode_case(c, out_hex):
    """Exact comparison per word.  Float families compare IEEE-754 `==` (the ISA
    is deterministic; the standing convention of every prior program-level
    experiment here).  INTEGER families compare the RAW 32-BIT WORD, because a
    negative integer result's bit pattern is a NaN and NaN != NaN would report
    a false failure.
    Returns (observed, per-word outcomes, overall match, sentinel value)."""
    raw = bytes.fromhex(out_hex)
    words = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    uwords = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    observed, outcomes = {}, {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        got = words[idx] if idx < len(words) else None
        observed[k] = got
        outcomes[k] = classify_word(got, expected)
        ok = ok and (got == expected)
    for k, expected in c.get("oracle_bits", {}).items():
        idx = int(k)
        got = uwords[idx] if idx < len(uwords) else None
        observed[k] = got
        outcomes[k] = classify_bits(got, expected)
        ok = ok and (got == expected)
    sent = None
    if c.get("sentinel"):
        si = S.sentinel_word_index()
        sent = words[si] if si < len(words) else None
    return observed, outcomes, ok, sent


VICTIM_RETRIES = 5


def run_one(c, args):
    """Runs the case, retrying ONLY on an `InnocentVictim` command-buffer
    failure.  That class means the driver discarded our command buffer because
    a DIFFERENT process's work faulted and the device reset -- it is evidence
    about the machine, not about our encoding, so recording it as a result
    would be a confident wrong label (FIELD-SWEEP-PROTOCOL.md section 7,
    NEO-TARGET-BRIEF.md).  Every other outcome, including a genuine fault, is
    recorded on the first observation and re-tested by run.py's separate
    majority-of-3 revalidation pass."""
    work = Path(args.run_dir) / "work" / ("case_%04d" % c["i"])
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    common = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
              "--function", "k", "--grid", "1", "--tg", "1", "--no-fast-math",
              "--shdump", str(Path(args.bin_dir) / "shdump"),
              "--agxrun", str(Path(args.bin_dir) / "agxrun"),
              "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
              "--workdir", str(work), "--run-timeout", "20"]

    if c["carrier"] == "dag":
        mem_path, imem_path, poison_path = build_dag_buffers(work)
        argv = common + ["--source", str(EXP / "kernels" / CARRIER_DAG),
                         "--buf", "0=@%s" % poison_path,
                         "--buf", "1=@%s" % mem_path,
                         "--buf", "2=@%s" % imem_path,
                         "--out", "0=%d" % OUT_WORDS,
                         "--splice", "_agc.main@0=%s" % c["hex"]]
    elif c["carrier"] == "cf":
        (work / "a.bin").write_bytes(struct.pack("<f", c["cf_a"]))
        (work / "n.bin").write_bytes(struct.pack("<i", c["cf_n"]))
        (work / "poison.bin").write_bytes(struct.pack("<I", S.POISON_U32) * OUT_WORDS)
        argv = common + ["--source", str(EXP / "kernels" / CARRIER_CF),
                         "--buf", "0=@%s" % (work / "poison.bin"),
                         "--buf", "1=@%s" % (work / "a.bin"),
                         "--buf", "2=@%s" % (work / "n.bin"),
                         "--out", "0=%d" % OUT_WORDS,
                         "--splice", "_agc.main@0=%s" % c["hex"]]
    else:
        raise ValueError("unknown carrier %r" % c["carrier"])

    started = time.time()
    victim_retries = 0
    for attempt in range(VICTIM_RETRIES + 1):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
            timed_out, exc = False, None
            stdout, stderr, exitc = r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired as e:
            timed_out, exc = True, "TimeoutExpired"
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            exitc = None

        status, out_hex, pipeline_source, fault_class = "NO_STATUS", None, None, ""
        for line in stdout.splitlines():
            if line.startswith("STATUS "):
                status = line.split(None, 1)[1].strip()
            elif line.startswith("OUT 0 "):
                out_hex = line[len("OUT 0 "):].strip()
            elif line.startswith("PIPELINE_SOURCE"):
                pipeline_source = line.split(None, 1)[1].strip()
            elif line.startswith("ERROR "):
                fault_class = line[len("ERROR "):].strip()
        if "InnocentVictim" not in fault_class:
            break
        victim_retries += 1
    dur_ms = int((time.time() - started) * 1000)

    observed, outcomes, ok, sent = {}, {}, False, None
    if status == "OK" and out_hex:
        observed, outcomes, ok, sent = decode_case(c, out_hex)

    if timed_out:
        outcome = "hang"
    elif status != "OK":
        outcome = "victim" if "InnocentVictim" in fault_class else "fault"
    elif c.get("sentinel") and sent != S.sentinel_expected_f32():
        outcome = "invalid_run"
    else:
        outcome = outcomes.get("0", "ok" if ok else "wrong_value")
        if len(outcomes) > 1:
            outcome = "ok" if ok else "wrong_value"

    record = {
        "i": c["i"], "name": c["name"], "group": c["group"], "carrier": c["carrier"],
        "oracle": c["oracle"], "oracle_bits": c.get("oracle_bits", {}),
        "expect_match": c["expect_match"], "notes": c["notes"],
        "prov": c.get("prov"),
        "argv": argv,
        "timed_out": timed_out, "exception": exc, "exit": exitc,
        "status": status, "fault_class": fault_class, "pipeline_source": pipeline_source,
        "out_hex": out_hex, "observed": observed, "word_outcomes": outcomes,
        "outcome": outcome, "sentinel": sent, "match": ok,
        "victim_retries": victim_retries,
        "stdout": stdout, "stderr": stderr,
    }
    return record, dur_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-index", type=int, required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    cs = CM.build_cases()
    c = cs[a.case_index]
    record, dur_ms = run_one(c, a)
    record["duration_ms"] = dur_ms
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
