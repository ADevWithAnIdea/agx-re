#!/usr/bin/env python3
"""Analyze only normalized own-main/readback evidence from EXP-0050."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
RAW = HERE / "raw"
RUNS = [RAW / "m4_20260817_run01", RAW / "m4_20260817_run02"]
CASES = [
    "c0", "c1-only", "c2-only", "c0-c2-decl02", "c0-c2-decl20",
    "mrt3-decl012", "mrt3-decl210", "mrt3-swap12", "color-depth",
    "depth-color-decl", "depth-only", "color-fixed-depth", "mask-f",
    "mask-5", "mask-a", "mask-0", "mask-5-declfirst", "discard-half",
    "atomic-all", "atomic-before-discard", "atomic-after-discard",
    "splice-rt1-to-rt2",
]

CLEAR0 = "01020304" * 4
ZERO = "00000000" * 4
C0 = "11223344" * 4
C1 = "55667788" * 4
C2 = "99aabbcc" * 4

EXPECTED = {
    "c0": ([C0, None, None], None, 0),
    "c1-only": ([None, C1, None], None, 0),
    "c2-only": ([None, None, C2], None, 0),
    "c0-c2-decl02": ([C0, None, C2], None, 0),
    "c0-c2-decl20": ([C0, None, C2], None, 0),
    "mrt3-decl012": ([C0, C1, C2], None, 0),
    "mrt3-decl210": ([C0, C1, C2], None, 0),
    "mrt3-swap12": ([C0, C2, C1], None, 0),
    "color-depth": ([C0, None, None], "0000803e" * 4, 0),
    "depth-color-decl": ([C0, None, None], "0000803e" * 4, 0),
    "depth-only": ([None, None, None], "0000203f" * 4, 0),
    "color-fixed-depth": ([C0, None, None], "0000403f" * 4, 0),
    "mask-f": (["a00000ff" * 4, None, None], None, 0),
    "mask-5": (["40010282" * 4, None, None], None, 0),
    "mask-a": (["60010282" * 4, None, None], None, 0),
    "mask-0": ([CLEAR0, None, None], None, 0),
    "mask-5-declfirst": (["40010282" * 4, None, None], None, 0),
    "discard-half": ([CLEAR0[:16] + C0[:16], None, None], None, 0),
    "atomic-all": ([C0, None, None], None, 4),
    "atomic-before-discard": ([CLEAR0[:16] + C0[:16], None, None], None, 4),
    "atomic-after-discard": ([CLEAR0[:16] + C0[:16], None, None], None, 2),
    "splice-rt1-to-rt2": ([C0, ZERO, C1], None, 0),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_case(run: Path, case: str) -> dict[str, object]:
    return json.loads((run / f"case_{case}.json").read_text())


def main_bytes(record: dict[str, object]) -> bytes:
    data = bytes.fromhex(str(record["main_hex"]))
    assert len(data) == record["main_length"]
    assert hashlib.sha256(data).hexdigest() == record["main_sha256"]
    return data


def color_stores(data: bytes) -> list[dict[str, object]]:
    stores = []
    for off in range(len(data) - 11):
        if data[off:off + 3] == b"\xe7\x06\x54":
            stores.append({
                "offset": off,
                "bytes": data[off:off + 12].hex(),
                "selector_byte_plus_5": data[off + 5],
            })
    return stores


def depth_stores(data: bytes) -> list[dict[str, object]]:
    stores = []
    for off in range(len(data) - 5):
        if data[off:off + 3] == b"\xd7\x14\x54":
            stores.append({"offset": off, "bytes": data[off:off + 6].hex()})
    return stores


def tile_access_records(data: bytes) -> list[dict[str, object]]:
    records = []
    for off in range(len(data) - 5):
        head = data[off:off + 3]
        if head in (b"\x87\x02\x54", b"\x07\x02\x54"):
            records.append({
                "offset": off,
                "kind": "setup" if head[0] == 0x87 else "end",
                "bytes": data[off:off + 6].hex(),
                "semantic_selector_byte_plus_3": data[off + 3],
                "control_byte_plus_4": data[off + 4],
            })
    return records


def byte_diffs(a: bytes, b: bytes) -> list[dict[str, int]]:
    assert len(a) == len(b)
    return [{"offset": i, "a": x, "b": y}
            for i, (x, y) in enumerate(zip(a, b)) if x != y]


def analyze() -> tuple[dict[str, object], str]:
    records: dict[str, dict[str, dict[str, object]]] = {}
    for run in RUNS:
        assert not json.loads((run / "failures.json").read_text())
        records[run.name] = {}
        for case in CASES:
            record = load_case(run, case)
            main_bytes(record)
            render = record["render"]
            assert render["status"] == "OK"
            assert render["pipeline_source"] == "archive"
            colors, depth, counter = EXPECTED[case]
            assert render["colors"] == colors, (case, render["colors"], colors)
            assert render["depth_hex"] == depth, (case, render["depth_hex"], depth)
            assert render["counter"] == counter, (case, render["counter"], counter)
            records[run.name][case] = record

    a, b = (records[run.name] for run in RUNS)
    repeat = {}
    for case in CASES:
        keys = ("source_sha256", "main_hex", "main_length", "main_sha256", "render")
        repeat[case] = all(a[case][key] == b[case][key] for key in keys)
        assert repeat[case], case

    byte_equal_pairs = [
        ("c0-c2-decl02", "c0-c2-decl20"),
        ("mrt3-decl012", "mrt3-decl210"),
        ("color-depth", "depth-color-decl"),
        ("mask-5", "mask-5-declfirst"),
        ("c0", "color-fixed-depth"),
    ]
    pair_results = {}
    for left, right in byte_equal_pairs:
        x, y = main_bytes(a[left]), main_bytes(a[right])
        pair_results[f"{left}__{right}"] = {
            "byte_equal": x == y, "length": len(x), "sha256": a[left]["main_sha256"]}
        assert x == y

    stores = {case: color_stores(main_bytes(a[case])) for case in CASES}
    expected_selectors = {
        "c0": [0], "c1-only": [0], "c2-only": [0],
        "c0-c2-decl02": [2, 0], "c0-c2-decl20": [2, 0],
        "mrt3-decl012": [4, 2, 0], "mrt3-decl210": [4, 2, 0],
        "mrt3-swap12": [4, 2, 0],
    }
    for case, expected in expected_selectors.items():
        got = [store["selector_byte_plus_5"] for store in stores[case]]
        assert got == expected, (case, got, expected)

    tile_access = {case: tile_access_records(main_bytes(a[case]))
                   for case in expected_selectors}
    isolated_semantic = {}
    for case, expected in (("c0", 0x0c), ("c1-only", 0x30), ("c2-only", 0xc0)):
        selected = [record for record in tile_access[case]
                    if record["semantic_selector_byte_plus_3"] != 0]
        got = [record["semantic_selector_byte_plus_3"] for record in selected]
        assert got == [expected, expected], (case, got)
        isolated_semantic[case] = got
    isolated_diffs = {
        "c0_to_c1_only": byte_diffs(main_bytes(a["c0"]), main_bytes(a["c1-only"])),
        "c0_to_c2_only": byte_diffs(main_bytes(a["c0"]), main_bytes(a["c2-only"])),
    }
    assert isolated_diffs["c0_to_c1_only"] == [
        {"offset": 29, "a": 0x0c, "b": 0x30},
        {"offset": 47, "a": 0x0c, "b": 0x30},
    ]
    assert isolated_diffs["c0_to_c2_only"] == [
        {"offset": 29, "a": 0x0c, "b": 0xc0},
        {"offset": 47, "a": 0x0c, "b": 0xc0},
    ]

    depths = {case: depth_stores(main_bytes(a[case]))
              for case in ("color-depth", "depth-color-decl", "depth-only",
                           "color-fixed-depth")}
    assert len(depths["color-depth"]) == 1
    assert len(depths["depth-color-decl"]) == 1
    assert len(depths["depth-only"]) == 1
    assert depths["color-fixed-depth"] == []

    mask_diffs = {
        "f_to_5": byte_diffs(main_bytes(a["mask-f"]), main_bytes(a["mask-5"])),
        "5_to_a": byte_diffs(main_bytes(a["mask-5"]), main_bytes(a["mask-a"])),
    }
    assert mask_diffs["f_to_5"] == [{"offset": 45, "a": 0x1e, "b": 0x0a}]
    assert mask_diffs["5_to_a"] == [{"offset": 45, "a": 0x0a, "b": 0x14}]
    assert a["mask-0"]["main_length"] == 32
    assert not stores["mask-0"]

    mutation = a["splice-rt1-to-rt2"]["mutation"]
    assert mutation["change_count"] == 1
    assert mutation["before"] == "0x02" and mutation["after"] == "0x04"
    intact = main_bytes(a["mrt3-decl012"])
    spliced = main_bytes(a["splice-rt1-to-rt2"])
    splice_diffs = byte_diffs(intact, spliced)
    assert splice_diffs == [{"offset": mutation["changed_main_offset"],
                             "a": 0x02, "b": 0x04}]

    summary = {
        "scope": "local Apple M4/G16G only; no A18 claim",
        "runs": [run.name for run in RUNS],
        "case_count_per_run": len(CASES),
        "all_repeat_evidence_equal": all(repeat.values()),
        "repeat": repeat,
        "main": {case: {"length": a[case]["main_length"],
                         "sha256": a[case]["main_sha256"]} for case in CASES},
        "declaration_order_pairs": pair_results,
        "color_store_records": stores,
        "tile_access_records": tile_access,
        "isolated_semantic_selectors": isolated_semantic,
        "isolated_main_diffs": isolated_diffs,
        "depth_store_records": depths,
        "mask_literal_diffs": mask_diffs,
        "splice_diff": splice_diffs,
        "splice_observed": a["splice-rt1-to-rt2"]["render"],
        "hypotheses": {
            "H1": "SUPPORTED for live source-path routing; selector refines to compact active-output ordinal in sparse cases",
            "H2": "SUPPORTED for tested depth values and declaration-order pair",
            "H3": "SUPPORTED for tested masks and declaration-order pair",
            "H4": "SUPPORTED for tested discard and atomic ordering",
            "H5": "FALSIFIED as combined: RT2 received RT1 value, but unwritten RT1 was zero rather than requested clear",
        },
        "evidence_limits": [
            "OWN-SHADER-DIFF/compiler-emitted correlation is not a complete native ABI",
            "single checked splice validates a compact store selector only in the tested contiguous three-RT pipeline",
            "the relationship between semantic tile-access selectors and compact store ordinals is only bounded for tested outputs",
            "no full prolog/epilog linkage, arbitrary-format generation, Linux UAPI mapping, or A18 validation",
        ],
    }

    lines = [
        "EXP-0050 strict own-shader/readback analysis",
        "OBSERVATIONS",
        f"- {len(CASES)} cases per run x 2 runs = {len(CASES)*2} forced-archive executions; all exact repeat evidence matches.",
        "- Declaration-order pairs are byte-identical: sparse RT0+RT2 (98 B), MRT0/1/2 (142 B), color+depth (156 B), and mask-5 (252 B).",
        "- c0 and color-fixed-depth are also byte-identical (54 B): merely attaching/writing fixed depth does not change the tested fragment main.",
        "- Live sparse outputs route by semantic MSL index. Own-main store selector byte +5 is compact: c0/c1-only/c2-only all 0; RT0+RT2 is [2,0]; RT0/1/2 is [4,2,0]. Separate surrounding tile-access selectors carry semantic RT values 0c/30/c0 for isolated color(0/1/2).",
        "- Shader depth writes exact 0.25/0.625; the no-shader-depth control writes interpolated 0.75. The exact d7 14 54 depth-store signature occurs only in shader-depth cases.",
        "- 4x sample masks resolve distinctly: f=a00000ff, 5=40010282, a=60010282, 0=01020304. f/5/a differ at one own-main byte (+0x2d: 1e/0a/14); mask-zero removes the color-store path (32 B main).",
        "- Discard kills the left two pixels. Counters are atomic-all=4, before-discard=4, after-discard=2.",
        "- Safe splice changed exactly one own-main byte, store selector 02->04. RT1 became unwritten and RT2 received RT1's authored value in both runs.",
        "- Counterexample: spliced RT1 read back 00000000, not requested clear 05060708; H5's combined clear prediction is falsified and no clear/background inference is promoted.",
        "",
        "INTERPRETATION",
        "- The tested compiler canonicalizes output declaration order and emits stores in descending compact active-output order.",
        "- The store selector is not universally semantic [[color(n)]]*2: sparse color(1)-only and color(2)-only both emit compact selector 0 while the bracket's semantic selector changes 0c->30/c0 and live output reaches RT1/RT2. Earlier contiguous-only observations conflated these two selector roles.",
        "- Mask and depth findings are source-path/compiler correlations. Only the checked contiguous-MRT selector mutation is live splice evidence.",
        "",
        "VERDICT",
        "- PARTIAL M4-only P0.8 evidence. Full FS ABI, prolog/epilog linkage, tilebuffer mapping, arbitrary formats, independent code generation, Linux mapping, and A18 remain OPEN.",
    ]
    return summary, "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    summary, report = analyze()
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.report:
        args.report.write_text(report)
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
