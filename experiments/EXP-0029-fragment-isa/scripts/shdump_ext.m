// shdump_ext.m — EXP-0029 extension of tools/shdump/shdump.m (OUR OWN tool).
// Adds --ncolor N (N colour attachments, all colorFormat), --cfmt i=FMT (per-
// attachment format), and --depth-format D (depth attachment) so MRT / [[depth]]
// / imageblock / raster-order-group fragment pipelines compile & serialize.
// Clean-room: public Metal API on OUR OWN MSL only; no Apple binary inspected.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif
static void die(const char *m, NSError *e){ fprintf(stderr,"shdump_ext: %s%s%s\n",m,e?": ":"",e?[[e localizedDescription] UTF8String]:""); exit(1);}
enum { OPT_VERTEX=200, OPT_FRAGMENT, OPT_CFMT, OPT_NCOLOR, OPT_DEPTH, OPT_NOFAST };
static const struct option L[]={
 {"output",1,0,'o'},{"vertex",1,0,OPT_VERTEX},{"fragment",1,0,OPT_FRAGMENT},
 {"cfmt",1,0,OPT_CFMT},{"ncolor",1,0,OPT_NCOLOR},{"depth-format",1,0,OPT_DEPTH},
 {"no-fast-math",0,0,OPT_NOFAST},{0,0,0,0}};
int main(int argc,char**argv){@autoreleasepool{
 const char*out=0,*vn=0,*fn=0; int ncolor=1; NSUInteger cfmt[8]; for(int i=0;i<8;i++)cfmt[i]=MTLPixelFormatBGRA8Unorm;
 NSUInteger depthFmt=MTLPixelFormatInvalid; BOOL fast=YES; int c;
 while((c=getopt_long(argc,argv,"o:",L,0))>0){switch(c){
  case 'o':out=optarg;break; case OPT_VERTEX:vn=optarg;break; case OPT_FRAGMENT:fn=optarg;break;
  case OPT_NCOLOR:ncolor=atoi(optarg);break; case OPT_DEPTH:depthFmt=(NSUInteger)strtoul(optarg,0,0);break;
  case OPT_NOFAST:fast=NO;break;
  case OPT_CFMT:{int i;NSUInteger f;if(sscanf(optarg,"%d=%lu",&i,&f)==2&&i>=0&&i<8)cfmt[i]=f;break;}
  default:die("bad arg",0);} }
 if(!out||optind>=argc)die("usage: -o out.bin --vertex v --fragment f [--ncolor N] [--cfmt i=FMT] [--depth-format D] src.metal",0);
 NSError*e=0; NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]] encoding:NSUTF8StringEncoding error:&e];
 if(!src)die("read src",e);
 id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); if(!dev)die("no device",0);
 fprintf(stderr,"shdump_ext: device=%s\n",[[dev name]UTF8String]);
 MTLCompileOptions*co=[MTLCompileOptions new]; [co setFastMathEnabled:fast];
 id<MTLLibrary>lib=[dev newLibraryWithSource:src options:co error:&e]; if(!lib)die("compile",e);
 id<MTLFunction>vf=[lib newFunctionWithName:[NSString stringWithUTF8String:vn]];
 id<MTLFunction>ff=[lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
 if(!vf||!ff)die("function missing",0);
 MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
 id<MTLBinaryArchive>arc=[dev newBinaryArchiveWithDescriptor:ad error:&e]; if(!arc)die("archive",e);
 MTLRenderPipelineDescriptor*rd=[MTLRenderPipelineDescriptor new];
 [rd setVertexFunction:vf]; [rd setFragmentFunction:ff];
 for(int i=0;i<ncolor;i++) rd.colorAttachments[i].pixelFormat=(MTLPixelFormat)cfmt[i];
 if(depthFmt!=MTLPixelFormatInvalid) rd.depthAttachmentPixelFormat=(MTLPixelFormat)depthFmt;
 id<MTLRenderPipelineState>ps=[dev newRenderPipelineStateWithDescriptor:rd error:&e];
 if(!ps)die("pipeline",e);
 fprintf(stderr,"shdump_ext: pipeline OK ncolor=%d depth=%lu\n",ncolor,(unsigned long)depthFmt);
 if(![arc addRenderPipelineFunctionsWithDescriptor:rd error:&e])die("addRenderPipeline",e);
 if(![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]] error:&e])die("serialize",e);
 fprintf(stderr,"shdump_ext: wrote %s\n",out); return 0;
}}
