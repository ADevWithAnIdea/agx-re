// EXP-M4-02 bf16_matrix_probe.m — focused investigation of the ONE capability
// delta seen in the battery: bfloat simdgroup_matrix REJECTED on M4.
// Question: is it the ELEMENT TYPE (bfloat) that is rejected, or a constructor/
// spelling artifact?  Test several spellings; capture the FULL diagnostic.
// Clean-room: OUR OWN MSL only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

typedef struct { const char *name; const char *src; } P;

static P PS[] = {
// control: half via template spelling (not the typedef) — isolates "type vs typedef"
{"half_template_ctor",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device half* o [[buffer(0)]]){ simdgroup_matrix<half,8,8> a(1.0); simdgroup_store(a,o,8); }\n"},
// bf16: scalar constructor
{"bf16_scalar_ctor",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]]){ simdgroup_matrix<bfloat,8,8> a(bfloat(1.0)); simdgroup_store(a,o,8); }\n"},
// bf16: default ctor + load from a bfloat buffer (no scalar ctor)
{"bf16_default_ctor_load",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]], device const bfloat* in [[buffer(1)]]){ simdgroup_matrix<bfloat,8,8> a; simdgroup_load(a,in,8); simdgroup_store(a,o,8); }\n"},
// bf16: make_filled helper
{"bf16_make_filled",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]]){ auto a = make_filled_simdgroup_matrix<bfloat,8,8>(bfloat(1.0)); simdgroup_store(a,o,8); }\n"},
// bf16 inputs, fp32 accumulator matmul (the mixed->fp32 path the A18 census cites)
{"bf16_in_f32_acc_matmul",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device float* o [[buffer(0)]], device const bfloat* A [[buffer(1)]], device const bfloat* B [[buffer(2)]]){\n"
 "  simdgroup_matrix<bfloat,8,8> a,b; simdgroup_load(a,A,8); simdgroup_load(b,B,8);\n"
 "  simdgroup_matrix<float,8,8> c(0.0);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n"
 "  simdgroup_store(c,o,8); }\n"},
// pure bf16 matmul (bf16 accumulator)
{"bf16_all_matmul",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]], device const bfloat* A [[buffer(1)]], device const bfloat* B [[buffer(2)]]){\n"
 "  simdgroup_matrix<bfloat,8,8> a,b,c(bfloat(0));\n simdgroup_load(a,A,8); simdgroup_load(b,B,8);\n"
 "  simdgroup_multiply_accumulate(c,a,b,c);\n simdgroup_store(c,o,8); }\n"},
// control: does plain bfloat scalar exist at all on this compiler?
{"bfloat_scalar_exists",
 "#include <metal_stdlib>\nusing namespace metal;\n"
 "kernel void k(device bfloat* o [[buffer(0)]]){ bfloat x = bfloat(1.0); o[0]=x+bfloat(2.0); }\n"},
};

int main(void){ @autoreleasepool {
  id<MTLDevice> d = MTLCreateSystemDefaultDevice();
  printf("device=%s  arch=%s\n\n", d.name.UTF8String, d.architecture.name.UTF8String);
  for (unsigned i=0;i<sizeof(PS)/sizeof(PS[0]);i++){
    NSError *e=nil;
    id<MTLLibrary> lib=[d newLibraryWithSource:[NSString stringWithUTF8String:PS[i].src] options:nil error:&e];
    printf("==== %s : %s ====\n", PS[i].name, lib?"COMPILED":"REJECTED");
    if(!lib && e) printf("%s\n", e.localizedDescription.UTF8String);
    printf("\n");
  }
  return 0;
}}
