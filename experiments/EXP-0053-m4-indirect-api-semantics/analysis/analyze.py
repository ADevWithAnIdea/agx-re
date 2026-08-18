#!/usr/bin/env python3
"""Deterministically reduce EXP-0053 authored public-API stdout."""

import argparse
import json
import re
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
CANONICAL = ("m4_20260817_run05", "m4_20260817_run06")
FAILED = ("m4_20260817_run01", "m4_20260817_run02")
PAIR_RE = re.compile(r"([a-z_]+)=([^ ]+)")
RUN02_STDOUT_LINES = [
    "DEVICE Apple M4",
    "SUPPORT icb_api=attempted",
    "COMMAND label=indirect-zero status=4 error=none",
    "COMPUTE case=indirect-zero expected_threads=0 counter=0 mismatches=0 guards=0 args=0,1,1 output_fnv=577e53ec5812a283",
    "COMMAND label=cpu-mutate-before-commit status=4 error=none",
    "COMPUTE case=cpu-mutate-before-commit expected_threads=24 counter=24 mismatches=0 guards=0 args=3,1,1 output_fnv=08b5d47700595c6b",
    "COMMAND label=gpu-producer-prior-encoder status=4 error=none",
    "COMPUTE case=gpu-producer-prior-encoder expected_threads=32 counter=32 mismatches=0 guards=0 args=4,1,1 output_fnv=45481b45a99fef63",
    "COMMAND label=indirect-draw-zero status=4 error=none",
    "DRAW case=indirect-draw-zero vertices=0 guards=0 rgba=01020304010203040102030401020304",
    "COMMAND label=indirect-draw-three status=4 error=none",
    "DRAW case=indirect-draw-three vertices=3 guards=0 rgba=11223344112233441122334411223344",
    "COMMAND label=full status=5 error=Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "COMMAND label=prefix status=5 error=Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "COMMAND label=suffix status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=middle status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=empty status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=reset-middle status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=restore-one status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=optimized-full status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "RESULT FAIL",
]

SENTINEL = 0xd00dfeed


def u32hex(words):
    return struct.pack("<" + "I" * len(words), *words).hex()


def fnv1a(data):
    value = 1469598103934665603
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return f"{value:016x}"


def expected_compute(groups):
    threads = groups * 8
    args = [SENTINEL] * 11; args[4:7] = [groups, 1, 1]
    counter = [SENTINEL, threads, SENTINEL]
    output = [SENTINEL] * 72
    output[4:4 + threads] = [0x51000000 ^ index for index in range(threads)]
    output_bytes = bytes.fromhex(u32hex(output))
    return {"expected_threads":str(threads),"counter":str(threads),"mismatches":"0","guards":"0",
            "args":f"{groups},1,1","output_fnv":fnv1a(output_bytes),"arg_hex":u32hex(args),
            "counter_hex":u32hex(counter),"output_hex":output_bytes.hex()}


EXPECTED_COMPUTE = {"indirect-zero":expected_compute(0),
                    "cpu-mutate-before-commit":expected_compute(3),
                    "gpu-producer-prior-encoder":expected_compute(4)}


def expected_draw(vertices, rgba):
    args = [SENTINEL] * 12; args[4:8] = [vertices, 1, 0, 0]
    return {"vertices":str(vertices),"guards":"0","rgba":rgba,"arg_hex":u32hex(args)}


