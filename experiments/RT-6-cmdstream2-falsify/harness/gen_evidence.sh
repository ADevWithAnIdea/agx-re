#!/bin/bash
cd ~/cleanroom_work/rt6
OUT=RAW_EVIDENCE.txt
{
echo "===================== RT-6 RAW EVIDENCE (A18 Pro / G17P, macOS 26.6 25G5043d) ====================="
echo "All draws/dispatches status=4, zero faults/reboots. iotrace arm64e, read-only. hex bytes in addr order; le32 = little-endian u32."
echo
echo "########## CLAIM 1: INDIRECT DRAW/DISPATCH ##########"
echo "--- non-indexed DIRECT VDM 0x18000 (counts inline) ---"; python3 hexreg.py capi_draw_direct 18000 0x64 0x78
echo "--- non-indexed INDIRECT VDM (argBuf=0x1000001c600): opcode 0x6404, +0x68 hi=0x100, +0x6c lo=0x1c600 ---"; python3 hexreg.py capi_draw_indirect 18000 0x64 0x78
echo "--- INDEXED DIRECT VDM (idxBuf=0x...1c600): opcode 0x61f2 @+0x6c, cut @+0x68, idxVA @+0x70, idxCnt @+0x74, instCnt @+0x78 ---"; python3 hexreg.py capi_idx_direct 18000 0x64 0x8c
echo "--- INDEXED INDIRECT VDM (idxBuf=0x...1c600, argBuf=0x...1c700): opcode 0x6432, idxVA inline @+0x70, args hi @+0x74=0x100 lo @+0x78=0x1c700 ---"; python3 hexreg.py capi_idx_indirect 18000 0x64 0x88
echo "--- indirect DISPATCH CDM 0x100000b0000: [direct] single record, term 0x40000000 @+0x2c ---"; python3 hexreg.py capi_disp_direct 100000b0000 0x00 0x30
echo "--- [indirect] 2nd record @+0x2c; aux shader 0x2404=0x90100>>6 @+0x34; argptr-into-argbuf @+0x40 ---"; python3 hexreg.py capi_disp_indirect 100000b0000 0x2c 0x48
echo "--- [indirect] user argBuf VA (0x1000001c900) staged @0x10000080000+0xb0 ---"; python3 hexreg.py capi_disp_indirect 10000080000 0xb0 0xb8
echo "--- MULTIPLE indirect draws in one pass (argBuf0=0x...18800 @+0x6c, argBuf1=0x...18900 @+0x78) ---"; python3 hexreg.py capi_midraw 18000 0x64 0x7c
echo
echo "########## CLAIM 2: FULL ICB ##########"
for c in capi_icb_n1 capi_icb_n2 capi_icb_n3; do echo "--- $c: cmd-count @0x18000+0x04 + draw opcode hits ---"; python3 hexreg.py $c 18000 0x04 0x08; python3 opscan.py $c 18000 | grep draw; done
echo "--- ICB draw record inline vertexCount (n1 @0x1a8): opcode 0x61c4, vtxCnt @+0x1ac=3, instCnt @+0x1b0=1 ---"; python3 hexreg.py capi_icb_n1 18000 0x1a8 0x1b4
echo "--- mesh-in-ICB micb1: cmd-count + 0x70000600 record @0x181c4 ---"; python3 hexreg.py capi_micb1 18000 0x04 0x08; python3 opscan.py capi_micb1 18000 | grep mesh
echo "--- mesh-in-ICB micb2: cmd-count=2 + two 0x70000600 records ---"; python3 hexreg.py capi_micb2 18000 0x04 0x08; python3 opscan.py capi_micb2 18000 | grep mesh
echo "--- ADVERSARIAL execute-range subset (enc=3): exec(0,2) ---"; python3 hexreg.py capi_icb_enc3_r0_2 18000 0x04 0x08; python3 opscan.py capi_icb_enc3_r0_2 18000 | grep draw
echo "--- ADVERSARIAL execute-range subset: exec(1,2) -> +0x04 still 3, all 3 records still materialized ---"; python3 hexreg.py capi_icb_enc3_r1_2 18000 0x04 0x08; python3 opscan.py capi_icb_enc3_r1_2 18000 | grep draw
echo "--- ADVERSARIAL mixed draw|mesh ICB (ACCEPTED status=4): +0x04=2, one 0x61c4 + one 0x70000600 ---"; python3 hexreg.py capi_icb_mixed 18000 0x04 0x08; python3 opscan.py capi_icb_mixed 18000
echo
echo "########## CLAIM 3: OCCLUSION QUERY ##########"
echo "--- visBuf ptr 0x10000100000+0x00 (visBuf VA=0x10000018800): +0x00 lo=0x18800 +0x04 hi=0x100 ---"; python3 hexreg.py capq_count 10000100000 0x00 0x08
echo "--- mode 0x58000+0x8c bit14 (0x4000): none/bool/count ---"; for c in capq_none capq_bool capq_count; do echo -n "$c: "; python3 hexreg.py $c 58000 0x8c 0x90 | grep -oE 'le32=0x[0-9a-f]+'; done
echo "--- offset 0x58000+0xa0 = byteOffset<<14: off 0/8/16/4096 ---"; for c in capq_count capq_c8 capq_c16 capq_clarge; do echo -n "$c: "; python3 hexreg.py $c 58000 0xa0 0xa4 | grep -oE 'le32=0x[0-9a-f]+'; done
echo "--- readbacks (bool->1, count->4096=64x64, off8->visBuf[1], two->both 4096) ---"; for c in capq_bool capq_count capq_c8 capq_two; do echo "$c:"; grep -E 'VIS\[[01]' $c/stdout.txt; done
echo
echo "########## CLAIM 4: TIMESTAMPS ##########"
grep -hE 'TSCORR|SUPPORTS' capt_corr/stdout.txt capt_csamp/stdout.txt
echo "--- csample (dispatch-boundary) => unsupported, resolve all-zero ---"; grep -E 'CSAMPLE|TS\[' capt_csamp/stdout.txt
echo "--- rsample (stage-boundary) => real nanoseconds ---"; grep -E 'TS\[|TS delta' capt_rsamp/stdout.txt
echo
echo "########## CLAIM 5: GEOMETRY OUTPUT ##########"
echo "--- viewport count 0x68000+0x900 = ((count-1)<<12)|0x0C00: base/vp4/vp16 ---"; for c in capo_base capo_vp4 capo_vp16; do echo -n "$c: "; python3 hexreg.py $c 68000 0x900 0x904 | grep -oE 'le32=0x[0-9a-f]+'; done
echo "--- clip mask 0x58000+0x20 bits[7:0]: base/clip3/clip8 ---"; for c in capo_base capo_clip3 capo_clip8; do echo -n "$c: "; python3 hexreg.py $c 58000 0x20 0x24 | grep -oE 'le32=0x[0-9a-f]+'; done
echo "--- point_size bit18 (0x40000) / vpidx bit19 (0x80000) 0x58000+0x20 (base=0x00010000) ---"; for c in capo_point capo_vpidx1; do echo -n "$c: "; python3 hexreg.py $c 58000 0x20 0x24 | grep -oE 'le32=0x[0-9a-f]+'; done
echo "--- restart cut index 0x18000+0x68 + opcode @+0x6c: ix16(list)/str16r/str32r ---"; for c in capo_ix16 capo_str16r capo_str32r; do echo "$c:"; python3 hexreg.py $c 18000 0x68 0x70; done
echo "--- viewport 0x18-byte stride: vp4 vs vpmod (perturb only vp[1] h+znear) -> only floats 3-6 of vp[1] change ---"; python3 bodiff.py capo_vp4 capo_vpmod --va 0x68000 --maxlen 0x980 2>/dev/null | grep -E '0x09|differing'
echo "===================== END ====================="
} > $OUT 2>&1
echo "wrote $OUT ($(wc -l < $OUT) lines)"
