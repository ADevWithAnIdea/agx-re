// iohello_draw.m — minimal OWN Metal triangle draw for iotrace capture.
//
// Part of EXP-0009 (ROADMAP 0.5). The render analogue of iohello_compute: a
// tiny full-screen-triangle draw into a small offscreen BGRA8 target, run under
// the iotrace interposer to capture the IOKit call sequence + shared-memory
// contents around a *graphics* submit (tiler/fragment work), and to contrast it
// with the compute path. Prints the GPU VAs of its own resources for grepping.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Our own MSL, our own draw.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o iohello_draw iohello_draw.m
// Usage:          [--iters N] [--w W] [--h H]  (defaults: 1, 64, 64)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    unsigned char b[8];
    for (int i = 0; i < 8; i++) b[i] = (va >> (8 * i)) & 0xff;
    printf("VA %-10s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i = 0; i < 8; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long iters = 1, W = 64, H = 64; int doDump = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--iters") && i + 1 < argc) iters = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--w") && i + 1 < argc) W = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--h") && i + 1 < argc) H = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--dump")) doDump = 1;
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("DRAW w=%ld h=%ld iters=%ld\n", W, H, iters);

        NSString *src = @"#include <metal_stdlib>\n"
                         "using namespace metal;\n"
                         "struct VO { float4 pos [[position]]; float4 col; };\n"
                         "vertex VO v_main(uint vid [[vertex_id]]) {\n"
                         "  float2 p[3] = { float2(-1,-1), float2(3,-1), float2(-1,3) };\n"
                         "  VO o; o.pos = float4(p[vid], 0, 1); o.col = float4(0.25, 0.5, 0.75, 1); return o;\n"
                         "}\n"
                         "fragment float4 f_main(VO in [[stage_in]]) { return in.col; }\n";
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { printf("COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> vfn = [lib newFunctionWithName:@"v_main"];
        id<MTLFunction> ffn = [lib newFunctionWithName:@"f_main"];

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vfn; pd.fragmentFunction = ffn;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }

        MTLTextureDescriptor *td =
            [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        // Backing buffer for the target so we can print its GPU VA.
        // (The texture's own VA is not exposed; the draw still references it.)

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
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it, (long)[cb status]);
            if (doDump && it == iters - 1) {
                fflush(stdout);
                kill(getpid(), SIGUSR1);
                usleep(400000);
            }
        }

        unsigned char px[4];
        [target getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0];
        printf("PIXEL bgra=%02x%02x%02x%02x (expect ~bf 80 40 ff)\n", px[0], px[1], px[2], px[3]);
        return 0;
    }
}
