### T1 — bucket census (664 emitter-grade fields)

| bucket | fields | share |
|---|---:|---:|
| `STABLE-LIVE` | 359 | 54.1% |
| `INERT-MULTI` | 23 | 3.5% |
| `INERT-SINGLE` | 81 | 12.2% |
| `UNSTABLE` | 41 | 6.2% |
| `SINGLE-RUN` | 16 | 2.4% |
| `UNVERIFIABLE` | 144 | 21.7% |
| **total** | **664** | |

`UNVERIFIABLE` by reason: `field-named-but-unstructured` 24, `no-field-records` 60, `no-raw` 47, `raw-present-but-unattributable` 13

### T2 — per cited experiment

| experiment | cited by | STABLE | I-MULTI | I-SINGLE | UNSTABLE | 1-RUN | UNVER | raw verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `EXP-0154` | 98 | 72 | 2 | 20 | 4 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0155` | 90 | 73 | 10 | 0 | 7 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0139` | 61 | 43 | 2 | 7 | 9 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0141` | 56 | 35 | 3 | 15 | 3 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-M4-14` | 49 | 0 | 0 | 0 | 0 | 0 | 49 | no raw files |
| `EXP-0138` | 46 | 34 | 0 | 10 | 2 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0156` | 44 | 31 | 3 | 8 | 2 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0144` | 42 | 28 | 1 | 2 | 11 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0140` | 39 | 13 | 1 | 5 | 0 | 0 | 20 | per-value records parsed and bit-attributed |
| `EXP-0147` | 31 | 16 | 1 | 11 | 3 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0162` | 18 | 0 | 0 | 2 | 0 | 16 | 0 | per-value records parsed and bit-attributed |
| `EXP-0119` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-0112` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-O2C` | 10 | 0 | 0 | 0 | 0 | 0 | 10 | raw present, NO per-value field records |
| `EXP-0161` | 9 | 9 | 0 | 0 | 0 | 0 | 0 | per-value records parsed and bit-attributed |
| `EXP-0090` | 8 | 0 | 0 | 0 | 0 | 0 | 8 | raw present, NO per-value field records |
| `EXP-0153` | 7 | 5 | 0 | 1 | 0 | 0 | 1 | per-value records parsed and bit-attributed |
| `EXP-0105` | 7 | 0 | 0 | 0 | 0 | 0 | 7 | raw present, NO per-value field records |
| `EXP-0006` | 7 | 0 | 0 | 0 | 0 | 0 | 7 | raw present, NO per-value field records |
| `EXP-0099` | 6 | 0 | 0 | 0 | 0 | 0 | 6 | raw present, NO per-value field records |
| `EXP-O2D` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0113` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0016` | 5 | 0 | 0 | 0 | 0 | 0 | 5 | raw present, NO per-value field records |
| `EXP-0092` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0029` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0115` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `RT-10-isa-pass2` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0018` | 4 | 0 | 0 | 0 | 0 | 0 | 4 | raw present, NO per-value field records |
| `EXP-0010` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `RT-1a-FIX` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `RT-ISA-FIX` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |
| `EXP-0034` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | raw present, NO per-value field records |

### T3 — emittability ladder (denominator 166 emitter-relevant descriptors)

| withholding policy | fields withheld | emittable | of 166 |
|---|---:|---:|---:|
| published `validation.json` | 0 | 67 | 40.4% |
| `inert_single_only` | 81 | 43 | 25.9% |
| `inert_single_plus_unstable` | 122 | 33 | 19.9% |
| `chain_broken_only` | 195 | 22 | 13.3% |
| `lenient` | 242 | 17 | 10.2% |
| `strict` | 266 | 16 | 9.6% |

### T4 — instructions that lose emittable status under the strict set

| instruction | withheld fields | buckets | citing experiments |
|---|---:|---|---|
| `atomic_mem` | 1 | UNSTABLE 1 | `EXP-0141` |
| `copysign` | 1 | INERT-SINGLE 1 | `EXP-0138` |
| `cvt_f2h` | 1 | UNSTABLE 1 | `EXP-0144` |
| `falu_acc` | 1 | INERT-SINGLE 1 | `EXP-0154` |
| `if_push` | 1 | INERT-SINGLE 1 | `EXP-0140` |
| `iter_at` | 1 | UNSTABLE 1 | `EXP-0155` |
| `mov_imm` | 1 | UNVERIFIABLE 1 | `EXP-0153` |
| `pack_convert` | 1 | UNSTABLE 1 | `EXP-0144` |
| `pixel_order` | 1 | UNVERIFIABLE 1 | `EXP-0093` |
| `shift_amt_move` | 1 | INERT-SINGLE 1 | `EXP-0154` |
| `stop` | 1 | UNVERIFIABLE 1 | `EXP-0003`, `EXP-0010` |
| `uniform_mov` | 1 | INERT-SINGLE 1 | `EXP-0140` |
| `cvt_f2i` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0144` |
| `cvt_i2f_src` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0144` |
| `frag_color_store` | 2 | UNVERIFIABLE 2 | `EXP-0029` |
| `imageblock_store` | 2 | UNSTABLE 1, UNVERIFIABLE 1 | `EXP-0155`, `EXP-O2D` |
| `ishift` | 2 | INERT-SINGLE 1, UNSTABLE 1 | `EXP-0139` |
| `iter` | 2 | UNVERIFIABLE 2 | `EXP-0029` |
| `iunary` | 2 | UNVERIFIABLE 2 | `EXP-M4-14` |
| `jump_cond` | 2 | INERT-SINGLE 2 | `EXP-0156` |
| `n3_sample_read` | 2 | INERT-SINGLE 2 | `EXP-0147` |
| `simd_reduce` | 2 | UNVERIFIABLE 2 | `EXP-0018`, `EXP-O2D`, `RT-ISA-FIX` |
| `tex_deriv` | 2 | UNSTABLE 1, UNVERIFIABLE 1 | `EXP-0016`, `EXP-0155` |
| `vtx_out_pos` | 2 | INERT-SINGLE 2 | `EXP-0147` |
| `frame_prologue` | 3 | UNVERIFIABLE 3 | `EXP-M4-14` |
| `ibfe` | 3 | INERT-SINGLE 3 | `EXP-0154` |
| `jump` | 3 | INERT-SINGLE 2, UNVERIFIABLE 1 | `EXP-0010`, `EXP-0115`, `EXP-0140`, `EXP-0156` |
| `spill_frame_marker` | 3 | UNVERIFIABLE 3 | `EXP-M4-14` |
| `tile_read_mrt` | 3 | INERT-SINGLE 2, UNSTABLE 1 | `EXP-0147` |
| `atomic_tg` | 4 | INERT-SINGLE 2, UNSTABLE 2 | `EXP-0141`, `EXP-0156` |
| `frag_color_pack` | 4 | UNSTABLE 1, UNVERIFIABLE 3 | `EXP-0155`, `EXP-M4-14` |
| `get_sr` | 4 | INERT-SINGLE 1, UNVERIFIABLE 3 | `EXP-0031`, `EXP-0092`, `EXP-0140`, `EXP-M4-14` |
| `half_alu` | 4 | UNVERIFIABLE 4 | `EXP-0033`, `EXP-M4-14` |
| `ibitcount` | 4 | UNSTABLE 1, UNVERIFIABLE 3 | `EXP-0129`, `EXP-0139`, `EXP-M4-14` |
| `reg_move_c1` | 4 | UNVERIFIABLE 4 | `EXP-0101`, `EXP-0113`, `EXP-0140` |
| `reg_move_cb` | 4 | UNVERIFIABLE 4 | `EXP-0140` |
| `threadgroup_barrier` | 4 | INERT-SINGLE 2, UNSTABLE 2 | `EXP-0141` |
| `reg_move_c0` | 5 | UNVERIFIABLE 5 | `EXP-0101`, `EXP-0113`, `EXP-0140` |
| `reg_move_c2var` | 5 | UNVERIFIABLE 5 | `EXP-0140` |
| `reg_move_c9` | 5 | UNVERIFIABLE 5 | `EXP-0113`, `EXP-0140` |
| `tile_read` | 5 | INERT-SINGLE 3, UNSTABLE 2 | `EXP-0147` |
| `atomic_rmw` | 6 | INERT-SINGLE 6 | `EXP-0141`, `EXP-0156` |
| `device_load` | 6 | INERT-SINGLE 4, UNVERIFIABLE 2 | `EXP-0010`, `EXP-0082`, `EXP-0083`, `EXP-0100`, `EXP-0141` |
| `device_store` | 6 | INERT-SINGLE 3, UNVERIFIABLE 3 | `EXP-0082`, `EXP-0083`, `EXP-0092`, `EXP-0100`, `EXP-0141` |
| `link_save_restore` | 6 | UNVERIFIABLE 6 | `EXP-M4-14` |
| `iadd2` | 7 | INERT-SINGLE 3, UNSTABLE 4 | `EXP-0139`, `EXP-0153` |
| `unpack_convert` | 7 | UNSTABLE 7 | `EXP-0144` |
| `half_alu_ext8` | 9 | INERT-SINGLE 2, UNVERIFIABLE 7 | `EXP-0138`, `EXP-M4-14` |
| `tex_addr_setup` | 11 | UNVERIFIABLE 11 | `EXP-M4-14` |
| `matrix_mac` | 12 | INERT-SINGLE 2, UNVERIFIABLE 10 | `EXP-0147`, `EXP-O2C`, `RT-10-isa-pass2` |
| `falu2` | 15 | UNSTABLE 2, UNVERIFIABLE 13 | `EXP-0005`, `EXP-0006`, `EXP-0020`, `EXP-0086`, `EXP-0089`, `EXP-0090`, `EXP-0099`, `EXP-0105`, `EXP-0112`, `EXP-0113`, `EXP-0119`, `EXP-0138`, `EXP-M4-10`, `RT-1a-FIX` |

### T5 — field NAMES that block the most instructions

| field name | instructions blocked | instructions |
|---|---:|---|
| `dst` | 13 | `cvt_f2i`, `falu2`, `frag_color_pack`, `get_sr`, `matrix_mac`, `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9`, `reg_move_cb`, `uniform_mov`, `unpack_convert`, `vtx_out_pos` |
| `src_flag` | 5 | `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9`, `shift_amt_move` |
| `b1` | 4 | `iunary`, `link_save_restore`, `n3_sample_read`, `spill_frame_marker` |
| `b3` | 4 | `link_save_restore`, `n3_sample_read`, `reg_move_cb`, `spill_frame_marker` |
| `form` | 4 | `get_sr`, `ibitcount`, `reg_move_cb`, `tex_addr_setup` |
| `op_desc` | 4 | `atomic_tg`, `reg_move_c0`, `reg_move_c2var`, `reg_move_c9` |
| `opsel` | 4 | `falu2`, `half_alu`, `half_alu_ext8`, `iunary` |
| `src` | 4 | `frag_color_store`, `imageblock_store`, `reg_move_cb`, `unpack_convert` |
| `srcA` | 4 | `half_alu`, `half_alu_ext8`, `iadd2`, `ibfe` |
| `src_class` | 4 | `reg_move_c0`, `reg_move_c1`, `reg_move_c9`, `unpack_convert` |
| `src_reg` | 4 | `reg_move_c0`, `reg_move_c1`, `reg_move_c2var`, `reg_move_c9` |
| `base_slot` | 3 | `atomic_rmw`, `device_load`, `device_store` |
| `cache` | 3 | `falu_acc`, `tex_addr_setup`, `unpack_convert` |
| `reserved7` | 3 | `device_load`, `device_store`, `link_save_restore` |
| `tail` | 3 | `ibitcount`, `tile_read`, `tile_read_mrt` |
| `access_desc` | 2 | `device_load`, `device_store` |
| `addr_desc_hi` | 2 | `atomic_mem`, `atomic_rmw` |
| `amode` | 2 | `atomic_rmw`, `atomic_tg` |
| `b2` | 2 | `spill_frame_marker`, `tile_read` |
| `b4` | 2 | `tile_read`, `tile_read_mrt` |
| `b5` | 2 | `half_alu_ext8`, `threadgroup_barrier` |
| `b6_hi` | 2 | `tile_read`, `tile_read_mrt` |
| `b7` | 2 | `pack_convert`, `tile_read` |
| `dtype` | 2 | `matrix_mac`, `simd_reduce` |
| `idx_off` | 2 | `device_load`, `device_store` |
| `marker` | 2 | `frame_prologue`, `link_save_restore` |
| `mode` | 2 | `iter`, `matrix_mac` |
| `op` | 2 | `cvt_f2h`, `simd_reduce` |
| `op_enable` | 2 | `ibitcount`, `matrix_mac` |
| `reserved` | 2 | `jump_cond`, `stop` |
| `reserved13` | 2 | `device_load`, `device_store` |
| `rsv6` | 2 | `half_alu_ext8`, `tex_addr_setup` |
| `scope` | 2 | `if_push`, `link_save_restore` |
| `srcB_imm` | 2 | `falu2`, `iadd2` |
| `src_cache` | 2 | `cvt_i2f_src`, `ishift` |

### T6 — representative-arm defect (H2): inert arm + stable-live arm, same raw

| field | experiment | inert arm(s) (values swept) | stable-live arm(s) (moved) |
|---|---|---|---|
| `device_store.addr_mode` | `EXP-0141` | `synth\|S_addr_mode` (256) | `synth\|S_addr_mode_fwd` (128) |
| `frag_color_store.flags` | `EXP-0155` | `fcs@iter0` (256) | `fcs@pack0` (128) |
| `ibitcount.cache` | `EXP-0139` | `SYNTH:carrier_dag@k\|IBITCOUNT` (2) | `NAT:k_pop@ibitcount+0x012\|IBITCOUNT_NAT` (1) |
| `iter.coeff_sel` | `EXP-0155` | `iter@cent1` (256), `iter@frag0W` (256) | `iter@frag1` (128) |
| `iter.loc` | `EXP-0155` | `iter@frag0W` (256) | `iter@cent1` (48), `iter@cent4` (96), `iter@frag1` (128) |
| `jump_cond.offset` | `EXP-0156` | `cfN\|jc.liveness` (3) | `cf0\|jump_cond.offset` (2) |
| `mov_imm.dst` | `EXP-0140` | `uni\|mov_imm.dst` (16) | `uni\|mov_imm.dst.alias_scan` (3) |
| `sel.b1` | `EXP-0140` | `dsel5\|sel.body.wide` (13) | `dsel5\|sel.body.b1` (136) |
| `tex_sample.chain` | `EXP-0155` | `tex_sample@lo_0` (16) | `tex_sample@lo_1` (3), `tex_sample@t1_0` (1), `tex_sample@t1_1` (2), `tex_sample@t1_2` (2), `tex_sample@t2_0` (1), `tex_sample@t2_1` (1), `tex_sample@t2_2` (2) |
| `tex_sample.lod_present` | `EXP-0155` | `tex_sample@t2_2` (256), `tex_sample@tc_0` (256) | `tex_sample@lo_0` (128), `tex_sample@lo_1` (128), `tex_sample@lo_2` (128), `tex_sample@t1_0` (128), `tex_sample@t1_1` (128), `tex_sample@t1_2` (128), `tex_sample@t2_0` (128) |
| `tex_sample.samp_extra` | `EXP-0155` | `tex_sample@lo_0` (256), `tex_sample@lo_2` (256), `tex_sample@t1_0` (256), `tex_sample@t1_2` (256), `tex_sample@t2_0` (256), `tex_sample@t2_1` (256), `tex_sample@t2_2` (256), `tex_sample@tc_0` (256) | `tex_sample@lo_1` (128) |

### T7 — the INERT-SINGLE list (the suspect class)

| field | values swept | arm | runs | evidence |
|---|---:|---|---:|---|
| `atomic_rmw.addr_desc_hi` | 4 | `EXP-0141:atdev\|atdev_atomic_rmw_b6` | 2 | `EXP-0141` |
| `atomic_rmw.amode` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b2` | 2 | `EXP-0141` |
| `atomic_rmw.base_slot` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b4` | 2 | `EXP-0141` |
| `atomic_rmw.op_msb` | 2 | `EXP-0156:atdev\|atdev_atomic_rmw_b12` | 2 | `EXP-0156` |
| `atomic_rmw.per_lane` | 2 | `EXP-0156:atdev\|atdev_atomic_rmw_b12` | 2 | `EXP-0156` |
| `atomic_rmw.rsv3` | 256 | `EXP-0141:atdev\|atdev_atomic_rmw_b3` | 2 | `EXP-0141` |
| `atomic_tg.amode` | 256 | `EXP-0141:attg\|attg_atomic_tg_b2` | 2 | `EXP-0141` |
| `atomic_tg.ret_desc` | 256 | `EXP-0141:attg\|attg_atomic_tg_b3` | 2 | `EXP-0141` |
| `copysign.operands` | 256 | `EXP-0138:copysign` | 3 | `EXP-0138` |
| `cvt_f2i.b9` | 256 | `EXP-0144:c_f2i\|F` | 2 | `EXP-0144` |
| `cvt_i2f_src.src_cache` | 256 | `EXP-0144:c_i2f_src\|F` | 2 | `EXP-0144` |
| `device_load.access_desc` | 256 | `EXP-0141:synth\|L_access_desc` | 2 | `EXP-0141` |
| `device_load.addr_mode` | 256 | `EXP-0141:synth\|L_addr_mode` | 2 | `EXP-0141` |
| `device_load.reserved13` | 256 | `EXP-0141:synth\|L_reserved13` | 2 | `EXP-0141` |
| `device_load.reserved7` | 256 | `EXP-0141:synth\|L_reserved7` | 2 | `EXP-0141` |
| `device_store.access_desc` | 256 | `EXP-0141:synth\|S_access_desc` | 2 | `EXP-0141` |
| `device_store.reserved13` | 256 | `EXP-0141:synth\|S_reserved13` | 2 | `EXP-0141` |
| `device_store.reserved7` | 256 | `EXP-0141:synth\|S_reserved7` | 2 | `EXP-0141` |
| `falu2_ext.srcA_size` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_ext.srcB_imm` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_ext.srcB_neg` | 2 | `EXP-0154:SYNTH+LIFTED:k_sat_add@falu2_ext[32:40]\|FALU2_EXT` | 3 | `EXP-0154` |
| `falu2_uni.srcA_size` | 2 | `EXP-0138:carrier_uni` | 5 | `EXP-0138` |
| `falu2i.imm_flag` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_acc.cache` | 2 | `EXP-0154:SYNTH+LIFTED:k_sum@falu_acc[252:256]\|FALU_ACC` | 3 | `EXP-0154` |
| `falu_srcmod12b.mod_hi` | 16 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_srcmod12b.mod_lo` | 8 | `EXP-0138:carrier_uni` | 6 | `EXP-0138` |
| `falu_srcmod12b.srcB_imm` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `falu_srcmod12b.srcB_neg` | 2 | `EXP-0138:carrier` | 3 | `EXP-0138` |
| `fspecial_est.srcA` | 29 | `EXP-0154:SYNTH+LIFTED:k_rsqrt@fspecial_est[18:24]\|FSPECIAL_EST` | 3 | `EXP-0154` |
| `fspecial_est.subop` | 256 | `EXP-0138:fspecial_est` | 2 | `EXP-0138` |
| `get_sr.form` | 2 | `EXP-0140:uni\|get_sr.form` | 3 | `EXP-0140` |
| `half_alu_ext8.b7_lo` | 2 | `EXP-0138:half_alu_ext8` | 3 | `EXP-0138` |
| `half_alu_ext8.b7_mid` | 32 | `EXP-0138:half_alu_ext8` | 3 | `EXP-0138` |
| `iadd2.addsub` | 5 | `EXP-0153:u64\|C_i64add` | 2 | `EXP-0153` |
| `iadd2.b2_fmt` | 64 | `EXP-0139:SYNTH:carrier_dag@k\|IADD2` | 2 | `EXP-0139` |
| `iadd2.srcB_reg_hi` | 128 | `EXP-0139:SYNTH:carrier_dag@k\|IADD2` | 2 | `EXP-0139` |
| `ibfe.b2_bit0` | 2 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfe.sign_ext` | 2 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfe.srcA` | 29 | `EXP-0154:SYNTH+LIFTED:k_bfe@ibfe[18:30]\|IBFE` | 2 | `EXP-0154` |
| `ibfins.cache` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `ibfins.mask_hi` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `ibfins.mask_imm` | 256 | `EXP-0154:SYNTH+LIFTED:k_rot_var@ibfins[42:54]\|IBFINS` | 3 | `EXP-0154` |
| `icmp_pred.neg` | 2 | `EXP-0139:NAT:k_div@icmp_pred+0x0cc\|ICMP_PRED` | 2 | `EXP-0139` |
| `if_push.scope` | 256 | `EXP-0140:cf\|if_push.scope@7` | 3 | `EXP-0140` |
| `if_push_pred.scope` | 256 | `EXP-0140:cf\|if_push_pred.scope@4` | 3 | `EXP-0140` |
| `ilogic.outmod` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z6` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z8` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `ilogic.z9` | 256 | `EXP-0154:SYNTH+LIFTED:k_and@ilogic[32:42]\|ILOGIC` | 2 | `EXP-0154` |
| `imad.b11` | 256 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.b1hi` | 128 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.b2_bit0` | 2 | `EXP-0154:SYNTH+LIFTED:k_imad@imad[32:44]\|IMAD` | 2 | `EXP-0154` |
| `imad.b2_fmt` | 64 | `EXP-0139:NAT:k_imad@imad+0x020\|IMAD` | 2 | `EXP-0139` |
| `imad.store_en` | 2 | `EXP-0154:SYNTH+LIFTED:k_imad@imad[32:44]\|IMAD` | 2 | `EXP-0154` |
| `irotate.b2` | 256 | `EXP-0154:SYNTH+LIFTED:k_rot_imm@irotate[18:30]\|IROTATE` | 2 | `EXP-0154` |
| `isel8.cmpB` | 256 | `EXP-0154:SYNTH+LIFTED:k_rsqrt@isel8[18:32]\|ISEL8` | 3 | `EXP-0154` |
| `ishift.pad9` | 256 | `EXP-0139:NAT:k_ashr@ishift+0x012\|ISHIFT` | 2 | `EXP-0139` |
| `jump.branch_ctrl` | 254 | `EXP-0156:cfN\|jump.branch_ctrl` | 2 | `EXP-0156` |
| `jump.link` | 256 | `EXP-0140:cf\|jump.link@13` | 3 | `EXP-0140` |
| `jump_cond.cf_scope` | 256 | `EXP-0156:cf0\|jump_cond.cf_scope@NAT` | 2 | `EXP-0156` |
| `jump_cond.reserved` | 256 | `EXP-0156:cf0\|jump_cond.reserved@NAT` | 2 | `EXP-0156` |
| `matrix_mac.b11_rsv` | 32 | `EXP-0147:matrix_mac` | 2 | `EXP-0147` |
| `matrix_mac.dst_desc_lo` | 64 | `EXP-0147:matrix_mac` | 2 | `EXP-0147` |
| `n3_sample_read.b1` | 256 | `EXP-0147:n3_sample_read` | 2 | `EXP-0147` |
| `n3_sample_read.b3` | 256 | `EXP-0147:n3_sample_read` | 2 | `EXP-0147` |
| `packed_half2_hi.srcA` | 256 | `EXP-0162:c_ph2\|packed_half2_hi` | 1 | `EXP-0162` |
| `packed_half2_hi.srcB` | 256 | `EXP-0162:c_ph2\|packed_half2_hi` | 1 | `EXP-0162` |
| `shift_amt_move.src_flag` | 2 | `EXP-0154:SYNTH+LIFTED:k_rot_var@shift_amt_move[76:80]\|SHIFT_AMT_MOVE` | 2 | `EXP-0154` |
| `tg_addr_compute.b3` | 256 | `EXP-0156:tgac\|tgac.b3` | 2 | `EXP-0156` |
| `tg_addr_compute.b4` | 256 | `EXP-0156:tgac\|tgac.b4` | 2 | `EXP-0156` |
| `tg_addr_compute.b5` | 256 | `EXP-0156:tgac\|tgac.b5` | 2 | `EXP-0156` |
| `threadgroup_barrier.b5` | 256 | `EXP-0141:tgtile\|tgtile_threadgroup_barrier_b5` | 2 | `EXP-0141` |
| `threadgroup_barrier.flags` | 256 | `EXP-0141:tgtile\|tgtile_threadgroup_barrier_b4` | 2 | `EXP-0141` |
| `tile_read.b2` | 256 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read.b4` | 256 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read.b6_hi` | 128 | `EXP-0147:tile_read` | 2 | `EXP-0147` |
| `tile_read_mrt.b4` | 256 | `EXP-0147:tile_read_mrt` | 2 | `EXP-0147` |
| `tile_read_mrt.b6_hi` | 128 | `EXP-0147:tile_read_mrt` | 2 | `EXP-0147` |
| `uniform_mov.dst` | 16 | `EXP-0140:uni\|regmove.dst` | 3 | `EXP-0140` |
| `vtx_out_pos.dst` | 16 | `EXP-0147:vtx_out_pos` | 2 | `EXP-0147` |
| `vtx_out_pos.slot` | 256 | `EXP-0147:vtx_out_pos` | 2 | `EXP-0147` |
