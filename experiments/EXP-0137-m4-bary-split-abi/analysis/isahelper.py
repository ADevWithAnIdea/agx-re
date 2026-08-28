"""isahelper.py -- EXP-0129 shared disassembly-summary helper (OWN-SHADER).

Thin wrapper around tools/agx-isa/isadb.py's disassemble() (READ-ONLY,
unmodified, imported not copied) that reduces a raw hex byte string
extracted from OUR OWN compiled shader (via tools/shdump/agxparse.py) to a
small, deterministic, byte-comparable JSON-safe summary: per-instruction
mnemonic list, the `iter` family's (dst, src_slot, mode, loc) tuples (the
decisive H1 evidence), and counts of `fspecial` (rcp/rsqrt/exp2 SFU),
`call`, `frame_marker`, `ret`/`ret_luse`, and `pop_reconverge`.

CLEAN-ROOM: isadb.py's table was built entirely from our own compiled
shader bytes (see tools/agx-isa/README.md); this module only calls its
published disassemble() API on bytes WE extracted from OUR OWN shaders.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]  # analysis/ -> EXP-0129-.../ -> experiments/ -> agx-re
ISADB_DIR = REPO / "tools" / "agx-isa"
if str(ISADB_DIR) not in sys.path:
    sys.path.insert(0, str(ISADB_DIR))
import isadb  # noqa: E402  (tools/agx-isa/isadb.py, read-only, unmodified)


def disasm_summary(hexstr: str) -> dict:
    if not hexstr:
        return {"n_bytes": 0, "clean": True, "n_instr": 0, "mnemonics": [],
                "iters": [], "n_fspecial": 0, "n_call": 0, "n_frame_marker": 0,
                "n_ret": 0, "n_pop_reconverge": 0, "leftover_bytes": 0}
    buf = bytes.fromhex(hexstr)
    recs, leftover = isadb.disassemble(buf)
    mnemonics = []
    iters = []
    n_fspecial = n_call = n_frame_marker = n_ret = n_pop_reconverge = 0
    off = 0
    clean = True
    for r in recs:
        if r.get("error"):
            clean = False
            mnemonics.append("UNKNOWN")
            break
        mn = r["mnemonic"]
        mnemonics.append(mn)
        f = r["fields"]
        if mn == "iter":
            iters.append({"off": off, "dst": f.get("dst"), "src_slot": f.get("src_slot"),
                           "mode": f.get("mode"), "loc": f.get("loc")})
        elif mn == "fspecial":
            n_fspecial += 1
        elif mn == "call":
            n_call += 1
        elif mn == "frame_marker":
            n_frame_marker += 1
        elif mn in ("ret", "ret_luse"):
            n_ret += 1
        elif mn == "pop_reconverge":
            n_pop_reconverge += 1
        off += r["length"]
    if leftover:
        clean = False
    return {
        "n_bytes": len(buf), "clean": clean, "n_instr": len(mnemonics),
        "mnemonics": mnemonics, "iters": iters, "n_fspecial": n_fspecial,
        "n_call": n_call, "n_frame_marker": n_frame_marker, "n_ret": n_ret,
        "n_pop_reconverge": n_pop_reconverge,
        "leftover_bytes": len(leftover) if leftover else 0,
    }
