// meshsweep207.m -- EXP-0207 persistent OWN-SHADER MESH render sweep runner.
//
// The mesh-stage analogue of harness/rendersweep207.m, and the reason
// `mesh_out_src.sel` has never been dispatched: the field is MESH-STAGE ONLY,
// every prior census that declined it ran COMPUTE kernels, and no runner in this
// repository could execute a spliced MESH pipeline at all.  EXP-0187 found the
// first carrier that emits the op; this runs it.
//
// Same stdin/stdout JSON protocol as rendersweep207.m so the same driver and the
// same safe reader-thread wrapper serve both.  Each request re-loads the binary
// archive FROM DISK and forces the mesh pipeline to come from it with
// MTLPipelineOptionFailOnBinaryArchiveMiss, so the bytes we spliced execute.
//
// stdin : {"id","archive","object","mesh","fragment","w","h","format",
//          "clear":[[r,g,b,a]],"fbuf":[...],"tgobj":N,"tgmesh":N,"grid":N}
//          "object" may be omitted/null for a mesh-only pipeline.
// stdout: {"id","status":"OK","gputime_ns":N,"raw":"<hex>","pixels":[...]}
//
// CLEAN-ROOM: public Metal API only, on OUR OWN compiled MSL.  No Apple binary
// is disassembled, decompiled, or introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o meshsweep207 meshsweep207.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void respond_fail(NSString *rid, const char *status, NSString *msg) {
    NSString *m = msg ? [[msg stringByReplacingOccurrencesOfString:@"\"" withString:@"'"]
                          stringByReplacingOccurrencesOfString:@"\n" withString:@" "] : @"";
    printf("{\"id\":\"%s\",\"status\":\"%s\",\"error\":\"%s\"}\n",
           [rid UTF8String], status, [m UTF8String]);
    fflush(stdout);
}

// A NaN or an infinity printed with %g is `nan` / `inf`, which is NOT valid JSON,
// and a single such pixel makes the whole response unparseable -- observed in
// work/pilot02 as five `measurement_failed` cases whose raw payload began with
// 0x7f800000 (+inf).  A measurement failure is not an observation, so the fix is
// to keep the response parseable: the authoritative observable is the exact
// `raw` byte string, and this convenience array emits JSON null for any
// non-finite value rather than an unparseable token.
static void appendNum(NSMutableString *s, double v, BOOL comma) {
    if (comma) [s appendString:@","];
    if (isfinite(v)) [s appendFormat:@"%.9g", v];
    else             [s appendString:@"null"];
}

static void hexcat(NSMutableString *dst, const uint8_t *b, NSUInteger n) {
    static const char *H = "0123456789abcdef";
    char *tmp = (char *)malloc(n * 2 + 1);
    for (NSUInteger i = 0; i < n; i++) { tmp[i*2] = H[b[i] >> 4]; tmp[i*2+1] = H[b[i] & 15]; }
    tmp[n*2] = 0;
    [dst appendString:[NSString stringWithUTF8String:tmp]];
    free(tmp);
}

