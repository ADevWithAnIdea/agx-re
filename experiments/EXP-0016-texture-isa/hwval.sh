#!/bin/bash
# EXP-0016 HW-validation driver (runs on the A18 target). Re-runs every splice-and-
# observe test and saves logs to raw/. CLEAN-ROOM: OWN-SHADER; our own compiled
# (and spliced) bytes only. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"; mkdir -p raw out
SRC=kernels/tex_frag.metal; CSRC=kernels/tex_comp.metal
log(){ echo "=== $1 ==="; }

{
  log "1. sample runs + coordinate->texel (f_sample, 4x4 grid, distinct texels)"
  ./texr --archive out/frag_f_sample.bin --source $SRC --vertex v_main --fragment f_sample \
     --width 4 --height 4 --t0 grid 2>&1 | grep -E "PIPELINE_SOURCE|PIXEL|STATUS"

  log "2. two_tex baseline t0(60,20,0,128)+t1(0,0,180,64) = (60,20,180,192)"
  ./texr --archive out/frag_f_two_tex.bin --source $SRC --vertex v_main --fragment f_two_tex \
     --width 1 --height 1 --t0 60,20,0,128 --t1 0,0,180,64 2>&1 | grep -E "PIXEL|STATUS"

  log "3. TEXTURE-SLOT splice: sample#2 op+4 bit0x80 (tex1->tex0). expect t0+t0, blue->0"
  OFF=$(python3 agxparse.py out/frag_f_two_tex.bin --stage fragment --locate _agc.main | cut -d' ' -f1)
  echo "  _agc.main abs off=$OFF ; splice byte $((OFF+84)) 0x81->0x01"
  python3 splice.py out/frag_f_two_tex.bin out/two_tex_slice.bin $((OFF+84))=01 >/dev/null
  ./texr --archive out/two_tex_slice.bin --source $SRC --vertex v_main --fragment f_two_tex \
     --width 1 --height 1 --t0 60,20,0,128 --t1 0,0,180,64 2>&1 | grep -E "PIXEL|STATUS"

  log "4. SAMPLER-SLOT splice: two_samp sample#2 op+5 (samp1->samp0), 8x8 grid"
  OFF=$(python3 agxparse.py out/frag_f_two_samp.bin --stage fragment --locate _agc.main | cut -d' ' -f1)
  echo "  _agc.main abs off=$OFF ; splice byte $((OFF+85)) 0x01->0x00"
  python3 splice.py out/frag_f_two_samp.bin out/two_samp_slice.bin $((OFF+85))=00 >/dev/null
  ./texr --archive out/frag_f_two_samp.bin --source $SRC --vertex v_main --fragment f_two_samp \
     --width 8 --height 8 --t0 grid 2>&1 | grep "PIXEL" > /tmp/b.txt
  ./texr --archive out/two_samp_slice.bin --source $SRC --vertex v_main --fragment f_two_samp \
     --width 8 --height 8 --t0 grid 2>&1 | grep "PIXEL" > /tmp/s.txt
  echo "  pixels changed by the sampler-slot splice: $(diff /tmp/b.txt /tmp/s.txt | grep -c '^<') / 64"
  echo "  sample of the change (row 0):"; diff /tmp/b.txt /tmp/s.txt | grep -E '^[<>] PIXEL [0-4] 0 ' | head -10

  log "5. texture.read (0xb0 mode 0x17): c_read reads texel[coord] into buffer"
  ./texcomp --archive out/comp_c_read.bin --source $CSRC --function c_read --mode read 2>&1 \
     | grep -E "PIPELINE_SOURCE|OUT|STATUS"

  log "6. texture.write (0xd7): c_write moves buffer colours into texel[coord]"
  ./texcomp --archive out/comp_c_write.bin --source $CSRC --function c_write --mode write 2>&1 \
     | grep -E "PIPELINE_SOURCE|TEXEL|STATUS"
} 2>&1 | tee raw/hw_validation.txt
echo "=== DONE ==="
