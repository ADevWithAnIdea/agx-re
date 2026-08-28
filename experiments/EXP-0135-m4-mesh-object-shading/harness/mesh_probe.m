// EXP-0135 mesh_probe.m — OWN-SHADER mesh/object pipeline probe (M4).
//
// One process = one case (per CLAUDE.md's recovery model: isolate one change
// per dispatch). Compiles a caller-supplied object+mesh+fragment MSL source
// (optionally with preprocessor macros, e.g. NV/NP/PAYLOAD_BYTES/AMP_COUNT --
// see kernels/mesh_sweep.metal) via the public newLibraryWithSource: runtime
// API, builds an MTLMeshRenderPipelineDescriptor (with optional
// payloadMemoryLength override / supportIndirectCommandBuffers), creates the
// pipeline, and (unless --no-render) dispatches it one of four ways:
//   direct    - drawMeshThreadgroups:threadsPerObjectThreadgroup:...
//   indirect  - drawMeshThreadgroupsWithIndirectBuffer:...: a small embedded
//               compute kernel first writes (X,Y,Z) into a
//               MTLDispatchThreadgroupsIndirectArguments-shaped buffer at a
//               caller-controlled byte offset.
//   icb_cpu   - CPU-authored id<MTLIndirectRenderCommand> drawMeshThreadgroups,
//               executed via executeCommandsInBuffer:.., with a caller
//               controlled MTLIndirectCommandBufferExecutionRange.
//   icb_gpu   - GPU-authored (compute-kernel-encoded) ICB mesh command, loaded
//               from a second source file (--icb-src / --icb-fn) using the
//               EXP-0124 ICBContainer/argument-encoder pattern.
// Prints one machine-parseable line per field; final line is always
// "STATUS <token>". Every GPU-touching call happens inside this one process;
// the external harness applies the hard timeout (kills this process on hang).
//
// Clean-room: OUR OWN MSL only, public Metal runtime API only. Nothing here
// disassembles, decompiles, or introspects any Apple binary.
//
// Build: clang -fobjc-arc -O1 -framework Metal -framework Foundation \
//              -o mesh_probe mesh_probe.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); fflush(stdout); }

static NSString *errText(NSError *e) {
    return e ? [e localizedDescription] : @"(none)";
}

