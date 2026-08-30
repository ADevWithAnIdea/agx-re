### Bucket summary

| field | bucket | live on | inert on (carriers w/ proven detection power) |
|---|---|---|---|
| `frag_color_store.store_mode` | **INERT-ROBUST** | — | cent4, ibhalf, layer, mrt3, tileread, tilerw2, vflat |
| `frag_tile_setup.access` | **INERT-ROBUST** | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `frag_tile_setup.b5` | **INERT-ROBUST** | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `frag_tile_setup.sel` | **INERT-ROBUST** | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `imageblock_store.b4` | **INERT-ROBUST** | — | atoff4, ibms4, ibsamp |
| `iter.b9` | **INERT-ROBUST** | — | atoff1, cent4, mrt3, vflat, vhalf, vmany |
| `iter_at.loc` | **LIVE** | cent4/fragment#0, cent4/fragment#1, cent4/fragment#2, atoff4/fragment#0, atoff4/fragment#1 | atoff1, cent1 |
| `simd_ballot.cache` | **INERT-ROBUST** | — | sball, scache, sdiv |
| `simd_shuffle.cache` | **INERT-ROBUST** | — | sball, scache, sdiv, stype |
| `simd_shuffle.rsv9` | **LIVE** | stype/compute#13, stype/compute#15 | sball, scache, sdiv, stype |
| `tex_coord_setup.b5` | **LIVE** | bits/fragment#0, bits/fragment#1, fclass/fragment#1, vsrc/vertex#0, vsrc/vertex#1, vhalf/v | fclass |
| `tex_coord_setup.b6` | **LIVE** | vsrc/vertex#0, vsrc/vertex#1, vhalf/vertex#0, ms4out/fragment#0 | bits, fclass, sball |
| `tex_coord_setup.b8` | **LIVE** | vsrc/vertex#0, vsrc/vertex#1, vhalf/vertex#0, ms4out/fragment#0 | bits, fclass, sball |
| `tex_coord_setup.b9` | **INERT-ROBUST** | — | bits, fclass, ms4out, sball, vhalf, vsrc |
| `tex_coord_setup.idx` | **LIVE** | vsrc/vertex#0 | bits, fclass, ms4out, sball, vhalf, vsrc |
| `tex_write.amode` | **STILL-UNDERPOWERED** | — | twdim, twtype |
| `tex_write.rsv11` | **STILL-UNDERPOWERED** | — | twdim, twtype |
| `vary_store.b7` | **INERT-ROBUST** | — | vclip, vflat, vhalf, vmany, vsrc |
| `vary_store.hint2` | **INERT-ROBUST** | — | vclip, vflat, vhalf, vmany, vsrc |
| `vary_store.hint6` | **LIVE** | vmany/vertex#9, vmany/vertex#16, vhalf/vertex#0, vhalf/vertex#6, vflat/vertex#4, vsrc/vert | vclip, vmany |

Totals: **INERT-ROBUST** 11, **LIVE** 7, **STILL-UNDERPOWERED** 2

Runs compared: g17p_20260830_run01


### LIVE fields — exact rules

