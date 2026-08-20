#!/usr/bin/env python3
"""Report two pre-established fields from the archive of an authored MSL source.

The temporary archive is deleted before this program exits.  This program never
extracts, writes, prints, or hashes shader code or any archive member other than
the metadata payload needed for field decoding.
"""
import argparse
import importlib.util
import json
import struct
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
SHDUMP_SRC = REPO / "tools/shdump/shdump.m"
AGXPARSE = REPO / "tools/shdump/agxparse.py"

spec = importlib.util.spec_from_file_location("agxparse", AGXPARSE)
ap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ap)


def fields(buf, pos):
    vt = pos - struct.unpack_from("<i", buf, pos)[0]
    count = (struct.unpack_from("<H", buf, vt)[0] - 4) // 2
    return {i: pos + off for i in range(count)
            if (off := struct.unpack_from("<H", buf, vt + 4 + 2 * i)[0])}


def metadata(blob):
    outer = None
    for off, _, _ in ap.iter_gpu_images(blob):
        try:
            candidate = ap.MachO(blob, off)
        except ValueError:
            continue
        if candidate.cputype == ap.APPLE_GPU_CPUTYPE:
            outer = candidate
            break
    if outer is None:
        raise ValueError("no AppleGPU image in own pipeline archive")
    sec = outer.find_section("__TEXT", "__compute")
    nested = ap.MachO(blob, outer.base + sec["offset"])
    meta = next((blob[outer.base + sec["offset"] + s["offset"]:
                      outer.base + sec["offset"] + s["offset"] + s["size"]]
                 for s in nested.sections if s["seg"] == "__GPU_METADATA"), None)
    if meta is None:
        raise ValueError("own compute metadata absent")
    root = struct.unpack_from("<I", meta, 0)[0]
    top = fields(meta, root)
    child = top[0] + struct.unpack_from("<I", meta, top[0])[0]
    values = {str(i): struct.unpack_from("<I", meta, p)[0]
              for i, p in fields(meta, child).items() if p + 4 <= len(meta)}
    return {"gpr_field_0": values.get("0"),
            "scratch_field_41_or_14": values.get("41", values.get("14")),
            "metadata_code_bytes_inspected": 0,
            "metadata_archive_retained": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if HERE not in source.parents:
        raise SystemExit("source must be inside this experiment")
    with tempfile.TemporaryDirectory(prefix="exp0057-own-metadata-") as tmp:
        tmp = Path(tmp); tool = tmp / "shdump"; archive = tmp / "own.metallib"
        subprocess.run(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                        "-o", tool, SHDUMP_SRC], check=True, timeout=30)
        result = subprocess.run([tool, "-o", archive, "-f", "k_main", "--no-fast-math", source],
                                text=True, capture_output=True, timeout=60)
        if result.returncode:
            raise SystemExit(result.stderr)
        answer = metadata(archive.read_bytes())
        answer["source"] = str(source.relative_to(REPO))
        answer["compiler_stderr"] = result.stderr.splitlines()
        print(json.dumps(answer, sort_keys=True))


if __name__ == "__main__":
    main()
