#!/usr/bin/env python3
"""EXP-0206 contract freezer -- writes CAPTURE_CONTRACT.json from what is on disk.

Runs on the M4 (the evidence store), never on the neo. It hashes every authored
input and every pinned tool, so a capture can be checked against THIS contract
rather than against whatever HEAD happens to be when a later run starts. The
repository revision is RECORDED, NOT GATED: sibling experiments commit
continuously and a "HEAD must not move" gate would abort this experiment through
no fault of its own (it happened to EXP-0082).
"""
import hashlib, json, subprocess, sys, time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
FILES = sorted(
    [p for p in EXP.rglob("*")
     if p.is_file() and "__pycache__" not in p.parts and "raw" not in p.parts
     and "work" not in p.parts and p.name != "CAPTURE_CONTRACT.json"])


def sh(*c):
    try:
        return subprocess.check_output(c, text=True, cwd=str(EXP), timeout=30).strip()
    except Exception as e:                                      # noqa: BLE001
        return "ERR %s" % e


def main():
    doc = {
        "experiment": "EXP-0206",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": {"device": "Apple A18 Pro / G17P", "arch": "applegpu_g17p",
                   "accelerator": "AGXAcceleratorG17P", "cores": 5,
                   "os": "macOS 26.6 (25G5043d)", "family": "Apple9",
                   "host": "192.168.170.254", "remote_dir": "~/agxre/EXP-0206"},
        "repo_revision_recorded_not_gated": sh("git", "rev-parse", "HEAD"),
        "repo_dirty": bool(sh("git", "status", "--porcelain")),
        "timeouts": {"per_request_watchdog_s": 8.0, "compile_s": 600,
                     "ssh_alarm_s": 900},
        "retries": {"confirm_attempts": 3, "innocent_retries": 3,
                    "canary_retries": 3},
        "abort_path": "NONE. No hang budget (FIELD-SWEEP-PROTOCOL 3c).",
        "gated_runs": ["g17p_20260830_run01", "g17p_20260830_run02"],
        "calibration_not_citable": ["raw/prefreeze/**", "analysis/census.py",
                                    "analysis/dump_walk.py", "any --limit-values run",
                                    "raw/*pilot*"],
        "raw_schema": {
            "path": "raw/<run_id>/sweep.jsonl",
            "one_json_object_per_case_flushed_and_fsynced": True,
            "keys": ["carrier", "arm", "key", "region", "instr", "field", "value",
                     "bytes", "token", "observed", "vals", "oracle", "match",
                     "prediction_ok", "outcome", "class", "status", "statuses",
                     "fault_classes", "innocent_retries", "gputime_ns", "role",
                     "occ", "occ_dim", "off", "instr_len", "start", "width",
                     "note", "ts", "synthesized"],
            "observed": "{vh: sha256-12 of the 32 value words, sent: sentinel word, "
                        "nunwritten: count of words still POISON, tail_ok: bool}. "
                        "gputime_ns is DELIBERATELY NOT in `observed` -- it varies "
                        "run to run and would manufacture movement from scheduling "
                        "noise.",
            "vals": "the full 32-word vector, retained on EVERY non-matching case "
                    "and on every baseline, so a deviation is fully reconstructible",
            "outcome": ["ok", "silent_zero", "wrong_value", "not_written",
                        "wrong_value", "fault", "hang", "invalid_run",
                        "nondeterministic", "measurement_failure"],
            "class": "the wave_audit.py HARD token when the case is a hard outcome, "
                     "null otherwise. Hard outcomes are NEVER movement.",
        },
        "amendments": [
            {"n": 1, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "what": "Occurrence acceptance widened to allow a BOUNDED RESYNC past "
                     "an instruction the pinned db.json cannot decode, and an "
                     "explicit rejection of signature hits that lie INSIDE a "
                     "decoded instruction.",
             "why": "The pre-freeze census found that every NON-LEAF callee our "
                    "compiler emits ends with the 6-byte word `ef 02 54 00 00 50`, "
                    "which the pinned DB has no descriptor for, immediately before "
                    "the non-leaf return `8f 12 54 00`. A pure linear walk dies "
                    "just short of the ONLY occurrences in the corpus carrying "
                    "linkmode 0x12 -- exactly the value the leaf-only carriers of "
                    "the withdrawn `ret_luse.linkmode` measurement could never "
                    "reach. Keeping the unamended rule would have silently "
                    "reproduced that blind spot. Separately, `call` carries a "
                    "literal 0x8f at byte+4, so every direct call produces a "
                    "spurious `ret` signature hit four bytes in; those are now "
                    "rejected explicitly."},
            {"n": 2, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "what": "Added target `stop.reserved@synth_mid`: a CONSTRUCTED "
                     "mid-program stop, built by overwriting the optional 4-byte "
                     "`frame_marker` with `0e 00 00 00`.",
             "why": "H6 assumed a kernel with an out-of-line callee would place the "
                    "callee after the main body's stop, giving a mid-program "
                    "terminator for free. The census REFUTED that: the callee lives "
                    "in its own symbol region and `follows_code` is False at all "
                    "nine natural stops. Without a constructed one there is no "
                    "positive control in the termination dimension at all, and "
                    "FIELD-SWEEP-PROTOCOL section 9 would force UNRESOLVED by "
                    "default rather than by measurement."},
            {"n": 3, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "what": "Carrier lists for `if_push.scope` and `pop_reconverge.scope` "
                     "trimmed from six loop shapes to four, and `cl_atomic` added to "
                     "`pop_reconverge.scope`.",
             "why": "Device-time budget, plus a census finding: `cl_atomic`'s "
                    "compiled pop is `0f 06 24 02 00 00` -- scope 0x24, the OTHER "
                    "documented bank -- while every loop carrier emits 0x04, so the "
                    "compiler itself spans the dimension across the amended set. "
                    "The two dropped loop shapes add no dimension value the four "
                    "retained ones do not already carry."},
            {"n": 4, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "what": "`not_written` reclassified from HARD to a VALID payload.",
             "why": "Pilot p01 (calibration): the synthesized mid-program stop "
                    "returns sentinel-present + all 32 value words still POISON. "
                    "That is a valid execution with the most informative payload in "
                    "the experiment -- it is HOW a terminator announces itself -- and "
                    "scoring it hard would have deleted the very observation the "
                    "termination-dimension positive control exists to make. "
                    "`invalid_run` (sentinel MISSING) remains hard."},
        ],
        "pilot_findings_calibration_only": {
            "throughput_s_per_case": 0.234,
            "final stop byte0 -> 0x00": "ok, program still correct -- the FINAL stop "
                "is not a terminator on G17P, reconfirming EXP-0003/EXP-0010, so the "
                "termination control does NOT fire there",
            "synthesized mid-program stop": "not_written (sentinel present, 32 words "
                "poison) -- a MID-PROGRAM stop DOES terminate; the control FIRES",
            "call.offset -8": "still correct: the target lands in the 8 bytes of pad "
                "before the callee and falls through. The FORWARD deltas are the ones "
                "expected to fire.",
        },
        "files": {},
    }
    for p in FILES:
        doc["files"][str(p.relative_to(EXP))] = {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size}
    a = json.load(open(EXP / "harness" / "arms206.json"))
    doc["arms"] = {"n_arms": len(a["arms"]),
                   "n_cases": sum(len(x["values"]) for x in a["arms"]),
                   "n_no_occurrence": len(a["no_occurrence"]),
                   "sha256": doc["files"]["harness/arms206.json"]["sha256"]}
    (EXP / "CAPTURE_CONTRACT.json").write_text(json.dumps(doc, indent=1, sort_keys=True))
    print("frozen: %d files, %d arms, %d cases"
          % (len(doc["files"]), doc["arms"]["n_arms"], doc["arms"]["n_cases"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
