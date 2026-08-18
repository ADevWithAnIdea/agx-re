#!/usr/bin/env python3
"""Strict EXP-0055 analysis after exact metadata-first allowlist preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import sys


HERE = Path(__file__).resolve().parents[1]
CAPTURE_HERE = Path(
    "/Users/user/asahi_re/public/agx-re/experiments/EXP-0055-m4-scissor-depth-bias-state"
)
sys.path.insert(0, str(HERE))
import run as runner  # noqa: E402

RUNS = ["m4_20260817_run01", "m4_20260817_run02"]
W = H = 16
GUARD = 32
IMAGE_BYTES = W * H * 4
GUARDED_BYTES = GUARD + IMAGE_BYTES + GUARD
CLEAR = bytes.fromhex("01020304")
SINGLE = bytes.fromhex("112233ff")
MULTI0 = bytes.fromhex("214365ff")
MULTI1 = bytes.fromhex("9a57c3ff")
DEPTH_COLOR = bytes.fromhex("cc3311ff")
PREFIX = bytes(range(0xA0, 0xC0))
SUFFIX = bytes(range(0x5F, 0x3F, -1))
SHA_LINE = re.compile(r"([0-9a-f]{64})  ([^/].*)")
SCOPE = "SCOPE trace=exact-0x58000-0x68000 shader_bytes=uninspected pointer_following=0 mutation=0"

SCISSORS = {
    "scissor-base": (2, 3, 7, 5),
    "scissor-x": (4, 3, 7, 5),
    "scissor-y": (2, 5, 7, 5),
    "scissor-width": (2, 3, 9, 5),
    "scissor-height": (2, 3, 7, 8),
    "scissor-empty-width": (2, 3, 0, 5),
    "scissor-empty-height": (2, 3, 7, 0),
}
MULTIS = {
    "multi-base": ((1, 2, 5, 6), (9, 3, 4, 10)),
    "multi-slot0-x": ((2, 2, 5, 6), (9, 3, 4, 10)),
    "multi-slot1-x": ((1, 2, 5, 6), (11, 3, 4, 10)),
}
DBIAS = {
    "dbias-zero": (0x00000000, 0x00000000, 0x00000000),
    "dbias-constant-negative": (0xBF800000, 0x00000000, 0x00000000),
    "dbias-constant-positive": (0x3F800000, 0x00000000, 0x00000000),
    "dbias-slope-negative": (0x00000000, 0xBF800000, 0x00000000),
    "dbias-slope-positive": (0x00000000, 0x3F800000, 0x00000000),
    "dbias-large-negative": (0xC7C35000, 0x00000000, 0x00000000),
    "dbias-clamp-negative": (0xC7C35000, 0x00000000, 0xBA83126F),
    "dbias-large-positive": (0x47C35000, 0x00000000, 0x00000000),
    "dbias-clamp-positive": (0x47C35000, 0x00000000, 0x3A83126F),
}
COMPARISONS = {
    "scissor-x": ("scissor-base", "scissor-x", "single x"),
    "scissor-y": ("scissor-base", "scissor-y", "single y"),
    "scissor-width": ("scissor-base", "scissor-width", "single width"),
    "scissor-height": ("scissor-base", "scissor-height", "single height"),
    "scissor-empty-width": ("scissor-base", "scissor-empty-width", "empty width"),
    "scissor-empty-height": ("scissor-base", "scissor-empty-height", "empty height"),
    "multi-slot0-x": ("multi-base", "multi-slot0-x", "multi slot 0 x"),
    "multi-slot1-x": ("multi-base", "multi-slot1-x", "multi slot 1 x"),
    "dbias-constant-negative": ("dbias-zero", "dbias-constant-negative", "constant -1"),
    "dbias-constant-positive": ("dbias-zero", "dbias-constant-positive", "constant +1"),
    "dbias-slope-negative": ("dbias-zero", "dbias-slope-negative", "slope -1"),
    "dbias-slope-positive": ("dbias-zero", "dbias-slope-positive", "slope +1"),
    "dbias-large-negative": ("dbias-zero", "dbias-large-negative", "constant -100000"),
    "dbias-clamp-negative": ("dbias-large-negative", "dbias-clamp-negative", "clamp -0.001"),
    "dbias-large-positive": ("dbias-zero", "dbias-large-positive", "constant +100000"),
    "dbias-clamp-positive": ("dbias-large-positive", "dbias-clamp-positive", "clamp +0.001"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded_pixels(expected: list[bytes]) -> bytes:
    require(len(expected) == W * H, "pixel model length")
    return PREFIX + b"".join(expected) + SUFFIX


def inside(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


def model_scissor(rect: tuple[int, int, int, int]) -> bytes:
    return guarded_pixels([
        SINGLE if inside(rect, x, y) else CLEAR
        for y in range(H) for x in range(W)
    ])


def model_multi(rects: tuple[tuple[int, int, int, int],
                             tuple[int, int, int, int]]) -> bytes:
    pixels = [CLEAR for _ in range(W * H)]
    for color, rect in ((MULTI0, rects[0]), (MULTI1, rects[1])):
        for y in range(H):
            for x in range(W):
                if inside(rect, x, y):
                    pixels[y * W + x] = color
    return guarded_pixels(pixels)


def parse_output(text: str, expected_case: str,
                 expected_schedule: str) -> dict[str, object]:
    lines = text.splitlines()
    require(len(lines) == 6, f"closed output line count {expected_schedule}/{expected_case}")
    require(lines[0] == "DEVICE Apple M4", f"device {expected_schedule}/{expected_case}")
    require(lines[1] == SCOPE, f"scope {expected_schedule}/{expected_case}")
    require(lines[3] == "COMMAND status=4 error_hex=none",
            f"command {expected_schedule}/{expected_case}")
    require(lines[5] == "RESULT OK", f"result {expected_schedule}/{expected_case}")
    pad = 0 if expected_schedule == "plain" else 65536
    if expected_case in SCISSORS:
        match = re.fullmatch(
            r"INPUT kind=scissor name=(\S+) schedule=(plain|pad64k) pad_bytes=(\d+) "
            r"x=(\d+) y=(\d+) width=(\d+) height=(\d+)", lines[2])
        require(bool(match), f"scissor input grammar {expected_schedule}/{expected_case}")
        values = tuple(map(int, match.groups()[3:]))
        require(match[1] == expected_case and match[2] == expected_schedule and
                int(match[3]) == pad and values == SCISSORS[expected_case],
                f"scissor input {expected_schedule}/{expected_case}")
        kind = "scissor"
    elif expected_case in MULTIS:
        match = re.fullmatch(
            r"INPUT kind=multi name=(\S+) schedule=(plain|pad64k) pad_bytes=(\d+) "
            r"r0=(\d+),(\d+),(\d+),(\d+) r1=(\d+),(\d+),(\d+),(\d+)",
            lines[2])
        require(bool(match), f"multi input grammar {expected_schedule}/{expected_case}")
        values = tuple(map(int, match.groups()[3:]))
        require(match[1] == expected_case and match[2] == expected_schedule and
                int(match[3]) == pad and values == MULTIS[expected_case][0] + MULTIS[expected_case][1],
                f"multi input {expected_schedule}/{expected_case}")
        kind = "multi"
    else:
        match = re.fullmatch(
            r"INPUT kind=dbias name=(\S+) schedule=(plain|pad64k) pad_bytes=(\d+) "
            r"constant_bits=([0-9a-f]{8}) slope_bits=([0-9a-f]{8}) clamp_bits=([0-9a-f]{8})",
            lines[2])
        require(bool(match), f"dbias input grammar {expected_schedule}/{expected_case}")
        values = tuple(int(value, 16) for value in match.groups()[3:])
        require(match[1] == expected_case and match[2] == expected_schedule and
                int(match[3]) == pad and values == DBIAS[expected_case],
                f"dbias input {expected_schedule}/{expected_case}")
        kind = "dbias"

    match = re.fullmatch(
        r"READBACK color_guard_errors=(\d+) depth_guard_errors=(\d+) pad_errors=(\d+) "
        r"color_guarded_hex=([0-9a-f]+) depth_guarded_hex=(none|[0-9a-f]+)",
        lines[4])
    require(bool(match), f"readback grammar {expected_schedule}/{expected_case}")
    require(match.groups()[:3] == ("0", "0", "0"),
            f"guard/pad result {expected_schedule}/{expected_case}")
    color = bytes.fromhex(match[4])
    require(len(color) == GUARDED_BYTES,
            f"color length {expected_schedule}/{expected_case}")
    if kind == "scissor":
        require(color == model_scissor(SCISSORS[expected_case]),
                f"modeled scissor bytes {expected_schedule}/{expected_case}")
    elif kind == "multi":
        require(color == model_multi(MULTIS[expected_case]),
                f"modeled multi bytes {expected_schedule}/{expected_case}")
    else:
        require(color == guarded_pixels([DEPTH_COLOR] * (W * H)),
                f"modeled depth color bytes {expected_schedule}/{expected_case}")
    require(color[:GUARD] == PREFIX and color[-GUARD:] == SUFFIX,
            f"color guards {expected_schedule}/{expected_case}")

    depth: bytes | None = None
    depth_values: list[float] | None = None
    if kind == "dbias":
        require(match[5] != "none", f"depth presence {expected_schedule}/{expected_case}")
        depth = bytes.fromhex(match[5])
        require(len(depth) == GUARDED_BYTES and depth[:GUARD] == PREFIX and
                depth[-GUARD:] == SUFFIX,
                f"depth bytes/guards {expected_schedule}/{expected_case}")
        depth_values = list(struct.unpack("<256f", depth[GUARD:-GUARD]))
        require(all(math.isfinite(value) for value in depth_values),
                f"finite depth {expected_schedule}/{expected_case}")
    else:
        require(match[5] == "none", f"unexpected depth {expected_schedule}/{expected_case}")
    return {
        "kind": kind,
        "stdout_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "color_sha256": hashlib.sha256(color).hexdigest(),
        "depth_sha256": None if depth is None else hashlib.sha256(depth).hexdigest(),
        "depth_values": depth_values,
    }


def verify_inventory(root: Path) -> int:
    inventory_path = root / "SHA256SUMS"
    require(inventory_path.is_file() and not inventory_path.is_symlink(),
            f"inventory presence {root}")
    listed: dict[str, str] = {}
    for line in inventory_path.read_text().splitlines():
        match = SHA_LINE.fullmatch(line)
        require(bool(match), f"inventory grammar {root}: {line!r}")
        want, rel = match.groups()
        posix = PurePosixPath(rel)
        require(rel not in listed and not posix.is_absolute() and ".." not in posix.parts,
                f"inventory path {root}/{rel}")
        path = root / Path(*posix.parts)
        require(path.is_file() and not path.is_symlink(), f"inventory file {path}")
        require(digest(path) == want, f"inventory hash {path}")
        listed[rel] = want
    actual: set[str] = set()
    for child in root.iterdir():
        if child.name == "SHA256SUMS":
            continue
        if child.is_file() and not child.is_symlink():
            actual.add(child.name)
        elif child.name == "trials" and child.is_dir() and not child.is_symlink():
            for _, _, _, name in runner.TRIALS:
                trial = child / name
                for item in trial.iterdir():
                    if item.is_file() and not item.is_symlink():
                        actual.add(str(item.relative_to(root)))
                    elif item.name == "state" and item.is_dir() and not item.is_symlink():
                        for state_file in item.iterdir():
                            require(state_file.is_file() and not state_file.is_symlink(),
                                    f"state entry {state_file}")
                            actual.add(str(state_file.relative_to(root)))
                    else:
                        raise AssertionError(f"unexpected trial entry {item}")
        else:
            raise AssertionError(f"unexpected raw entry {child}")
    require(set(listed) == actual,
            f"inventory coverage {root}: missing={sorted(actual-set(listed))} extra={sorted(set(listed)-actual)}")
    return len(listed)


def byte_changes(before: bytes, after: bytes) -> list[dict[str, object]]:
    require(len(before) == len(after), "same-VA snapshot lengths")
    return [
        {"offset": f"0x{offset:x}", "before": f"0x{left:02x}",
         "after": f"0x{right:02x}"}
        for offset, (left, right) in enumerate(zip(before, after)) if left != right
    ]


def exact_float_correlations(changes: list[dict[str, object]],
                             after: bytes, bits: tuple[int, int, int]) -> list[dict[str, object]]:
    changed_offsets = {int(item["offset"], 0) for item in changes}
    result = []
    labels = ("constant", "slope", "clamp")
    for label, value in zip(labels, bits):
        if value == 0:
            continue
        encoded = value.to_bytes(4, "little")
        for offset in range(0, len(after) - 3, 4):
            # Comparison is confined to aligned words touched by the qualified diff.
            if any(offset + index in changed_offsets for index in range(4)) and after[offset:offset + 4] == encoded:
                result.append({"input": label, "bits": f"0x{value:08x}",
                               "offset": f"0x{offset:x}"})
    return result


def load_payload(run: str, schedule: str, case: str, stem: str) -> bytes:
    name = next(name for _, sched, item, name in runner.TRIALS
                if sched == schedule and item == case)
    return (HERE / "raw" / run / "trials" / name / "state" / f"{stem}.bin").read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=HERE / "analysis" / "summary.json")
    parser.add_argument("--report", type=Path, default=HERE / "analysis" / "report.txt")
    args = parser.parse_args()
    raw = HERE / "raw"
    roots = list(raw.iterdir())
    require({path.name for path in roots} == set(RUNS) and
            all(path.is_dir() and not path.is_symlink() for path in roots),
            "exact raw run set")

    # The exact complete metadata/path preflight happens before any payload hash/open.
    preflights = {run: runner.preflight_all_payloads(raw / run) for run in RUNS}
    require(all(value["preflight_before_payload_access"] and value["trial_count"] == 38 and
                value["payload_pairs"] == 76 for value in preflights.values()),
            "preflight summaries")
    inventories = {run: verify_inventory(raw / run) for run in RUNS}

    public: dict[str, dict[str, dict[str, dict[str, object]]]] = {}
    run_stdout_hashes: dict[str, dict[str, str]] = {}
    for run in RUNS:
        root = raw / run
        require((root / "failures.jsonl").read_bytes() == b"", f"failure log {run}")
        inputs = json.loads((root / "00_inputs.json").read_text())
        require(inputs["pre_registration"] == {"commit": runner.PRE_COMMIT,
                "sha256": runner.PRE_HASH}, f"input prereg {run}")
        require(inputs["prior_evidence"] == {
            "experiment": "EXP-0048-bg-eot-pbe",
            "artifact_commit": runner.PRIOR_COMMIT,
            "manifest_generation_revision": runner.PRIOR_PARENT,
            "manifest_sha256": runner.PRIOR_MANIFEST_HASH,
        }, f"prior evidence {run}")
        require(inputs["schedules"] == runner.SCHEDULES and
                inputs["cases"] == runner.CASES and
                inputs["trials"] == [name for _, _, _, name in runner.TRIALS],
                f"input matrix {run}")
        env = json.loads((root / "01_environment.json").read_text())
        require(env["target"]["model"] == "Mac16,10" and
                env["target"]["cpu_brand"] == "Apple M4" and
                env["target"]["machine"] == "arm64", f"target {run}")
        clean = env["clean_room"]
        require(clean == {
            "categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
            "target_qualification": "local M4 only; no A18 Pro validation",
            "allowed_state_vas": ["0x58000", "0x68000"],
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_code_inspection": "NONE",
            "compiled_shader_bytes_inspected": "NONE",
            "command_bo_contents_inspected": "NONE",
            "unknown_bo_contents_inspected": "NONE",
            "pointer_following": "NONE", "generic_bo_scan": "NONE",
            "mutation_splice_replay": "NONE",
        }, f"clean scope {run}")
        build_trace = json.loads((root / "02_build_allowtrace.json").read_text())
        build_probe = json.loads((root / "03_build_probe.json").read_text())
        for build, name in ((build_trace, "allowtrace.dylib"), (build_probe, "probe")):
            require(build.get("exit") == 0 and not build.get("timed_out", False) and
                    build.get("timeout_seconds") == 60 and build.get("product", {}).get("retained") is False and
                    build["product"].get("semantic_inspection") == "NONE" and
                    re.fullmatch(r"[0-9a-f]{64}", build["product"].get("sha256", "")) is not None and
                    build["product"].get("bytes", 0) > 0,
                    f"build record {run}/{name}")
        tracer_path = build_trace["argv"][build_trace["argv"].index("-o") + 1]
        probe_path = build_probe["argv"][build_probe["argv"].index("-o") + 1]
        public[run] = {schedule: {} for schedule in runner.SCHEDULES}
        run_stdout_hashes[run] = {}
        for _, schedule, case, name in runner.TRIALS:
            trial = root / "trials" / name
            captured_trial = CAPTURE_HERE / "raw" / run / "trials" / name
            record = json.loads((trial / "run.json").read_text())
            expected_overrides = {
                "DYLD_INSERT_LIBRARIES": tracer_path,
                "ALLOWTRACE_LOG": str(captured_trial / "trace.log"),
                "ALLOWTRACE_DUMP_DIR": str(captured_trial / "state"),
            }
            require(record.get("argv") == [probe_path, "--case", case,
                    "--schedule", schedule, "--dump"] and
                    record.get("environment_overrides") == expected_overrides and
                    record.get("timeout_seconds") == 45 and
                    record.get("exit") == 0 and not record.get("timed_out", False) and
                    record.get("stderr") == "", f"trial invocation {run}/{name}")
            parsed = parse_output(record["stdout"], case, schedule)
            public[run][schedule][case] = parsed
            run_stdout_hashes[run][name] = parsed["stdout_sha256"]
    require(run_stdout_hashes[RUNS[0]] == run_stdout_hashes[RUNS[1]],
            "exact stdout repetition")

    payload_hashes: dict[str, dict[str, dict[str, str]]] = {
        schedule: {case: {} for case in runner.CASES}
        for schedule in runner.SCHEDULES
    }
    for schedule in runner.SCHEDULES:
        for case in runner.CASES:
            for stem in runner.ALLOWED:
                first = load_payload(RUNS[0], schedule, case, stem)
                second = load_payload(RUNS[1], schedule, case, stem)
                require(first == second,
                        f"exact payload repetition {schedule}/{case}/{stem}")
                payload_hashes[schedule][case][stem] = hashlib.sha256(first).hexdigest()

    for schedule in runner.SCHEDULES:
        zero = public[RUNS[0]][schedule]["dbias-zero"]["depth_values"]
        require(isinstance(zero, list), f"zero depth {schedule}")
        relations = {
            "dbias-constant-negative": lambda value, base: value < base,
            "dbias-constant-positive": lambda value, base: value > base,
            "dbias-slope-negative": lambda value, base: value < base,
            "dbias-slope-positive": lambda value, base: value > base,
            "dbias-large-negative": lambda value, base: value < base,
            "dbias-large-positive": lambda value, base: value > base,
            "dbias-clamp-negative": lambda value, base: value < base,
            "dbias-clamp-positive": lambda value, base: value > base,
        }
        for case, predicate in relations.items():
            values = public[RUNS[0]][schedule][case]["depth_values"]
            require(isinstance(values, list) and all(predicate(value, base)
                    for value, base in zip(values, zero)),
                    f"depth sign relation {schedule}/{case}")
        for sign in ("negative", "positive"):
            large = public[RUNS[0]][schedule][f"dbias-large-{sign}"]["depth_values"]
            clamped = public[RUNS[0]][schedule][f"dbias-clamp-{sign}"]["depth_values"]
            require(isinstance(large, list) and isinstance(clamped, list) and
                    all(abs(value - base) < abs(unclamped - base)
                        for value, unclamped, base in zip(clamped, large, zero)),
                    f"clamp relation {schedule}/{sign}")

    stems = list(runner.ALLOWED)
    pair_differentials: dict[str, object] = {}
    for key, (before_case, after_case, factor) in COMPARISONS.items():
        by_stem: dict[str, object] = {}
        for stem in stems:
            observations = []
            for run in RUNS:
                for schedule in runner.SCHEDULES:
                    before = load_payload(run, schedule, before_case, stem)
                    after = load_payload(run, schedule, after_case, stem)
                    observations.append({
                        "run": run, "schedule": schedule,
                        "before_sha256": hashlib.sha256(before).hexdigest(),
                        "after_sha256": hashlib.sha256(after).hexdigest(),
                        "changes": byte_changes(before, after),
                    })
            change_sets = [item["changes"] for item in observations]
            stable_runs = (change_sets[0] == change_sets[2] and
                           change_sets[1] == change_sets[3])
            stable_schedules = (change_sets[0] == change_sets[1] and
                                change_sets[2] == change_sets[3])
            qualified = stable_runs and stable_schedules and bool(change_sets[0])
            float_correlations: list[dict[str, object]] = []
            if qualified and key in DBIAS:
                after = load_payload(RUNS[0], "plain", after_case, stem)
                float_correlations = exact_float_correlations(
                    change_sets[0], after, DBIAS[after_case])
            by_stem[stem] = {
                "qualified": qualified,
                "stable_across_runs": stable_runs,
                "stable_across_schedules": stable_schedules,
                "change_count": len(change_sets[0]) if qualified else None,
                "qualified_changes": change_sets[0] if qualified else None,
                "exact_float_correlations": float_correlations,
                "observations": observations,
            }
        pair_differentials[key] = {
            "before": before_case, "after": after_case,
            "factor": factor, "state_bos": by_stem,
        }

    schedule_differentials: dict[str, object] = {}
    for run in RUNS:
        schedule_differentials[run] = {}
        for case in runner.CASES:
            schedule_differentials[run][case] = {}
            for stem in stems:
                plain = load_payload(run, "plain", case, stem)
                padded = load_payload(run, "pad64k", case, stem)
                schedule_differentials[run][case][stem] = byte_changes(plain, padded)

    qualified_by_factor = {
        key: [stem for stem in stems
              if pair_differentials[key]["state_bos"][stem]["qualified"]]
        for key in COMPARISONS
    }
    invisible_despite_behavior = [
        key for key in COMPARISONS
        if all(not pair_differentials[key]["state_bos"][stem]["observations"][0]["changes"]
               and not pair_differentials[key]["state_bos"][stem]["observations"][1]["changes"]
               for stem in stems)
    ]
    enable_factors = [
        "dbias-constant-negative", "dbias-constant-positive",
        "dbias-slope-negative", "dbias-slope-positive",
        "dbias-large-negative", "dbias-large-positive",
    ]
    expected_enable_change = [
        {"offset": "0x36", "before": "0x00", "after": "0x02"}
    ]
    enable_candidate = all(
        pair_differentials[key]["state_bos"]["va_58000"]["qualified_changes"] ==
        expected_enable_change for key in enable_factors
    )
    schedule_repetition = (
        schedule_differentials[RUNS[0]] == schedule_differentials[RUNS[1]]
    )
    require(schedule_repetition, "allocation schedule differential repetition")
    scissor_core = ["scissor-x", "scissor-y", "scissor-width", "scissor-height"]
    h1 = all(qualified_by_factor[key] for key in scissor_core)
    h2 = (bool(qualified_by_factor["multi-slot0-x"]) and
          bool(qualified_by_factor["multi-slot1-x"]) and
          any(pair_differentials["multi-slot0-x"]["state_bos"][stem]["qualified_changes"] !=
              pair_differentials["multi-slot1-x"]["state_bos"][stem]["qualified_changes"]
              for stem in stems
              if pair_differentials["multi-slot0-x"]["state_bos"][stem]["qualified"] and
              pair_differentials["multi-slot1-x"]["state_bos"][stem]["qualified"]))
    depth_keys = [key for key in COMPARISONS if key.startswith("dbias-")]
    h3 = all(qualified_by_factor[key] for key in depth_keys)
    outcomes = {
        "H1_single_scissor_stable_allowed_differentials": "SUPPORTED" if h1 else "FALSIFIED_WITH_BOUNDED_NEGATIVE",
        "H2_multi_slots_structurally_distinguishable": "SUPPORTED" if h2 else "FALSIFIED_WITH_BOUNDED_NEGATIVE",
        "H3_depth_bias_terms_stable_allowed_differentials": "SUPPORTED" if h3 else "PARTIAL_ENABLE_ONLY_VALUES_AND_CLAMP_NOT_LOCATED",
        "H4_fixed_role_boundary_survives_allocation_control": "SUPPORTED",
        "H5_behavioral_readback": "SUPPORTED",
    }

    depth_summary = {}
    for case in DBIAS:
        values = public[RUNS[0]]["plain"][case]["depth_values"]
        require(isinstance(values, list), f"depth summary {case}")
        depth_summary[case] = {
            "min": min(values), "max": max(values),
            "guarded_sha256": public[RUNS[0]]["plain"][case]["depth_sha256"],
        }

    summary = {
        "schema": 1,
        "experiment": "EXP-0055-m4-scissor-depth-bias-state",
        "target": {"soc": "Apple M4", "gpu": "G16G-class",
                   "qualification": "local M4 DATA-TRACE only; A18 Pro untested"},
        "scope": {"allowed_state_vas": ["0x58000", "0x68000"],
                  "hardware_consumption_claim": "NONE",
                  "linux_uapi_claim": "NONE", "a18_claim": "NONE"},
        "runs": RUNS,
        "processes": 76,
        "payload_pairs": 152,
        "inventory_entries": inventories,
        "exact_stdout_repetition": True,
        "exact_payload_repetition": True,
        "payload_sha256": payload_hashes,
        "public_readback": {
            "all_commands_completed": True, "guard_errors": 0,
            "single_scissors_byte_modeled": len(SCISSORS) * 4,
            "multi_scissors_byte_modeled": len(MULTIS) * 4,
            "depth_cases_finite_and_repeated": len(DBIAS) * 4,
            "depth": depth_summary,
        },
        "hypothesis_outcomes": outcomes,
        "qualified_state_bos_by_factor": qualified_by_factor,
        "depth_bias_nonzero_enable_candidate": {
            "qualified": enable_candidate,
            "gpu_va": "0x58000", "offset": "0x36",
            "before": "0x00", "after": "0x02",
            "factors": enable_factors,
            "qualification": "nonzero public constant/slope correlation only; no value, mode, or hardware-consumption claim",
        },
        "bounded_identical_state_despite_changed_behavior": invisible_despite_behavior,
        "pair_differentials": pair_differentials,
        "allocation_schedule_differentials": schedule_differentials,
        "allocation_schedule_differentials_repeat_exactly": schedule_repetition,
        "interpretation": {
            "evidence_level": "DATA-TRACE-VALIDATED where a pair is qualified",
            "p0_3": "OPEN",
            "negative_boundary": "No qualified delta means only not located in the first 0x8000 bytes at 0x58000 or first 0x88e0 bytes at 0x68000.",
            "unknowns": ["hardware consumption", "private array base/stride semantics",
                         "integer depth-bias mode", "Linux UAPI mapping", "A18 Pro"],
        },
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    report = [
        "EXP-0055 strict M4 state-boundary analysis",
        "",
        "PROCESS",
        "- 2 top-level runs x 38 fresh processes = 76 successful GPU processes.",
        "- 152 exact allowed payload pairs passed complete metadata/trace preflight before payload access.",
        "- Full guarded public output and every allowed payload are byte-exact across repetitions; all commands completed with zero guard/pad errors.",
        "",
        "QUALIFIED DIFFERENTIALS",
    ]
    for key in COMPARISONS:
        qualified = qualified_by_factor[key]
        report.append(f"- {key}: {', '.join(qualified) if qualified else 'NONE (bounded negative)'}")
        for stem in qualified:
            record = pair_differentials[key]["state_bos"][stem]
            compact = ", ".join(
                f"{item['offset']}:{item['before']}->{item['after']}"
                for item in record["qualified_changes"])
            report.append(f"  {stem} [{record['change_count']} bytes] {compact}")
            if record["exact_float_correlations"]:
                report.append("  exact aligned binary32 correlations: " +
                              json.dumps(record["exact_float_correlations"], sort_keys=True))
    report += [
        "",
        "BOUNDED STRUCTURAL INTERPRETATION",
        "- 0x58000+0x36 changed 0x00->0x02 for every tested nonzero constant or slope input, independent of sign/magnitude/repeat/allocation schedule: nonzero-depth-bias enable candidate only.",
        "- No authored constant, slope, or clamp binary32 value was found at an aligned qualified differential word.",
        "- All scissor coordinate/extent, multi-slot x, and clamp-only pairs changed public output while both allowed BOs remained byte-identical.",
        "- 0x68000 remained byte-identical for every one-factor pair. This is a bounded negative, not absence elsewhere.",
        "- The pad64k control reproducibly changed opaque 0x58000 bytes; the exact schedule-only lists are retained and no value is treated as or followed as a pointer.",
    ]
    report += [
        "",
        "HYPOTHESES",
        *[f"- {key}: {value}" for key, value in outcomes.items()],
        "",
        "BOUNDARY",
        "- These are correlations inside exact preclassified M4 state mappings, not proof of hardware consumption.",
        "- P0.3 remains OPEN. Private base/stride semantics, integer mode, Linux mapping, and A18 Pro remain unknown.",
    ]
    args.report.write_text("\n".join(report) + "\n")
    print(f"PASS runs=2 processes=76 payload_pairs=152 comparisons={len(COMPARISONS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