| field | arm (carrier) | moved / swept | equivalence classes | live bits | exact rule | cross-run |
|---|---|---|---|---|---|---|
| `iter_at.loc` | `atoff4/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `atoff4/fragment#1` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `cent4/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `cent4/fragment#1` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `cent4/fragment#2` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `ms4cent/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `ms4out/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `simd_shuffle.rsv9` | `stype/compute#13` | 240/256 | 10 | 1,2,6,7 | 240 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `simd_shuffle.rsv9` | `stype/compute#15` | 248/256 | 8 | 1,2,5,6,7 | 248 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `tex_coord_setup.b5` | `bits/fragment#0` | 240/256 | 2 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `bits/fragment#1` | 240/256 | 3 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `fclass/fragment#1` | 240/256 | 3 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `ms4out/fragment#0` | 192/256 | 3 | 0,1,2,3,4 | 192 values, set = 0x1,0x3,0x5,0x7,0x9,0xb,0xd,0xf,0x10,0x11,0x12,0x13, | agree |
| `tex_coord_setup.b5` | `sball/compute#0` | 208/256 | 2 | 0,1,2,4 | 208 values, set = 0x1,0x3,0x4,0x5,0x7,0x9,0xb,0xc,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vhalf/vertex#0` | 208/256 | 5 | 0,1,2,3,4 | 208 values, set = 0x1,0x3,0x5,0x7,0x8,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vsrc/vertex#0` | 208/256 | 4 | 0,1,2,3,4 | 208 values, set = 0x1,0x3,0x5,0x7,0x8,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vsrc/vertex#1` | 200/256 | 3 | 0,1,2,3,4 | 200 values, set = 0x1,0x3,0x5,0x7,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x12,0 | agree |
| `tex_coord_setup.b6` | `ms4out/fragment#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vhalf/vertex#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vsrc/vertex#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vsrc/vertex#1` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b8` | `ms4out/fragment#0` | 192/256 | 3 | 3,4 | 192 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `tex_coord_setup.b8` | `vhalf/vertex#0` | 128/256 | 2 | 3 | exactly the values with bit3 set | agree |
| `tex_coord_setup.b8` | `vsrc/vertex#0` | 128/256 | 2 | 3 | exactly the values with bit3 set | agree |
| `tex_coord_setup.b8` | `vsrc/vertex#1` | 192/256 | 2 | 3,4 | 192 values, set = 0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10,0x11,0x12,0x13, | agree |
| `tex_coord_setup.idx` | `vsrc/vertex#0` | 128/256 | 2 | 7 | exactly the values with bit7 clear | agree |
| `vary_store.hint6` | `vflat/vertex#4` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vhalf/vertex#0` | 128/256 | 4 | 0,1,2,3,4,5,6,7 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vhalf/vertex#6` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vmany/vertex#16` | 128/256 | 65 | 0,1,2,3,4,5,6,7 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vmany/vertex#9` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vsrc/vertex#5` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vsrc/vertex#6` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |


### INERT-ROBUST fields — the envelope actually tested

| field | carriers (all with proven detection power) | arms | values per arm | total inert observations |
|---|---|---|---|---|
| `frag_color_store.store_mode` | cent4, ibhalf, layer, mrt3, tileread, tilerw2, vflat | 8 | 256 | 2048 |
| `frag_tile_setup.access` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `frag_tile_setup.b5` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `frag_tile_setup.sel` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `imageblock_store.b4` | atoff4, ibms4, ibsamp | 3 | 256 | 768 |
| `iter.b9` | atoff1, cent4, mrt3, vflat, vhalf, vmany | 6 | 256 | 1536 |
| `simd_ballot.cache` | sball, scache, sdiv | 4 | 256 | 1024 |
| `simd_shuffle.cache` | sball, scache, sdiv, stype | 8 | 2 | 16 |
| `tex_coord_setup.b9` | bits, fclass, ms4out, sball, vhalf, vsrc | 9 | 256 | 2304 |
| `vary_store.b7` | vclip, vflat, vhalf, vmany, vsrc | 9 | 256 | 2304 |
| `vary_store.hint2` | vclip, vflat, vhalf, vmany, vsrc | 9 | 256 | 2304 |


### STILL-UNDERPOWERED fields

| field | why | carriers reached |
|---|---|---|
| `tex_write.amode` | only 2 distinct carrier(s) with proven detection power (bar is 3) | twdim, twtype |
| `tex_write.rsv11` | only 2 distinct carrier(s) with proven detection power (bar is 3) | twdim, twtype |


### Detection power, per arm

71 of 72 arms pass the strict gate (status OK + observation changed + still decodes as the arm's mnemonic) in every run.

Arms WITHOUT strict detection power (excluded from every verdict):

- `iter@vmany/fragment#0` — {"g17p_20260830_run01": {"detect_ok_strict": false, "fault_only_controls": ["grp=0xd0/decode", "grp=0x0/decode"], "in_run_detect_ok": false, "profile_steps": 15, "strict_live_controls": []}}