static MTLSize parseSize(const char *s, MTLSize dflt) {
    if (!s) return dflt;
    unsigned long x = 1, y = 1, z = 1;
    sscanf(s, "%lu,%lu,%lu", &x, &y, &z);
    return MTLSizeMake((NSUInteger)x, (NSUInteger)y, (NSUInteger)z);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *srcPath = NULL, *objName = "obj_main", *meshName = "mesh_main",
                   *fragName = "frag_main", *mode = "direct";
        const char *icbSrcPath = NULL, *icbFnName = "icbw_encode_mesh";
        long payloadOverride = -1; // -1 = do not touch (leave Metal default 0)
        int icbSupport = 0, noRender = 0, noObject = 0;
        long width = 32, height = 32;
        const char *gridS = "1,1,1", *objTgS = "1,1,1", *meshTgS = "32,1,1";
        long indX = 1, indY = 1, indZ = 1, indWriteOff = 0, indCallOff = -1, indBufBytes = -1;
        long icbMax = 4, icbLoc = 0, icbLen = -1; // icbLen -1 => use full-buffer executeCommandsInBuffer:
        long icbGridX = 1, icbGridY = 1, icbGridZ = 1;
        int doDump = 0;
        NSMutableDictionary *macros = [NSMutableDictionary dictionary];

        static struct option longOpts[] = {
            {"src", required_argument, 0, 1}, {"object", required_argument, 0, 2},
            {"mesh", required_argument, 0, 3}, {"fragment", required_argument, 0, 4},
            {"define", required_argument, 0, 5}, {"payload-override", required_argument, 0, 6},
            {"icb-support", required_argument, 0, 7}, {"mode", required_argument, 0, 8},
            {"no-render", no_argument, 0, 9}, {"no-object", no_argument, 0, 10},
            {"width", required_argument, 0, 11}, {"height", required_argument, 0, 12},
            {"grid", required_argument, 0, 13}, {"obj-tg", required_argument, 0, 14},
            {"mesh-tg", required_argument, 0, 15},
            {"indirect-x", required_argument, 0, 16}, {"indirect-y", required_argument, 0, 17},
            {"indirect-z", required_argument, 0, 18}, {"indirect-write-offset", required_argument, 0, 19},
            {"indirect-call-offset", required_argument, 0, 20}, {"indirect-buffer-bytes", required_argument, 0, 21},
            {"icb-max", required_argument, 0, 22}, {"icb-loc", required_argument, 0, 23},
            {"icb-len", required_argument, 0, 24}, {"icb-src", required_argument, 0, 25},
            {"icb-fn", required_argument, 0, 26}, {"icb-grid", required_argument, 0, 27},
            {"dump", no_argument, 0, 28},
            {0, 0, 0, 0}
        };
        int c, idx;
        while ((c = getopt_long(argc, argv, "", longOpts, &idx)) != -1) {
            switch (c) {
                case 1: srcPath = optarg; break;
                case 2: objName = optarg; break;
                case 3: meshName = optarg; break;
                case 4: fragName = optarg; break;
                case 5: {
                    char *eq = strchr(optarg, '=');
                    if (eq) {
                        NSString *k = [[NSString alloc] initWithBytes:optarg length:(eq - optarg) encoding:NSUTF8StringEncoding];
                        NSString *v = [NSString stringWithUTF8String:eq + 1];
                        macros[k] = v;
                    }
                    break;
                }
                case 6: payloadOverride = strtol(optarg, NULL, 0); break;
                case 7: icbSupport = (int)strtol(optarg, NULL, 0); break;
                case 8: mode = optarg; break;
                case 9: noRender = 1; break;
                case 10: noObject = 1; break;
                case 11: width = strtol(optarg, NULL, 0); break;
                case 12: height = strtol(optarg, NULL, 0); break;
                case 13: gridS = optarg; break;
                case 14: objTgS = optarg; break;
                case 15: meshTgS = optarg; break;
                case 16: indX = strtol(optarg, NULL, 0); break;
                case 17: indY = strtol(optarg, NULL, 0); break;
                case 18: indZ = strtol(optarg, NULL, 0); break;
                case 19: indWriteOff = strtol(optarg, NULL, 0); break;
                case 20: indCallOff = strtol(optarg, NULL, 0); break;
                case 21: indBufBytes = strtol(optarg, NULL, 0); break;
                case 22: icbMax = strtol(optarg, NULL, 0); break;
                case 23: icbLoc = strtol(optarg, NULL, 0); break;
                case 24: icbLen = strtol(optarg, NULL, 0); break;
                case 25: icbSrcPath = optarg; break;
                case 26: icbFnName = optarg; break;
                case 27: sscanf(optarg, "%ld,%ld,%ld", &icbGridX, &icbGridY, &icbGridZ); break;
                case 28: doDump = 1; break;
                default: fprintf(stderr, "unknown option\n"); return 2;
            }
        }
        if (!srcPath) { fprintf(stderr, "need --src\n"); return 2; }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { emit_status("NO_DEVICE"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcPath]
                                                    encoding:NSUTF8StringEncoding error:&err];
        if (!src) { printf("COMPILE FAIL\nCOMPILE_ERROR %s\n", [errText(err) UTF8String]); emit_status("COMPILE_FAIL"); return 1; }

        MTLCompileOptions *copts = [MTLCompileOptions new];
        if (macros.count) [copts setPreprocessorMacros:macros];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:copts error:&err];
        if (!lib) { printf("COMPILE FAIL\nCOMPILE_ERROR %s\n", [errText(err) UTF8String]); emit_status("COMPILE_FAIL"); return 1; }
        printf("COMPILE OK\nCOMPILE_ERROR NONE\n");
        fflush(stdout);

        id<MTLFunction> ofn = noObject ? nil : [lib newFunctionWithName:[NSString stringWithUTF8String:objName]];
        id<MTLFunction> mfn = [lib newFunctionWithName:[NSString stringWithUTF8String:meshName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fragName]];
        if ((!noObject && !ofn) || !mfn || !ffn) {
            printf("PIPELINE FAIL\nPIPELINE_ERROR function-missing (obj=%d mesh=%d frag=%d)\n",
                   ofn != nil, mfn != nil, ffn != nil);
            emit_status("PIPELINE_FAIL");
            return 1;
        }

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        md.objectFunction = ofn;
        md.meshFunction = mfn;
        md.fragmentFunction = ffn;
        md.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        if (payloadOverride >= 0) md.payloadMemoryLength = (NSUInteger)payloadOverride;
        if (icbSupport) md.supportIndirectCommandBuffers = YES;

        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
        if (!pso) { printf("PIPELINE FAIL\nPIPELINE_ERROR %s\n", [errText(err) UTF8String]); emit_status("PIPELINE_FAIL"); return 1; }
        printf("PIPELINE OK\nPIPELINE_ERROR NONE\n");
        printf("REFLECT objTGMax=%lu meshTGMax=%lu meshGridMax=%lu\n",
               (unsigned long)[pso maxTotalThreadsPerObjectThreadgroup],
               (unsigned long)[pso maxTotalThreadsPerMeshThreadgroup],
               (unsigned long)[pso maxTotalThreadgroupsPerMeshGrid]);
        fflush(stdout);

        if (noRender) { emit_status("OK"); return 0; }

        // --- render target ---
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                                 width:(NSUInteger)width height:(NSUInteger)height mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];

        // Optional pre-pass: write the indirect-draw argument buffer.
        id<MTLBuffer> indBuf = nil;
        if (!strcmp(mode, "indirect")) {
            long bufBytes = indBufBytes > 0 ? indBufBytes : (indWriteOff + 16);
            if (bufBytes < 16) bufBytes = 16;
            indBuf = [dev newBufferWithLength:(NSUInteger)bufBytes options:MTLResourceStorageModeShared];
            memset([indBuf contents], 0xAA, (size_t)bufBytes); // poison, to detect partial writes
            NSString *wsrc = @"#include <metal_stdlib>\nusing namespace metal;\n"
                              "kernel void indirect_writer(device uchar *buf [[buffer(0)]], constant uint3 &xyz [[buffer(1)]], constant uint &off [[buffer(2)]]) {\n"
                              "  device uint *p = (device uint *)(buf + off); p[0]=xyz.x; p[1]=xyz.y; p[2]=xyz.z; }\n";
            id<MTLLibrary> wlib = [dev newLibraryWithSource:wsrc options:nil error:&err];
            if (!wlib) { printf("PIPELINE FAIL\nPIPELINE_ERROR indirect-writer-compile: %s\n", [errText(err) UTF8String]); emit_status("PIPELINE_FAIL"); return 1; }
            id<MTLFunction> wfn = [wlib newFunctionWithName:@"indirect_writer"];
            id<MTLComputePipelineState> wpso = [dev newComputePipelineStateWithFunction:wfn error:&err];
            if (!wpso) { printf("PIPELINE FAIL\nPIPELINE_ERROR indirect-writer-pso: %s\n", [errText(err) UTF8String]); emit_status("PIPELINE_FAIL"); return 1; }
            uint32_t xyz[3] = {(uint32_t)indX, (uint32_t)indY, (uint32_t)indZ};
            uint32_t woff = (uint32_t)indWriteOff;
            id<MTLBuffer> xyzBuf = [dev newBufferWithBytes:xyz length:12 options:MTLResourceStorageModeShared];
            id<MTLBuffer> offBuf = [dev newBufferWithBytes:&woff length:4 options:MTLResourceStorageModeShared];
            id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
            [ce setComputePipelineState:wpso];
            [ce setBuffer:indBuf offset:0 atIndex:0];
            [ce setBuffer:xyzBuf offset:0 atIndex:1];
            [ce setBuffer:offBuf offset:0 atIndex:2];
            [ce dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
            [ce endEncoding];
        }

        // Optional pre-pass: encode a GPU-authored ICB mesh command.
        id<MTLIndirectCommandBuffer> icb = nil;
        if (!strcmp(mode, "icb_cpu") || !strcmp(mode, "icb_gpu")) {
            MTLIndirectCommandBufferDescriptor *icd = [MTLIndirectCommandBufferDescriptor new];
            icd.commandTypes = MTLIndirectCommandTypeDrawMeshThreadgroups;
            icd.inheritPipelineState = YES;
            icb = [dev newIndirectCommandBufferWithDescriptor:icd maxCommandCount:(NSUInteger)icbMax options:0];
            if (!icb) { printf("PIPELINE FAIL\nPIPELINE_ERROR icb-alloc-failed\n"); emit_status("PIPELINE_FAIL"); return 1; }
            printf("ICB_CREATE OK\n");

            if (!strcmp(mode, "icb_cpu")) {
                id<MTLIndirectRenderCommand> rc = [icb indirectRenderCommandAtIndex:0];
                [rc drawMeshThreadgroups:MTLSizeMake((NSUInteger)icbGridX, (NSUInteger)icbGridY, (NSUInteger)icbGridZ)
                threadsPerObjectThreadgroup:MTLSizeMake(1, 1, 1)
                  threadsPerMeshThreadgroup:parseSize(meshTgS, MTLSizeMake(32, 1, 1))];
            } else {
                if (!icbSrcPath) { printf("PIPELINE FAIL\nPIPELINE_ERROR icb_gpu-needs---icb-src\n"); emit_status("PIPELINE_FAIL"); return 1; }
                NSString *isrc = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:icbSrcPath]
                                                             encoding:NSUTF8StringEncoding error:&err];
                if (!isrc) { printf("COMPILE FAIL\nCOMPILE_ERROR icb-src-read: %s\n", [errText(err) UTF8String]); emit_status("COMPILE_FAIL"); return 1; }
                id<MTLLibrary> ilib = [dev newLibraryWithSource:isrc options:nil error:&err];
                if (!ilib) { printf("COMPILE FAIL\nCOMPILE_ERROR icb-gpu-encoder: %s\n", [errText(err) UTF8String]); emit_status("COMPILE_FAIL"); return 1; }
                id<MTLFunction> encFn = [ilib newFunctionWithName:[NSString stringWithUTF8String:icbFnName]];
                if (!encFn) { printf("PIPELINE FAIL\nPIPELINE_ERROR icb-gpu-fn-missing\n"); emit_status("PIPELINE_FAIL"); return 1; }
                id<MTLComputePipelineState> encPSO = [dev newComputePipelineStateWithFunction:encFn error:&err];
                if (!encPSO) { printf("PIPELINE FAIL\nPIPELINE_ERROR icb-gpu-pso: %s\n", [errText(err) UTF8String]); emit_status("PIPELINE_FAIL"); return 1; }
                id<MTLArgumentEncoder> argEnc = [encFn newArgumentEncoderWithBufferIndex:0];
                id<MTLBuffer> argBuf = [dev newBufferWithLength:argEnc.encodedLength options:MTLResourceStorageModeShared];
                [argEnc setArgumentBuffer:argBuf offset:0];
                [argEnc setIndirectCommandBuffer:icb atIndex:0];
                uint32_t gridArr[3] = {(uint32_t)icbGridX, (uint32_t)icbGridY, (uint32_t)icbGridZ};
                id<MTLBuffer> gridBuf = [dev newBufferWithBytes:gridArr length:12 options:MTLResourceStorageModeShared];
                id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
                [ce setComputePipelineState:encPSO];
                [ce setBuffer:argBuf offset:0 atIndex:0];
                [ce setBuffer:gridBuf offset:0 atIndex:1];
                [ce useResource:icb usage:MTLResourceUsageWrite];
                [ce dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
                [ce endEncoding];
            }
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];

        MTLSize objTg = parseSize(objTgS, MTLSizeMake(1, 1, 1));
        MTLSize meshTg = parseSize(meshTgS, MTLSizeMake(32, 1, 1));
        MTLSize grid = parseSize(gridS, MTLSizeMake(1, 1, 1));

        if (!strcmp(mode, "direct")) {
            [enc drawMeshThreadgroups:grid threadsPerObjectThreadgroup:objTg threadsPerMeshThreadgroup:meshTg];
        } else if (!strcmp(mode, "indirect")) {
            NSUInteger callOff = indCallOff >= 0 ? (NSUInteger)indCallOff : (NSUInteger)indWriteOff;
            [enc drawMeshThreadgroupsWithIndirectBuffer:indBuf indirectBufferOffset:callOff
                             threadsPerObjectThreadgroup:objTg threadsPerMeshThreadgroup:meshTg];
        } else if (!strcmp(mode, "icb_cpu") || !strcmp(mode, "icb_gpu")) {
            if (icbLen < 0) {
                [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0, (NSUInteger)icbMax)];
            } else {
                MTLIndirectCommandBufferExecutionRange range = {(uint32_t)icbLoc, (uint32_t)icbLen};
                // executeCommandsInBuffer:indirectBuffer:indirectBufferOffset: expects a
                // buffer holding the range; build one so we exercise the exact
                // public entry point EXP-0098 characterized for ordinary ICBs.
                id<MTLBuffer> rangeBuf = [dev newBufferWithBytes:&range
                                                           length:sizeof(range)
                                                          options:MTLResourceStorageModeShared];
                [enc executeCommandsInBuffer:icb indirectBuffer:rangeBuf indirectBufferOffset:0];
            }
        } else {
            printf("PIPELINE FAIL\nPIPELINE_ERROR unknown-mode-%s\n", mode);
            emit_status("PIPELINE_FAIL");
            return 1;
        }
        [enc endEncoding];
        printf("DISPATCH OK\n");
        fflush(stdout);

        [cb commit];
        [cb waitUntilCompleted];
        MTLCommandBufferStatus st = [cb status];
        printf("CMDBUF_STATUS %ld\n", (long)st);
        if (st == MTLCommandBufferStatusError) {
            printf("CMDBUF_ERROR %s\n", [errText([cb error]) UTF8String]);
            fflush(stdout);
            emit_status("CMDBUF_ERROR");
            return 1;
        }
        printf("CMDBUF_ERROR NONE\n");
        fflush(stdout);

        if (doDump) {
            // Ask the iotrace interposer (if loaded) to snapshot every
            // registered BO now, while the command stream is still mapped.
            // Harmless no-op if the interposer is not loaded.
            kill(getpid(), SIGUSR1);
            usleep(400000);
        }

        size_t npx = (size_t)width * (size_t)height;
        unsigned char *px = (unsigned char *)malloc(npx * 4);
        [target getBytes:px bytesPerRow:(NSUInteger)(width * 4)
              fromRegion:MTLRegionMake2D(0, 0, (NSUInteger)width, (NSUInteger)height) mipmapLevel:0];
        long covered = 0;
        for (size_t i = 0; i < npx; i++) {
            unsigned char *p = px + i * 4;
            if (p[0] || p[1] || p[2]) covered++;
        }
        printf("COVERED %ld %ld\n", covered, (long)npx);
        long cx = width / 2, cy = height / 2;
        unsigned char *cp = px + (cy * width + cx) * 4;
        printf("CENTER bgra=%02x%02x%02x%02x\n", cp[0], cp[1], cp[2], cp[3]);
        free(px);

        emit_status("OK");
        return 0;
    }
}
