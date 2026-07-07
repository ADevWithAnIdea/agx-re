// texrun.m -- clean-room OWN-SHADER compute runner WITH texture + sampler binding.
// Extends the agxrun pattern (load a possibly-spliced binary archive, force it to
// run from the archive) with N bound textures and M bound samplers, so we can
// falsify the texture-sample encoding (tex-slot / sampler-slot / variant bytes)
// on the compute path with clean numeric read-back.
//
// CLEAN-ROOM: our own code, public Metal API, on our own compiled shader bytes.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o texrun texrun.m
//
// Usage:
//   texrun --archive A.bin --source S.metal --function k --grid N --tg T \
//          --tex i=W,H,r,g,b,a,r,g,b,a,...   (rgba8unorm texels, row-major)
//          --samp i=nearest|linear
//          --out IDX=NBYTES
//          [--rwtex i=W,H]   (a writable rgba32float texture, zero-init, dumped after)
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit(const char*s){printf("STATUS %s\n",s);}
static void fail(const char*s,const char*m,NSError*e){emit(s);if(e)printf("ERROR %s: %s\n",m,[[e localizedDescription]UTF8String]);else if(m)printf("ERROR %s\n",m);fflush(stdout);exit(1);}

enum{OPT_NFM=128,OPT_TEX,OPT_SAMP,OPT_RWTEX};
static const struct option L[]={
 {"archive",1,0,'a'},{"source",1,0,'s'},{"function",1,0,'f'},{"grid",1,0,'g'},
 {"tg",1,0,'t'},{"buf",1,0,'b'},{"out",1,0,'o'},{"no-fast-math",0,0,OPT_NFM},
 {"tex",1,0,OPT_TEX},{"samp",1,0,OPT_SAMP},{"rwtex",1,0,OPT_RWTEX},{0,0,0,0}};

