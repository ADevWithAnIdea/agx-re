#!/bin/sh
cd ~/cleanroom_work/EXP-M5-10
P=scripts
{
echo "############ SAMPLE POSITIONS: msaa4b vs msaa4sp (all BOs, wide) ############"
python3 $P/alldiff.py u_msaa4b u_msaa4sp 0x8000
echo; echo "############ PBE storage-image: iw_w vs iw_w256 (width 64->256, height 64->128) ############"
python3 $P/alldiff.py u_iw_w u_iw_w256 0x9480
echo; echo "############ PBE: iw_w vs iw_wr32 (format rgba8->r32u) ############"
python3 $P/alldiff.py u_iw_w u_iw_wr32 0x9480
echo; echo "############ PBE: iw_w(write) vs iw_r(read) — write-desc vs read-desc ############"
python3 $P/alldiff.py u_iw_r u_iw_w 0x9480
echo; echo "############ PBE: iw_w(write) vs iw_rw(read_write, TWO descriptors) ############"
python3 $P/alldiff.py u_iw_w u_iw_rw 0x9480
echo; echo "############ PBE arg-buffer resource table dump (iw_w, va100000f0000) ############"
F=$(ls u_iw_w/bo_*va100000f0000_*.hex)
for O in 0x14a0 0x14a8 0x14b0 0x14b8; do python3 $P/shex.py "$F" $O 8; done
echo; echo "############ USC compute: uc_t1 vs uc_t3 (textures) ############"
python3 $P/alldiff.py u_uc_t1 u_uc_t3 0x9480
echo "--- uc_t1 vs uc_s3 (samplers) ---"; python3 $P/alldiff.py u_uc_t1 u_uc_s3 0x9480
echo "--- uc_t1 vs uc_b4 (buffers) ---"; python3 $P/alldiff.py u_uc_t1 u_uc_b4 0x9480
echo; echo "############ USC graphics: ug_t1 vs ug_t3 / ug_b4 ############"
python3 $P/alldiff.py u_ug_t1 u_ug_t3 0x2000
echo "--- ug_t1 vs ug_b4 ---"; python3 $P/alldiff.py u_ug_t1 u_ug_b4 0x2000
echo; echo "############ INDIRECT dispatch: in_disp vs in_idisp (CDM 0x100000b0000) ############"
python3 $P/alldiff.py u_in_disp u_in_idisp 0x400
echo; echo "############ INDIRECT draw: VDM record (va18000) in_draw ############"
FD=$(ls u_in_draw/bo_*va18000_*.hex)
for O in 0x84 0x88 0x8c 0x90 0x94 0x98; do python3 $P/shex.py "$FD" $O 4; done
echo "--- in_drawidx VDM ---"
FI=$(ls u_in_drawidx/bo_*va18000_*.hex)
for O in 0x84 0x88 0x8c 0x90 0x94 0x98 0x9c 0xa0; do python3 $P/shex.py "$FI" $O 4; done
echo; echo "############ TILING: tp192 backing va10000080000 first 64 u32 (expect Morton: 0,1,0x10000,0x10001,2,3,...) ############"
FT=$(ls u_tp192/bo_*va10000080000_*.hex)
python3 $P/shex.py "$FT" 0x00 64
python3 $P/shex.py "$FT" 0x40 64
} >rt2_analysis.txt 2>&1
echo done
