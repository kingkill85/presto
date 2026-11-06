// SPDX-License-Identifier: GPL-2.0-or-later
// Mono DMX effects and bounded MUS sequencing through a YM3812 emulator.
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include "i_sound.h"
#include "w_wad.h"
#include "z_zone.h"
#include "vendor/emu8950.h"
#define RATE 22050
#define CHANNELS 16
#define OPL_CLOCK 3579545
#define OPL_RATE (OPL_CLOCK/72/OPL_RATE_DIV)
static unsigned le16(const uint8_t *p){return p[0]|p[1]<<8;}
static uint32_t le32(const uint8_t *p){return p[0]|p[1]<<8|p[2]<<16|(uint32_t)p[3]<<24;}
int use_libsamplerate;
float libsamplerate_scale;
char *timidity_cfg_path;
void I_InitTimidityConfig(void){}

typedef struct {const uint8_t *data;unsigned len,rate;} effect;
typedef struct {effect *fx;uint32_t pos,frac,step;int volume;} channel;
effect effects[128];
channel channels[CHANNELS];
unsigned effect_count;
static boolean sfx_init(boolean prefix){(void)prefix;return true;}
static void sfx_stop(int c){if(c>=0&&c<CHANNELS)channels[c].fx=NULL;}
static void sfx_shutdown(void){memset(channels,0,sizeof(channels));}
static int sfx_lump(sfxinfo_t *s){char name[12];snprintf(name,sizeof(name),"ds%s",s->link?s->link->name:s->name);return W_GetNumForName(name);}
static void cache_one(sfxinfo_t *s){
    if(s->driver_data)return;
    if(s->link){cache_one(s->link);s->driver_data=s->link->driver_data;return;}
    if(effect_count>=128)return;
    int lump=W_CheckNumForName("__none__");
    char name[12];snprintf(name,sizeof(name),"ds%s",s->name);lump=W_CheckNumForName(name);
    if(lump<0)return;
    int len=W_LumpLength(lump);if(len<40)return;
    const uint8_t *data=W_CacheLumpNum(lump,PU_STATIC);
    unsigned count=le32(data+4),rate=le16(data+2);
    if(le16(data)!=3 || rate<1000 || rate>48000 || count>len-8 || count<=32)return;
    effect *e=&effects[effect_count++];e->data=data+24;e->len=count-32;e->rate=rate;s->driver_data=e;
}
static void cache_sounds(sfxinfo_t *s,int n){for(int i=1;i<n;i++)cache_one(&s[i]);}
static void sfx_params(int c,int vol,int sep){(void)sep;if(c>=0&&c<CHANNELS)channels[c].volume=vol<0?0:vol>127?127:vol;}
static int sfx_start(sfxinfo_t *s,int c,int vol,int sep){
    if(c<0||c>=CHANNELS)return -1;cache_one(s);if(!s->driver_data)return -1;
    channels[c].fx=s->driver_data;channels[c].pos=channels[c].frac=0;
    channels[c].step=((effect *)s->driver_data)->rate*65536u/RATE;
    sfx_params(c,vol,sep);return c;
}
static boolean sfx_playing(int c){return c>=0&&c<CHANNELS&&channels[c].fx;}
static void no_update(void){}
static snddevice_t devices[]={SNDDEVICE_SB,SNDDEVICE_ADLIB};
sound_module_t DG_sound_module={devices,2,sfx_init,sfx_shutdown,sfx_lump,no_update,sfx_params,sfx_start,sfx_stop,sfx_playing,cache_sounds};

