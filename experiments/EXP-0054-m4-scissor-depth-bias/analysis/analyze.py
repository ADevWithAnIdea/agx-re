#!/usr/bin/env python3
"""Deterministically reduce EXP-0054 authored public-API readbacks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RUNS = {
    "m4_20260817_run01": "initial",
    "m4_20260817_run02": "initial",
    "m4_20260817_run03": "final",
    "m4_20260817_run04": "final",
}
CANONICAL = ("m4_20260817_run03", "m4_20260817_run04")
INITIAL = ("m4_20260817_run01", "m4_20260817_run02")
W = H = 16
GUARD = 32
PIXEL_BYTES = W * H * 4
GUARDED_BYTES = GUARD + PIXEL_BYTES + GUARD
PAIR_RE = re.compile(r"([a-z0-9_]+)=([^ ]+)")
CLEAR = bytes.fromhex("01020304")
SINGLE = bytes.fromhex("112233ff")
MULTI0 = bytes.fromhex("214365ff")
MULTI1 = bytes.fromhex("9a57c3ff")
BASE = bytes.fromhex("224488ff")
BIASED = bytes.fromhex("cc3311ff")

SCISSOR = {
    "scissor-full": (0, 0, 16, 16),
    "scissor-asymmetric": (3, 5, 7, 4),
    "scissor-edge": (15, 14, 1, 2),
    "scissor-empty-width": (6, 7, 0, 5),
    "scissor-empty-height": (6, 7, 5, 0),
}
MULTI = {
    "multi-base": ((1, 2, 5, 6), (9, 3, 4, 10)),
    "multi-rect1-change": ((1, 2, 5, 6), (11, 8, 3, 5)),
}
BIAS = {
    "dbias-flat-zero": ("flat", "less", 0.0, 0.0, 0.0, False),
    "dbias-flat-negative": ("flat", "less", -1.0, 0.0, 0.0, True),
    "dbias-flat-positive": ("flat", "less", 1.0, 0.0, 0.0, False),
    "dbias-flat-slope-negative": ("flat", "less", 0.0, -1.0, 0.0, False),
    "dbias-flat-slope-positive": ("flat", "less", 0.0, 1.0, 0.0, False),
    "dbias-slope-zero": ("sloped", "less", 0.0, 0.0, 0.0, False),
    "dbias-slope-negative": ("sloped", "less", 0.0, -1.0, 0.0, True),
    "dbias-slope-positive": ("sloped", "less", 0.0, 1.0, 0.0, False),
    "dbias-large-negative": ("flat", "less", None, 0.0, 0.0, True),
    "dbias-clamp-negative": ("flat", "less", None, 0.0, -0.001, True),
    "dbias-large-positive": ("flat", "greater", None, 0.0, 0.0, True),
    "dbias-clamp-positive": ("flat", "greater", None, 0.0, 0.001, True),
}

DEPTH_SHA_COMMON = {
    "dbias-flat-zero": "f6266df512f071ac505eed191ae133d690a7755f1f079e31cd24da47ac98e3ae",
    "dbias-flat-negative": "9c5fbb5df80f3c3a9f785087e3d08c98167a7bbea275518bf25fcd658c76759f",
    "dbias-flat-positive": "f6266df512f071ac505eed191ae133d690a7755f1f079e31cd24da47ac98e3ae",
    "dbias-flat-slope-negative": "f6266df512f071ac505eed191ae133d690a7755f1f079e31cd24da47ac98e3ae",
    "dbias-flat-slope-positive": "f6266df512f071ac505eed191ae133d690a7755f1f079e31cd24da47ac98e3ae",
    "dbias-slope-zero": "d7e77b67cffe621b04e5a2db4dbbebb1d3d20c3a656664ddb970665e4b70e1a8",
    "dbias-slope-negative": "ce090c809f1c2856d25ab0e842eb649a8fb91548158585657b063583b0de846e",
    "dbias-slope-positive": "d7e77b67cffe621b04e5a2db4dbbebb1d3d20c3a656664ddb970665e4b70e1a8",
}
DEPTH_SHA_INITIAL = {
    "dbias-large-negative": "a128198c899f694198282cb765607afdeec530fce615a2808df078f186b548e4",
    "dbias-clamp-negative": "a128198c899f694198282cb765607afdeec530fce615a2808df078f186b548e4",
    "dbias-large-positive": "9a90a74a591b04ca512c8fe49553c94f706622eca72a4a190d283086140903e5",
    "dbias-clamp-positive": "9a90a74a591b04ca512c8fe49553c94f706622eca72a4a190d283086140903e5",
}
DEPTH_SHA_FINAL = {
    "dbias-large-negative": "e20d87f128ba0b430af8b2235f6a2962e904453cc62524bd2613d6ffb9baf9ac",
    "dbias-clamp-negative": "0da1e0272080e7c152f81b0d051ae5dd0dd4c75a391a477bf105c37fd4fe0feb",
    "dbias-large-positive": "965c2f7f275bd2a3a97d2b9c2aed399b978ae005f07ac4fc4f2169f5cde5df21",
    "dbias-clamp-positive": "84352c23b35937cc31d19f65bf75f607f335018d831d1bdee5b5d7567af960f2",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def fbits(value: float) -> str:
    return f"{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def expected_guards() -> tuple[bytes, bytes]:
    return bytes(0xA0 + i for i in range(GUARD)), bytes(0x5F - i for i in range(GUARD))


def guarded(value: str, label: str) -> bytes:
    require(len(value) == GUARDED_BYTES * 2 and re.fullmatch(r"[0-9a-f]+", value) is not None,
            f"{label}: guarded hex shape")
    data = bytes.fromhex(value); prefix, suffix = expected_guards()
    require(data[:GUARD] == prefix and data[-GUARD:] == suffix, f"{label}: guards")
    return data[GUARD:-GUARD]


def fields(line: str, prefix: str) -> dict[str, str]:
    require(line.startswith(prefix + " "), f"prefix {line!r}")
    values: dict[str, str] = {}
    for key, value in PAIR_RE.findall(line[len(prefix) + 1:]):
        require(key not in values, f"duplicate {key}")
        values[key] = value
    require(" ".join(f"{key}={value}" for key, value in values.items()) == line[len(prefix) + 1:],
            f"closed grammar {line!r}")
    return values


def expected_scissor(rect: tuple[int, int, int, int]) -> bytes:
    x, y, width, height = rect
    out = bytearray(CLEAR * (W * H))
    for py in range(y, y + height):
        for px in range(x, x + width):
            out[(py * W + px) * 4:(py * W + px + 1) * 4] = SINGLE
    return bytes(out)


def expected_multi(rects: tuple[tuple[int, int, int, int], tuple[int, int, int, int]]) -> bytes:
    out = bytearray(CLEAR * (W * H))
    for rect, color in zip(rects, (MULTI0, MULTI1)):
        x, y, width, height = rect
        for py in range(y, y + height):
            for px in range(x, x + width):
                out[(py * W + px) * 4:(py * W + px + 1) * 4] = color
    return bytes(out)


def color_counts(data: bytes, first: bytes, second: bytes) -> tuple[int, int, int, int]:
    counts = [0, 0, 0, 0]
    for index in range(W * H):
        pixel = data[index * 4:index * 4 + 4]
        if pixel == first: counts[0] += 1
        elif pixel == second: counts[1] += 1
        elif pixel == CLEAR: counts[2] += 1
        else: counts[3] += 1
    return tuple(counts)


def parse_run(run_id: str, generation: str) -> dict[str, object]:
    record = json.loads((EXP / "raw" / run_id / "run.json").read_text())
    require(record["exit"] == 0 and not record.get("timed_out", False), f"{run_id}: execution")
    lines = record["stdout"].splitlines()
    require(lines[:3] == ["DEVICE Apple M4",
            "SCOPE trace=none compiled_shader_bytes=uninspected integer_bias_selector=absent_public_header",
            "MULTI supported=1 error_hex=none"], f"{run_id}: header")
    require(lines[-1] == "RESULT OK" and record["stdout"].endswith("\n"), f"{run_id}: result")
    require(len(lines) == 23, f"{run_id}: exact line count")
    expected_order = [*SCISSOR, *MULTI, *BIAS]
    observed_order: list[str] = []
    summary: dict[str, dict[str, object]] = {}
    for line in lines[3:-1]:
        item = fields(line, "CASE")
        name = item["name"]; observed_order.append(name)
        require(name not in summary, f"{run_id}: duplicate case {name}")
        require(item["accepted"] == "1" and item["status"] == "4" and item["error_hex"] == "none",
                f"{run_id}/{name}: status")
        require(item["guard_errors"] == "0", f"{run_id}/{name}: guard count")
        if item["kind"] == "scissor":
            require(set(item) == {"kind","name","x","y","width","height","accepted","status",
                    "error_hex","changed","clear","other","guard_errors","color_guarded_hex"},
                    f"{run_id}/{name}: scissor fields")
            rect = SCISSOR[name]
            require(tuple(int(item[key]) for key in ("x","y","width","height")) == rect,
                    f"{run_id}/{name}: rectangle")
            color = guarded(item["color_guarded_hex"], f"{run_id}/{name}/color")
            expect = expected_scissor(rect)
            require(color == expect, f"{run_id}/{name}: exact pixels")
            changed, _, clear, other = color_counts(color, SINGLE, MULTI1)
            require((int(item["changed"]),int(item["clear"]),int(item["other"])) ==
                    (changed,clear,other), f"{run_id}/{name}: counts")
            summary[name] = {"changed":changed,"clear":clear,"sha256":hashlib.sha256(color).hexdigest()}
        elif item["kind"] == "multi":
            require(set(item) == {"kind","name","accepted","status","error_hex","red","green",
                    "clear","other","guard_errors","color_guarded_hex"},
                    f"{run_id}/{name}: multi fields")
            color = guarded(item["color_guarded_hex"], f"{run_id}/{name}/color")
            expect = expected_multi(MULTI[name]); require(color == expect, f"{run_id}/{name}: exact pixels")
            red, green, clear, other = color_counts(color, MULTI0, MULTI1)
            require(tuple(int(item[key]) for key in ("red","green","clear","other")) ==
                    (red,green,clear,other), f"{run_id}/{name}: counts")
            summary[name] = {"red":red,"green":green,"clear":clear,
                             "sha256":hashlib.sha256(color).hexdigest()}
        else:
            require(item["kind"] == "dbias" and name in BIAS, f"{run_id}/{name}: kind")
            require(set(item) == {"kind","name","geometry","compare","constant_bits","slope_bits",
                    "clamp_bits","accepted","status","error_hex","base","biased","clear","other",
                    "finite","guard_errors","color_guarded_hex","depth_guarded_hex"},
                    f"{run_id}/{name}: dbias fields")
            geometry, compare, constant, slope, clamp, passes = BIAS[name]
            if constant is None:
                sign = -1.0 if "negative" in name else 1.0
                constant = sign * (100.0 if generation == "initial" else 100000.0)
            require((item["geometry"],item["compare"],item["constant_bits"],item["slope_bits"],item["clamp_bits"]) ==
                    (geometry,compare,fbits(constant),fbits(slope),fbits(clamp)),
                    f"{run_id}/{name}: exact API inputs")
            color = guarded(item["color_guarded_hex"], f"{run_id}/{name}/color")
            depth = guarded(item["depth_guarded_hex"], f"{run_id}/{name}/depth")
            expected_color = BIASED if passes else BASE
            require(color == expected_color * (W * H), f"{run_id}/{name}: exact color")
            base, biased, clear, other = color_counts(color, BASE, BIASED)
            require(tuple(int(item[key]) for key in ("base","biased","clear","other")) ==
                    (base,biased,clear,other), f"{run_id}/{name}: counts")
            values = struct.unpack("<256f", depth)
            require(all(math.isfinite(value) for value in values) and item["finite"] == "256",
                    f"{run_id}/{name}: finite depth")
            depth_hash = hashlib.sha256(depth).hexdigest()
            expected_hashes = DEPTH_SHA_COMMON | (DEPTH_SHA_INITIAL if generation == "initial" else DEPTH_SHA_FINAL)
            require(depth_hash == expected_hashes[name], f"{run_id}/{name}: exact depth bytes")
            summary[name] = {"base":base,"biased":biased,"depth_sha256":depth_hash,
                             "depth_min":min(values),"depth_max":max(values),
                             "unique_depth_values":len(set(values))}
    require(observed_order == expected_order, f"{run_id}: case order")
    return {"run":run_id,"generation":generation,"cases":summary,
            "stdout_sha256":hashlib.sha256(record["stdout"].encode()).hexdigest()}


def analyze() -> dict[str, object]:
    runs = [parse_run(run_id, generation) for run_id, generation in RUNS.items()]
    require(runs[0]["stdout_sha256"] == runs[1]["stdout_sha256"], "initial repetitions differ")
    require(runs[2]["stdout_sha256"] == runs[3]["stdout_sha256"], "final repetitions differ")
    initial = runs[0]["cases"]; final = runs[2]["cases"]
    require(all(initial[name] == final[name] for name in [*SCISSOR,*MULTI,
            *list(BIAS)[:8]]), "unchanged follow-up cases differ")
    def flat(name: str) -> float:
        return float(final[name]["depth_min"])
    def f32(value: float) -> float:
        return struct.unpack("<f", struct.pack("<f", value))[0]
    unit = 2.0 ** -24
    require(flat("dbias-flat-negative") == f32(0.5 - unit),
            "constant -1 / 2^-24 correlation")
    require(float(initial["dbias-large-negative"]["depth_min"]) == f32(0.5 - 100.0 * unit) and
            float(initial["dbias-large-positive"]["depth_min"]) == f32(0.5 + 100.0 * unit),
            "constant magnitude-100 / 2^-24 correlation")
    require(flat("dbias-large-negative") == f32(0.5 - 100000.0 * unit) and
            flat("dbias-large-positive") == f32(0.5 + 100000.0 * unit),
            "constant magnitude-100000 / 2^-24 correlation")
    return {
        "schema":1,
        "experiment":"EXP-0054-m4-scissor-depth-bias",
        "canonical_runs":list(CANONICAL),
        "preserved_initial_successes":list(INITIAL),
        "runs":runs,
        "observations":{
            "single_scissor_changed_pixels":{"full":256,"asymmetric":28,"edge":2,
                "empty_width":0,"empty_height":0},
            "multiple_scissor_pixels":{"base":{"slot0":30,"slot1":40},
                "slot1_changed":{"slot0":30,"slot1":15}},
            "flat_constant_negative":flat("dbias-flat-negative"),
            "flat_unbiased":flat("dbias-flat-zero"),
            "flat_depth32_constant_unit":"2^-24 for tested -1, +/-100, +/-100000 inputs",
            "sloped_unbiased_range":[final["dbias-slope-zero"]["depth_min"],
                                      final["dbias-slope-zero"]["depth_max"]],
            "sloped_negative_range":[final["dbias-slope-negative"]["depth_min"],
                                      final["dbias-slope-negative"]["depth_max"]],
            "initial_clamp_control":{"negative_equal":
                initial["dbias-large-negative"]["depth_sha256"] == initial["dbias-clamp-negative"]["depth_sha256"],
                "positive_equal":initial["dbias-large-positive"]["depth_sha256"] ==
                                  initial["dbias-clamp-positive"]["depth_sha256"]},
            "engaged_clamp":{"negative_unclamped":flat("dbias-large-negative"),
                "negative_clamped":flat("dbias-clamp-negative"),
                "positive_unclamped":flat("dbias-large-positive"),
                "positive_clamped":flat("dbias-clamp-positive")},
        },
        "hypotheses":{
            "H1":"SUPPORTED for tested exact half-open/empty single scissors",
            "H2":"SUPPORTED for tested two public viewport-indexed scissors and slot-1 perturbation",
            "H3":"SUPPORTED for tested constant/slope signs and flat slope-only controls",
            "H4":"FALSIFIED as preregistered: magnitude 100 did not engage the 0.001 clamp",
            "H5":"PUBLIC API ABSENCE ONLY; private/integer mode remains UNKNOWN",
            "H6":"SUPPORTED for tested sign-matched magnitude-100000/0.001 clamp pairs",
        },
        "scope":{"target":"Apple M4/G16G-class only","a18_pro":"UNTESTED",
            "p0_3":"OPEN","isp_scissor_base":"UNKNOWN","isp_dbias_base":"UNKNOWN",
            "integer_depth_bias":"UNKNOWN","linux_uapi_mapping":"NOT ESTABLISHED",
            "bo_payload_tracing":"NONE","apple_binary_introspection":"NONE",
            "compiled_shader_bytes_inspected":"NONE"},
    }


def report(result: dict[str, object]) -> str:
    obs = result["observations"]; clamp = obs["engaged_clamp"]
    return "\n".join([
        "EXP-0054 deterministic analysis",
        "canonical_runs=" + ",".join(result["canonical_runs"]),
        "preserved_initial_successes=" + ",".join(result["preserved_initial_successes"]),
        "scissor=full:256,asymmetric:28,edge:2,empty-width:0,empty-height:0 exact",
        "multi=base-slot0:30,base-slot1:40,changed-slot0:30,changed-slot1:15 exact",
        f"depth_flat=base:{obs['flat_unbiased']:.9g},constant-negative:{obs['flat_constant_negative']:.9g}",
        "depth32_flat_constant_unit=2^-24 for tested -1,+/-100,+/-100000 inputs",
        "initial_clamp_control=inactive; clamped and unclamped magnitude-100 bytes identical",
        f"engaged_negative=unclamped:{clamp['negative_unclamped']:.9g},clamped:{clamp['negative_clamped']:.9g}",
        f"engaged_positive=unclamped:{clamp['positive_unclamped']:.9g},clamped:{clamp['positive_clamped']:.9g}",
        "verdict=PARTIAL; public M4 behavior only; P0.3 remains OPEN",
        "unknown=isp_scissor_base,isp_dbias_base,integer-mode,Linux-UAPI,A18",
        "apple_binary_introspection=NONE",
        "bo_payload_tracing=NONE",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    result = analyze()
    (args.output_dir / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "report.txt").write_text(report(result))


if __name__ == "__main__":
    main()
