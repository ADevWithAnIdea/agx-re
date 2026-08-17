/* Exact negative control for EXP-0048's blend case. */
#define main exp0048_matrix_main_not_called
#include "probe.m"
#undef main

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *source_out = NULL; int do_dump = 0;
        for (int i=1; i<argc; ++i) {
            if (!strcmp(argv[i],"--source-out") && i+1<argc) source_out=argv[++i];
            else if (!strcmp(argv[i],"--dump")) do_dump=1;
            else { fprintf(stderr,"unknown/missing argument: %s\n",argv[i]); return 2; }
        }
        if (!source_out) { fprintf(stderr,"--source-out required\n"); return 2; }
        Case c={"rgba8-load-store-draw-control",K_RGBA8,K_RGBA8,
                MTLLoadActionLoad,MTLStoreActionStore,1,0,0};
        const NSUInteger W=32,H=32,BPR=256,LEN=0x4000;
        id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if(!dev)return 3;
        printf("DEVICE %s\nCASE %s fmt0=rgba8 fmt1=rgba8 load=%lu store=%lu draw=1 blend=0 atomic=0 w=32 h=32 bpr=256\n",
               [[dev name] UTF8String],c.name,(unsigned long)c.load,(unsigned long)c.store);
        NSString *vsrc=vertex_source(),*fsrc=fragment_source(&c);
        NSString *combined=[NSString stringWithFormat:@"// VERTEX\n%@\n// FRAGMENT\n%@",vsrc,fsrc];
        NSError *err=nil;
        if(![combined writeToFile:[NSString stringWithUTF8String:source_out] atomically:NO
                         encoding:NSUTF8StringEncoding error:&err])return 4;
        id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc options:nil error:&err];
        id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc options:nil error:&err];
        if(!vl||!fl){fprintf(stderr,"SHADER_FAIL %s\n",[[err localizedDescription] UTF8String]);return 5;}
        MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
        pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
        pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
        pd.colorAttachments[1].pixelFormat=MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if(!pso){fprintf(stderr,"PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]);return 6;}
        id<MTLBuffer> counter=[dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        id<MTLBuffer> b0=[dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        id<MTLBuffer> b1=[dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        memset([counter contents],0,LEN);
        init_surface([b0 contents],LEN,BPR,W,H,K_RGBA8,0);
        init_surface([b1 contents],LEN,BPR,W,H,K_RGBA8,1);
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
        id<MTLTexture> t0=[b0 newTextureWithDescriptor:td offset:0 bytesPerRow:BPR];
        id<MTLTexture> t1=[b1 newTextureWithDescriptor:td offset:0 bytesPerRow:BPR];
        printf("USER_VA counter=0x%llx rt0=0x%llx rt1=0x%llx\n",(unsigned long long)[counter gpuAddress],(unsigned long long)[b0 gpuAddress],(unsigned long long)[b1 gpuAddress]);
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture=t0;rp.colorAttachments[1].texture=t1;
        for(NSUInteger i=0;i<2;++i){rp.colorAttachments[i].loadAction=MTLLoadActionLoad;rp.colorAttachments[i].storeAction=MTLStoreActionStore;}
        id<MTLCommandQueue> q=[dev newCommandQueue];id<MTLCommandBuffer> cb=[q commandBuffer];
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];MTLViewport vp={0,0,W,H,0,1};[enc setViewport:vp];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[enc endEncoding];
        [cb commit];[cb waitUntilCompleted];
        printf("COMMAND status=%ld error=%s\n",(long)[cb status],[cb error]?[[[cb error] localizedDescription] UTF8String]:"none");
        if([cb status]!=MTLCommandBufferStatusCompleted||[cb error])return 7;
        uint8_t*p0=[b0 contents],*p1=[b1 contents];print_first("rt0",p0);print_first("rt1",p1);
        printf("RESULT rt0_fnv=0x%016llx rt1_fnv=0x%016llx rt0_uniform=%d rt1_uniform=%d counter=%u\n",
               (unsigned long long)fnv1a_active(p0,BPR,W,H),(unsigned long long)fnv1a_active(p1,BPR,W,H),
               uniform_active(p0,BPR,W,H),uniform_active(p1,BPR,W,H),*(uint32_t*)[counter contents]);
        fflush(stdout);if(do_dump){kill(getpid(),SIGUSR1);usleep(500000);}return 0;
    }
}
