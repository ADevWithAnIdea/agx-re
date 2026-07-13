#!/bin/sh
cd ~/cleanroom_work/EXP-M5-10
P=scripts
{
echo "############ ATTACHMENT FORMAT WORD: bgra8 vs r32f (locate the descriptor BO) ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_r32f 0x800
echo; echo "############ bgra8 vs rgba32f ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_rgba32f 0x800
echo; echo "############ bgra8 vs rgb10a2 ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_rgb10a2 0x800
echo; echo "############ MRT: 1 vs 2 vs 4 ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_mrt2 0x1000
echo "--- mrt2 vs mrt4 ---"
python3 $P/alldiff.py m_rt_mrt2 m_rt_mrt4 0x1000
echo; echo "############ MSAA: base vs msaa2 vs msaa4 ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_msaa2 0x1000
echo "--- msaa2 vs msaa4 ---"
python3 $P/alldiff.py m_rt_msaa2 m_rt_msaa4 0x1000
echo; echo "############ SAMPLE POSITIONS: msaa4 vs msaa4_sp ############"
python3 $P/alldiff.py m_rt_msaa4 m_rt_msaa4_sp 0x1000
echo "--- msaa2 vs msaa2_sp ---"
python3 $P/alldiff.py m_rt_msaa2 m_rt_msaa2_sp 0x1000
echo; echo "############ MEMORYLESS: base vs memless ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_memless 0x1000
echo; echo "############ LOAD/STORE: base vs load_dc / load_ld / store_dc ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_load_dc 0x1000
echo "--- load_ld ---"; python3 $P/alldiff.py m_rt_bgra8 m_rt_load_ld 0x1000
echo "--- store_dc ---"; python3 $P/alldiff.py m_rt_bgra8 m_rt_store_dc 0x1000
echo; echo "############ MSAA RESOLVE: msaa4 vs msaa4_res ############"
python3 $P/alldiff.py m_rt_msaa4 m_rt_msaa4_res 0x1000
echo; echo "############ TILE SIZE: 0x68000 +0x900..+0x910 for various RT sizes ############"
for N in rt_bgra8 rt_w128h64 rt_w1920; do
  echo "--- $N (0x68000 region) ---"
  for O in 0x900 0x904 0x908 0x90c 0x9d0 0x9d4 0x9d8 0x9dc; do python3 $P/shex.py m_$N/bo_sigusr1_h0_va68000_*.hex $O 4; done
done
echo; echo "############ OCCLUSION QUERY: base vs occl_b / occl_c / offsets ############"
python3 $P/alldiff.py m_rt_bgra8 m_rt_occl_b 0x1000
echo "--- occl_b vs occl_c (mode bit) ---"; python3 $P/alldiff.py m_rt_occl_b m_rt_occl_c 0x1000
echo "--- occl_c vs occl_c64 (offset) ---"; python3 $P/alldiff.py m_rt_occl_c m_rt_occl_c64 0x1000
echo "--- occl_c vs occl_c256 ---"; python3 $P/alldiff.py m_rt_occl_c m_rt_occl_c256 0x1000
echo "--- occl result values ---"; grep OCCL r_rt_occl_*.txt
} >rt_analysis.txt 2>&1
echo done
