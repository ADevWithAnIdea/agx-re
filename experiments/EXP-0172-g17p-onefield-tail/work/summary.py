import json,os
ROOT="/Users/user/asahi_re/public/agx-re"
db=json.load(open(os.path.join(ROOT,"tools/agx-isa/db.json")))
val=json.load(open(os.path.join(ROOT,"tools/agx-isa/validation.json")))
byM={i["mnemonic"]:i for i in db["instructions"]}
targets=[("cubearray_coord_const","b3"),("dev_scoreboard_fence","scope_flag"),("falu2i","imm_flag"),
 ("frame_marker_compact","b1"),("get_sr","form"),("half_alu_fma12","ext"),("imageblock_store","src"),
 ("irotate","b2"),("mesh_out_src","sel"),("n4_cf_word","b3"),("ret","scoreboard"),
 ("simd_ballot","cache"),("simd_shuffle","cache"),("tex_deriv","dstsrc"),("tex_sample","coord"),("vary_slot","slot")]
for m,f in targets:
    i=byM[m]; v=val["instructions"].get(m,{})
    fd=[x for x in i.get("fields",[]) if x["name"]==f]
    fd=fd[0] if fd else None
    print("#"*72)
    print("%s.%s  len=%d match=%s emit_unsafe=%s" % (m,f,i["length"],i["match"],i.get("emit_unsafe")))
    print("  field: %s" % json.dumps(fd))
    print("  all fields: %s" % ", ".join("%s@%d/%d"%(x["name"],x["start"],x["width"]) for x in i.get("fields",[])))
    print("  instr note: %s" % json.dumps((v.get("_instruction") or {})))
    print("  field val: %s" % json.dumps(v.get(f,{}),indent=2))
    print("  semantics: %s" % i.get("semantics","")[:600])
    print("  provenance: %s" % i.get("provenance","")[:400])