int main(int argc, char **argv) { @autoreleasepool {
    const char *sourcePath = NULL;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--source") && i + 1 < argc) sourcePath = argv[++i];
    if (!sourcePath) { fprintf(stderr, "need --source\n"); return 2; }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "no Metal device\n"); return 2; }
    if (![dev supportsFamily:MTLGPUFamilyApple7]) {
        fprintf(stderr, "device does not report mesh-capable family\n");
    }
    id<MTLCommandQueue> q = [dev newCommandQueue];

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "read source failed\n"); return 2; }
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:[MTLCompileOptions new] error:&err];
    if (!lib) { fprintf(stderr, "compile failed: %s\n",
                        [[err localizedDescription] UTF8String]); return 2; }

    printf("READY %s\n", [[dev name] UTF8String]);
    fflush(stdout);

    char *line = NULL; size_t cap = 0; ssize_t n;
    while ((n = getline(&line, &cap, stdin)) > 0) { @autoreleasepool {
        NSData *jd = [NSData dataWithBytes:line length:(NSUInteger)n];
        NSDictionary *req = [NSJSONSerialization JSONObjectWithData:jd options:0 error:nil];
        if (![req isKindOfClass:[NSDictionary class]]) {
            respond_fail(@"?", "BAD_REQUEST", @"not a JSON object"); continue;
        }
        NSString *rid = req[@"id"] ?: @"?";
        NSString *arc = req[@"archive"];
        NSString *on = req[@"object"], *mn = req[@"mesh"], *fn = req[@"fragment"];
        NSUInteger W = [(req[@"w"] ?: @8) unsignedIntegerValue];
        NSUInteger H = [(req[@"h"] ?: @8) unsignedIntegerValue];
        NSUInteger TGO = [(req[@"tgobj"] ?: @1) unsignedIntegerValue];
        NSUInteger TGM = [(req[@"tgmesh"] ?: @12) unsignedIntegerValue];
        NSUInteger GRID = [(req[@"grid"] ?: @1) unsignedIntegerValue];
        NSArray *clear = req[@"clear"];
        NSArray *fbuf = req[@"fbuf"];
        if (!arc || !mn || !fn) { respond_fail(rid, "BAD_REQUEST", @"need archive/mesh/fragment"); continue; }

        NSError *e = nil;
        id<MTLLibrary> alib = [dev newLibraryWithURL:[NSURL fileURLWithPath:arc] error:&e];
        if (!alib) { respond_fail(rid, "COMPILE_FAIL", [e localizedDescription]); continue; }
        id<MTLFunction> ofn = (on && ![on isKindOfClass:[NSNull class]])
                              ? [alib newFunctionWithName:on] : nil;
        id<MTLFunction> mfn = [alib newFunctionWithName:mn];
        id<MTLFunction> ffn = [alib newFunctionWithName:fn];
        if (!mfn || !ffn || (on && ![on isKindOfClass:[NSNull class]] && !ofn)) {
            respond_fail(rid, "FUNCTION_MISSING", nil); continue;
        }

        MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
        [ad setUrl:[NSURL fileURLWithPath:arc]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&e];
        if (!archive) { respond_fail(rid, "ARCHIVE_FAIL", [e localizedDescription]); continue; }

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        md.objectFunction = ofn;
        md.meshFunction = mfn;
        md.fragmentFunction = ffn;
        md.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        [md setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md
                                                  options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                               reflection:nil error:&e];
        if (!pso) { respond_fail(rid, "PIPELINE_MISS", [e localizedDescription]); continue; }

        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                               width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [dev newTextureWithDescriptor:td];

        float fb[32]; memset(fb, 0, sizeof fb);
        for (NSUInteger i = 0; i < 32 && fbuf && i < [fbuf count]; i++) fb[i] = [fbuf[i] floatValue];
        id<MTLBuffer> fbb = [dev newBufferWithBytes:fb length:sizeof fb
                                            options:MTLResourceStorageModeShared];

        double c[4] = {0,0,0,0};
        if (clear && [clear count]) {
            NSArray *ci = clear[0];
            for (NSUInteger k = 0; k < 4 && k < [ci count]; k++) c[k] = [ci[k] doubleValue];
        }
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(c[0], c[1], c[2], c[3]);

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:fbb offset:0 atIndex:0];
        [enc setObjectBuffer:fbb offset:0 atIndex:0];
        [enc setMeshBuffer:fbb offset:0 atIndex:0];
        [enc drawMeshThreadgroups:MTLSizeMake(GRID, 1, 1)
      threadsPerObjectThreadgroup:MTLSizeMake(TGO, 1, 1)
        threadsPerMeshThreadgroup:MTLSizeMake(TGM, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(rid, "CMDBUF_ERROR", [[cb error] localizedDescription]); continue;
        }

        NSMutableString *out = [NSMutableString stringWithFormat:
            @"{\"id\":\"%@\",\"status\":\"OK\",\"gputime_ns\":%llu,\"raw\":\"",
            rid, (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9)];
        NSUInteger nb = W * H * 16;
        uint8_t *px = (uint8_t *)malloc(nb);
        [tex getBytes:px bytesPerRow:W * 16
           fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
        hexcat(out, px, nb);
        [out appendString:@"\",\"pixels\":["];
        float *f = (float *)px;
        for (NSUInteger p = 0; p < W * H; p++) {
            [out appendString:(p ? @",[" : @"[")];
            for (int k = 0; k < 4; k++) appendNum(out, (double)f[p*4+k], k > 0);
            [out appendString:@"]"];
        }
        [out appendString:@"]}\n"];
        free(px);
        fputs([out UTF8String], stdout);
        fflush(stdout);
    }}
    free(line);
    return 0;
}}
