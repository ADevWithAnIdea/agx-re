// uvar.m — parametric OWN Metal DRAW for EXP-G1a.
//   G1-a: vary bound resource counts (textures / samplers / uniform buffers) one at a
//         time -> diff the USC program 0x10000130000 to find the bind-word tags.
//   G1-c: bind system values / FF datums (viewport, [[position]], point coord) -> see
//         which uniform-register slot each lands in via the USC uniform preamble.
//   G1-e: pass a controllable number/order of float4 varyings VS->FS -> capture the
//         varying-linkage BO 0x10000120000 + the USC + code, and (for HW validation)
//         emit one chosen varying to the render target for pixel readback.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader is our own MSL compiled
// at runtime; we print our own resource GPU VAs for correlation. No Apple binary is
// inspected. We document binding-word DESCRIPTOR data (non-copyrightable), not the
// compiler-generated uniform-program ALU (rule 5).
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o uvar uvar.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void die(const char *m){ printf("ARGERR %s\n", m); exit(2); }
static void print_va(const char *label, uint64_t va){
    printf("VA %-12s = 0x%016llx\n", label, (unsigned long long)va);
}

// ---------------------------------------------------------------------------
// Vertex shader: buffer(0)=positions. Emits [[position]] + `nvary` float4 varyings.
// Each varying k gets a distinct, position-dependent gradient value so the FS output
// (when it echoes varying `vout`) is a recognisable pattern for HW validation.
// `vbuf` extra constant buffers at buffer(1..vbuf) fold into position (kept live).
// `usevid`/`useiid`/`usepos` toggle system-value reads (G1-c sysval probing).
// ---------------------------------------------------------------------------
static NSString *vsrc(int nvary,int vbuf,int usevid,int useiid){
    NSMutableString *ins=[NSMutableString string];
    NSMutableString *outs=[NSMutableString string];
    for(int k=0;k<nvary;k++)
        [outs appendFormat:@"  float4 v%d;\n",k];
    NSMutableString *args=[NSMutableString stringWithString:
        @"vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]],\n"
         "                 const device float2* p [[buffer(0)]]"];
    for(int b=0;b<vbuf;b++)
        [args appendFormat:@",\n                 constant float4* ub%d [[buffer(%d)]]",b,b+1];
    [args appendString:@") {\n"];
    NSMutableString *body=[NSMutableString string];
    [body appendString:@"  float2 q = p[vid];\n  float bias=0;\n"];
    if(usevid) [body appendString:@"  bias += float(vid)*1e-30f;\n"];
    if(useiid) [body appendString:@"  bias += float(iid)*1e-30f;\n"];
    for(int b=0;b<vbuf;b++)
        [body appendFormat:@"  bias += ub%d[0].x*1e-30f;\n",b];
    [body appendString:@"  VO o; o.pos=float4(q+float2(bias,bias),0,1);\n"];
    // distinct per-varying gradient: v_k = (q.x*(k+1), q.y*(k+1), (k+1)*0.1, 1)
    for(int k=0;k<nvary;k++)
        [body appendFormat:
          @"  o.v%d=float4(q.x*%d.0f, q.y*%d.0f, %d.0f*0.1f, 1.0f);\n",k,k+1,k+1,k+1];
    [body appendString:@"  return o;\n}\n"];
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]];\n%@ };\n%@%@",
       outs, args, body];
}

