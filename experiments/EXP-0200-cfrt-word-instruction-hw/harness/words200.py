#!/usr/bin/env python3
"""EXP-0200 -- the fill catalogue and the HOST-SIDE PREDICTION for every fill.

THE MEASUREMENT, in one paragraph.

`n1_word`, `n2_compact2`, `n3_word`, `rtq_pred`, `n4_cf_word` and `n4_rt_word`
are all `_instruction: tokenization-only`. That label means exactly one thing:
we can DECODE the bytes, and the only claim the descriptor makes about the
hardware is a LENGTH -- "length 2 / 4, +N lands on the next op leader in every
corpus occurrence". Nobody has ever asked the silicon what length it consumes.
Round-tripping cannot answer it (a round trip is symmetric across encode and
decode and passes against an assembler that cannot clear a bit, EXP-0170), and
neither can decoding the compiler's own bytes again.

So we ask the hardware directly, with a ruler we build out of instructions whose
`_instruction` row is ALREADY `hardware-run`:

    stop      `0e 00 00 00`   length 4   hardware-run (EXP-0003/EXP-0010).
                              "corrupting the whole word is a no-op -- the
                              program still terminates correctly", so the 24-bit
                              body is free for us to use as filler.
    mov_imm   `0c 20`         length 2   hardware-run (EXP-0031/0140/0153/
                              0167/0168; 196,114 GENERATED instances).
    icmp_pred `0a 00 ..`      length 6   hardware-run (EXP-0104/0115/0112).

THE RULER. Take an 8-byte HOLE: a run of consecutive instructions, on the
executed path, AFTER the store of the integrity sentinel `out[1] = 7.5` and
BEFORE the store of the result `out[0]`. Overwrite the whole hole with

    <candidate word W>  ++  stop  ++  zero padding

and read back the POISONED output buffer.

  * If the hardware consumes exactly len(W) bytes at W's encoding, the `stop`
    we planted is the next instruction decoded, the program halts there, and
    `out[0]` comes back still holding its poison `0xDEADBEEF` while the sentinel
    `out[1]` holds 7.5.  -> `not_written`: *the program ran, and our word did
    not eat the terminator*.
  * If the hardware consumes MORE than len(W) bytes, it swallows the `stop`,
    execution continues to the original store, and `out[0]` is written.

Two anchors calibrate the ruler AT THE SAME STOP OFFSET, so the reading is a
contrast and not an absolute:

    A_mov2   `0c 20` ++ stop ++ 00 00   stop at +2, known 2-byte word
                                        -> PREDICT not_written
    A_icmp6  `0a 00` ++ stop ++ 00 00   stop at +2, known 6-byte word
                                        -> PREDICT written (the 6-byte compare
                                           swallows the terminator)

`C_reach` (`stop` at +0) is the reachability control: if it does not come back
`not_written`, the hole is not on the executed path before the result store and
**every fill at that hole is barred from supporting any verdict** -- inert or
live. `C_null` (the original bytes) must come back `ok` at the carrier's oracle.

WHAT THE RULER CAN AND CANNOT SEE, stated before the run.
`not_written` for a 2-byte candidate proves consumption <= 2, and the parcel is
2 bytes (`db.json.parcel_bytes`), so that is exactly 2. For a 4-byte candidate
it proves consumption <= 4; it CANNOT separate "one 4-byte op" from "two 2-byte
tokens", because the trailing halves of all three 4-byte candidates (`00 00`,
`00 <b3>`, `20 80`) are themselves legal 2-byte pad encodings. The honest claim
is therefore TOTAL BYTES CONSUMED, which is the number an emitter needs.

THE SECOND ARM: TRANSPARENCY. At a NATURAL occurrence of a compact word (a hole
of exactly the word's own length), substitute each same-length candidate and
require the carrier's ordinary non-zero oracle to survive. That is the same
generate-and-observe, with the opposite prediction: `ok`, at the oracle. Every
target word therefore has records with at least two DIFFERENT predicted
payloads, which is what makes the oracle discriminating rather than constant.

FALSIFIERS, pre-registered here in code.
  * A 2-byte candidate that comes back `written` where `A_mov2` came back
    `not_written`, at the same hole: its consumption is NOT 2 bytes.
  * `A_icmp6` coming back `not_written`: the ruler cannot see over-read at all,
    and no length claim may be made from that hole.
  * `C_reach` coming back `written`: the hole is dead; bar it.
  * A candidate that faults or hangs where the anchors do not: the encoding is
    not architecturally benign at that point -- a first-class negative.

CLEAN-ROOM: every byte here is a value WE choose, written into the compiled form
of MSL WE wrote. No Apple binary is disassembled or introspected. The encodings
come from `pinned/db.json`, which this project built from its own compiled
shaders.
"""

