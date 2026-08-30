#!/usr/bin/env python3
"""EXP-0206 instruction location by TWO INDEPENDENT METHODS, from the PINNED db.

Method A -- SIGNATURE SCAN: every byte offset whose bytes satisfy every `match`
constraint of the descriptor under test. Depends only on that one descriptor, so
it is immune to any change a sibling experiment makes to the tokenizer's length
rules (EXP-0182 was editing exactly those).

Method B -- TOKENIZER WALK: a full resync-free `disassemble()` of `_agc.main`
with the pinned isadb, taking every instruction the walk lands on. Depends on the
length rule for every PRECEDING byte, and is the only method that can tell a
4-byte `if_push` from the 14-byte direct CALL that shares its `0f 05` leader, or
tell a real `stop` from a `0x0e` byte sitting inside another instruction.

**Only offsets BOTH methods agree on become arms** (PRE_REGISTRATION.md section
4.1). Disagreements are recorded in the census as a first-class result, not
filtered away: a descriptor whose signature matches where the walk says there is
no such instruction is a db-model defect worth reporting.

Every arm's mutated bytes are additionally re-tokenized at dispatch time and the
pinned tokenizer's opinion recorded on EVERY case -- two fields were withdrawn on
2026-08-30 after their "movement" turned out to be the sweep encoding a DIFFERENT
instruction.

HARD EXIT if the pinned db.json / isadb.py are absent: nothing in this experiment
may resolve through `tools/agx-isa`, which sibling experiments edit concurrently.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is scanned.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def pinned_dir():
    for cand in (EXP / "pinned", Path.home() / "agxre" / "EXP-0206" / "pinned"):
        if (cand / "isadb.py").exists() and (cand / "db.json").exists():
            return cand
    sys.stderr.write(
        "FATAL: EXP-0206 pinned isadb.py/db.json not found. This experiment must "
        "NOT resolve through tools/agx-isa (sibling experiments edit it).\n")
    raise SystemExit(2)


PINNED = pinned_dir()
sys.path.insert(0, str(PINNED))
import isadb  # noqa: E402  (READ-ONLY use of the pinned snapshot)

if Path(isadb.__file__).resolve() != (PINNED / "isadb.py").resolve():
    sys.stderr.write("FATAL: isadb resolved to %s, not the pinned copy\n"
                     % isadb.__file__)
    raise SystemExit(2)

DB = json.loads((PINNED / "db.json").read_text())
DESC = {d["mnemonic"]: d for d in DB["instructions"]}
PARCEL = DB.get("parcel_bytes", 2)


def field_span(mnemonic, field):
    for f in DESC[mnemonic]["fields"]:
        if f["name"] == field:
            return f["start"], f["width"]
    raise KeyError("%s.%s not in the pinned db" % (mnemonic, field))


def _bits(raw, start, width):
    return (int.from_bytes(raw, "little") >> start) & ((1 << width) - 1)


def get_field(raw, mnemonic, field):
    s, w = field_span(mnemonic, field)
    return _bits(raw, s, w)


def signature_offsets(main, mnemonic, step=1):
    """Method A. `step` is 1 (byte granularity) deliberately: a hit that is not
    parcel-aligned is evidence the descriptor's signature is ambiguous, and it is
    recorded rather than filtered away."""
    d = DESC[mnemonic]
    L = d["length"]
    out = []
    for off in range(0, len(main) - L + 1, step):
        raw = bytes(main[off:off + L])
        if all(_bits(raw, s, w) == v for (s, w, v) in d["match"]):
            out.append(off)
    return out


def walk(main):
    """Method B. -> [{off, len, mnemonic}], plus any tail the walk could not
    consume (recorded, never silently dropped)."""
    recs, off, n = [], 0, len(main)
    err = None
    while off < n:
        try:
            rec, length = isadb.decode_one(bytes(main), off)
        except Exception as e:                                  # noqa: BLE001
            err = {"off": off, "error": str(e)[:200]}
            break
        if not length or length <= 0:
            err = {"off": off, "error": "non-positive length %r" % (length,)}
            break
        recs.append({"off": off, "len": length,
                     "mnemonic": rec.get("mnemonic"),
                     "op": rec.get("op_mnemonic")})
        off += length
    return recs, err


RESYNC_MAX = 32


def walk_resync(buf):
    """Linear walk, with a BOUNDED RESYNC when the pinned DB has no descriptor.

    Discovered by this experiment's own census: every NON-LEAF callee our
    compiler emits ends with the 6-byte word `ef 02 54 00 00 50` -- a
    frame-epilogue the pinned db.json cannot decode -- immediately followed by
    the NON-LEAF return `8f 12 54 00`. A pure linear walk therefore dies just
    before the only occurrence in the whole corpus that carries
    `linkmode == 0x12`, which is exactly the value the leaf-only carriers of the
    withdrawn `ret_luse.linkmode` measurement could never reach. Refusing to
    resync would silently reproduce that experiment's blind spot.

    On failure at K, offsets K+2, K+4, ... K+RESYNC_MAX (parcel steps) are tried
    and the FIRST one from which the walk reaches the end of the region WITHOUT
    a further error is accepted. Every accepted resync records the skipped bytes
    verbatim, and every viable alternative resync point is recorded too, so an
    ambiguous resync is visible rather than hidden.
    """
    recs, gaps, off, n = [], [], 0, len(buf)
    while off < n:
        try:
            rec, length = isadb.decode_one(bytes(buf), off)
            if not length or length <= 0:
                raise ValueError("non-positive length %r" % (length,))
        except Exception as e:                                  # noqa: BLE001
            viable = []
            for r in range(off + PARCEL, min(off + RESYNC_MAX, n) + 1, PARCEL):
                sub, sub_err = walk(buf[r:])
                if sub_err is None and sub:
                    viable.append(r)
            if not viable:
                gaps.append({"from": off, "to": None, "error": str(e)[:200],
                             "bytes": bytes(buf[off:]).hex(), "viable": []})
                break
            r = viable[0]
            gaps.append({"from": off, "to": r, "error": str(e)[:200],
                         "bytes": bytes(buf[off:r]).hex(), "viable": viable,
                         "ambiguous": len(viable) > 1})
            off = r
            continue
        recs.append({"off": off, "len": length, "mnemonic": rec.get("mnemonic"),
                     "op": rec.get("op_mnemonic"), "resynced": bool(gaps)})
        off += length
    return recs, gaps


def occurrences(main, mnemonic):
    """Offsets the two methods agree on, under the acceptance rule of
    PRE_REGISTRATION.md section 4.1 as AMENDED after the census (amendment
    recorded in CAPTURE_CONTRACT.json):

      (A) the signature scan and the RESYNC walk both land on the offset; or
      (B) the signature matches, `decode_one` at that exact offset returns the
          target mnemonic, the offset lies OUTSIDE every instruction the walk
          decoded, and the bytes from there to the end of the region tokenize
          cleanly.

    A signature hit that lies strictly INSIDE a decoded instruction is FALSE and
    is rejected: `call` carries a literal `0x8f` at byte+4, so every direct call
    produces a spurious `ret` / `ret_luse` signature hit four bytes in. Six such
    hits appear in this corpus and none is an instruction.
    """
    sig = set(signature_offsets(main, mnemonic))
    recs, gaps = walk_resync(main)
    wlk = set(r["off"] for r in recs if r["mnemonic"] == mnemonic)
    inside = set()
    for r in recs:
        for k in range(r["off"] + 1, r["off"] + r["len"]):
            inside.add(k)
    agreed = sorted(sig & wlk)
    resync_only = []
    for off in sorted(sig - wlk):
        if off in inside:
            continue
        t = token_at(main, off)
        if t.get("mnemonic") != mnemonic:
            continue
        sub, sub_err = walk(main[off:])
        if sub_err is None and sub:
            resync_only.append(off)
    return {
        "agreed": agreed,
        "resync_accepted": resync_only,
        "accepted": sorted(set(agreed) | set(resync_only)),
        "signature_only": sorted(sig - wlk),
        "signature_inside_decoded": sorted((sig - wlk) & inside),
        "walk_only": sorted(wlk - sig),
        "gaps": gaps,
        "walk_len": len(recs),
        "walk_covered_bytes": (recs[-1]["off"] + recs[-1]["len"]) if recs else 0,
        "main_len": len(main),
    }


def follows_code(main, off, length):
    """For `stop`: is there any further instruction after this word that the walk
    can decode? A MID-PROGRAM stop (code follows -- typically an out-of-line
    callee placed past the main body's terminator) is a completely different
    claim from the FINAL stop that EXP-0003/EXP-0010 proved inert."""
    end = off + length
    if end >= len(main):
        return False, 0
    rest = len(main) - end
    # Trailing all-zero padding is not "code".
    if all(b == 0 for b in main[end:]):
        return False, rest
    return True, rest


def token_at(main, off):
    """What the PINNED tokenizer says the bytes at `off` are. Never raises: a
    mutated instruction is often deliberately undecodable by OUR disassembler,
    and the hardware -- not our tool -- is the authority on what bytes mean."""
    try:
        rec, length = isadb.decode_one(bytes(main), off)
        return {"mnemonic": rec["mnemonic"], "op": rec.get("op_mnemonic"),
                "length": length}
    except Exception as e:                                      # noqa: BLE001
        return {"mnemonic": None, "op": None, "length": None,
                "error": str(e)[:120]}


def code_regions(regions):
    """Region names that hold CODE. `_agc.main.constant_program` is a constant
    data blob, not instructions, and tokenizing it would produce garbage."""
    return [n for n in regions if not n.endswith(".constant_program")]


def compile_carrier(bin_dir, metal_path, func, out_dir):
    """shdump our own MSL -> (archive path, {region_name: {abs, len, bytes}}).

    A kernel with an out-of-line callee puts the callee in its OWN symbol region
    of the shader `__text` section, NOT inside `_agc.main`. The first census run
    of this experiment found `ret` in ZERO carriers for exactly that reason: the
    walk only ever saw `_agc.main`, which contains the CALL but not the callee's
    RETURN. Every region is therefore carved and splice-addressed separately.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arch = out_dir / ("carrier_%s.bin" % func)
    subprocess.run([str(Path(bin_dir) / "shdump"), "-o", str(arch),
                    "--no-fast-math", "-f", func, str(metal_path)],
                   check=True, capture_output=True, timeout=600)
    sys.path.insert(0, str(PINNED))
    import agxparse  # noqa: E402  (READ-ONLY use of the pinned snapshot)
    if Path(agxparse.__file__).resolve() != (PINNED / "agxparse.py").resolve():
        sys.stderr.write("FATAL: agxparse resolved to %s, not the pinned copy\n"
                         % agxparse.__file__)
        raise SystemExit(2)
    buf = Path(arch).read_bytes()
    _rep, pieces = agxparse.extract_agx(buf)
    if not pieces:
        raise RuntimeError("no AGX code carved from %s" % arch)
    regions = {}
    for name, blob in pieces.items():
        if name == "__whole_text__":
            continue
        loc = agxparse.locate_region(buf, name)
        if loc is None:
            continue
        regions[name] = {"abs": loc[0], "len": loc[1], "bytes": blob}
        if loc[1] != len(blob):
            regions[name]["len_mismatch"] = True
    return str(arch), regions
