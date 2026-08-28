// render_eot.m -- EXP-0130 OWN-SHADER + HW-PROBE render harness.
//
// Freshly authored for this experiment (modeled on the same public Metal
// API sequence already HW-validated locally on M4 by EXP-0117's
// harness/render.m "logic"/"nan" modes: RGBA32Float target, LoadActionClear
// with an exact float clearColor establishing a known tilebuffer content,
// a fragment function reading that content via [[color(0)]], StoreActionStore
// writing the real backing texture, then getBytes: readback). One process
// per invocation; one case per invocation; prints one JSON line to stdout.
//
// CLEAN-ROOM: public Metal API only, on our own MSL (kernels/eot_construct.metal).
// No Apple binary is disassembled, decompiled, or introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o render_eot render_eot.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void jfail(const char *stage, NSError *err) {
    NSString *msg = err ? [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] : @"";
    msg = [msg stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
    printf("{\"status\":\"FAIL\",\"stage\":\"%s\",\"error\":\"%s\"}\n", stage, [msg UTF8String]);
    fflush(stdout);
}

enum { O_SRC=128, O_MODE, O_CASE, O_DR, O_DG, O_DB, O_DA, O_KR, O_KG, O_KB, O_KA };
static const struct option L[] = {
    {"source",required_argument,0,O_SRC}, {"mode",required_argument,0,O_MODE}, {"case",required_argument,0,O_CASE},
    {"dr",required_argument,0,O_DR}, {"dg",required_argument,0,O_DG}, {"db",required_argument,0,O_DB}, {"da",required_argument,0,O_DA},
    {"kr",required_argument,0,O_KR}, {"kg",required_argument,0,O_KG}, {"kb",required_argument,0,O_KB}, {"ka",required_argument,0,O_KA},
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp = NULL, *mode = NULL, *casename = "case";
    double dr=0,dg=0,db=0,da=0, kr=0,kg=0,kb=0,ka=0;
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) {
            case O_SRC: srcp = optarg; break;
            case O_MODE: mode = optarg; break;
            case O_CASE: casename = optarg; break;
            case O_DR: dr = atof(optarg); break;
            case O_DG: dg = atof(optarg); break;
            case O_DB: db = atof(optarg); break;
            case O_DA: da = atof(optarg); break;
            case O_KR: kr = atof(optarg); break;
            case O_KG: kg = atof(optarg); break;
            case O_KB: kb = atof(optarg); break;
            case O_KA: ka = atof(optarg); break;
        }
    }
    if (!srcp || !mode) { fprintf(stderr, "need --source and --mode\n"); return 2; }

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "no Metal device\n"); return 2; }
    id<MTLCommandQueue> q = [dev newCommandQueue];

    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "read source failed\n"); return 2; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { jfail("compile", err); return 0; }

    NSString *m = [NSString stringWithUTF8String:mode];
    id<MTLFunction> vf = [lib newFunctionWithName:@"v_full"];
    if (!vf) { jfail("vertex_function", nil); return 0; }

    NSString *fname = nil;
    if ([m isEqualToString:@"evict"]) fname = @"f_eot_evict";
    else if ([m isEqualToString:@"ctrl"]) fname = @"f_eot_ctrl";
    else if ([m isEqualToString:@"combine"]) fname = @"f_eot_combine";
    else { fprintf(stderr, "unknown mode %s\n", mode); return 2; }

    id<MTLFunction> ff = [lib newFunctionWithName:fname];
    if (!ff) { jfail("fragment_function", nil); return 0; }

    const NSUInteger W = 2, H = 2;
    MTLTextureDescriptor *td =
        [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                             width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];

    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.fragmentFunction = ff;
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    // blendingEnabled left NO (default): the shader's own return value is
    // the stored color directly, with no additional hardware blend pass.
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { jfail("pipeline", err); return 0; }

    float konst[4] = {(float)kr, (float)kg, (float)kb, (float)ka};
    id<MTLBuffer> kbuf = [dev newBufferWithBytes:konst length:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = tex;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(dr, dg, db, da);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    if ([m isEqualToString:@"ctrl"] || [m isEqualToString:@"combine"]) {
        [enc setFragmentBuffer:kbuf offset:0 atIndex:0];
    }
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if (cb.error) { jfail("cmdbuf", cb.error); return 0; }

    float px[4];
    [tex getBytes:px bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2, H/2, 1, 1) mipmapLevel:0];

    printf("{\"status\":\"OK\",\"mode\":\"%s\",\"case\":\"%s\",\"dst\":[%.17g,%.17g,%.17g,%.17g],"
           "\"konst\":[%.17g,%.17g,%.17g,%.17g],\"result\":[%.17g,%.17g,%.17g,%.17g],"
           "\"gputime_ns\":%llu}\n",
           mode, casename, dr, dg, db, da, kr, kg, kb, ka,
           (double)px[0], (double)px[1], (double)px[2], (double)px[3],
           (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));
    fflush(stdout);
    return 0;
}}
