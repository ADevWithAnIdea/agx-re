#!/usr/bin/env python3
"""EXP-0149 per-case executor.

Differences from EXP-0112's executor, all mandated by FIELD-SWEEP-PROTOCOL SS7:
  * the read-back buffer is POISONED with 0xDEADBEEF (never zero-initialised),
    so "silent zero" and "never written" are distinguishable -- the exact
    artefact that made EXP-0128 misread mov_imm.imm_top (EXP-0140 db_defects);
  * a UNIQUE splice-archive path per request (per-case work dir + nonce);
  * an INTEGRITY SENTINEL through an independent path: the spliced _agc.main
    is read back out of the archive by agxtest (--dump-main) and compared
    byte-for-byte against the program this experiment intended to run;
  * MAJORITY-OF-3 before any case is recorded as a fault, and the OS fault
    classification string (agxrun's `ERROR <msg>: <localizedDescription>`)
    is captured verbatim.

One case per process invocation.  Prints one JSON object to stdout.
"""
import argparse, json, os, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import casematrix as CM  # noqa: E402
import generator as G    # noqa: E402

CARRIER_DAG = "carrier_dag.metal"
CARRIER_CF = "carrier_cf.metal"
POISON_WORD = 0xDEADBEEF


def poison_file(path, n_words):
    path.write_bytes(struct.pack("<%dI" % n_words, *([POISON_WORD] * n_words)))
    return path


def build_dag_buffers(work):
    mem_path = work / "mem.bin"
    mem_path.write_bytes(b"".join(struct.pack("<f", v) for v in G.MEM_WORDS))
    imem_path = work / "imem.bin"
    imem_path.write_bytes(b"".join(struct.pack("<i", v) for v in G.IMEM_WORDS))
    return mem_path, imem_path