// ---------------------------------------------------------------------------
// Fragment shader: reads stage_in (nvary varyings), samples `ftex` textures with
// `fsmp` samplers, reads `fbuf` constant buffers. `vout>=0` -> output that varying
// directly (HW validation of the linkage); else output the summed accumulator.
// ---------------------------------------------------------------------------
static NSString *fsrc(int nvary,int ftex,int fsmp,int fbuf,int vout){
    NSMutableString *ins=[NSMutableString string];
    for(int k=0;k<nvary;k++)
        [ins appendFormat:@"  float4 v%d;\n",k];
    NSMutableString *args=[NSMutableString stringWithString:
        @"fragment float4 f_main(VO in [[stage_in]]"];
    for(int t=0;t<ftex;t++)
        [args appendFormat:@",\n            texture2d<float> t%d [[texture(%d)]]",t,t];
    for(int s=0;s<fsmp;s++)
        [args appendFormat:@",\n            sampler s%d [[sampler(%d)]]",s,s];
    for(int b=0;b<fbuf;b++)
        [args appendFormat:@",\n            constant float4* fb%d [[buffer(%d)]]",b,b+1];
    [args appendString:@") {\n"];
    NSMutableString *body=[NSMutableString string];
    [body appendString:@"  float2 uv = in.pos.xy*0.01f;\n  float4 acc=float4(0);\n"];
    for(int k=0;k<nvary;k++)
        [body appendFormat:@"  acc += in.v%d;\n",k];
    // each texture used via read() (no sampler dependency) -> isolates TEXTURE binding
    for(int t=0;t<ftex;t++)
        [body appendFormat:@"  acc += t%d.read(uint2(0));\n",t];
    // each sampler used on texture 0 -> isolates SAMPLER binding (needs ftex>=1)
    for(int s=0;s<fsmp;s++)
        [body appendFormat:@"  acc += t0.sample(s%d, uv);\n",s];
    for(int b=0;b<fbuf;b++)
        [body appendFormat:@"  acc += fb%d[0];\n",b];
    if(vout>=0 && vout<nvary)
        [body appendFormat:@"  return in.v%d + acc*1e-30f;\n",vout];
    else
        [body appendString:@"  return acc;\n"];
    [body appendString:@"}\n"];
    // rebuild VO struct to match VS
    NSMutableString *outs=[NSMutableString string];
    for(int k=0;k<nvary;k++)
        [outs appendFormat:@"  float4 v%d;\n",k];
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]];\n%@ };\n%@%@",
       outs, args, body];
}

