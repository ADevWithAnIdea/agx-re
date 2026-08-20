#!/usr/bin/env python3
"""Fail-closed provenance and semantic verifier for the retained EXP-0057 runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ("m4_20260819_run01", "m4_20260819_run02")
LEVELS = {"baseline": None, "p576": 592, "p1024": 1040, "p2048": 2064,
          "p4096": 4112, "p8192": 8208, "p16384": 16400}
SHAPES = {"tg32": 32, "tg256": 256}


def require(ok, why):
    if not ok: raise SystemExit(f"FAIL {why}")


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_map(items):
    out = {}
    for item in items:
        path = HERE / item["path"]
        require(not path.is_symlink() and path.is_file(), f"bad artifact {item['path']}")
        require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"digest {item['path']}")
        require(item["path"] not in out, f"duplicate manifest path {item['path']}")
        out[item["path"]] = path
    return out


def capture(path):
    obj = json.loads(path.read_text())
    require(obj.get("timeout") is False and obj.get("exit") == 0, f"capture failure {path.name}")
    return json.loads(obj["stdout"])


def verify_run(name):
    root = HERE / "raw" / name
    require(root.is_dir() and not root.is_symlink(), f"run root {name}")
    result = {}
    for level, want_scratch in LEVELS.items():
        meta = capture(root / f"metadata_{level}.json")
        require(meta["metadata_archive_retained"] is False and meta["metadata_code_bytes_inspected"] == 0,
                f"metadata scope {name}/{level}")
        require(meta["scratch_field_41_or_14"] == want_scratch, f"scratch metadata {name}/{level}")
        require(meta["source"] == f"experiments/EXP-0057-m4-scratch-pressure-envelope/raw/{name}/sources/{level}.metal",
                f"source identity {name}/{level}")
        result[level] = {"gpr_field_0": meta["gpr_field_0"], "scratch": want_scratch, "shapes": {}}
        for shape, tg in SHAPES.items():
            item = capture(root / f"trial_{level}_{shape}.json")
            require(item == {"phase": "execution", "device": "Apple M4", "status": 4, "tg": tg,
                             "threads": 32768, "words": (0 if level == "baseline" else int(level[1:]) // 4),
                             "prefix_guard": True, "suffix_guard": True, "exact": True, "error": ""},
                    f"public result {name}/{level}/{shape}")
            result[level]["shapes"][shape] = item
    require(not (root / "STOP.json").exists(), f"unexpected stop {name}")
    return result


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    require(manifest["experiment"] == "EXP-0057-m4-scratch-pressure-envelope", "manifest experiment")
    require(manifest["clean_room"] == {"apple_binary_introspection": False, "apple_helper_program_bytes_inspected": False,
        "apple_command_state_code_unknown_bo_bytes_inspected": False, "compiled_non_authored_code_inspected": False}, "clean room attestation")
    artifacts = artifact_map(manifest["raw_artifacts"] + manifest["analysis_artifacts"] + manifest["source_tools"])
    # No binary dump, BO trace, captured code, or other payload class is accepted.
    forbidden = (".bin", ".dylib", ".metallib", "maptrace", "bo_", "command_")
    require(not any(any(word in rel.lower() for word in forbidden) for rel in artifacts), "forbidden retained artifact name")
    first, second = verify_run(RUNS[0]), verify_run(RUNS[1])
    require(first == second, "cross-run semantic mismatch")
    repeat = json.loads((HERE / "analysis/m4_20260819_repeat.json").read_text())
    require(repeat["semantic_match"] is True and repeat["mismatches"] == {}, "repeat artifact")
    print("PASS runs=2 processes=28 levels=7 shapes=2 scratch_max=16400 raw_no_bo_or_code=1")


if __name__ == "__main__": main()
