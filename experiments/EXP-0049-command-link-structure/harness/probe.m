// EXP-0049 authored public-Metal command-link structure probe.
// No command memory or Apple-authored code is read or modified by this program.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef enum { ENGINE_CDM, ENGINE_VDM } Engine;
typedef enum {
    V_CDM_DIRECT, V_CDM_INDIRECT, V_CDM_ENCODER1, V_CDM_PAD7,
    V_VDM_STATE1, V_VDM_STABLE, V_VDM_PASS1, V_VDM_PAD7,
} Variant;

typedef struct {
    Variant variant;
    Engine engine;
    const char *name;
    long count;
    int dump;
} Config;

static int parse_variant(const char *s, Config *cfg) {
    cfg->name = s;
    if (!strcmp(s,"cdm-direct")) cfg->variant=V_CDM_DIRECT,cfg->engine=ENGINE_CDM;
    else if (!strcmp(s,"cdm-indirect")) cfg->variant=V_CDM_INDIRECT,cfg->engine=ENGINE_CDM;
    else if (!strcmp(s,"cdm-encoder1")) cfg->variant=V_CDM_ENCODER1,cfg->engine=ENGINE_CDM;
    else if (!strcmp(s,"cdm-pad7")) cfg->variant=V_CDM_PAD7,cfg->engine=ENGINE_CDM;
    else if (!strcmp(s,"vdm-state1")) cfg->variant=V_VDM_STATE1,cfg->engine=ENGINE_VDM;
    else if (!strcmp(s,"vdm-stable")) cfg->variant=V_VDM_STABLE,cfg->engine=ENGINE_VDM;
    else if (!strcmp(s,"vdm-pass1")) cfg->variant=V_VDM_PASS1,cfg->engine=ENGINE_VDM;
    else if (!strcmp(s,"vdm-pad7")) cfg->variant=V_VDM_PAD7,cfg->engine=ENGINE_VDM;
    else return 0;
    return 1;
}

static NSString *shader_source(void) {
    return @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "kernel void kernel_a(device uint *out [[buffer(0)]], constant uint &tag [[buffer(1)]], uint i [[thread_position_in_grid]]) { out[i]=tag+i; }\n"
            "kernel void kernel_b(device uint *out [[buffer(0)]], constant uint &tag [[buffer(1)]], uint i [[thread_position_in_grid]]) { out[i]=(tag^0x10000000u)+i; }\n"
            "struct VOut { float4 position [[position]]; };\n"
            "vertex VOut vertex_main(uint vid [[vertex_id]], const device float2 *p [[buffer(0)]]) { VOut o; o.position=float4(p[vid%3],0,1); return o; }\n"
            "fragment float4 fragment_a(constant float4 &c [[buffer(0)]]) { return c; }\n"
            "fragment float4 fragment_b(constant float4 &c [[buffer(0)]]) { return float4(c.b,c.r,c.g,c.a); }\n";
}

static id<MTLComputePipelineState> make_compute(id<MTLDevice> dev, NSString *name, NSError **err) {
    id<MTLLibrary> lib=[dev newLibraryWithSource:shader_source() options:nil error:err];
    if(!lib)return nil;id<MTLFunction> fn=[lib newFunctionWithName:name];
    return fn?[dev newComputePipelineStateWithFunction:fn error:err]:nil;
}

static id<MTLRenderPipelineState> make_render(id<MTLDevice> dev, NSString *name, NSError **err) {
    id<MTLLibrary> lib=[dev newLibraryWithSource:shader_source() options:nil error:err];
    if(!lib)return nil;MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"vertex_main"];
    pd.fragmentFunction=[lib newFunctionWithName:name];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    return [dev newRenderPipelineStateWithDescriptor:pd error:err];
}

static uint64_t fnv1a(const uint8_t *p,size_t bpr,size_t w,size_t h) {
    uint64_t v=1469598103934665603ULL;
    for(size_t y=0;y<h;++y)for(size_t x=0;x<w*4;++x){v^=p[y*bpr+x];v*=1099511628211ULL;}
    return v;
}