int main(int argc, char **argv){
  @autoreleasepool {
    long W=64,H=64,iters=1;
    int nvary=1,ftex=0,fsmp=0,fbuf=0,vbuf=0,vout=-1,usevid=0,useiid=0,doDump=0;
    for(int i=1;i<argc;i++){
      const char *a=argv[i];
      #define NEXT (i+1<argc?argv[++i]:(die("missing value"),(char*)0))
      if(!strcmp(a,"--w"))W=strtol(NEXT,0,0);
      else if(!strcmp(a,"--h"))H=strtol(NEXT,0,0);
      else if(!strcmp(a,"--vary"))nvary=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--ftex"))ftex=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--fsmp"))fsmp=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--fbuf"))fbuf=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--vbuf"))vbuf=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--vout"))vout=(int)strtol(NEXT,0,0);
      else if(!strcmp(a,"--vid"))usevid=1;
      else if(!strcmp(a,"--iid"))useiid=1;
      else if(!strcmp(a,"--dump"))doDump=1;
      else printf("UNKNOWN ARG %s\n",a);
      #undef NEXT
    }
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG w=%ld h=%ld vary=%d ftex=%d fsmp=%d fbuf=%d vbuf=%d vout=%d vid=%d iid=%d\n",
           W,H,nvary,ftex,fsmp,fbuf,vbuf,vout,usevid,useiid);
    NSError *err=nil;
    NSString *vs=vsrc(nvary,vbuf,usevid,useiid);
    NSString *fs=fsrc(nvary,ftex,fsmp,fbuf,vout);
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    if(!vl){ printf("VS_FAIL %s\n",[[err localizedDescription] UTF8String]); printf("---VS---\n%s\n",[vs UTF8String]); return 1; }
    id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
    if(!fl){ printf("FS_FAIL %s\n",[[err localizedDescription] UTF8String]); printf("---FS---\n%s\n",[fs UTF8String]); return 1; }

    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    // render target (shared so we can read back)
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    NSUInteger bpr=((W*4+255)&~255UL);
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    print_va("rtBuf",[rtb gpuAddress]);

    // vertex buffer (fullscreen tri)
    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float *vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    print_va("vtxBuf",[vb gpuAddress]);

    // input textures
    NSMutableArray *texs=[NSMutableArray array];
    for(int t=0;t<ftex;t++){
      MTLTextureDescriptor *itd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                  width:2 height:2 mipmapped:NO];
      itd.usage=MTLTextureUsageShaderRead; itd.storageMode=MTLStorageModeShared;
      id<MTLTexture> it=[dev newTextureWithDescriptor:itd];
      unsigned char px[16]={ (unsigned char)(t*20),0,0,255, 0,(unsigned char)(t*20),0,255,
                             0,0,(unsigned char)(t*20),255, 255,255,255,255 };
      [it replaceRegion:MTLRegionMake2D(0,0,2,2) mipmapLevel:0 withBytes:px bytesPerRow:8];
      [texs addObject:it];
    }
    // samplers
    NSMutableArray *smps=[NSMutableArray array];
    for(int s=0;s<fsmp;s++){
      MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];
      sd.minFilter = (s&1)?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
      sd.magFilter = sd.minFilter;
      [smps addObject:[dev newSamplerStateWithDescriptor:sd]];
    }
    // uniform (constant) buffers for FS
    NSMutableArray *fbufs=[NSMutableArray array];
    for(int b=0;b<fbuf;b++){
      id<MTLBuffer> ub=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
      ((float*)[ub contents])[0]=0.001f*(b+1);
      [fbufs addObject:ub];
      char lbl[16]; snprintf(lbl,sizeof lbl,"fbuf%d",b); print_va(lbl,[ub gpuAddress]);
    }
    NSMutableArray *vbufs=[NSMutableArray array];
    for(int b=0;b<vbuf;b++){
      id<MTLBuffer> ub=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
      ((float*)[ub contents])[0]=0.002f*(b+1);
      [vbufs addObject:ub];
      char lbl[16]; snprintf(lbl,sizeof lbl,"vbuf%d",b); print_va(lbl,[ub gpuAddress]);
    }

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0; it<iters; it++){
      MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
      rp.colorAttachments[0].texture=target;
      rp.colorAttachments[0].loadAction=MTLLoadActionClear;
      rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
      rp.colorAttachments[0].storeAction=MTLStoreActionStore;
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
      [enc setRenderPipelineState:pso];
      [enc setVertexBuffer:vb offset:0 atIndex:0];
      for(int b=0;b<vbuf;b++)[enc setVertexBuffer:vbufs[b] offset:0 atIndex:b+1];
      for(int t=0;t<ftex;t++)[enc setFragmentTexture:texs[t] atIndex:t];
      for(int s=0;s<fsmp;s++)[enc setFragmentSamplerState:smps[s] atIndex:s];
      for(int b=0;b<fbuf;b++)[enc setFragmentBuffer:fbufs[b] offset:0 atIndex:b+1];
      [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
      [enc endEncoding];
      [cb commit];
      [cb waitUntilCompleted];
      printf("SUBMIT iter=%ld done status=%ld\n", it,(long)[cb status]);
      if(doDump&&it==iters-1){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    }
    // read back centre pixel for HW validation
    unsigned char *pxb=(unsigned char*)malloc(bpr*H);
    [target getBytes:pxb bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0];
    for(long yy=0; yy<H; yy+= (H>1?H/2:1)){
      for(long xx=0; xx<W; xx+= (W>1?W/2:1)){
        unsigned char *p=pxb+yy*bpr+xx*4;
        printf("PIXEL %ld %ld bgra=%02x%02x%02x%02x rgba=%.3f,%.3f,%.3f,%.3f\n",
               xx,yy,p[0],p[1],p[2],p[3],p[2]/255.0,p[1]/255.0,p[0]/255.0,p[3]/255.0);
      }
    }
    free(pxb);
    return 0;
  }
}
