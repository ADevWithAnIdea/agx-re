// rendersweep.m -- EXP-0178 persistent OWN-SHADER render sweep runner.
//
// DERIVATIVE of our own experiments/EXP-0147-m4-emit-pipeline-misc/harness/
// rendersweep.m (itself the render analogue of tools/agxtest/agxrender.m).
// EXP-0178 adds ONE capability and changes nothing else: an INDEXED draw with
// baseVertex / baseInstance, so the vertex-stage `get_sr` carrier can make
// vertex_id, instance_id, base_vertex and base_instance mutually
// distinguishable in the read-back. `"draw":"indexed"` selects it; the default
// stays the original non-indexed drawPrimitives path, byte-for-byte compatible
// with EXP-0147's requests.
//
//
// The render analogue of tools/agxtest/agxrun_persist.m: keeps ONE live
// MTLDevice + queue for the process lifetime and services many
// (spliced-archive, clear-colour, uniform) -> pixels requests read as
// one-JSON-object-per-line on stdin. Each request re-loads the binary
// archive FROM DISK and forces the render pipeline to come from it with
// MTLPipelineOptionFailOnBinaryArchiveMiss, so the bytes we spliced are the
// bytes that execute (same mechanism tools/agxtest/agxrender.m proves).
//
// CLEAN-ROOM: public Metal API only, driving OUR OWN compiled MSL. No Apple
// binary is disassembled, decompiled, or introspected.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o rendersweep rendersweep.m
//
// stdin  : {"id":"r1","archive":"p.bin","vs":"v_a","fs":"f_a","w":4,"h":4,
//           "nrt":1,"samples":1,"clear":[[0,0,0,0]],"fbuf":[1,2,3,4],"vbuf":[...],
//           "tex":[0,0,0,0],"instances":8,
//           "draw":"indexed","basevertex":9,"baseinstance":5}
// "draw":"indexed" issues drawIndexedPrimitives with a 3-entry uint16
// index buffer {0,1,2} plus the given baseVertex/baseInstance; omit it (or
// pass "prim") for the original non-indexed drawPrimitives.
// "tex" allocates a 1x1 RGBA32Float read_write texture pre-filled with that
// value and bound at texture(0) (the raster_order_group carrier); its value
// AFTER the draw is returned as "tex". "instances" draws the triangle N times
// so N fragments race on the same texel.
// stdout : {"id":"r1","status":"OK","pixels":[[r,g,b,a],...],"gputime_ns":N}
//          status in OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL |
//                       PIPELINE_MISS | CMDBUF_ERROR | BAD_REQUEST

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