def decode_case(c, out_hex):
    raw = bytes.fromhex(out_hex)
    words_f = [struct.unpack("<f", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    words_u = [struct.unpack("<I", raw[i:i + 4])[0] for i in range(0, len(raw) - 3, 4)]
    observed = {}
    ok = True
    for k, expected in c["oracle"].items():
        idx = int(k)
        got = words_f[idx] if idx < len(words_f) else None
        observed[k] = got
        ok = ok and (got == expected)
    oracle_idx = {int(k) for k in c["oracle"]}
    poison_left = [i for i, u in enumerate(words_u) if i not in oracle_idx and u == POISON_WORD]
    poison_gone = [i for i, u in enumerate(words_u) if i not in oracle_idx and u != POISON_WORD]
    return observed, ok, {"poison_intact_words": poison_left, "poison_overwritten_words": poison_gone,
                          "words_u32": words_u}


def one_attempt(c, args, attempt):
    work = Path(args.run_dir) / "work" / ("case_%03d_a%d" % (c["i"], attempt))
    work.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo)
    out_words = max(int(k) for k in c["oracle"]) + 1
    # UNIQUE splice-archive path per request (SS7)
    archive = work / ("arch_case%03d_a%d.bin" % (c["i"], attempt))
    poison = poison_file(work / "poison_out.bin", out_words)

    common = [sys.executable, "-B", str(repo / "tools" / "agxtest" / "agxtest.py"),
              "--function", "k", "--grid", "1", "--tg", "1", "--no-fast-math",
              "--shdump", str(Path(args.bin_dir) / "shdump"),
              "--agxrun", str(Path(args.bin_dir) / "agxrun"),
              "--agxparse", str(repo / "tools" / "shdump" / "agxparse.py"),
              "--workdir", str(work), "--archive", str(archive),
              "--run-timeout", "30", "--dump-main",
              "--out", "0=%d" % out_words,
              "--buf", "0=@%s" % poison,          # POISONED read-back buffer
              "--splice", "_agc.main@0=%s" % c["hex"]]

    if c["carrier"] == "dag":
        mem_path, imem_path = build_dag_buffers(work)
        argv = common[:3] + ["--source", str(EXP / "kernels" / CARRIER_DAG)] + common[3:] + [
            "--buf", "1=@%s" % mem_path, "--buf", "2=@%s" % imem_path]
    elif c["carrier"] == "cf":
        a_path = work / "a.bin"; a_path.write_bytes(struct.pack("<f", c["cf_a"]))
        n_path = work / "n.bin"; n_path.write_bytes(struct.pack("<i", c["cf_n"]))
        argv = common[:3] + ["--source", str(EXP / "kernels" / CARRIER_CF)] + common[3:] + [
            "--buf", "1=@%s" % a_path, "--buf", "2=@%s" % n_path]
    else:
        raise ValueError("unknown carrier %r" % c["carrier"])

    started = time.time()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=45)
        timed_out, exc = False, None
        stdout, stderr, exitc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        timed_out, exc = True, "TimeoutExpired"
        stdout, stderr, exitc = (e.stdout or ""), (e.stderr or ""), None
    dur_ms = int((time.time() - started) * 1000)

    status, out_hex, pipeline_source, main_spliced, os_error = "NO_STATUS", None, None, None, None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1].strip()
        elif line.startswith("OUT 0 "):
            out_hex = line[len("OUT 0 "):].strip()
        elif line.startswith("PIPELINE_SOURCE"):
            pipeline_source = line.split(None, 1)[1].strip()
        elif line.startswith("MAIN_SPLICED "):
            main_spliced = line.split(None, 1)[1].strip()
        elif line.startswith("ERROR "):
            os_error = line[len("ERROR "):].strip()

    # INTEGRITY SENTINEL (independent path): what the archive actually holds
    # must equal the program we intended, byte for byte.
    sentinel = None
    if main_spliced is not None:
        sentinel = (main_spliced.lower() == c["hex"].lower())

    observed, ok, extra = ({}, False, {})
    if status == "OK" and out_hex:
        observed, ok, extra = decode_case(c, out_hex)
    return {"attempt": attempt, "status": status, "os_error": os_error,
            "out_hex": out_hex, "observed": observed, "match": ok,
            "integrity_sentinel_ok": sentinel, "pipeline_source": pipeline_source,
            "timed_out": timed_out, "exception": exc, "exit": exitc,
            "duration_ms": dur_ms, "argv": argv,
            "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-2000:], **extra}


def run_one(c, args):
    attempts = [one_attempt(c, args, 0)]
    # MAJORITY-OF-3 before recording a fault (FIELD-SWEEP-PROTOCOL SS7.1)
    if attempts[0]["status"] != "OK":
        attempts.append(one_attempt(c, args, 1))
        attempts.append(one_attempt(c, args, 2))
    statuses = [a["status"] for a in attempts]
    final = max(set(statuses), key=statuses.count)
    chosen = next(a for a in attempts if a["status"] == final)
    outcome = ("ok" if (final == "OK" and chosen["match"]) else
               "fault" if final in ("CMDBUF_ERROR", "HANG") else
               "wrong_value" if final == "OK" else "undecodable")
    if outcome == "wrong_value" and chosen.get("observed"):
        vals = list(chosen["observed"].values())
        if vals and all(v == 0.0 for v in vals):
            outcome = "silent_zero"
    return {
        "i": c["i"], "name": c["name"], "group": c["group"], "carrier": c["carrier"],
        "oracle": c["oracle"], "expect_match": c["expect_match"], "notes": c["notes"],
        "fully_synthesized": c["fully_synthesized"], "copied_fields": c["copied_fields"],
        "carrier_fields": c["carrier_fields"], "prov_counts": c["prov_counts"],
        "n_offnatural": c["n_offnatural"],
        "status": final, "statuses": statuses, "n_attempts": len(attempts),
        "os_error": chosen["os_error"], "out_hex": chosen["out_hex"],
        "observed": chosen["observed"], "match": chosen["match"], "outcome": outcome,
        "integrity_sentinel_ok": chosen["integrity_sentinel_ok"],
        "pipeline_source": chosen["pipeline_source"],
        "poison_intact_words": chosen.get("poison_intact_words"),
        "poison_overwritten_words": chosen.get("poison_overwritten_words"),
        "attempts": attempts,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-index", type=int, required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    cs = CM.build_cases()
    c = cs[a.case_index]
    print(json.dumps(run_one(c, a), sort_keys=True))


if __name__ == "__main__":
    main()
