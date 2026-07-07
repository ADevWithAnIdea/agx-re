#!/bin/bash
# Compile each render kernel and extract vertex+fragment _agc.main hex.
# Runs on the device in ~/cleanroom_work/exp0029.
cd ~/cleanroom_work/exp0029 || exit 1
mkdir -p out raw
run() {
  local name="$1"; shift
  local src="kernels/${name}.metal"
  ./shdump -o "out/${name}.bin" --render --vertex v_main --fragment f_main "$@" "$src" 2>"raw/${name}.shdump.err"
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "$name COMPILE_FAIL rc=$rc  $(head -1 raw/${name}.shdump.err)"
    return
  fi
  local fhex=$(python3 agxparse.py "out/${name}.bin" --stage fragment --extract-hex 2>/dev/null)
  local vhex=$(python3 agxparse.py "out/${name}.bin" --stage vertex   --extract-hex 2>/dev/null)
  echo "$fhex" > "raw/${name}.frag.hex"
  echo "$vhex" > "raw/${name}.vert.hex"
  echo "$name OK frag=${#fhex} vert=${#vhex}"
}

# Single-attachment kernels (default colorFormat 80 = bgra8Unorm)
for k in interp_smooth interp_flat interp_noperspective interp_centroid \
         interp_sample interp_centroid_nopersp interp_sample_nopersp \
         interp_pull_center interp_pull_centroid interp_pull_sample interp_pull_offset \
         out_const out_half out_discard blend_read blend_read_half; do
  run "$k"
done
