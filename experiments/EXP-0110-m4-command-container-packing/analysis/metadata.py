#!/usr/bin/env python3
"""EXP-0110 metadata.py -- P0.7 container/metadata field surveyor.

Reads the __GPU_METADATA FlatBuffer that travels with a shader WE compiled
from OUR OWN MSL (OWN-SHADER), via the read-only tools/shdump/agxparse.py
container parser (imported, never edited -- its source hash is recorded by
run.py). This is our own authored FlatBuffer field walker (same technique as
EXP-0020's fbstats.py / EXP-0041's metadata.py, reimplemented fresh here so
this experiment's provenance chain does not depend on editing another
experiment's files).

FlatBuffer root -> field 0 (uoffset) -> a stats table whose small integer
fields are the compiler's declared footprint. Already-established field
indices (EXP-0020/0024/EXP-M4-09/EXP-0041, OWN-SHADER + DATA-TRACE):
  0  = GPR footprint
  9  = threadgroup-memory-used flag
  14/41 = scratch (spill) byte size
  31 = uniform footprint
  32 = presence == compute launch-descriptor occupancy-tier bit (EXP-M4-09)
This module surveys ALL small-integer fields (not just the known ones) so a
resource-count sweep can flag NEW fields that vary with texture/sampler/
buffer counts -- the P0.7 "resource specifiers" gap.
"""
import importlib.util
import os
import struct
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
AGXPARSE_PATH = os.path.join(REPO, "tools", "shdump", "agxparse.py")

_spec = importlib.util.spec_from_file_location("agxparse_ro", AGXPARSE_PATH)
ap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ap)


def gpu_image(buf):
    for off, size, note in ap.iter_gpu_images(buf):
        try:
            mo = ap.MachO(buf, off)
        except ValueError:
            continue
        if mo.cputype == ap.APPLE_GPU_CPUTYPE:
            return mo
    return None


def stage_metadata_sections(buf, stage_section="__compute"):
    """Return {seg_name: bytes} for all __GPU_* sections inside one stage's
    nested Mach-O (e.g. __GPU_METADATA, __GPU_STATS_MD)."""
    mo = gpu_image(buf)
    if mo is None:
        return {}
    s = mo.find_section("__TEXT", stage_section)
    if not s:
        return {}
    nb = mo.base + s["offset"]
    try:
        nested = ap.MachO(buf, nb)
    except ValueError:
        return {}
    out = {}
    for sec in nested.sections:
        if sec["seg"].startswith("__GPU"):
            o = nb + sec["offset"]
            out[sec["seg"]] = bytes(buf[o:o + sec["size"]])
    return out


def _table_fields(buf, tpos):
    soff = struct.unpack_from("<i", buf, tpos)[0]
    vt = tpos - soff
    vtsize = struct.unpack_from("<H", buf, vt)[0]
    nf = (vtsize - 4) // 2
    fields = {}
    for i in range(nf):
        foff = struct.unpack_from("<H", buf, vt + 4 + i * 2)[0]
        if foff:
            fields[i] = tpos + foff
    return fields


def survey_fields(meta):
    """Root -> field0 uoffset -> stats table. Returns {field_index: value}
    for every small (<=8 byte, interpreted as u32 when the field itself is
    >=4 bytes past position, else the raw byte) field in that table -- a
    superset survey, not just the previously-known indices."""
    if len(meta) < 8:
        return {}
    root = struct.unpack_from("<I", meta, 0)[0]
    rf = _table_fields(meta, root)
    if 0 not in rf:
        return {}
    f0pos = rf[0]
    sub = f0pos + struct.unpack_from("<I", meta, f0pos)[0]
    ff = _table_fields(meta, sub)
    out = {}
    for i, p in ff.items():
        if p + 4 <= len(meta):
            out[i] = struct.unpack_from("<I", meta, p)[0]
        elif p < len(meta):
            out[i] = meta[p]
    return out


def survey(archive_path, stage_section="__compute"):
    buf = open(archive_path, "rb").read()
    secs = stage_metadata_sections(buf, stage_section)
    meta = secs.get("__GPU_METADATA", b"")
    fields = survey_fields(meta) if meta else {}
    return {
        "meta_len": len(meta),
        "fields": fields,
        "sections_present": sorted(secs.keys()),
        "agxparse_sha256_path": AGXPARSE_PATH,
    }


if __name__ == "__main__":
    r = survey(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "__compute")
    import json
    print(json.dumps(r, indent=2, sort_keys=True))
