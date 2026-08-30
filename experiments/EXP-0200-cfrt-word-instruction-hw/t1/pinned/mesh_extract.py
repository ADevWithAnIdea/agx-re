#!/usr/bin/env python3
# mesh_extract.py — EXP-0030 thin wrapper over tools/shdump/agxparse.py that
# teaches the (unmodified) parser about the MESH pipeline's extra AGX stages.
#
# The mesh pipeline archive is the same Metal fat binary as a render archive; we
# hypothesise the AppleGPU image carries __TEXT,__object and __TEXT,__mesh
# sections analogous to __vertex/__fragment. Rather than edit the shared tool we
# monkeypatch its STAGE_SECTIONS map (the carve/locate code paths iterate that
# global), then reuse its exact Mach-O carving. CLEAN-ROOM: pure container
# parsing of OUR OWN serialized archive.
#
# Usage:
#   python3 mesh_extract.py A.bin                       # structural report (all stages)
#   python3 mesh_extract.py A.bin --stage mesh --extract-hex [--symbol _agc.main]
#   python3 mesh_extract.py A.bin --stage object --locate _agc.main
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agxparse  # our own parser (copied alongside)

# Teach it the extra sections. Order controls the default single-stage pick.
for stage, sect in (("object", "__object"), ("mesh", "__mesh")):
    if stage not in agxparse.STAGE_SECTIONS:
        agxparse.STAGE_SECTIONS[stage] = sect
        agxparse.SECTION_STAGE[sect] = stage
agxparse.SHADER_SECTIONS = tuple(agxparse.STAGE_SECTIONS.values())

ALL_STAGES = tuple(agxparse.STAGE_SECTIONS.keys())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("container")
    ap.add_argument("--stage", choices=ALL_STAGES, default=None)
    ap.add_argument("--symbol", default="_agc.main")
    ap.add_argument("--whole-text", action="store_true")
    ap.add_argument("--extract-hex", action="store_true")
    ap.add_argument("--locate", nargs="?", const="_agc.main")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with open(args.container, "rb") as f:
        buf = f.read()

    if args.locate is not None:
        loc = agxparse.locate_region(buf, args.locate, stage=args.stage)
        if loc is None:
            sys.stderr.write(f"mesh_extract: could not locate '{args.locate}' "
                             f"in stage {args.stage}\n")
            sys.exit(2)
        print(f"{loc[0]} {loc[1]}")
        sys.exit(0)

    report, stages = agxparse.extract_all_stages(buf)

    if args.extract_hex:
        pieces = stages.get(args.stage) if args.stage else None
        if pieces is None and not args.stage:
            for s in ALL_STAGES:
                if s in stages:
                    pieces = stages[s]; break
        if pieces is None:
            sys.stderr.write(f"mesh_extract: no bytes for stage {args.stage}\n"); sys.exit(2)
        key = "__whole_text__" if args.whole_text else args.symbol
        data = pieces.get(key)
        if data is None:
            sys.stderr.write(f"mesh_extract: no symbol {key}\n"); sys.exit(2)
        print(data.hex())
        sys.exit(0)

    if args.json:
        print(json.dumps(report, indent=2)); sys.exit(0)

    print(f"container magic : {report['container_magic']}")
    print(f"AIR64 present   : {report['air_present']}")
    for img in report["images"]:
        print(f"\nimage @ {img.get('offset')}: {img.get('note')}")
        if "error" in img:
            print(f"  error: {img['error']}"); continue
        print(f"  cputype : {img.get('cputype')} filetype={img.get('filetype')}")
        for s in img.get("sections", []):
            print(f"    section {s}")
    print(f"\nstages present: {', '.join(report.get('stages', {}))}")
    for stage_name, a in report.get("stages", {}).items():
        print(f"\nAGX [{stage_name}] ({a['kind']}) from {a.get('outer_section')}:")
        print(f"  nested cputype   : {a.get('nested_cputype')}")
        print(f"  __text size      : {a.get('whole_text_length')}")
        print(f"  _agc.main length : {a.get('main_length')}")
        for (name, start, end, length) in a.get("regions", []):
            print(f"  region {name}: [{start}:{end}] ({length} bytes)")


if __name__ == "__main__":
    main()
