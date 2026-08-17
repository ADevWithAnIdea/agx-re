#!/usr/bin/env python3
"""Derive deterministic EXP-0052 claims from the retained public-API logs."""

import argparse
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
CANONICAL_RUNS = ("m4_20260817_run03", "m4_20260817_run04")
PRESERVED_FAILURES = ("m4_20260817_run01", "m4_20260817_run02")

CAL_RE = re.compile(
    r"^CAL i=(\d+) delay_ns=(\d+) c0=(\d+) g0=(\d+) c1=(\d+) g1=(\d+)$"
)
SAMPLE_RE = re.compile(r"^SAMPLES (\S+) base=(\d+) count=(\d+)(.*)$")
VALUE_RE = re.compile(r" v(\d+)=(\d+)")
COMMAND_RE = re.compile(
    r"^COMMAND (\S+) status=(\d+) error=(\S+) gpuStart=([0-9.]+) gpuEnd=([0-9.]+)$"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_stdout(run_id):
    record = json.loads((EXP / "raw" / run_id / "run.json").read_text())
    return record, record["stdout"].splitlines()


def parse_success(run_id):
    record, lines = load_stdout(run_id)
    require(record["exit"] == 0, f"{run_id}: nonzero exit")
    require(lines[-1] == "RESULT OK", f"{run_id}: missing result")
    require(lines.count("DEVICE Apple M4") == 1, f"{run_id}: device line")
    require(lines.count("SUPPORT dispatch=0 draw=0 stage=1") == 1,
            f"{run_id}: support line")

    calibrations = []
    samples = {}
    commands = []
    for line in lines:
        match = CAL_RE.match(line)
        if match:
            calibrations.append(tuple(map(int, match.groups())))
            continue
        match = SAMPLE_RE.match(line)
        if match:
            label, base, count, tail = match.groups()
            indexed = [(int(index), int(value)) for index, value in VALUE_RE.findall(tail)]
            require([index for index, _ in indexed] == list(range(int(count))),
                    f"{run_id}: {label} value indices")
            values = [value for _, value in indexed]
            require(len(values) == int(count), f"{run_id}: {label} count")
            samples[label] = {"base": int(base), "values": values}
            continue
        match = COMMAND_RE.match(line)
        if match:
            label, status, error, start, end = match.groups()
            commands.append((label, int(status), error, float(start), float(end)))

    require(len(calibrations) == 64, f"{run_id}: calibration count")
    require([row[0] for row in calibrations] == list(range(64)),
            f"{run_id}: calibration indices")
    require([row[1] for row in calibrations] ==
            [delay for _ in range(16) for delay in (0, 100000, 1000000, 5000000)],
            f"{run_id}: calibration delay sequence")
    expected_samples = {
        "pre-commit": (0, 4), "in-flight": (0, 4),
        "post-light": (0, 4), "post-heavy": (4, 4), "post-two-pass": (8, 8),
        **{f"post-pair-{i}": (16 + i * 8, 8) for i in range(5)},
    }
    require(set(samples) == set(expected_samples), f"{run_id}: sample labels")
    for label, (base, count) in expected_samples.items():
        require(samples[label]["base"] == base and len(samples[label]["values"]) == count,
                f"{run_id}: {label} layout")
    expected_commands = {
        "light-initial": 1, "heavy-initial": 1, "two-pass-one-command": 1,
        "light-repeat": 5, "heavy-repeat": 5,
    }
    require(len(commands) == 13, f"{run_id}: command count")
    require({label: sum(command[0] == label for command in commands)
             for label in expected_commands} == expected_commands,
            f"{run_id}: command labels")
    require(all(status == 4 and error == "none" and end >= start
                for _, status, error, start, end in commands),
            f"{run_id}: command completion")
    cpu_values = [value for row in calibrations for value in (row[2], row[4])]
    gpu_values = [value for row in calibrations for value in (row[3], row[5])]
    offsets = [row[2] - row[3] for row in calibrations]
    offsets += [row[4] - row[5] for row in calibrations]
    delta_error = [(row[4] - row[2]) - (row[5] - row[3]) for row in calibrations]

    passes = []
    for label in ("post-light", "post-heavy", "post-two-pass"):
        values = samples[label]["values"]
        for offset in range(0, len(values), 4):
            passes.append(values[offset:offset + 4])
    repeat_pairs = []
    for repetition in range(5):
        values = samples[f"post-pair-{repetition}"]["values"]
        passes.extend((values[:4], values[4:]))
        repeat_pairs.append({
            "light_fragment_ns": values[3] - values[2],
            "heavy_fragment_ns": values[7] - values[6],
        })

    two_pass = samples["post-two-pass"]["values"]
    pixel = next(line.split()[1] for line in lines if line.startswith("PIXEL "))
    return {
        "run": run_id,
        "calibration_intervals": len(calibrations),
        "timestamp_pair_calls": len(calibrations) * 2,
        "cpu_monotonic": all(a < b for a, b in zip(cpu_values, cpu_values[1:])),
        "gpu_monotonic": all(a < b for a, b in zip(gpu_values, gpu_values[1:])),
        "cpu_gpu_offsets_ns": sorted(set(offsets)),
        "cpu_gpu_delta_error_ns": sorted(set(delta_error)),
        "stage_passes": len(passes),
        "all_stage_samples_nonzero": all(all(values) for values in passes),
        "all_within_pass_ordered": all(
            values[0] <= values[1] <= values[2] <= values[3] for values in passes
        ),
        "resolved_value_counts": {
            label: len(entry["values"]) for label, entry in sorted(samples.items())
        },
        "precommit_values": samples["pre-commit"]["values"],
        "postcommit_prewait_values": samples["in-flight"]["values"],
        "raw_postcommit_label": "in-flight (historical label; status was not sampled)",
        "completed_commands": len(commands),
        "repeat_pairs": repeat_pairs,
        "all_repeat_heavy_gt_light": all(
            pair["heavy_fragment_ns"] > pair["light_fragment_ns"]
            for pair in repeat_pairs
        ),
        "two_pass_boundary_delta_ns": two_pass[4] - two_pass[3],
        "two_pass_first_range": two_pass[:4],
        "two_pass_second_range": two_pass[4:],
        "pixel": pixel,
    }


def analyze():
    runs = [parse_success(run_id) for run_id in CANONICAL_RUNS]
    failures = []
    for run_id in PRESERVED_FAILURES:
        record, lines = load_stdout(run_id)
        failures.append({
            "run": run_id,
            "exit": record["exit"],
            "last_stdout_line": lines[-1] if lines else "",
            "reason": "authored full-texture readback into four-byte stack buffer",
            "gpu_probe_completed_before_harness_fault": any(
                line == "SAMPLES post-pair-4 base=48 count=8" or
                line.startswith("SAMPLES post-pair-4 base=48 count=8 ")
                for line in lines
            ),
        })

    repeat_pairs = [pair for run in runs for pair in run["repeat_pairs"]]
    result = {
        "schema": 1,
        "experiment": "EXP-0052-m4-timestamp-semantics",
        "canonical_runs": list(CANONICAL_RUNS),
        "preserved_failed_runs": failures,
        "runs": runs,
        "aggregate": {
            "calibration_intervals": sum(run["calibration_intervals"] for run in runs),
            "timestamp_pair_calls": sum(run["timestamp_pair_calls"] for run in runs),
            "all_cpu_gpu_pairs_exact": all(
                run["cpu_gpu_offsets_ns"] == [0] and
                run["cpu_gpu_delta_error_ns"] == [0] for run in runs
            ),
            "all_calibration_monotonic": all(
                run["cpu_monotonic"] and run["gpu_monotonic"] for run in runs
            ),
            "stage_passes": sum(run["stage_passes"] for run in runs),
            "all_stage_samples_nonzero_and_ordered": all(
                run["all_stage_samples_nonzero"] and run["all_within_pass_ordered"]
                for run in runs
            ),
            "repeat_pairs": len(repeat_pairs),
            "all_repeat_heavy_gt_light": all(
                pair["heavy_fragment_ns"] > pair["light_fragment_ns"]
                for pair in repeat_pairs
            ),
            "light_fragment_ns": [pair["light_fragment_ns"] for pair in repeat_pairs],
            "heavy_fragment_ns": [pair["heavy_fragment_ns"] for pair in repeat_pairs],
            "two_pass_boundary_delta_ns": [
                run["two_pass_boundary_delta_ns"] for run in runs
            ],
            "all_precommit_and_postcommit_prewait_zero": all(
                not any(run["precommit_values"] + run["postcommit_prewait_values"])
                for run in runs
            ),
            "completed_commands": sum(run["completed_commands"] for run in runs),
            "pixels": [run["pixel"] for run in runs],
        },
        "hypotheses": {
            "H1": "SUPPORTED on tested M4 public API path",
            "H2": "SUPPORTED for all ten matched warm repeat pairs",
            "H3": "FALSIFIED: adjacent render-pass stage ranges overlap at boundary",
            "H4": "REFINED: pre-commit and immediate post-commit/pre-wait resolves were zero; completion status at the latter resolve was not sampled",
            "H5": "SUPPORTED only for public resolve payload shape",
        },
        "scope": {
            "target": "Apple M4/G16G-class only",
            "a18_pro": "UNTESTED",
            "linux_uapi_mapping": "NOT ESTABLISHED",
            "private_counter_bo": "NOT INSPECTED",
            "apple_binary_introspection": "NONE",
            "compiled_shader_bytes_inspected": "NONE",
        },
    }
    require(result["aggregate"]["all_cpu_gpu_pairs_exact"], "CPU/GPU pair mismatch")
    require(result["aggregate"]["all_calibration_monotonic"], "calibration regression")
    require(result["aggregate"]["all_stage_samples_nonzero_and_ordered"],
            "stage order or zero sample")
    require(result["aggregate"]["all_repeat_heavy_gt_light"],
            "heavy/light separation")
    require(all(delta < 0 for delta in result["aggregate"]["two_pass_boundary_delta_ns"]),
            "H3 falsifier missing")
    require(result["aggregate"]["all_precommit_and_postcommit_prewait_zero"],
            "unexpected early values")
    require(result["aggregate"]["pixels"] == ["5340bfff", "5340bfff"],
            "render output")
    return result


def report(result):
    agg = result["aggregate"]
    light = agg["light_fragment_ns"]
    heavy = agg["heavy_fragment_ns"]
    return "\n".join([
        "EXP-0052 deterministic analysis",
        f"canonical_runs={','.join(result['canonical_runs'])}",
        f"calibration_intervals={agg['calibration_intervals']}",
        f"timestamp_pair_calls={agg['timestamp_pair_calls']}",
        f"cpu_gpu_pairs_exact={str(agg['all_cpu_gpu_pairs_exact']).lower()}",
        f"calibration_monotonic={str(agg['all_calibration_monotonic']).lower()}",
        f"stage_passes={agg['stage_passes']}",
        f"stage_samples_nonzero_ordered={str(agg['all_stage_samples_nonzero_and_ordered']).lower()}",
        f"repeat_pairs={agg['repeat_pairs']}",
        f"heavy_gt_light_all={str(agg['all_repeat_heavy_gt_light']).lower()}",
        f"light_fragment_ns_min_max={min(light)},{max(light)}",
        f"heavy_fragment_ns_min_max={min(heavy)},{max(heavy)}",
        "two_pass_boundary_delta_ns=" + ",".join(map(str, agg["two_pass_boundary_delta_ns"])),
        f"precommit_postcommit_prewait_zero={str(agg['all_precommit_and_postcommit_prewait_zero']).lower()}",
        f"completed_commands={agg['completed_commands']}",
        "H3=FALSIFIED",
        "scope=M4 public Metal API behavior; no A18 or Linux UAPI claim",
        "apple_binary_introspection=NONE",
        "",
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = analyze()
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (args.output_dir / "report.txt").write_text(report(result))


if __name__ == "__main__":
    main()
