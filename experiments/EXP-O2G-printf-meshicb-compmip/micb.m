// micb.m — EXP-O2G part 2: encode a MESH draw inside an MTLIndirectCommandBuffer.
//
// The Metal API exposes MTLIndirectCommandTypeDrawMeshThreadgroups and
// -[MTLIndirectRenderCommand drawMeshThreadgroups:...]. This harness attempts, step by
// step (each guarded so a rejection is captured, not fatal), to:
//   (1) build a mesh render pipeline with supportIndirectCommandBuffers = YES,
//   (2) create an ICB whose commandTypes = DrawMeshThreadgroups,
//   (3) encode a mesh draw into the ICB (setRenderPipelineState + drawMeshThreadgroups),
//   (4) executeCommandsInBuffer: it inside a render pass and render to an offscreen target.
// Run under tools/iotrace with --dump to capture the combined encoding — specifically to
// see whether the ICB command layout carries the mesh-grid-dispatch record 0x70000600
// (EXP-0030) instead of the 0x61c4 draw-primitive record (EXP-0027 §1c ICB draw).
// If Metal rejects mesh-in-ICB at any step, that rejection (which step + error) IS the answer.
//
// CLEAN-ROOM: OWN-SHADER (our MSL) + public Metal API + DATA-TRACE. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o micb micb.m
// Usage: micb [--icbn N] [--threads] [--w W] [--h H] [--dump]
//   --threads : use MTLIndirectCommandTypeDrawMeshThreads + drawMeshThreads: instead
//   --icbn N  : commands to encode (default 1)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

#define STEP(msg) printf("STEP %s\n", msg); fflush(stdout);
#define FAILRET(tag, e) do { printf("REJECT at=%s err=%s\n", tag, \
    (e)?[[(e) localizedDescription] UTF8String]:"(nil, no NSError)"); fflush(stdout); } while(0)

