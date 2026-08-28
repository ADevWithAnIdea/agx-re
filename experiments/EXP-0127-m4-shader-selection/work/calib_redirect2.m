// Throwaway diagnostic (work/, non-recorded): redirect_red_to_green with
// PERSIG dumps at every stage, to search ALL BOs (not just the pool) for
// where the selector value actually lives / whether the redirect writes
// visibly propagate anywhere else before commit.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <dirent.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int find_pool_cpu(const char *dir, unsigned long long *cpu_out) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    struct dirent *e;
    char best[1200] = {0};
    while ((e = readdir(d)) != NULL) {
        if (strstr(e->d_name, "va58000_")) {
            snprintf(best, sizeof(best), "%s/%s", dir, e->d_name);
        }
    }
    closedir(d);
    if (!best[0]) return 0;
    FILE *f = fopen(best, "r");
    if (!f) return 0;
    char line[8192];
    if (!fgets(line, sizeof(line), f)) { fclose(f); return 0; }
    fclose(f);
    char *p = strstr(line, "cpu=0x");
    if (!p) return 0;
    *cpu_out = strtoull(p + 6, NULL, 16);
    return 1;
}

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
            [cb commit];
            [cb waitUntilCompleted];
            printf("DISCOVER %s status=%ld\n", names[i], (long)cb.status); fflush(stdout);
            kill(getpid(), SIGUSR1); usleep(400000); // dump00,01,02
        }

        // TEST: bind red again (state change from blue), find pool cpu ptr
        // manually via a helper read (we already know pool va from prior
        // dumps: 0x58000, but let's not hardcode the cpu ptr -- instead do
        // the pre-mutate dump now (dump03), then manually poke using a
        // dlopen-free direct read of the LATEST bo file's header to get the
        // cpu ptr, done in-process via a tiny inline parser).
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1);
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:red];
        [enc setVertexBuffer:verts offset:0 atIndex:0];
        [enc setVertexBuffer:params offset:0 atIndex:1];
        [enc setFragmentBuffer:params offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        printf("TEST_PRE_MUTATE\n"); fflush(stdout);
        kill(getpid(), SIGUSR1); usleep(400000); // dump03

        unsigned long long cpu = 0;
        if (!find_pool_cpu("calib2_maps/dump03", &cpu)) {
            fprintf(stderr, "FAIL pool not found\n"); return 2;
        }
        printf("POOL_CPU=0x%llx\n", cpu); fflush(stdout);

        uint32_t *sel_ptr = (uint32_t*)(uintptr_t)(cpu + 8);
        printf("PRE_MUTATE_VALUE=%u (0x%x)\n", *sel_ptr, *sel_ptr); fflush(stdout);
        *sel_ptr = 2176; // S_GREEN discovered above via colour... we know it's 2176 from prior run
        printf("POST_MUTATE_VALUE=%u (0x%x)\n", *sel_ptr, *sel_ptr); fflush(stdout);

        kill(getpid(), SIGUSR1); usleep(400000); // dump04 (post-mutate, pre-commit)

        [cb commit];
        [cb waitUntilCompleted];
        printf("COMMIT status=%ld error=%s\n", (long)cb.status,
               cb.error ? cb.error.localizedDescription.UTF8String : "none");
        unsigned char *px = (unsigned char*)tb.contents + 8*bpr + 8*4;
        printf("RESULT bgra=%02x%02x%02x%02x\n", px[0],px[1],px[2],px[3]);
        fflush(stdout);
        kill(getpid(), SIGUSR1); usleep(400000); // dump05 post-commit
        return 0;
    }
}
