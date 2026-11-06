#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "i_sound.h"
unsigned char genmidi[8+175*36], fx[8+256];
int W_CheckNumForName(char *n){return !strcmp(n,"GENMIDI")?0:!strcmp(n,"dstest")?1:-1;}
int W_GetNumForName(char *n){return W_CheckNumForName(n);}
int W_LumpLength(unsigned n){return n?sizeof(fx):sizeof(genmidi);}
void *W_CacheLumpNum(int n,int tag){(void)tag;return n?fx:genmidi;}
extern void doom_mix(uint32_t *,unsigned,unsigned,unsigned);
extern int music_playing;
int main(void){
 memcpy(genmidi,"#OPL_II#",8);
 for(int i=0;i<175;i++){
  unsigned char *p=genmidi+8+i*36+4;
  p[0]=1;p[1]=0xf2;p[2]=0x74;p[5]=20;
  p[7]=1;p[8]=0xf2;p[9]=0x74;p[12]=0;
 }
 assert(DG_music_module.Init());
 unsigned char song[32]={'M','U','S',26,8,0,16,0};
 unsigned char events[]={0x90,0xbc,100,10,0x80,60,10,0x60};
 memcpy(song+16,events,sizeof(events));
 void *handle=DG_music_module.RegisterSong(song,sizeof(song));assert(handle);
 DG_music_module.PlaySong(handle,0);
 uint32_t out[4096];doom_mix(out,4096,4095,100);
 unsigned lo=65535,hi=0;for(int i=0;i<4096;i++){unsigned v=out[i]>>16;assert(v<=4095);if(v<lo)lo=v;if(v>hi)hi=v;}
 printf("music PWM min/max %u %u\n",lo,hi);assert(hi>lo+10);assert(!music_playing);
 // A looping score with no delay must terminate instead of hanging the mixer.
 song[16]=0x60;song[4]=1;handle=DG_music_module.RegisterSong(song,sizeof(song));
 DG_music_module.PlaySong(handle,1);doom_mix(out,1,4095,100);assert(!music_playing);
 assert(!DG_music_module.RegisterSong(song,10));
 DG_music_module.Shutdown();
 fx[0]=3;fx[2]=0x11;fx[3]=0x2b;fx[4]=0;fx[5]=1;
 for(int i=8;i<sizeof(fx);i++)fx[i]=(i&16)?250:5;
 sfxinfo_t effect={0};strcpy(effect.name,"test");
 DG_sound_module.Init(1);assert(DG_sound_module.StartSound(&effect,0,127,128)==0);
 assert(DG_sound_module.SoundIsPlaying(0));doom_mix(out,1024,4095,100);
 assert(!DG_sound_module.SoundIsPlaying(0));
 lo=65535;hi=0;for(int i=0;i<1024;i++){unsigned v=out[i]>>16;if(v<lo)lo=v;if(v>hi)hi=v;}
 printf("sfx PWM min/max %u %u\n",lo,hi);assert(hi>lo+100);
 puts("bounded music and effect mixer OK");
}
