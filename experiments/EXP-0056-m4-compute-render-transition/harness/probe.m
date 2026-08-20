/* EXP-0056 authored public-Metal dependency probe. */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef enum { CPU_RENDER, COMPUTE_ONLY, COMPUTE_RENDER } Variant;
typedef struct { Variant variant; const char *name; int pad; } Config;
typedef struct { float position[3][2]; float color[4]; } Scene;

static int parse(int argc, char **argv, Config *c) {
    c->variant=COMPUTE_RENDER; c->name="compute-render"; c->pad=0;
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--variant") && i+1<argc) {
            c->name=argv[++i];
            if (!strcmp(c->name,"cpu-render")) c->variant=CPU_RENDER;
            else if (!strcmp(c->name,"compute-only")) c->variant=COMPUTE_ONLY;
            else if (!strcmp(c->name,"compute-render")) c->variant=COMPUTE_RENDER;
            else return 0;
        } else if (!strcmp(argv[i],"--pad64k")) c->pad=1;
        else if (!strcmp(argv[i],"--dump")) continue;
        else return 0;
    }
    return 1;
}

static NSString *source(void) {
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct Scene { float2 p[3]; float4 c; };\n"
    "kernel void make_scene(device Scene *s [[buffer(0)]], uint id [[thread_position_in_grid]]) {"
    " if(id==0){s->p[0]=float2(-1,-1);s->p[1]=float2(3,-1);s->p[2]=float2(-1,3);s->c=float4(0.25,0.5,0.75,1);}}\n"
    "struct V { float4 p [[position]]; float4 c; };\n"
    "vertex V vert(uint id [[vertex_id]], const device Scene *s [[buffer(0)]]) { V o;o.p=float4(s->p[id],0,1);o.c=s->c;return o;}\n"
    "fragment float4 frag(V in [[stage_in]]) {return in.c;}\n";
}

static uint64_t fnv(const uint8_t *p, size_t n) { uint64_t h=1469598103934665603ULL; for(size_t i=0;i<n;i++){h^=p[i];h*=1099511628211ULL;}return h; }
static void fill(Scene *s) { float p[3][2]={{-1,-1},{3,-1},{-1,3}}; memcpy(s->position,p,sizeof(p)); float c[4]={.25f,.5f,.75f,1};memcpy(s->color,c,sizeof(c)); }

int main(int argc,char **argv) { @autoreleasepool {
    Config cfg; if(!parse(argc,argv,&cfg)){fprintf(stderr,"usage: --variant cpu-render|compute-only|compute-render [--pad64k] --dump\n");return 2;}
    id<MTLDevice>d=MTLCreateSystemDefaultDevice(); if(!d)return 3;
    NSMutableArray *pad=[NSMutableArray array]; if(cfg.pad){id<MTLBuffer>b=[d newBufferWithLength:65536 options:MTLResourceStorageModeShared];memset(b.contents,0xa5,65536);[pad addObject:b];}
    NSError *e=nil; id<MTLLibrary>l=[d newLibraryWithSource:source() options:nil error:&e];
    id<MTLComputePipelineState> cp=[d newComputePipelineStateWithFunction:[l newFunctionWithName:@"make_scene"] error:&e];
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[l newFunctionWithName:@"vert"];pd.fragmentFunction=[l newFunctionWithName:@"frag"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState>rp=[d newRenderPipelineStateWithDescriptor:pd error:&e];if(!cp||!rp){fprintf(stderr,"PIPELINE_FAIL %s\n",e.localizedDescription.UTF8String);return 4;}
    id<MTLBuffer>scene=[d newBufferWithLength:sizeof(Scene) options:MTLResourceStorageModeShared];memset(scene.contents,0,sizeof(Scene));if(cfg.variant==CPU_RENDER)fill(scene.contents);
    id<MTLBuffer>out=[d newBufferWithLength:256*16 options:MTLResourceStorageModeShared];memset(out.contents,0,256*16);
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;id<MTLTexture>tex=[out newTextureWithDescriptor:td offset:0 bytesPerRow:256];
    id<MTLCommandBuffer>cb=[[d newCommandQueue] commandBuffer];
    if(cfg.variant!=CPU_RENDER){id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];[ce setComputePipelineState:cp];[ce setBuffer:scene offset:0 atIndex:0];[ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[ce endEncoding];}
    if(cfg.variant!=COMPUTE_ONLY){MTLRenderPassDescriptor *rd=[MTLRenderPassDescriptor new];rd.colorAttachments[0].texture=tex;rd.colorAttachments[0].loadAction=MTLLoadActionClear;rd.colorAttachments[0].storeAction=MTLStoreActionStore;rd.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);id<MTLRenderCommandEncoder>re=[cb renderCommandEncoderWithDescriptor:rd];[re setRenderPipelineState:rp];[re setVertexBuffer:scene offset:0 atIndex:0];[re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[re endEncoding];}
    [cb commit];[cb waitUntilCompleted]; uint8_t *b=out.contents; int ok=cb.status==MTLCommandBufferStatusCompleted&&!cb.error;
    if(cfg.variant==COMPUTE_ONLY){Scene *s=scene.contents;ok&=s->color[0]==.25f&&s->position[2][1]==3.f;printf("READBACK scene=%g,%g,%g\n",s->color[0],s->color[1],s->color[2]);}
    else {uint8_t *q=b+8*256+8*4;ok&=!memcmp(q,(uint8_t[]){0xbf,0x80,0x40,0xff},4);printf("READBACK center=%02x%02x%02x%02x fnv=%016llx\n",q[0],q[1],q[2],q[3],(unsigned long long)fnv(b,256*16));}
    printf("DEVICE %s\nVARIANT name=%s schedule=%s dependency=%d\nCOMMAND status=%ld error=%s\nRESULT ok=%d\n",d.name.UTF8String,cfg.name,cfg.pad?"pad64k":"plain",cfg.variant==COMPUTE_RENDER,(long)cb.status,cb.error?cb.error.localizedDescription.UTF8String:"none",ok);fflush(stdout);
    kill(getpid(),SIGUSR1);usleep(300000);return ok?0:6;
} }
