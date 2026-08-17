// EXP-0041 OWN-SHADER live CS/VS/FS pressure probe using public Metal APIs only.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void fail(const char *what, NSError *err) {
    fprintf(stderr, "FAIL %s%s%s\n", what, err ? ": " : "", err ? [[err localizedDescription] UTF8String] : "");
    exit(1);
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *stage = NULL, *path = NULL;
        unsigned k = 0, allocK = 0, requestedGrid = 64, requestedTg = 32;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--stage") && i + 1 < argc) stage = argv[++i];
            else if (!strcmp(argv[i], "--source") && i + 1 < argc) path = argv[++i];
            else if (!strcmp(argv[i], "--k") && i + 1 < argc) k = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--alloc-k") && i + 1 < argc) allocK = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--grid") && i + 1 < argc) requestedGrid = (unsigned)strtoul(argv[++i], 0, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) requestedTg = (unsigned)strtoul(argv[++i], 0, 0);
        }
        if (!stage || !path || !k) { fprintf(stderr, "usage: probe --stage cs|vs|fs --source x.metal --k K\n"); return 2; }
        if (!allocK) allocK = k;
        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                                   encoding:NSUTF8StringEncoding error:&err];
        if (!src) fail("read source", err);
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s STAGE %s K %u\n", [[dev name] UTF8String], stage, k);
        MTLCompileOptions *opts = [MTLCompileOptions new]; opts.fastMathEnabled = NO;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) fail("compile", err);
        id<MTLCommandQueue> q = [dev newCommandQueue];
        uint32_t n = 1;
        if (!strcmp(stage, "cs")) {
            id<MTLFunction> fn = [lib newFunctionWithName:@"k_main"];
            id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
            if (!pso) fail("compute pipeline", err);
            const unsigned grid = requestedGrid;
            id<MTLBuffer> out = [dev newBufferWithLength:grid * sizeof(float) options:MTLResourceStorageModeShared];
            id<MTLBuffer> in = [dev newBufferWithLength:(NSUInteger)grid * allocK * sizeof(float) options:MTLResourceStorageModeShared];
            float *ip = in.contents; for (NSUInteger i = 0; i < (NSUInteger)grid * allocK; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
            [ce setComputePipelineState:pso]; [ce setBuffer:out offset:0 atIndex:0]; [ce setBuffer:in offset:0 atIndex:1];
            [ce setBytes:&n length:sizeof(n) atIndex:2];
            [ce dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(requestedTg,1,1)]; [ce endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            if (cb.status != MTLCommandBufferStatusCompleted) fail("compute execution", cb.error);
            double sum = 0; float *op = out.contents; for (unsigned i = 0; i < grid; ++i) { if (!isfinite(op[i])) fail("nonfinite compute", nil); sum += op[i]; }
            printf("RESULT status=COMPLETED checksum=%.9g\n", sum);
        } else {
            id<MTLFunction> vf = [lib newFunctionWithName:@"v_main"];
            id<MTLFunction> ff = [lib newFunctionWithName:@"f_main"];
            MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
            pd.vertexFunction = vf; pd.fragmentFunction = ff; pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
            if (!pso) fail("render pipeline", err);
            const unsigned width = 8, height = 8, records = !strcmp(stage, "vs") ? 3 : width * height;
            id<MTLBuffer> in = [dev newBufferWithLength:records * k * sizeof(float) options:MTLResourceStorageModeShared];
            float *ip = in.contents; for (unsigned i = 0; i < records * k; ++i) ip[i] = (float)((i % 251) + 1) * 0.001f;
            NSUInteger bpr = 256;
            id<MTLBuffer> rt = [dev newBufferWithLength:bpr * height options:MTLResourceStorageModeShared];
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
            id<MTLTexture> tex = [rt newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture = tex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore; rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1);
            id<MTLCommandBuffer> cb = [q commandBuffer]; id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
            [re setRenderPipelineState:pso];
            if (!strcmp(stage, "vs")) { [re setVertexBuffer:in offset:0 atIndex:0]; [re setVertexBytes:&n length:sizeof(n) atIndex:1]; }
            else { [re setFragmentBuffer:in offset:0 atIndex:0]; [re setFragmentBytes:&n length:sizeof(n) atIndex:1]; }
            [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [re endEncoding]; [cb commit]; [cb waitUntilCompleted];
            if (cb.status != MTLCommandBufferStatusCompleted) fail("render execution", cb.error);
            unsigned long checksum = 0; unsigned char *p = rt.contents;
            for (unsigned y = 0; y < height; ++y) for (unsigned x = 0; x < width * 4; ++x) checksum += p[y*bpr+x];
            printf("RESULT status=COMPLETED checksum=%lu\n", checksum);
        }
        kill(getpid(), SIGUSR1); usleep(750000);
    }
    return 0;
}
