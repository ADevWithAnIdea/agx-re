#!/usr/bin/env python3
"""Verify frozen EXP-0047 evidence without executing the GPU."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

EXPECTED = {
    "fidentity": [
        "0x00000001", "0x007fffff", "0x80000001", "0x807fffff",
        "0x00000000", "0x80000000", "0x7fc12345", "0x7f800000",
    ],
    "fadd": [
        "0x00000000", "0x00000000", "0x80000000", "0x00000000",
        "0x80000000", "0x00800000",
    ],
    "fmul": [
        "0x00000000", "0x00000000", "0x80000000", "0x00000000",
        "0x7f800000", "0xff800000",
    ],
    "fmin": [
        "0x40400000", "0x40400000", "0x7fc54321", "0x80000000",
        "0x00000000", "0x80000000", "0x00000000", "0x7f800000",
        "0xff800000", "0x80000001", "0x3f800000", "0x3f800000",
        "0xc0000000", "0xc0000000", "0xff800000",
    ],
    "fmax": [
        "0x40400000", "0x40400000", "0x7fc54321", "0x80000000",
        "0x00000000", "0x80000000", "0x00000000", "0x7f800000",
        "0xff800000", "0x80000001", "0x40000000", "0x40000000",
        "0xbf800000", "0xbf800000", "0x7f800000",
    ],
    "hidentity": [
        "0x00000001", "0x000003ff", "0x00008001", "0x000083ff",
        "0x00000000", "0x00008000", "0x00007e55", "0x00007c00",
    ],
    "hadd": [
        "0x00000002", "0x00000400", "0x00008002", "0x00000000",
        "0x00008000", "0x00000001",
    ],
    "hmul": [
        "0x00000200", "0x00000002", "0x00008200", "0x00000000",
        "0x00007c00", "0x0000fc00",
    ],
    "rint": [
        "0x40000000", "0x40000000", "0xc0000000", "0xc0000000",
        "0x00000000", "0x80000000", "0x40400000", "0xc0400000",
        "0x3f800000", "0x40000000", "0x7f800000", "0xff800000",
        "0x7fc00000", "0x00000000", "0x80000000", "0x4b800000",
    ],
    "round": [
        "0x40000000", "0x40400000", "0xc0000000", "0xc0400000",
        "0x3f800000", "0xbf800000", "0x40400000", "0xc0400000",
        "0x3f800000", "0x40000000", "0x7f800000", "0xff800000",
        "0x7fc12345", "0x00000000", "0x00000000", "0x4b800000",
    ],
}

FUNCTIONS = {name: f"k_{name}" for name in EXPECTED}
INPUT_HASHES = {
    "fadd": "3bc85becc8765378b4656932771e1459b9c142caa32f04fcc529b734b16a35db",
    "fidentity": "d9ac9300ff502e7e8030249bad4dca5c23d76b76cc7896ec509d4d52bb8c64a4",
    "fmax": "ef39f534c1f68ec1fb325a6f947fb4f5beba87ca3b8ac2b7ebebd7199231df71",
    "fmin": "ef39f534c1f68ec1fb325a6f947fb4f5beba87ca3b8ac2b7ebebd7199231df71",
    "fmul": "3a0f7fbc7a9470bc73b6f96c593f34d6e577bb10f9b6bbf5cf5d30d968f44a58",
    "hadd": "1398e505246898e54fc85274beecaf81ca1d12493611911dad11231595dc3f39",
    "hidentity": "073cb676abd7e558ddf1017f30b67f2a7e9bb300d9f62371489e66bff19f4785",
    "hmul": "09cec1470e1d4be0aa09f899b5a9d06c8c26edc9a6456b67c4f5b560186534ff",
    "rint": "57bc95148d44dd487da16a47e09f8ff56a2ac76599bc86944ff6d24e48eba4d5",
    "round": "57bc95148d44dd487da16a47e09f8ff56a2ac76599bc86944ff6d24e48eba4d5",
}
AUTHORED_INPUTS = {
    "experiments/EXP-0047-m4-numerical-behavior/kernels/numeric.metal",
    "experiments/EXP-0047-m4-numerical-behavior/run_probe.py",
    "tools/agxtest/agxrun.m",
    "tools/agxtest/agxtest.py",
    "tools/shdump/agxparse.py",
    "tools/shdump/shdump.m",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main():
    raw = json.loads((HERE / "raw/m4-two-run-v3.json").read_text())
    require(raw["schema"] == 1, "schema")
    require(raw["apple_binary_introspection"] == "NONE", "clean-room marker")
    require(raw["passes_equal"] is True, "two passes differ")
    require(len(raw["passes"]) == 2, "expected two passes")
    require(raw["passes"][0] == raw["passes"][1], "pass payload mismatch")
    target = raw["target"]
    require(target["cpu_brand"] == "Apple M4", "target CPU")
    require(target["machine"] == "arm64", "target architecture")
    require(target["gpu_cores"] == 10, "target GPU core count")
    require(target["macos"] == "26.6.2" and target["build"] == "25G82", "OS identity")
    require(set(raw["passes"][0]) == set(EXPECTED), "case set")

    for name, case in raw["passes"][0].items():
        require(case["status"] == "OK", f"{name} status")
        require(case["pipeline_source"] == "archive", f"{name} archive source")
        require(case["function"] == FUNCTIONS[name], f"{name} function")
        inputs = json.dumps(case["inputs"], sort_keys=True, separators=(",", ":")).encode()
        require(hashlib.sha256(inputs).hexdigest() == INPUT_HASHES[name],
                f"{name} input matrix")
        require(len(case["outputs"]) == len(case["inputs"]["a"]),
                f"{name} input/output count")
        require(case["outputs"] == EXPECTED[name], f"{name} frozen output")
        main_bytes = bytes.fromhex(case["main_hex"])
        require(len(main_bytes) == case["main_length"], f"{name} main length")
        require(hashlib.sha256(main_bytes).hexdigest() == case["main_sha256"],
                f"{name} main hash")

    require(set(raw["authored_inputs"]) == AUTHORED_INPUTS, "authored input path set")
    for relative, digest in raw["authored_inputs"].items():
        path = REPO / relative
        require(path.is_file(), f"missing authored input {relative}")
        require(sha256(path) == digest, f"authored input changed: {relative}")

    manifest = json.loads((HERE / "manifest.json").read_text())
    require(manifest["base_revision"] == raw["repo_revision"], "revision binding")
    for artifact in manifest["artifacts"]:
        path = HERE / artifact["path"]
        require(path.is_file(), f"missing artifact {artifact['path']}")
        require(path.stat().st_size == artifact["bytes"], f"size {artifact['path']}")
        require(sha256(path) == artifact["sha256"], f"hash {artifact['path']}")
        require(path.suffix not in {".air", ".metallib", ".dylib", ".a"},
                f"forbidden compiled artifact {artifact['path']}")

    print(
        f"PASS cases={len(EXPECTED)} passes=2 artifacts={len(manifest['artifacts'])} "
        f"target={target['cpu_brand']}/{target['gpu_cores']}GPU"
    )


if __name__ == "__main__":
    main()