int main(int argc,char**argv){@autoreleasepool{
 const char*arch=0,*srcp=0,*fnn=0; long grid=1,tg=1; BOOL fm=YES;
 int inI[64],nin=0; const char*inP[64];
 int outI[64]; long outN[64]; int nout=0;
 // textures
 struct{int idx,w,h;unsigned char*px;}texs[16]; int ntex=0;
 struct{int idx;BOOL lin;}samps[16]; int nsamp=0;
 struct{int idx,w,h;}rwt[8]; int nrw=0;
 int c;
 while((c=getopt_long(argc,argv,"a:s:f:g:t:b:o:",L,0))>0){switch(c){
  case 'a':arch=optarg;break; case 's':srcp=optarg;break; case 'f':fnn=optarg;break;
  case 'g':grid=strtol(optarg,0,0);break; case 't':tg=strtol(optarg,0,0);break;
  case OPT_NFM:fm=NO;break;
  case 'b':{char*e=strchr(optarg,'=');*e=0;inI[nin]=(int)strtol(optarg,0,0);inP[nin]=e+1;nin++;break;}
  case 'o':{char*e=strchr(optarg,'=');*e=0;outI[nout]=(int)strtol(optarg,0,0);outN[nout]=strtol(e+1,0,0);nout++;break;}
  case OPT_TEX:{ // i=W,H,r,g,b,a,...
    char*e=strchr(optarg,'=');*e=0; int idx=(int)strtol(optarg,0,0);
    char*p=e+1; int w=atoi(strsep(&p,",")); int h=atoi(strsep(&p,","));
    unsigned char*px=calloc(w*h*4,1); int k=0;
    char*tok; while((tok=strsep(&p,","))&&k<w*h*4){px[k++]=(unsigned char)atoi(tok);}
    texs[ntex].idx=idx;texs[ntex].w=w;texs[ntex].h=h;texs[ntex].px=px;ntex++;break;}
  case OPT_SAMP:{char*e=strchr(optarg,'=');*e=0;samps[nsamp].idx=(int)strtol(optarg,0,0);
    samps[nsamp].lin=(strstr(e+1,"lin")!=0);nsamp++;break;}
  case OPT_RWTEX:{char*e=strchr(optarg,'=');*e=0;int idx=(int)strtol(optarg,0,0);
    char*p=e+1;rwt[nrw].idx=idx;rwt[nrw].w=atoi(strsep(&p,","));rwt[nrw].h=atoi(strsep(&p,","));nrw++;break;}
 }}
 if(!arch||!srcp||!fnn)fail("PIPELINE_FAIL","need --archive --source --function",0);
 id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); if(!dev)fail("PIPELINE_FAIL","no device",0);
 printf("DEVICE %s\n",[[dev name]UTF8String]);
 NSError*err=0;
 NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp] encoding:NSUTF8StringEncoding error:&err];
 if(!src)fail("COMPILE_FAIL","read source",err);
 MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:fm];
 id<MTLLibrary>lib=[dev newLibraryWithSource:src options:co error:&err]; if(!lib)fail("COMPILE_FAIL","compile",err);
 id<MTLFunction>fn=[lib newFunctionWithName:[NSString stringWithUTF8String:fnn]]; if(!fn)fail("FUNCTION_MISSING","fn",0);
 MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];[ad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:arch]]];
 id<MTLBinaryArchive>ar=[dev newBinaryArchiveWithDescriptor:ad error:&err]; if(!ar)fail("ARCHIVE_FAIL","archive",err);
 MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];[pd setComputeFunction:fn];[pd setBinaryArchives:@[ar]];
 id<MTLComputePipelineState>pso=[dev newComputePipelineStateWithDescriptor:pd options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&err];
 if(!pso)fail("PIPELINE_MISS","pso",err);
 printf("PIPELINE_SOURCE archive\n");
 id<MTLCommandQueue>q=[dev newCommandQueue];
 id<MTLBuffer>bufs[64]={0};
 for(int i=0;i<nin;i++){NSData*d=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:inP[i]]];
   bufs[inI[i]]=[dev newBufferWithBytes:[d bytes] length:[d length] options:MTLResourceStorageModeShared];}
 for(int i=0;i<nout;i++){if(!bufs[outI[i]])bufs[outI[i]]=[dev newBufferWithLength:outN[i] options:MTLResourceStorageModeShared];}
 // textures (rgba8unorm)
 id<MTLTexture>tx[16]={0};
 for(int i=0;i<ntex;i++){
   MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:texs[i].w height:texs[i].h mipmapped:NO];
   [td setUsage:MTLTextureUsageShaderRead];
   id<MTLTexture>t=[dev newTextureWithDescriptor:td];
   [t replaceRegion:MTLRegionMake2D(0,0,texs[i].w,texs[i].h) mipmapLevel:0 withBytes:texs[i].px bytesPerRow:texs[i].w*4];
   tx[texs[i].idx]=t;}
 // rw textures (rgba32float, zero)
 id<MTLTexture>rwtx[16]={0};
 for(int i=0;i<nrw;i++){
   MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:rwt[i].w height:rwt[i].h mipmapped:NO];
   [td setUsage:MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite];
   id<MTLTexture>t=[dev newTextureWithDescriptor:td];
   tx[rwt[i].idx]=t; rwtx[rwt[i].idx]=t;}
 // samplers
 id<MTLSamplerState>sm[16]={0};
 for(int i=0;i<nsamp;i++){
   MTLSamplerDescriptor*sd=[MTLSamplerDescriptor new];
   MTLSamplerMinMagFilter f=samps[i].lin?MTLSamplerMinMagFilterLinear:MTLSamplerMinMagFilterNearest;
   [sd setMinFilter:f];[sd setMagFilter:f];
   [sd setSAddressMode:MTLSamplerAddressModeClampToEdge];[sd setTAddressMode:MTLSamplerAddressModeClampToEdge];
   sm[samps[i].idx]=[dev newSamplerStateWithDescriptor:sd];}
 id<MTLCommandBuffer>cb=[q commandBuffer]; id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
 [en setComputePipelineState:pso];
 for(int i=0;i<64;i++)if(bufs[i])[en setBuffer:bufs[i] offset:0 atIndex:i];
 for(int i=0;i<16;i++)if(tx[i])[en setTexture:tx[i] atIndex:i];
 for(int i=0;i<16;i++)if(sm[i])[en setSamplerState:sm[i] atIndex:i];
 [en dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
 [en endEncoding];[cb commit];[cb waitUntilCompleted];
 if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","cmdbuf",[cb error]);
 printf("GPUTIME_NS %llu\n",(unsigned long long)(([cb GPUEndTime]-[cb GPUStartTime])*1e9));
 static const char H[]="0123456789abcdef";
 for(int i=0;i<nout;i++){int idx=outI[i];const unsigned char*p=[bufs[idx]contents];long n=outN[i];
   char*hx=malloc(n*2+1);for(long j=0;j<n;j++){hx[j*2]=H[p[j]>>4];hx[j*2+1]=H[p[j]&0xf];}hx[n*2]=0;
   printf("OUT %d %s\n",idx,hx);free(hx);}
 // dump rw textures as float rgba per texel
 for(int i=0;i<nrw;i++){int idx=rwt[i].idx;int w=rwt[i].w,h=rwt[i].h;
   float*buf=malloc(w*h*4*sizeof(float));
   [rwtx[idx] getBytes:buf bytesPerRow:w*4*sizeof(float) fromRegion:MTLRegionMake2D(0,0,w,h) mipmapLevel:0];
   printf("RWTEX %d",idx);for(int k=0;k<w*h*4;k++)printf(" %g",buf[k]);printf("\n");free(buf);}
 emit("OK");fflush(stdout);return 0;
}}
