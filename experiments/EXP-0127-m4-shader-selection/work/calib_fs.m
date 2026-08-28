// Throwaway calibration (work/, non-recorded): discover natural FS selector
// values for fs_red/fs_green/fs_blue via solo draws, and check whether the
// pool+0x08 selector is already correct PRE-commit (dump right after
// endEncoding, before commit) vs only after commit+wait, mirroring EXP-0116's
// calibration approach for the CDM tail link.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static id<MTLRenderPipelineState> mk(id<MTLDevice> dev, id<MTLLibrary> lib, NSString *fs, NSString *label) {
    MTLRenderPipelineDescriptor *d = [MTLRenderPipelineDescriptor new];
    d.label = label;
    d.vertexFunction = [lib newFunctionWithName:@"vs_main"];
    d.fragmentFunction = [lib newFunctionWithName:fs];
    d.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    NSError *e=nil;
    id<MTLRenderPipelineState> s = [dev newRenderPipelineStateWithDescriptor:d error:&e];
    if (!s) { fprintf(stderr, "FAIL %s: %s\n", label.UTF8String, e.localizedDescription.UTF8String); exit(2); }
    return s;
}

int main(void) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSError *e = nil;
        NSString *src = [NSString stringWithContentsOfFile:@"../kernels/fsredirect.metal" encoding:NSUTF8StringEncoding error:&e];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        if (!lib) { fprintf(stderr,"compile fail %s\n", e.localizedDescription.UTF8String); return 2; }
        id<MTLRenderPipelineState> red = mk(dev, lib, @"fs_red", @"red");
        id<MTLRenderPipelineState> green = mk(dev, lib, @"fs_green", @"green");
        id<MTLRenderPipelineState> blue = mk(dev, lib, @"fs_blue", @"blue");

        static const float tri[6] = {-1,-1, 3,-1, -1,3};
        id<MTLBuffer> verts = [dev newBufferWithBytes:tri length:sizeof(tri) options:MTLResourceStorageModeShared];
        id<MTLBuffer> params = [dev newBufferWithLength:0x100 options:MTLResourceStorageModeShared];
        float *p = params.contents; p[0]=1;p[1]=1;p[2]=0;p[3]=1;

        const NSUInteger w=16,h=16,bpr=64;
        id<MTLBuffer> tb = [dev newBufferWithLength:bpr*h options:MTLResourceStorageModeShared];
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:w height:h mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [tb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLRenderPipelineState> states[3] = {red, green, blue};
        const char *names[3] = {"red","green","blue"};
        for (int i=0;i<3;i++) {
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = tex;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1);
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:states[i]];
            [enc setVertexBuffer:verts offset:0 atIndex:0];
            [enc setVertexBuffer:params offset:0 atIndex:1];
            [enc setFragmentBuffer:params offset:0 atIndex:0];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            // PRE-COMMIT dump.
            printf("PRECOMMIT_DUMP name=%s\n", names[i]); fflush(stdout);
            kill(getpid(), SIGUSR1); usleep(400000);
            [cb commit];
            [cb waitUntilCompleted];
            unsigned char *px = tb.contents;
            unsigned char *s = px + 8*bpr + 8*4;
            printf("RESULT name=%s status=%ld bgra=%02x%02x%02x%02x\n", names[i],
                   (long)cb.status, s[0],s[1],s[2],s[3]);
            fflush(stdout);
            // POST-COMMIT dump.
            printf("POSTCOMMIT_DUMP name=%s\n", names[i]); fflush(stdout);
            kill(getpid(), SIGUSR1); usleep(400000);
        }
        return 0;
    }
}
