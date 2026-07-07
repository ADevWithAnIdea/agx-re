#!/bin/bash
# run_census.sh — EXP-0036 device driver. Compiles the OWN-SHADER corpus, extracts
# every stage's _agc.main, and writes per-stage hex to hex/. Run ON THE DEVICE in
# ~/cleanroom_work/exp0036 (which must contain shdump.m, shdump_mesh.m, fndump.m,
# agxparse.py, census_extract.py, and corpus/).
set -u
cd "$(dirname "$0")"
mkdir -p build hex
LOG=build/build.log; : > "$LOG"

echo "== building harnesses =="
clang -fobjc-arc -framework Metal -framework Foundation -o build/shdump shdump.m 2>>"$LOG" || { echo "shdump build FAILED"; tail "$LOG"; exit 1; }
clang -fobjc-arc -framework Metal -framework Foundation -o build/shdump_mesh shdump_mesh.m 2>>"$LOG" || echo "shdump_mesh build FAILED (mesh skipped)"
clang -fobjc-arc -framework Metal -framework Foundation -o build/fndump fndump.m 2>>"$LOG" || echo "fndump build FAILED (fptr skipped)"

extract() { # archive stage outname
  python3 census_extract.py "$1" "$2" _agc.main > "hex/$3.hex" 2>>"$LOG" \
    && echo "  ok  $3 ($2)  $(wc -c < hex/$3.hex | tr -d ' ') hex chars" \
    || { echo "  FAIL extract $3 ($2)"; rm -f "hex/$3.hex"; }
}

echo "== COMPUTE kernels (corpus_compute.metal) =="
COMPUTE="k_int_arith k_uint_arith k_float_arith k_half_arith k_half2_pack \
k_int_bitwise k_int_shift k_int_bitcount k_int_rotate k_int_bitfield k_int_minmax k_int64 \
k_cvt_fi k_cvt_half k_cvt_pack k_transcend k_transcend_round \
k_cf_if k_cf_loop k_cf_switch k_cf_call k_mem k_threadgroup \
k_atomics k_atomics_float k_atomics_tg \
k_subgroup_reduce k_subgroup_int k_subgroup_scan k_subgroup_shuffle k_subgroup_ballot k_quad \
k_matrix k_matrix_half k_builtins_ids k_builtins_folded"
for fn in $COMPUTE; do
  if build/shdump -f "$fn" -o "build/$fn.bin" corpus/corpus_compute.metal 2>>"$LOG"; then
    extract "build/$fn.bin" compute "$fn"
  else echo "  compile FAIL $fn"; fi
done

echo "== TEXTURE compute kernels (corpus_texture.metal) =="
TEX="k_tex_sample k_tex_lod k_tex_gather k_tex_compare k_tex_rw k_tex_array_cube k_tex_atomic k_tex_query k_tex_msaa"
for fn in $TEX; do
  if build/shdump -f "$fn" -o "build/$fn.bin" corpus/corpus_texture.metal 2>>"$LOG"; then
    extract "build/$fn.bin" compute "$fn"
  else echo "  compile FAIL $fn"; fi
done

echo "== RENDER pipelines (corpus_render.metal) =="
# pairs: name vertex fragment
RENDER="r_basic:v_basic:f_basic r_flat:v_flat:f_flat r_cent:v_cent:f_cent \
r_tex:v_basic:f_tex r_deriv:v_basic:f_deriv r_blend:v_basic:f_blend"
for spec in $RENDER; do
  IFS=: read name vfn ffn <<< "$spec"
  if build/shdump --render --vertex "$vfn" --fragment "$ffn" -o "build/$name.bin" corpus/corpus_render.metal 2>>"$LOG"; then
    extract "build/$name.bin" vertex   "${name}_vertex"
    extract "build/$name.bin" fragment "${name}_fragment"
  else echo "  compile FAIL $name"; fi
done

echo "== MESH pipeline (mesh.metal) =="
if [ -x build/shdump_mesh ]; then
  if build/shdump_mesh -o build/mesh.bin --object obj_main --mesh mesh_main --fragment frag_main corpus/mesh.metal 2>>"$LOG"; then
    extract build/mesh.bin object   mesh_object
    extract build/mesh.bin mesh     mesh_mesh
    extract build/mesh.bin fragment mesh_fragment
  else echo "  mesh compile FAIL"; fi
fi

echo "== FUNCTION TABLE (fptr.metal via fndump) =="
if [ -x build/fndump ]; then
  if build/fndump -o build/fptr.bin -f k_fptr --visible vadd,vmul corpus/fptr.metal 2>>"$LOG"; then
    extract build/fptr.bin compute k_fptr
  else echo "  fptr compile FAIL (see log)"; fi
fi

echo "== DONE. $(ls hex/*.hex 2>/dev/null | wc -l | tr -d ' ') stage hex files in hex/ =="