# ---------------------------------------------------------------- encodings
# All from the PINNED db.json `match` constraints; see analysis/contract200.py,
# which re-derives every one of these from the descriptor and FAILS LOUD on a
# mismatch rather than trusting this table.
STOP4 = bytes([0x0E, 0x00, 0x00, 0x00])       # stop            len 4  hardware-run
MOV2 = bytes([0x0C, 0x20])                    # mov_imm dst=0   len 2  hardware-run
ICMP2 = bytes([0x0A, 0x00])                   # icmp_pred head  len 6  hardware-run
PAD2 = bytes([0x00, 0x00])                    # pad_operand     len 2  tokenization-only
IFPUSH4 = bytes([0x0F, 0x05, 0x00, 0x54])     # if_push         len 4  isolated-byte-diff

TARGETS_2B = {
    "n1_word":     bytes([0x01, 0x00]),
    "n2_compact2": bytes([0x02, 0x00]),
    "n3_word":     bytes([0x03, 0x02]),
}


def n4_cf(b3):
    return bytes([0x04, 0x01, 0x00, b3 & 0xFF])


def n4_rt(dst):
    return bytes([0x04, dst & 0xFF, 0x20, 0x80])


RTQ_PRED = bytes([0x06, 0xC2, 0x00, 0x00])

# The `n4_rt_word.dst` hazard EXP-0187 mapped on G17P over 512 dense dispatches
# on two carriers with zero exceptions. Re-stated here as a PREDICATE, not a
# list, because protocol 3(c) is explicit that a contiguous hazard must be
# modelled and mapped, never budgeted around.
def rt_dst_hazardous(dst):
    """EXP-0187 (single run, G17P): `fault <=> (dst & 0b110) == 0b100`."""
    return (dst & 0b110) == 0b100


def _pad_to(body, n):
    assert len(body) <= n, (body.hex(), n)
    return body + b"\x00" * (n - len(body))


def ruler_fills(hole_len, dst_values, b3_values):
    """Every fill for an 8-byte ruler hole.

    Returns a list of dicts: `fid` (stable id), `instr` (the mnemonic the fill
    is EVIDENCE ABOUT), `hex`, `predict` in {not_written, written}, `role`,
    `note`. `predict` is the HOST-COMPUTED oracle: it is derived from the
    descriptor's own length claim plus the ruler's construction, before any
    dispatch, and it VARIES across the fill space -- a constant oracle would
    predict the carrier, not the encoding.
    """
    assert hole_len == 8, hole_len
    out = []

    def add(fid, instr, body, predict, role, note):
        out.append({"fid": fid, "instr": instr, "hex": _pad_to(body, 8).hex(),
                    "predict": predict, "role": role, "note": note})

    # ---- controls and anchors -------------------------------------------
    add("C_reach", "stop", STOP4, "not_written", "control_reach",
        "stop at +0. MUST fire: if the result is written the hole is not on "
        "the executed path before the result store and every fill here is "
        "barred from supporting a verdict.")
    add("A_mov2", "mov_imm", MOV2 + STOP4, "not_written", "anchor_len2",
        "known 2-byte hardware-run word, stop at +2. Calibrates the ruler at "
        "the same stop offset the 2-byte candidates use.")
    add("A_icmp6", "icmp_pred", ICMP2 + STOP4, "written", "anchor_len6",
        "known 6-byte hardware-run word, stop at +2. MUST fire in the OTHER "
        "direction: if this comes back not_written the ruler cannot see "
        "over-read and no length claim may be made from this hole.")
    add("A_pad2", "pad_operand", PAD2 + STOP4, "not_written", "anchor_len2b",
        "pad_operand is itself tokenization-only; recorded as corroboration, "
        "never as a calibration anchor.")
    add("A_ifpush4", "if_push", IFPUSH4 + STOP4, "not_written", "anchor_len4",
        "known 4-byte word, stop at +4 -- the offset the 4-byte candidates use.")
    add("A_stop6", "stop", PAD2 + PAD2 + STOP4, "not_written", "anchor_len4b",
        "two pads then stop at +4; corroborates that a stop is still honoured "
        "when it is not the first word of the hole.")

    # ---- the six target words -------------------------------------------
    for mn, enc in sorted(TARGETS_2B.items()):
        add("T_%s" % mn, mn, enc + STOP4, "not_written", "target",
            "candidate 2-byte word, stop at +2. Read against A_mov2 "
            "(not_written) and A_icmp6 (written) at the SAME offset.")
    add("T_rtq_pred", "rtq_pred", RTQ_PRED + STOP4, "not_written", "target",
        "candidate 4-byte word, stop at +4.")
    for b3 in b3_values:
        add("T_n4_cf_word_b3_%02x" % b3, "n4_cf_word", n4_cf(b3) + STOP4,
            "not_written", "target",
            "candidate 4-byte word `04 01 00 %02x`, stop at +4." % b3)
    for dst in dst_values:
        add("T_n4_rt_word_dst_%02x" % dst, "n4_rt_word", n4_rt(dst) + STOP4,
            "not_written", "target",
            "candidate 4-byte word `04 %02x 20 80`, stop at +4.%s" % (
                dst, "  EXP-0187 hazard predicate holds for this dst "
                     "((dst & 0b110) == 0b100): a command-buffer fault is the "
                     "expected outcome and is recorded as a hard outcome, "
                     "never as movement." if rt_dst_hazardous(dst) else ""))

    # ---- a flagged db length defect, measured rather than assumed -------
    # `op04_len8` is flagged emit_unsafe in db.json for over-consuming the
    # following leader. Our tokenizer lengths `04 42 21 80` at 8 bytes; if that
    # is right the stop at +4 is swallowed and the result IS written.
    add("D_op04_len8", "op04_len8", bytes([0x04, 0x42, 0x21, 0x80]) + STOP4,
        "written", "db_defect_probe",
        "the pinned tokenizer lengths these bytes at 8; if the hardware "
        "consumes 4 the stop survives and the flagged length rule is wrong.")
    return out