EXPECTED_DRAW = {
    "indirect-draw-zero": expected_draw(0,"01020304010203040102030401020304"),
    "indirect-draw-three": expected_draw(3,"11223344112233441122334411223344"),
}
EXPECTED_ICB = {
    "full": (0,4,0,"102030ff405060ff708090ffa0b0c0ff"),
    "prefix": (0,2,0,"102030ff405060ff0102030401020304"),
    "suffix": (2,2,0,"0102030401020304708090ffa0b0c0ff"),
    "middle": (1,2,0,"01020304405060ff708090ff01020304"),
    "empty": (0,0,0,"01020304010203040102030401020304"),
    "reset-middle": (0,4,0,"102030ff0102030401020304a0b0c0ff"),
    "restore-one": (0,4,0,"102030ff405060ff01020304a0b0c0ff"),
    "optimized-full": (0,4,1,"102030ff405060ff708090ffa0b0c0ff"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(line, prefix):
    require(line.startswith(prefix + " "), f"prefix {line!r}")
    result = {}
    for key, value in PAIR_RE.findall(line[len(prefix) + 1:]):
        require(key not in result, f"duplicate {prefix} key {key}")
        result[key] = value
    require(" ".join(f"{key}={value}" for key, value in result.items()) == line[len(prefix)+1:],
            f"closed grammar {line!r}")
    return result


def parse(run_id):
    record = json.loads((EXP / "raw" / run_id / "run.json").read_text())
    require(record["exit"] == 0 and not record.get("timed_out", False), f"{run_id}: execution")
    lines = record["stdout"].splitlines()
    require(lines[:2] == ["DEVICE Apple M4", "SUPPORT icb_api=attempted"], f"{run_id}: header")
    require(lines[-1] == "RESULT OK", f"{run_id}: result")
    commands, compute, draw, icb = [], {}, {}, {}
    for line in lines[2:-1]:
        if line.startswith("COMMAND "):
            item = fields(line, "COMMAND")
            require(set(item) == {"label","status","error"}, f"{run_id}: command fields")
            require(item["status"] == "4" and item["error"] == "none", f"{run_id}: command status")
            commands.append(item["label"])
        elif line.startswith("COMPUTE "):
            item = fields(line, "COMPUTE"); name = item.pop("case")
            require(name not in compute, f"{run_id}: duplicate compute")
            compute[name] = item
        elif line.startswith("DRAW "):
            item = fields(line, "DRAW"); name = item.pop("case")
            require(name not in draw, f"{run_id}: duplicate draw")
            draw[name] = item
        elif line.startswith("ICB "):
            item = fields(line, "ICB"); name = item.pop("case")
            require(name not in icb, f"{run_id}: duplicate ICB")
            require(set(item) == {"start","count","optimize","rgba"}, f"{run_id}: ICB fields")
            icb[name] = (int(item["start"]), int(item["count"]), int(item["optimize"]), item["rgba"])
        else:
            require(False, f"{run_id}: unknown stdout {line!r}")
    expected_commands = [*EXPECTED_COMPUTE, *EXPECTED_DRAW, *EXPECTED_ICB]
    require(commands == expected_commands, f"{run_id}: command sequence")
    require(compute == EXPECTED_COMPUTE, f"{run_id}: compute outputs")
    require(draw == EXPECTED_DRAW, f"{run_id}: draw outputs")
    require(icb == EXPECTED_ICB, f"{run_id}: ICB outputs")
    return {"run":run_id,"commands":len(commands),"compute":compute,"draw":draw,"icb":{
        name:{"start":value[0],"count":value[1],"optimize":value[2],"rgba":value[3]}
        for name,value in icb.items()}}


def analyze():
    runs = [parse(run_id) for run_id in CANONICAL]
    require(runs[0]["compute"] == runs[1]["compute"] and runs[0]["draw"] == runs[1]["draw"] and
            runs[0]["icb"] == runs[1]["icb"], "canonical repetitions differ")
    failures = []
    for run_id in FAILED:
        directory = EXP / "raw" / run_id
        build = json.loads((directory / "build.json").read_text())
        run_path = directory / "run.json"
        if run_id.endswith("01"):
            failures.append({"run":run_id,"phase":"build","exit":build["exit"],
                             "reason":"unsupported authored convenience-property spelling"})
        else:
            record = json.loads(run_path.read_text())
            require(record["stdout"].splitlines() == RUN02_STDOUT_LINES and
                    record["stdout"].endswith("\n"),
                    "m4_20260817_run02: closed exact failure transcript")
            failures.append({"run":run_id,"phase":"run","exit":record["exit"],
                             "reason":"authored ICB pipeline omitted public supportIndirectCommandBuffers opt-in",
                             "page_fault_recorded":"GPU Address Fault" in record["stdout"],
                             "later_submissions_ignored":"SubmissionsIgnored" in record["stdout"]})
    return {
        "schema":1,
        "experiment":"EXP-0053-m4-indirect-api-semantics",
        "canonical_runs":list(CANONICAL),
        "preserved_noncanonical_successes":["m4_20260817_run03","m4_20260817_run04"],
        "preserved_failures":failures,
        "runs":runs,
        "aggregate":{"successful_processes":2,"completed_commands":26,
                     "compute_guards_unchanged":True,"draw_argument_guards_unchanged":True,
                     "canonical_stdout_equal":True},
        "hypotheses":{"H1":"SUPPORTED for CPU pre-commit mutation and GPU prior-encoder producer",
                      "H2":"SUPPORTED for tested full/prefix/suffix/middle/empty ICB ranges",
                      "H3":"SUPPORTED for tested middle reset and one-slot restore",
                      "H4":"SUPPORTED for tested zero/nonzero compute and draw cases",
                      "H5":"SUPPORTED for tested full-range public optimization"},
        "scope":{"target":"Apple M4/G16G-class only","a18_pro":"UNTESTED",
                 "private_command_stream":"NOT INSPECTED","linux_uapi_mapping":"NOT ESTABLISHED",
                 "apple_binary_introspection":"NONE","compiled_shader_bytes_inspected":"NONE"},
    }


def report(result):
    return "\n".join([
        "EXP-0053 deterministic analysis",
        "canonical_runs=" + ",".join(result["canonical_runs"]),
        "successful_processes=2",
        "completed_commands=26",
        "indirect_compute=zero:0,cpu-precommit:24,gpu-prior-encoder:32",
        "indirect_draw=zero:clear,three:11223344x4",
        "icb_ranges=full,prefix,suffix,middle,empty exact",
        "icb_reset=middle removed;slot1 restored",
        "icb_optimization=full output preserved",
        "preserved_history=compile-rejection,page-fault-and-ignored-submissions,2 hash-only successes",
        "scope=M4 public Metal API behavior; no private stream, Linux UAPI, or A18 claim",
        "apple_binary_introspection=NONE",
        "",
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    result = analyze()
    (args.output_dir / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "report.txt").write_text(report(result))


if __name__ == "__main__":
    main()
