#!/usr/bin/env python3
"""EXP-0084 splice-kind case executable (run once per capture, one process).

Frozen sequence (see PRE_REGISTRATION.md "Splice identification algorithm"
and "Splice case procedure"):
  1. compile `splice_target` (tools/shdump) -> archive.
  2. extract + tokenize `_agc.main` (+ preamble) with tools/agx-isa; apply
     the shared `decode_lib.identify()` algorithm (l1/l2 = the two per-lane
     device_load instructions dereferencing pA[gid]/pB[gid]).
  3. run the UNMODIFIED archive (analysis/decode_lib-adjacent harness/
     splice_run) to observe which of {TAG_A, TAG_B} lands in `out` (the
     baseline observation grounds which of l1/l2 is "the load that feeds
     out", instead of assuming source/program order agree).
  4. splice EXACTLY ONE byte: the `index_reg` byte of whichever of l1/l2 the
     baseline showed feeds `out`, changed from its own index_reg value to
     the OTHER load's index_reg value.
  5. run the SPLICED archive; predicted refutable outcome: `out` now reads
     the tag that was previously in `outb` (mechanism confirmed), `outb`
     unchanged. Any other outcome (unchanged, corrupted, fault, hang) is
     recorded verbatim as a refutation/inconclusive result -- never coerced
     to match the prediction.

Prints ONE JSON line to stdout. No raw GPU address is ever read or printed
(splice_run.m never prints one either) -- only tag words, instruction field
values, and byte offsets, all deterministic given the frozen source.

Usage:
  python3 splice_case.py --shdump BIN --splice-run BIN --source SRC.metal \
      --function splice_target --work DIR
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode_lib  # noqa: E402
from procutil import rec  # noqa: E402

TIMEOUTS = {"build": 60, "extract": 20, "run": 60}
TAG_A_HEX = "5a0000aa"
TAG_B_HEX = "5a0000bb"


def parse_splice_run_json(stdout):
    try:
        p = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(p, dict):
        return None
    return p


def all_words_are(hexstr, want32hex):
    if not hexstr or len(hexstr) % 8 != 0:
        return False
    return all(hexstr[i:i + 8] == want32hex for i in range(0, len(hexstr), 8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shdump", required=True)
    ap.add_argument("--splice-run", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--function", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    archive = work / "archive.bin"
    spliced = work / "archive_spliced.bin"

    d = decode_lib.full_decode(a.shdump, a.source, a.function, archive, TIMEOUTS)
    out = {"schema": 1, "function": a.function, "build_ok": False,
           "ident": None, "baseline": None, "target": None,
           "splice_offset_abs": None, "splice_from": None, "splice_to": None,
           "spliced_result": None, "outcome": "build_fail"}
    if d["build"]["exit"] != 0 or d["build"]["timed_out"] or d["build"]["exception"] is not None:
        print(json.dumps(out, sort_keys=True))
        sys.stdout.flush()
        sys.exit(0)
    out["build_ok"] = True
    ident = d["ident"]
    out["ident"] = ident
    if ident is None or not ident["confirmation_ok"]:
        out["outcome"] = "identification_failed"
        print(json.dumps(out, sort_keys=True))
        sys.stdout.flush()
        sys.exit(0)

    # --- baseline run (unmodified archive) ---------------------------------
    zb = rec([a.splice_run, "--archive", archive, "--source", a.source,
              "--function", a.function], TIMEOUTS["run"], Path(a.splice_run).parent)
    baseline = parse_splice_run_json(zb["stdout"]) if not zb["timed_out"] and zb["exit"] == 0 else None
    out["baseline"] = baseline
    if baseline is None or baseline.get("status") != "OK" or baseline.get("pipeline_source") != "archive":
        out["outcome"] = "baseline_run_failed"
        print(json.dumps(out, sort_keys=True))
        sys.stdout.flush()
        sys.exit(0)

    out_is_a = all_words_are(baseline["out_hex"], TAG_A_HEX)
    out_is_b = all_words_are(baseline["out_hex"], TAG_B_HEX)
    outb_is_a = all_words_are(baseline["outb_hex"], TAG_A_HEX)
    outb_is_b = all_words_are(baseline["outb_hex"], TAG_B_HEX)
    if not ((out_is_a and outb_is_b) or (out_is_b and outb_is_a)):
        out["outcome"] = "baseline_unexpected_tags"
        print(json.dumps(out, sort_keys=True))
        sys.stdout.flush()
        sys.exit(0)

    # Whichever of l1/l2 feeds `out` (grounded in the observed baseline, not
    # assumed source order): l1 is program-order-first. We cannot directly
    # observe "which load feeds which store" from tags alone when both loads
    # use the SAME index_reg->address mapping normally (l1 always reads
    # addrs[0]=TAG_A, l2 always reads addrs[1]=TAG_B, by construction of
    # splice_target's source): out_is_a implies l1 feeds out (source order
    # preserved); out_is_b implies the compiler swapped store/load pairing
    # (l2 feeds out instead). Either way `target`/`other` below are chosen
    # so the SPLICE always redirects the load feeding `out` to the OTHER
    # load's index_reg.
    l1, l2 = ident["l1"], ident["l2"]
    target, other = (l1, l2) if out_is_a else (l2, l1)
    out["target"] = target
    predicted_out_after = TAG_B_HEX if out_is_a else TAG_A_HEX

    (abs_off, region_len), loc_receipt = decode_lib.locate(archive, "_agc.main", TIMEOUTS["extract"])
    splice_abs = abs_off + target["offset"] + 5  # index_reg field: bits[40:48] => byte 5
    from_val = target["index_reg"]
    to_val = other["index_reg"]
    out["splice_offset_abs"] = splice_abs
    out["splice_from"] = from_val
    out["splice_to"] = to_val

    raw = bytearray(Path(archive).read_bytes())
    if raw[splice_abs] != from_val:
        out["outcome"] = "splice_precondition_failed"
        print(json.dumps(out, sort_keys=True))
        sys.stdout.flush()
        sys.exit(0)
    raw[splice_abs] = to_val
    Path(spliced).write_bytes(bytes(raw))

    zs = rec([a.splice_run, "--archive", spliced, "--source", a.source,
              "--function", a.function], TIMEOUTS["run"], Path(a.splice_run).parent)
    spliced_result = parse_splice_run_json(zs["stdout"]) if not zs["timed_out"] and zs["exit"] == 0 else None
    out["spliced_result"] = spliced_result
    if spliced_result is None:
        out["outcome"] = "spliced_run_process_fault"
    elif spliced_result.get("status") != "OK" or spliced_result.get("pipeline_source") != "archive":
        out["outcome"] = "spliced_run_rejected_or_faulted"
    elif all_words_are(spliced_result["out_hex"], predicted_out_after) \
            and spliced_result["outb_hex"] == baseline["outb_hex"]:
        # out flipped to the OTHER load's tag; outb (fed by the untouched
        # load) is byte-identical to the baseline -- exactly the prediction.
        out["outcome"] = "confirmed"
    else:
        out["outcome"] = "refuted"

    # work/ (archive.bin, archive_spliced.bin) is retained for provenance --
    # never deleted here.
    print(json.dumps(out, sort_keys=True))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
