// calib2.m -- INFORMAL CALIBRATION ONLY. Two pipelines (red, blue), switch
// between them across two draws in the SAME command buffer, dump BOs, and
// inspect the FF-state pool (0x58000 family) for a field that changes
// between "red only" and "red then blue" -- looking for EXP-0042's reported
// FS selector at pool+0x08, to see whether it generalizes to this simpler
// two-pipeline case and whether it's nonzero/populated when an actual
// pipeline switch occurs (unlike calib0's single-pipeline case, which read
// 0 there).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <dirent.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static const char *SRC_RED =
"#include <metal_stdlib>\nusing namespace metal;\n"
"struct VOut { float4 pos [[position]]; };\n"
"vertex VOut v_main(uint vid [[vertex_id]]) {\n"
"  float2 p = float2(float((vid << 1) & 2), float(vid & 2));\n"
"  VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;\n"
"}\n"
"fragment float4 f_main() { return float4(1.0, 0.5, 0.25, 1.0); }\n";

static const char *SRC_BLUE =
"#include <metal_stdlib>\nusing namespace metal;\n"
"struct VOut { float4 pos [[position]]; };\n"
"vertex VOut v_main(uint vid [[vertex_id]]) {\n"
"  float2 p = float2(float((vid << 1) & 2), float(vid & 2));\n"
"  VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;\n"
"}\n"
"fragment float4 f_main() { return float4(0.1, 0.2, 0.9, 1.0); }\n";

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *dump_dir = argc > 1 ? argv[1] : "calib_maps4";
        mkdir(dump_dir, 0755);
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSError *err = nil;

        id<MTLLibrary> libR = [dev newLibraryWithSource:[NSString stringWithUTF8String:SRC_RED] options:nil error:&err];
        id<MTLLibrary> libB = [dev newLibraryWithSource:[NSString stringWithUTF8String:SRC_BLUE] options:nil error:&err];
        MTLRenderPipelineDescriptor *pdR = [MTLRenderPipelineDescriptor new];
        pdR.vertexFunction = [libR newFunctionWithName:@"v_main"];
        pdR.fragmentFunction = [libR newFunctionWithName:@"f_main"];
        pdR.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> psoR = [dev newRenderPipelineStateWithDescriptor:pdR error:&err];

        MTLRenderPipelineDescriptor *pdB = [MTLRenderPipelineDescriptor new];
        pdB.vertexFunction = [libB newFunctionWithName:@"v_main"];
        pdB.fragmentFunction = [libB newFunctionWithName:@"f_main"];
        pdB.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> psoB = [dev newRenderPipelineStateWithDescriptor:pdB error:&err];

        if (!psoR || !psoB) { fprintf(stderr, "pso fail\n"); return 2; }

        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];
        id<MTLCommandQueue> q = [dev newCommandQueue];

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        // Draw RED alone, in its own command buffer, then dump ("after_red").
        {
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:psoR];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            uint8_t px[64]; [target getBytes:px bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
            fprintf(stderr, "after RED bgra=%02x%02x%02x%02x\n", px[0],px[1],px[2],px[3]);
        }
        kill(getpid(), SIGUSR1); usleep(1200000);
        rename(dump_dir, "calib_maps4_after_red_TMP");
        mkdir(dump_dir, 0755);
        // move files back with a prefix so both snapshots coexist
        {
            char cmd[512];
            snprintf(cmd, sizeof(cmd), "for f in calib_maps4_after_red_TMP/*; do mv \"$f\" \"%s/afterred_$(basename $f)\"; done", dump_dir);
            system(cmd);
        }

        // Now draw BLUE (a real pipeline switch), fresh command buffer, dump ("after_blue").
        {
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:psoB];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            uint8_t px[64]; [target getBytes:px bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
            fprintf(stderr, "after BLUE bgra=%02x%02x%02x%02x\n", px[0],px[1],px[2],px[3]);
        }
        kill(getpid(), SIGUSR1); usleep(1200000);
        {
            char cmd[512];
            snprintf(cmd, sizeof(cmd), "for f in %s/bo_*; do mv \"$f\" \"%s/afterblue_$(basename $f)\"; done", dump_dir, dump_dir);
            system(cmd);
        }
        fprintf(stderr, "CALIB2_DONE\n");
        return 0;
    }
}
