#!/usr/bin/env python3
# EXP-M5-18 patch v3 (minimal-clean): name the CALL branch-and-link (0xff) + the indirect
# call-setup tail (0xfb) that otherwise swallows it. Leaves the 0x9e setup as harmless
# 2-byte fillers (naming it would need a length that breaks the direct-call clean resync).
import sys
src = open(sys.argv[1]).read()
LEN_ANCHOR = "    _b2 = buf[off + 2] if off + 2 < len(buf) else -1\n"
LEN_RULE = LEN_ANCHOR + '''    # ---- EXP-M5-18 (HW-VALIDATED splice+linked round-trip): M5 out-of-line CALL ----
    # branch-and-link `ff c7 ff 7f be 03 40 0e` (8B), shared by direct([[noinline]]) &
    # indirect(visible_function_table); operand-invariant (c_dyn8==c_dyn8b==c_dynxor). The
    # INDIRECT setup also emits a `fb 1e 1f 00` tail (4B) right before the branch (mis-read
    # as a 10-byte b_alu without this rule, which swallowed the branch). Both gates are exact
    # 3-4 byte signatures -> cannot mis-length a real b_alu/operand word.
    if b0 == 0xff and _b1 == 0xc7 and _b2 == 0xff and off + 3 < len(buf) and buf[off + 3] == 0x7f:
        return 8                       # m5_call (out-of-line CALL branch-and-link, EXP-M5-18 HW)
    if b0 == 0xfb and _b1 == 0x1e and _b2 == 0x1f and off + 3 < len(buf) and buf[off + 3] == 0x00:
        return 4                       # m5_call_tail (indirect call-setup tail, EXP-M5-18 HW)
'''
assert src.count(LEN_ANCHOR) == 1
src = src.replace(LEN_ANCHOR, LEN_RULE, 1)
DESC_ANCHOR = '''                     "(need an indirect-call splice testbed)."'''
idx = src.index(DESC_ANCHOR); close = src.index("    },\n", idx) + len("    },\n")
DESC = '''    # ---- M5 out-of-line CALL branch-and-link + indirect tail (EXP-M5-18, HW-validated) ----
    {
        "mnemonic": "m5_call",
        "length": 8,
        "match": [(0, 8, 0xff), (8, 8, 0xc7), (16, 8, 0xff), (24, 8, 0x7f)],
        "fields": [
            {"name": "b4", "start": 32, "width": 8, "type": "raw"},
            {"name": "b5", "start": 40, "width": 8, "type": "raw"},
            {"name": "b6", "start": 48, "width": 8, "type": "raw"},
            {"name": "b7", "start": 56, "width": 8, "type": "raw"},
        ],
        "semantics": "M5 out-of-line function-CALL branch-and-link `ff c7 ff 7f be 03 40 0e` (8B). The actual "
                     "control transfer for BOTH a direct([[noinline]]) and an indirect(visible_function_table) "
                     "call; byte-identical and operand-invariant across arg-count and callee body. Preceded by "
                     "the 0x43 frame_marker (`43 00 00 01`) and a `9e 60 <type> 0e ..` call-setup op (byte+2 "
                     "type: 0x00 direct = embeds the target PC in a `fe ..` tail; 0x01 indirect = target code-VA "
                     "loaded from the function table by a preceding m5_load). Callee returns via the epilogue "
                     "`27 00 04 00 20 00 a5 02`. RESOLVES the EXP-M5-11 MAJOR-4 open (M5 out-of-line CALL ABI). "
                     "b4(0xbe)/byte0(0xff) load-bearing (splice->CMDBUF_ERROR, redirects the branch); b6(0x40) inert; "
                     "b4..b7 kept raw (rule 5).",
        "provenance": "HW-VALIDATED (EXP-M5-18): shdumplink builds the LINKED pipeline (MTLLinkedFunctions=the "
                     "[[visible]] fns) so the archive carries the real _agc.main call site + each callee; agxrunlink "
                     "dispatches it FROM the archive (FailOnBinaryArchiveMiss) with a bound MTLVisibleFunctionTable. "
                     "Round-trip EXACT: c_dyn8 indirect out=[10,12..24]; c_noinline direct helper(a)=3a+1. Splice "
                     "sweep of _agc.main: byte0/+4 fault, the 0x43 marker leader+companion runtime-inert. "
                     "experiments/EXP-M5-18-call-abi/.",
    },
    {
        "mnemonic": "m5_call_tail",
        "length": 4,
        "match": [(0, 8, 0xfb), (8, 8, 0x1e), (16, 8, 0x1f), (24, 8, 0x00)],
        "fields": [],
        "semantics": "indirect call-setup tail `fb 1e 1f 00` (4B): the last setup word before the m5_call "
                     "branch on an INDIRECT (visible_function_table) call; completes materialising the "
                     "return context. Absent on the direct-call path. EXP-M5-18.",
        "provenance": "HW-VALIDATED (EXP-M5-18): present in c_dyn8/c_dyn8b/c_dynxor indirect calls between the "
                     "op04 setup and the m5_call branch; length 4 makes the branch reachable (else b_alu10 "
                     "swallows it). Splice: bytes load-bearing (CMDBUF_ERROR on corruption).",
    },
'''
src = src[:close] + DESC + src[close:]
open(sys.argv[2], "w").write(src)
print("patched v3 ->", sys.argv[2])
