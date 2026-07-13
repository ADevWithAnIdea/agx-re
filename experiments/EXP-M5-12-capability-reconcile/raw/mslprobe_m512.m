// Clean-room M5 MSL-acceptance probe for EXP-M5-12 (OBJ-2 capability reconcile).
// Compile-only (newLibraryWithSource:), NO GPU dispatch. All MSL below is OURS.
// Confirms PRESENCE at the MSL surface of graphics capabilities that had no M5
// capability row: layered rendering, fragment depth output + early_fragment_tests,
// fragment sample_mask (output + input coverage). ACCEPT/REJECT are the public
// runtime compiler's response to our own source. No Apple binary introspected.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static id<MTLDevice> gDev;

static void T(const char *name, NSString *src) {
    NSError *e = nil;
    MTLCompileOptions *o = [MTLCompileOptions new];
    id<MTLLibrary> lib = [gDev newLibraryWithSource:src options:o error:&e];
    if (lib) {
        printf("ACCEPT  %s\n", name);
    } else {
        NSString *m = e.localizedDescription ?: @"(nil)";
        m = [m stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        if (m.length > 180) m = [m substringToIndex:180];
        printf("REJECT  %s :: %s\n", name, m.UTF8String);
    }
}

int main(void) {
  @autoreleasepool {
    gDev = MTLCreateSystemDefaultDevice();
    printf("device = %s / macOS-runtime MSL compile probe\n", gDev.name.UTF8String);
    NSString *H = @"#include <metal_stdlib>\nusing namespace metal;\n";

    // ---- B-1: layered rendering (render_target_array_index) as a VERTEX output ----
    T("layer_rt_array_index_vsout", [H stringByAppendingString:
      @"struct VOut{float4 pos[[position]];uint layer[[render_target_array_index]];};"
      @"vertex VOut vmain(uint vid[[vertex_id]]){VOut o;o.pos=float4(0,0,0,1);o.layer=vid&7u;return o;}"]);
    // parallel: viewport_array_index (already documented) as control
    T("viewport_array_index_vsout", [H stringByAppendingString:
      @"struct VOut{float4 pos[[position]];uint vp[[viewport_array_index]];};"
      @"vertex VOut vmain(uint vid[[vertex_id]]){VOut o;o.pos=float4(0,0,0,1);o.vp=vid&15u;return o;}"]);
    // both together (single-pass layered + multi-viewport)
    T("layer_and_viewport_together", [H stringByAppendingString:
      @"struct VOut{float4 pos[[position]];uint layer[[render_target_array_index]];uint vp[[viewport_array_index]];};"
      @"vertex VOut vmain(uint vid[[vertex_id]]){VOut o;o.pos=float4(0,0,0,1);o.layer=vid&7u;o.vp=vid&15u;return o;}"]);

    // ---- M-1: fragment depth output [[depth(...)]] + [[early_fragment_tests]] ----
    T("frag_depth_any", [H stringByAppendingString:
      @"struct FOut{float4 c[[color(0)]];float d[[depth(any)]];};"
      @"fragment FOut fmain(){FOut o;o.c=float4(1);o.d=0.5f;return o;}"]);
    T("frag_depth_greater", [H stringByAppendingString:
      @"struct FOut{float4 c[[color(0)]];float d[[depth(greater)]];};"
      @"fragment FOut fmain(){FOut o;o.c=float4(1);o.d=0.5f;return o;}"]);
    T("frag_depth_less", [H stringByAppendingString:
      @"struct FOut{float4 c[[color(0)]];float d[[depth(less)]];};"
      @"fragment FOut fmain(){FOut o;o.c=float4(1);o.d=0.5f;return o;}"]);
    T("frag_early_fragment_tests", [H stringByAppendingString:
      @"[[early_fragment_tests]] fragment float4 fmain(){return float4(1);}"]);
    T("frag_early_fragment_tests_with_depth", [H stringByAppendingString:
      @"struct FOut{float4 c[[color(0)]];float d[[depth(greater)]];};"
      @"[[early_fragment_tests]] fragment FOut fmain(){FOut o;o.c=float4(1);o.d=0.5f;return o;}"]);

    // ---- M-2: fragment [[sample_mask]] output + input coverage mask ----
    T("frag_sample_mask_output", [H stringByAppendingString:
      @"struct FOut{float4 c[[color(0)]];uint m[[sample_mask]];};"
      @"fragment FOut fmain(){FOut o;o.c=float4(1);o.m=0x3u;return o;}"]);
    T("frag_sample_mask_input_coverage", [H stringByAppendingString:
      @"fragment float4 fmain(uint cov[[sample_mask]]){return float4(float(cov));}"]);
    T("frag_sample_id_and_mask", [H stringByAppendingString:
      @"fragment float4 fmain(uint sid[[sample_id]],uint cov[[sample_mask]]){return float4(float(sid+cov));}"]);

    // ---- MINOR: conservative rasterization qualifiers (expected REJECT / no MSL path) ----
    T("frag_primitive_barycentric_probe_control", [H stringByAppendingString:
      @"fragment float4 fmain(float3 bc[[barycentric_coord]]){return float4(bc,1);}"]);

    printf("DONE\n");
  }
  return 0;
}
