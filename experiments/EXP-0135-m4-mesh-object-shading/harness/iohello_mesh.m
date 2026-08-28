// iohello_mesh.m — EXP-0030 minimal OWN object+mesh+fragment draw for iotrace.
// The mesh analogue of tools/iotrace/iohello_draw.m: a tiny mesh-shader draw
// into an offscreen BGRA8 target, run under the iotrace interposer to capture the
// IOKit call sequence + shared-memory contents around a MESH submit, and to
// contrast it with the compute + ordinary-draw paths. Prints its resource VAs.
// CLEAN-ROOM: OWN-SHADER + public Metal API only.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o iohello_mesh iohello_mesh.m
// Usage:          [--iters N] [--w W] [--h H] [--dump]
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        long iters = 1, W = 32, H = 32; int doDump = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--iters") && i + 1 < argc) iters = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--w") && i + 1 < argc) W = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--h") && i + 1 < argc) H = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump")) doDump = 1;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("MESHDRAW w=%ld h=%ld iters=%ld\n", W, H, iters);

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
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { printf("COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> ofn = [lib newFunctionWithName:@"obj_main"];
        id<MTLFunction> mfn = [lib newFunctionWithName:@"mesh_main"];
        id<MTLFunction> ffn = [lib newFunctionWithName:@"frag_main"];

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        md.objectFunction = ofn; md.meshFunction = mfn; md.fragmentFunction = ffn;
        md.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
        if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }

        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        id<MTLCommandQueue> q = [dev newCommandQueue];

        for (long it = 0; it < iters; it++) {
            printf("SUBMIT iter=%ld begin\n", it);
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture = target;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            [enc drawMeshThreadgroups:MTLSizeMake(1,1,1)
                  threadsPerObjectThreadgroup:MTLSizeMake(1,1,1)
                    threadsPerMeshThreadgroup:MTLSizeMake(3,1,1)];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it, (long)[cb status]);
            if (doDump && it == iters - 1) { fflush(stdout); kill(getpid(), SIGUSR1); usleep(400000); }
        }
        unsigned char px[4];
        [target getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(W/2, H/2, 1, 1) mipmapLevel:0];
        printf("PIXEL center bgra=%02x%02x%02x%02x (expect green ~00 ff 00 ff)\n", px[0], px[1], px[2], px[3]);
        return 0;
    }
}