OPL *music_opl;
const uint8_t *instruments;
const uint8_t *song_begin,*song_end,*song_pos;
int music_volume=100,music_playing,music_paused,music_loop;
int64_t music_wait;
unsigned music_phase;
uint32_t voice_age;
typedef struct {int program,volume,expression,bend,sustain,velocity;} mus_channel;
typedef struct {int channel,note,pitch,velocity,released;const uint8_t *patch;unsigned age;} voice;
mus_channel mus_channels[16];
voice voices[9];
const uint8_t operators[9]={0,1,2,8,9,10,16,17,18};
const uint16_t fnums[13]={345,365,387,410,435,460,488,517,548,581,615,652,690};
static void key_off(int i){if(music_opl)OPL_writeReg(music_opl,0xb0+i,music_opl->reg[0xb0+i]&~32);voices[i].channel=-1;}
static void all_off(int channel){for(int i=0;i<9;i++)if(channel<0||voices[i].channel==channel)key_off(i);}
static void reset_channels(void){for(int i=0;i<16;i++){mus_channels[i]=(mus_channel){0,100,127,128,0,64};}all_off(-1);}
static void voice_volume(int i){
    voice *v=&voices[i];mus_channel *c=&mus_channels[v->channel];
    int volume=v->velocity*c->volume*c->expression/127/127;
    // Hardware attenuation steps are logarithmic. A small integer curve keeps
    // soft notes audible on the piezo without changing instrument operators.
    int attenuation=volume?((127-volume)*40/127):63;
    const uint8_t *p=v->patch;int level=(p[12]&63)+attenuation;if(level>63)level=63;
    OPL_writeReg(music_opl,0x40+operators[i]+3,(p[11]&192)|level);
    if(p[6]&1){level=(p[5]&63)+attenuation;if(level>63)level=63;OPL_writeReg(music_opl,0x40+operators[i],(p[4]&192)|level);}
}
static void voice_pitch(int i){
    voice *v=&voices[i];int pitch=v->pitch*256+(mus_channels[v->channel].bend-128)*4;
    if(pitch<0)pitch=0;if(pitch>127*256)pitch=127*256;
    int note=pitch>>8,frac=pitch&255,key=note%12,block=note/12-1;
    int f=fnums[key]+((fnums[key+1]-fnums[key])*frac>>8);
    if(block<0){f>>=-block;block=0;}while(block>7){f*=2;block--;}
    if(f>1023)f=1023;
    OPL_writeReg(music_opl,0xa0+i,f&255);OPL_writeReg(music_opl,0xb0+i,32|(block<<2)|(f>>8));
}
static void operator_load(int op,const uint8_t *p){
    OPL_writeReg(music_opl,0x20+op,p[0]);OPL_writeReg(music_opl,0x40+op,(p[4]&192)|(p[5]&63));
    OPL_writeReg(music_opl,0x60+op,p[1]);OPL_writeReg(music_opl,0x80+op,p[2]);OPL_writeReg(music_opl,0xe0+op,p[3]&3);
}
static void note_voice(int channel,int note,int velocity,const uint8_t *instrument,int sub){
    int selected=0;for(int i=0;i<9;i++){if(voices[i].channel<0){selected=i;break;}if(voices[i].age<voices[selected].age)selected=i;}
    key_off(selected);const uint8_t *p=instrument+4+sub*16;
    int pitch=(le16(instrument)&1)?instrument[3]:note;
    if(!(le16(instrument)&1))pitch+=(int16_t)le16(p+14);
    voices[selected]=(voice){channel,note,pitch,velocity,0,p,++voice_age};
    operator_load(operators[selected],p);operator_load(operators[selected]+3,p+7);
    OPL_writeReg(music_opl,0xc0+selected,p[6]);voice_volume(selected);voice_pitch(selected);
}
static void note_on(int channel,int note,int velocity){
    int instrument=channel==15?128+note-35:mus_channels[channel].program;
    if(!velocity){for(int i=0;i<9;i++)if(voices[i].channel==channel&&voices[i].note==note)key_off(i);return;}
    if(instrument<0||instrument>=175)return;
    const uint8_t *p=instruments+8+instrument*36;
    note_voice(channel,note,velocity,p,0);
    if(le16(p)&4)note_voice(channel,note,velocity,p,1);
}
static void note_off(int channel,int note){for(int i=0;i<9;i++)if(voices[i].channel==channel&&voices[i].note==note){if(mus_channels[channel].sustain)voices[i].released=1;else key_off(i);}}
static void controller(int ch,int control,int value){
    mus_channel *c=&mus_channels[ch];
    switch(control){
    case 0:c->program=value;break;
    case 3:c->volume=value;break;
    case 5:c->expression=value;break;
    case 8:c->sustain=value>=64;for(int i=0;i<9;i++)if(voices[i].channel==ch&&voices[i].released&&!c->sustain)key_off(i);break;
    case 10:case 11:all_off(ch);break;
    case 14:c->volume=100;c->expression=127;c->bend=128;c->sustain=0;all_off(ch);break;
    }
    for(int i=0;i<9;i++)if(voices[i].channel==ch)voice_volume(i);
}
static int read_byte(void){if(song_pos>=song_end){music_playing=0;return 0;}return *song_pos++;}
static void music_events(void){
    // Bounded even for malformed or zero-delay looping scores.
    for(int budget=0;budget<1024&&music_playing&&music_wait<=0;budget++){
        int event=read_byte(),ch=event&15,type=(event>>4)&7;
        if(!music_playing)break;
        if(type==0)note_off(ch,read_byte()&127);
        else if(type==1){int note=read_byte();if(note&128)mus_channels[ch].velocity=read_byte()&127;note_on(ch,note&127,mus_channels[ch].velocity);}
        else if(type==2){mus_channels[ch].bend=read_byte();for(int i=0;i<9;i++)if(voices[i].channel==ch)voice_pitch(i);}
        else if(type==3)controller(ch,read_byte(),0);
        else if(type==4){int control=read_byte();controller(ch,control,read_byte()&127);}
        else if(type==6){all_off(-1);if(music_loop){song_pos=song_begin;reset_channels();}else music_playing=0;}
        else music_playing=0;
        if((event&128)&&music_playing){unsigned delay=0;int b=0,n=0;do{b=read_byte();if(++n>4){music_playing=0;break;}delay=(delay<<7)|(b&127);}while(b&128);music_wait+=(int64_t)delay*RATE;}
    }
    if(music_wait<=0&&music_playing){music_playing=0;all_off(-1);}
}
static boolean music_init(void){
    int lump=W_CheckNumForName("GENMIDI");if(lump<0||W_LumpLength(lump)<8+175*36)return false;
    instruments=W_CacheLumpNum(lump,PU_STATIC);if(memcmp(instruments,"#OPL_II#",8))return false;
    music_opl=OPL_new(OPL_CLOCK,OPL_RATE);if(!music_opl)return false;
    OPL_setChipType(music_opl,2);OPL_writeReg(music_opl,1,32);reset_channels();return true;
}
static void music_stop(void){music_playing=0;all_off(-1);}
static void music_shutdown(void){music_stop();if(music_opl)OPL_delete(music_opl);music_opl=NULL;}
static void set_volume(int v){music_volume=v<0?0:v>127?127:v;}
static void music_pause(void){music_paused=1;}
static void music_resume(void){music_paused=0;}
static void *register_song(void *data,int len){
    const uint8_t *p=data;if(!music_opl||len<16||memcmp(p,"MUS\x1a",4))return NULL;
    unsigned offset=le16(p+6),length=le16(p+4);
    if(offset<16||offset>(unsigned)len||length>(unsigned)len-offset)return NULL;
    song_begin=p+offset;song_end=song_begin+length;return data;
}
static void unregister_song(void *data){(void)data;music_stop();song_begin=song_end=song_pos=NULL;}
static void play_song(void *data,boolean loop){if(!data||!song_begin)return;reset_channels();song_pos=song_begin;music_loop=loop;music_wait=0;music_phase=0;music_playing=1;music_paused=0;}
static boolean is_playing(void){return music_playing;}
music_module_t DG_music_module={devices,2,music_init,music_shutdown,set_volume,music_pause,music_resume,register_song,unregister_song,play_song,music_stop,is_playing,no_update};

void doom_mix(uint32_t *out,unsigned n,unsigned top,unsigned volume){
    for(unsigned i=0;i<n;i++){
        int sample=0;
        if(music_opl&&music_playing&&!music_paused){music_wait-=140;if(music_wait<=0)music_events();int sum=0,count=0;music_phase+=OPL_RATE;
            while(music_phase>=RATE){music_phase-=RATE;sum+=OPL_calc(music_opl);count++;}
            sample=(sum/count)*music_volume/127;}
        for(int c=0;c<CHANNELS;c++){
            channel *ch=&channels[c];effect *fx=ch->fx;if(!fx)continue;
            if(ch->pos>=fx->len){ch->fx=NULL;continue;}
            sample+=((int)fx->data[ch->pos]-128)*ch->volume;
            ch->frac+=ch->step;ch->pos+=ch->frac>>16;ch->frac&=65535;
        }
        if(sample>32767)sample=32767;if(sample< -32768)sample=-32768;
        int duty=top/2+sample*(int)volume/100*(int)top/65536;
        out[i]=(uint32_t)duty<<16;
    }
}
