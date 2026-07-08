#!/usr/bin/env python3
# census_extract.py — EXP-0036 thin wrapper over tools/shdump/agxparse.py that
# extracts the _agc.main of a chosen stage from an OUR-OWN serialized archive.
# It teaches the (unmodified) parser about the mesh pipeline's __object/__mesh
# stages by monkeypatching STAGE_SECTIONS (same trick as EXP-0030 mesh_extract).
# CLEAN-ROOM: pure container parsing of our own compiled archive.
#
#   python3 census_extract.py A.bin <stage> [symbol]   -> prints hex of that region
# stage in {compute,vertex,fragment,object,mesh}; symbol default _agc.main.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agxparse

for stage, sect in (("object", "__object"), ("mesh", "__mesh")):
    if stage not in agxparse.STAGE_SECTIONS:
        agxparse.STAGE_SECTIONS[stage] = sect
        agxparse.SECTION_STAGE[sect] = stage

def main():
    path = sys.argv[1]
    stage = sys.argv[2] if len(sys.argv) > 2 else None
    symbol = sys.argv[3] if len(sys.argv) > 3 else "_agc.main"
    with open(path, "rb") as f:
        buf = f.read()
    report, stages = agxparse.extract_all_stages(buf)
    pieces = stages.get(stage) if stage else None
    if pieces is None:
        sys.stderr.write(f"census_extract: stage {stage!r} not found; present={list(stages)}\n")
        sys.exit(2)
    data = pieces.get(symbol)
    if data is None:
        sys.stderr.write(f"census_extract: symbol {symbol!r} not in {list(pieces)}\n")
        sys.exit(3)
    sys.stdout.write(data.hex() + "\n")

if __name__ == "__main__":
    main()