int main(int argc, char **argv) {
    @autoreleasepool {
        long icbn = 1, W = 32, H = 32; int useThreads = 0, doDump = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--icbn") && i + 1 < argc) icbn = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--w") && i + 1 < argc) W = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--h") && i + 1 < argc) H = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--threads")) useThreads = 1;
            else if (!strcmp(argv[i], "--dump")) doDump = 1;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CONFIG icbn=%ld w=%ld h=%ld threads=%d\n", icbn, W, H, useThreads);

        NSError *err = nil;
        NSString *src =
          @"#include <metal_stdlib>\n#include <metal_mesh>\nusing namespace metal;\n"
           "struct VOut { float4 position [[position]]; float4 color; };\n"
           "struct POut { float3 pnormal [[flat]]; };\n"
           "using tri_mesh = metal::mesh<VOut, POut, 3, 1, metal::topology::triangle>;\n"
           "struct Payload { float scale; float p0; float p1; float p2; };\n"
           "[[object, max_total_threadgroups_per_mesh_grid(1)]]\n"
           "void obj_main(object_data Payload &pl [[payload]], mesh_grid_properties mgp, uint tid [[thread_position_in_grid]]) {\n"
           "  pl.scale = 1.0f; mgp.set_threadgroups_per_grid(uint3(1,1,1)); }\n"
           "[[mesh, max_total_threads_per_threadgroup(3)]]\n"
           "void mesh_main(tri_mesh out, const object_data Payload &pl [[payload]], uint lane [[thread_index_in_threadgroup]]) {\n"
           "  if (lane==0) out.set_primitive_count(1);\n"
           "  float2 P[3] = { float2(-0.5,-0.5), float2(0.5,-0.5), float2(0.0,0.5) };\n"
           "  VOut v; v.position = float4(P[lane]*pl.scale,0,1); v.color = float4(0,1,0,1);\n"
           "  out.set_vertex(lane, v); out.set_index(lane, uchar(lane));\n"
           "  if (lane==0){ POut p; p.pnormal=float3(0,0,1); out.set_primitive(0,p); } }\n"
           "struct FragIn { VOut v; POut p; };\n"
           "fragment float4 frag_main(FragIn in [[stage_in]]) { return in.v.color; }\n";
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { printf("COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }

        STEP("build mesh pipeline with supportIndirectCommandBuffers=YES");
        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        md.objectFunction = [lib newFunctionWithName:@"obj_main"];
        md.meshFunction = [lib newFunctionWithName:@"mesh_main"];
        md.fragmentFunction = [lib newFunctionWithName:@"frag_main"];
        md.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        md.supportIndirectCommandBuffers = YES;
        id<MTLRenderPipelineState> pso = nil;
        @try {
            pso = [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
        } @catch (NSException *ex) { printf("REJECT at=pipeline-exc name=%s reason=%s\n",
            [[ex name] UTF8String], [[ex reason] UTF8String]); }
        if (!pso) { FAILRET("pipeline-create-mesh-icb", err);
            // Retry WITHOUT ICB support to prove the pipeline itself is fine (isolates ICB as the blocker).
            md.supportIndirectCommandBuffers = NO; err = nil;
            id<MTLRenderPipelineState> p2 = [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
            printf("CONTROL mesh-pipeline-without-ICB = %s %s\n", p2?"OK":"FAIL", p2?"":(err?[[err localizedDescription] UTF8String]:""));
            return 0;
        }
        printf("OK mesh pipeline (supportIndirectCommandBuffers=YES) created\n");

        STEP("create ICB commandTypes=DrawMeshThreadgroups");
        MTLIndirectCommandBufferDescriptor *icbd = [MTLIndirectCommandBufferDescriptor new];
        icbd.commandTypes = useThreads ? MTLIndirectCommandTypeDrawMeshThreads
                                       : MTLIndirectCommandTypeDrawMeshThreadgroups;
        icbd.inheritBuffers = NO; icbd.inheritPipelineState = NO;
        if (@available(macOS 14.0, *)) icbd.maxMeshBufferBindCount = 1;
        id<MTLIndirectCommandBuffer> icb = nil;
        @try {
            icb = [dev newIndirectCommandBufferWithDescriptor:icbd maxCommandCount:(NSUInteger)icbn options:0];
        } @catch (NSException *ex) { printf("REJECT at=icb-create-exc name=%s reason=%s\n",
            [[ex name] UTF8String], [[ex reason] UTF8String]); return 0; }
        if (!icb) { printf("REJECT at=icb-create (nil, no NSError)\n"); return 0; }
        printf("OK ICB created maxCount=%ld\n", icbn);

        STEP("encode mesh draw into ICB command(s)");
        @try {
            for (long c = 0; c < icbn; c++) {
                id<MTLIndirectRenderCommand> rc = [icb indirectRenderCommandAtIndex:(NSUInteger)c];
                [rc setRenderPipelineState:pso];
                if (useThreads) {
                    [rc drawMeshThreads:MTLSizeMake(3,1,1)
                      threadsPerObjectThreadgroup:MTLSizeMake(1,1,1)
                        threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
                } else {
                    [rc drawMeshThreadgroups:MTLSizeMake(1,1,1)
                      threadsPerObjectThreadgroup:MTLSizeMake(1,1,1)
                        threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
                }
            }
        } @catch (NSException *ex) { printf("REJECT at=icb-encode-exc name=%s reason=%s\n",
            [[ex name] UTF8String], [[ex reason] UTF8String]); return 0; }
        printf("OK encoded %ld mesh command(s) into ICB\n", icbn);

        STEP("executeCommandsInBuffer inside a render pass");
        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        id<MTLCommandQueue> q = [dev newCommandQueue];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        @try {
            [enc setRenderPipelineState:pso];
            [enc executeCommandsInBuffer:icb withRange:NSMakeRange(0, (NSUInteger)icbn)];
        } @catch (NSException *ex) { printf("REJECT at=execute-exc name=%s reason=%s\n",
            [[ex name] UTF8String], [[ex reason] UTF8String]); [enc endEncoding]; return 0; }
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        printf("SUBMIT done status=%ld\n", (long)[cb status]);
        if ([cb error]) printf("CB_ERROR %s\n", [[[cb error] localizedDescription] UTF8String]);

        unsigned char px[4] = {0};
        [target getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(W/2, H/2, 1, 1) mipmapLevel:0];
        printf("PIXEL center bgra=%02x%02x%02x%02x (expect green ~00 ff 00 ff)\n", px[0], px[1], px[2], px[3]);
        if (doDump) { fflush(stdout); kill(getpid(), SIGUSR1); usleep(500000); }
        return 0;
    }
}