static void set_dynamic_state(id<MTLRenderCommandEncoder> enc,
                              id<MTLRenderPipelineState> pa,
                              id<MTLRenderPipelineState> pb,
                              id<MTLBuffer> vertices,long seq,int dynamic) {
    int use_b=dynamic&&(seq&1);
    [enc setRenderPipelineState:(use_b?pb:pa)];
    [enc setVertexBuffer:vertices offset:0 atIndex:0];
    uint8_t r=32+(uint8_t)((seq&7)*16),g=48+(uint8_t)(((seq+2)&7)*16),b=64+(uint8_t)(((seq+4)&7)*16);
    float color[4]={r/255.0f,g/255.0f,b/255.0f,1.0f};
    if(!dynamic){color[0]=0.25f;color[1]=0.5f;color[2]=0.75f;}
    [enc setFragmentBytes:color length:sizeof(color) atIndex:0];
    double inset=use_b?1.0:0.0;MTLViewport vp={inset,inset,64-inset,64-inset,0,1};
    [enc setViewport:vp];
}

static MTLRenderPassDescriptor *make_pass(id<MTLTexture> target,int first) {
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=first?MTLLoadActionClear:MTLLoadActionLoad;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
    return rp;
}

static int run_compute(Config cfg,id<MTLCommandQueue> q,
                       id<MTLComputePipelineState> pa,id<MTLComputePipelineState> pb,
                       id<MTLBuffer> output,id<MTLBuffer> indirect) {
    id<MTLCommandBuffer> cb=[q commandBuffer];id<MTLComputeCommandEncoder> enc=nil;
    int indirect_mode=cfg.variant==V_CDM_INDIRECT;
    int split=cfg.variant==V_CDM_ENCODER1;
    for(long i=0;i<cfg.count;++i){
        if(!enc)enc=[cb computeCommandEncoder];
        int use_b=indirect_mode&&(i&1);
        [enc setComputePipelineState:(use_b?pb:pa)];
        [enc setBuffer:output offset:0 atIndex:0];
        uint32_t tag=0xa0000000u|((uint32_t)i&0xffffu);
        [enc setBytes:&tag length:4 atIndex:1];
        if(indirect_mode)[enc dispatchThreadgroupsWithIndirectBuffer:indirect indirectBufferOffset:0
                                                  threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        else [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
        if(split){[enc endEncoding];enc=nil;}
    }
    if(enc)[enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("COMMAND status=%ld error=%s\n",(long)cb.status,cb.error?[[cb.error localizedDescription]UTF8String]:"none");
    uint32_t tag=0xa0000000u|((uint32_t)(cfg.count-1)&0xffffu);
    if(indirect_mode&&((cfg.count-1)&1))tag^=0x10000000u;
    uint32_t *out=output.contents;int ok=cb.status==MTLCommandBufferStatusCompleted&&!cb.error&&out[0]==tag&&out[63]==tag+63;
    printf("READBACK compute0=0x%08x compute63=0x%08x expected0=0x%08x expected63=0x%08x\n",out[0],out[63],tag,tag+63);
    return ok;
}

static int run_render(Config cfg,id<MTLCommandQueue> q,
                      id<MTLRenderPipelineState> pa,id<MTLRenderPipelineState> pb,
                      id<MTLBuffer> vertices,id<MTLTexture> target,id<MTLBuffer> render_out) {
    id<MTLCommandBuffer> cb=[q commandBuffer];id<MTLRenderCommandEncoder> enc=nil;
    int dynamic=cfg.variant==V_VDM_STATE1||cfg.variant==V_VDM_PAD7;
    int pass1=cfg.variant==V_VDM_PASS1;
    for(long i=0;i<cfg.count;++i){
        if(!enc){enc=[cb renderCommandEncoderWithDescriptor:make_pass(target,i==0)];set_dynamic_state(enc,pa,pb,vertices,i,dynamic);}
        else if(dynamic)set_dynamic_state(enc,pa,pb,vertices,i,1);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:(i&1)?6:3 instanceCount:1];
        if(pass1){[enc endEncoding];enc=nil;}
    }
    if(enc)[enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("COMMAND status=%ld error=%s\n",(long)cb.status,cb.error?[[cb.error localizedDescription]UTF8String]:"none");
    const size_t bpr=256;uint8_t *p=render_out.contents;uint8_t *center=p+32*bpr+32*4;
    uint8_t want[4]={0xbf,0x80,0x40,0xff};
    if(dynamic){long s=cfg.count-1;uint8_t r=32+(uint8_t)((s&7)*16),g=48+(uint8_t)(((s+2)&7)*16),b=64+(uint8_t)(((s+4)&7)*16);
        if(s&1){want[0]=g;want[1]=r;want[2]=b;}else{want[0]=b;want[1]=g;want[2]=r;}}
    int ok=cb.status==MTLCommandBufferStatusCompleted&&!cb.error&&!memcmp(center,want,4);
    printf("READBACK center_bgra=%02x%02x%02x%02x expected=%02x%02x%02x%02x fnv=0x%016llx\n",
           center[0],center[1],center[2],center[3],want[0],want[1],want[2],want[3],
           (unsigned long long)fnv1a(p,bpr,64,64));
    return ok;
}

int main(int argc,char **argv){
    @autoreleasepool{
        Config cfg={.variant=V_CDM_DIRECT,.engine=ENGINE_CDM,.name="cdm-direct",.count=1,.dump=0};
        for(int i=1;i<argc;++i){
            if(!strcmp(argv[i],"--variant")&&i+1<argc){if(!parse_variant(argv[++i],&cfg)){fprintf(stderr,"bad variant\n");return 2;}}
            else if(!strcmp(argv[i],"--count")&&i+1<argc)cfg.count=strtol(argv[++i],NULL,0);
            else if(!strcmp(argv[i],"--dump"))cfg.dump=1;
            else{fprintf(stderr,"usage: %s --variant NAME --count N [--dump]\n",argv[0]);return 2;}
        }
        if(cfg.count<1||cfg.count>4096){fprintf(stderr,"count out of range\n");return 2;}
        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();if(!dev)return 3;
        printf("DEVICE %s\nVARIANT name=%s engine=%s count=%ld mutation=0\n",[[dev name]UTF8String],cfg.name,cfg.engine==ENGINE_CDM?"cdm":"vdm",cfg.count);
        NSMutableArray *padding=[NSMutableArray array];
        if(cfg.variant==V_CDM_PAD7||cfg.variant==V_VDM_PAD7)for(int i=0;i<7;++i){id<MTLBuffer>b=[dev newBufferWithLength:0x3000 options:MTLResourceStorageModeShared];memset(b.contents,0x40+i,0x3000);[padding addObject:b];}
        NSError *err=nil;
        id<MTLComputePipelineState>ca=make_compute(dev,@"kernel_a",&err),cb=make_compute(dev,@"kernel_b",&err);
        id<MTLRenderPipelineState>ra=make_render(dev,@"fragment_a",&err),rb=make_render(dev,@"fragment_b",&err);
        if(!ca||!cb||!ra||!rb){fprintf(stderr,"PIPELINE_FAIL %s\n",err?[[err localizedDescription]UTF8String]:"unknown");return 4;}
        id<MTLBuffer>output=[dev newBufferWithLength:256 options:MTLResourceStorageModeShared];
        id<MTLBuffer>vertices=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
        float pos[6]={-1,-1,3,-1,-1,3};memcpy(vertices.contents,pos,sizeof(pos));
        id<MTLBuffer>render_out=[dev newBufferWithLength:256*64 options:MTLResourceStorageModeShared];memset(render_out.contents,0,256*64);
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
        id<MTLTexture>target=[render_out newTextureWithDescriptor:td offset:0 bytesPerRow:256];
        id<MTLBuffer>indirect=[dev newBufferWithLength:0x100 options:MTLResourceStorageModeShared];
        uint32_t args[3]={2,1,1};memcpy(indirect.contents,args,sizeof(args));
        printf("USER_VA output=0x%llx vertices=0x%llx render=0x%llx indirect=0x%llx\n",
               (unsigned long long)output.gpuAddress,(unsigned long long)vertices.gpuAddress,
               (unsigned long long)render_out.gpuAddress,(unsigned long long)indirect.gpuAddress);
        id<MTLCommandQueue>q=[dev newCommandQueue];if(!q||!target)return 5;
        int ok=cfg.engine==ENGINE_CDM?run_compute(cfg,q,ca,cb,output,indirect):run_render(cfg,q,ra,rb,vertices,target,render_out);
        printf("RESULT ok=%d\n",ok);fflush(stdout);
        if(cfg.dump){kill(getpid(),SIGUSR1);usleep(500000);}
        return ok?0:6;
    }
}