int main(int argc, char **argv) { @autoreleasepool {
    const char *sourcePath = NULL;
    BOOL fastMath = NO;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--source") && i + 1 < argc) sourcePath = argv[++i];
        else if (!strcmp(argv[i], "--fast-math")) fastMath = YES;
    }
    if (!sourcePath) { fprintf(stderr, "need --source\n"); return 2; }

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "no Metal device\n"); return 2; }
    id<MTLCommandQueue> q = [dev newCommandQueue];

    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { fprintf(stderr, "read source failed\n"); return 2; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    [co setFastMathEnabled:fastMath];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
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
        NSString *vsn = req[@"vs"], *fsn = req[@"fs"];
        NSUInteger W = [(req[@"w"] ?: @1) unsignedIntegerValue];
        NSUInteger H = [(req[@"h"] ?: @1) unsignedIntegerValue];
        NSUInteger NRT = [(req[@"nrt"] ?: @1) unsignedIntegerValue];
        NSUInteger SAMP = [(req[@"samples"] ?: @1) unsignedIntegerValue];
        NSArray *clear = req[@"clear"];
        NSArray *fbuf = req[@"fbuf"], *vbuf = req[@"vbuf"], *texinit = req[@"tex"];
        NSUInteger INST = [(req[@"instances"] ?: @1) unsignedIntegerValue];
        NSString *DRAW = req[@"draw"] ?: @"prim";
        NSInteger BASEV = [(req[@"basevertex"] ?: @0) integerValue];
        NSUInteger BASEI = [(req[@"baseinstance"] ?: @0) unsignedIntegerValue];
        if (!arc || !vsn || !fsn || NRT < 1 || NRT > 4) {
            respond_fail(rid, "BAD_REQUEST", @"need archive/vs/fs, nrt in 1..4"); continue;
        }

        NSError *e = nil;
        // CRUCIAL (mirrors tools/agxtest/agxrun_persist.m): a library compiled
        // from *source* has a fixed AIR identity whose native code Metal
        // memoizes in-process, so a later spliced archive is IGNORED and the
        // original code runs. Load a FRESH MTLLibrary from the spliced
        // archive's own bytes each request so every splice really executes.
        // (EXP-0147 measured this: without it, every splice returns the
        // baseline pixel.)
        id<MTLLibrary> alib = [dev newLibraryWithURL:[NSURL fileURLWithPath:arc] error:&e];
        if (!alib) { respond_fail(rid, "COMPILE_FAIL", [e localizedDescription]); continue; }
        id<MTLFunction> vf = [alib newFunctionWithName:vsn];
        id<MTLFunction> ff = [alib newFunctionWithName:fsn];
        if (!vf || !ff) { respond_fail(rid, "FUNCTION_MISSING", nil); continue; }

        MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
        [ad setUrl:[NSURL fileURLWithPath:arc]];
        id<MTLBinaryArchive> archive = [dev newBinaryArchiveWithDescriptor:ad error:&e];
        if (!archive) { respond_fail(rid, "ARCHIVE_FAIL", [e localizedDescription]); continue; }

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        [pd setVertexFunction:vf]; [pd setFragmentFunction:ff];
        for (NSUInteger i = 0; i < NRT; i++)
            pd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA32Float;
        pd.rasterSampleCount = SAMP;
        [pd setBinaryArchives:@[archive]];
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithDescriptor:pd
                                              options:MTLPipelineOptionFailOnBinaryArchiveMiss
                                           reflection:nil error:&e];
        if (!pso) { respond_fail(rid, "PIPELINE_MISS", [e localizedDescription]); continue; }

        // Render targets (resolve targets when multisampled).
        NSMutableArray *tex = [NSMutableArray array];
        NSMutableArray *msaa = [NSMutableArray array];
        for (NSUInteger i = 0; i < NRT; i++) {
            MTLTextureDescriptor *td =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                   width:W height:H mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            td.storageMode = MTLStorageModeShared;
            [tex addObject:[dev newTextureWithDescriptor:td]];
            if (SAMP > 1) {
                MTLTextureDescriptor *md =
                    [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                       width:W height:H mipmapped:NO];
                md.textureType = MTLTextureType2DMultisample;
                md.sampleCount = SAMP;
                md.usage = MTLTextureUsageRenderTarget;
                md.storageMode = MTLStorageModePrivate;
                [msaa addObject:[dev newTextureWithDescriptor:md]];
            }
        }

        float fb[4] = {0,0,0,0}, vb[4] = {0,0,0,0};
        for (NSUInteger i = 0; i < 4 && fbuf && i < [fbuf count]; i++) fb[i] = [fbuf[i] floatValue];
        for (NSUInteger i = 0; i < 4 && vbuf && i < [vbuf count]; i++) vb[i] = [vbuf[i] floatValue];
        id<MTLBuffer> fbb = [dev newBufferWithBytes:fb length:16 options:MTLResourceStorageModeShared];
        id<MTLBuffer> vbb = [dev newBufferWithBytes:vb length:16 options:MTLResourceStorageModeShared];

        id<MTLTexture> rwtex = nil;
        if (texinit) {
            MTLTextureDescriptor *rtd =
                [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                   width:1 height:1 mipmapped:NO];
            rtd.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
            rtd.storageMode = MTLStorageModeShared;
            rwtex = [dev newTextureWithDescriptor:rtd];
            float t0v[4] = {0,0,0,0};
            for (NSUInteger i = 0; i < 4 && i < [texinit count]; i++) t0v[i] = [texinit[i] floatValue];
            [rwtex replaceRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0 withBytes:t0v bytesPerRow:16];
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        for (NSUInteger i = 0; i < NRT; i++) {
            double c[4] = {0,0,0,0};
            if (clear && i < [clear count]) {
                NSArray *ci = clear[i];
                for (NSUInteger k = 0; k < 4 && k < [ci count]; k++) c[k] = [ci[k] doubleValue];
            }
            if (SAMP > 1) {
                rp.colorAttachments[i].texture = msaa[i];
                rp.colorAttachments[i].resolveTexture = tex[i];
                rp.colorAttachments[i].storeAction = MTLStoreActionMultisampleResolve;
            } else {
                rp.colorAttachments[i].texture = tex[i];
                rp.colorAttachments[i].storeAction = MTLStoreActionStore;
            }
            rp.colorAttachments[i].loadAction = MTLLoadActionClear;
            rp.colorAttachments[i].clearColor = MTLClearColorMake(c[0], c[1], c[2], c[3]);
        }

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:fbb offset:0 atIndex:0];
        [enc setVertexBuffer:vbb offset:0 atIndex:0];
        if (rwtex) [enc setFragmentTexture:rwtex atIndex:0];
        if ([DRAW isEqualToString:@"indexed"]) {
            // 3-entry uint16 index buffer {0,1,2}: the ONLY draw form that
            // gives [[base_vertex]] / [[base_instance]] non-zero values.
            uint16_t idx[3] = {0, 1, 2};
            id<MTLBuffer> ib = [dev newBufferWithBytes:idx length:sizeof(idx)
                                               options:MTLResourceStorageModeShared];
            [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3
                             indexType:MTLIndexTypeUInt16 indexBuffer:ib
                     indexBufferOffset:0 instanceCount:INST
                            baseVertex:BASEV baseInstance:BASEI];
        } else {
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3
                  instanceCount:INST];
        }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            respond_fail(rid, "CMDBUF_ERROR", [[cb error] localizedDescription]); continue;
        }

        NSMutableString *out = [NSMutableString stringWithFormat:
            @"{\"id\":\"%@\",\"status\":\"OK\",\"gputime_ns\":%llu,\"pixels\":[",
            rid, (unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9)];
        float *px = (float *)malloc(W * H * 4 * sizeof(float));
        BOOL first = YES;
        for (NSUInteger i = 0; i < NRT; i++) {
            [tex[i] getBytes:px bytesPerRow:W * 16
                  fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
            for (NSUInteger p = 0; p < W * H; p++) {
                [out appendFormat:@"%s[%.9g,%.9g,%.9g,%.9g]", first ? "" : ",",
                     (double)px[p*4+0], (double)px[p*4+1], (double)px[p*4+2], (double)px[p*4+3]];
                first = NO;
            }
        }
        free(px);
        [out appendString:@"]"];
        if (rwtex) {
            float tv[4];
            [rwtex getBytes:tv bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
            [out appendFormat:@",\"tex\":[%.9g,%.9g,%.9g,%.9g]",
                 (double)tv[0], (double)tv[1], (double)tv[2], (double)tv[3]];
        }
        [out appendString:@"}\n"];
        fputs([out UTF8String], stdout);
        fflush(stdout);
    }}
    free(line);
    return 0;
}}