def transparency_fills(hole_len, orig_bytes):
    """Fills for a NATURAL hole of exactly `hole_len` bytes at a compact-word
    occurrence: substitute each same-length candidate and require the carrier's
    ordinary oracle to survive.  Prediction `ok` (written, at the oracle).

    The reachability control here is the same `stop` fill: it must come back
    `not_written`, otherwise the occurrence is not on the executed path and
    nothing measured at it means anything -- the failure mode that made
    EXP-0187's `rq_ccount#0` uninterpretable.
    """
    out = []

    def add(fid, instr, body, predict, role, note):
        assert len(body) == hole_len, (fid, len(body), hole_len)
        out.append({"fid": fid, "instr": instr, "hex": body.hex(),
                    "predict": predict, "role": role, "note": note})

    add("X_null", "-", bytes(orig_bytes), "ok", "baseline_inplace",
        "the unmutated bytes, dispatched through the identical path.")
    if hole_len == 2:
        add("X_reach", "stop", bytes([0x0E, 0x00]), "not_written",
            "control_reach",
            "stop leader in the 2-byte hole: byte0 0x0e halts regardless of "
            "how many bytes it reads. MUST fire.")
        add("X_over", "icmp_pred", ICMP2, "wrong_or_fault", "control_over",
            "a known 6-byte word in a 2-byte hole desynchronises the stream by "
            "4 bytes. MUST NOT come back at the oracle.")
        for mn, enc in sorted(TARGETS_2B.items()):
            if bytes(orig_bytes) == enc:
                continue                     # not a substitution: it IS the baseline
            add("X_%s" % mn, mn, enc, "ok", "target",
                "generated 2-byte candidate substituted for a different "
                "2-byte word; the successor must still be decoded at +2.")
        add("X_mov_imm", "mov_imm", MOV2, "ok", "anchor_len2",
            "known 2-byte hardware-run word: if THIS breaks the program the "
            "hole is not a clean 2-byte slot and the arm is barred.")
    elif hole_len == 4:
        add("X_reach", "stop", STOP4, "not_written", "control_reach",
            "stop in the 4-byte hole. MUST fire.")
        add("X_over", "icmp_pred", ICMP2 + bytes([0x00, 0x00]),
            "wrong_or_fault", "control_over",
            "a known 6-byte word in a 4-byte hole desynchronises by 2 bytes.")
        for mn, enc in (("rtq_pred", RTQ_PRED), ("n4_cf_word", n4_cf(0x00))):
            if bytes(orig_bytes) == enc:
                continue
            add("X_%s" % mn, mn, enc, "ok", "target",
                "generated 4-byte candidate substituted for a different "
                "4-byte word; the successor must still be decoded at +4.")
        if bytes(orig_bytes)[:1] != b"\x04" or bytes(orig_bytes)[2:] != b"\x20\x80":
            add("X_n4_rt_word", "n4_rt_word", n4_rt(0x42), "ok", "target",
                "generated `04 42 20 80` (a dst value EXP-0187 measured clean "
                "on two carriers).")
        add("X_if_push", "if_push", IFPUSH4, "ok", "anchor_len4",
            "known 4-byte word; if THIS breaks the program the hole is not a "
            "clean 4-byte slot and the arm is barred.")
    else:
        raise ValueError("transparency holes are 2 or 4 bytes, not %d" % hole_len)
    return out
